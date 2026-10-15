"""Artwork generation, previews and PNG/SVG export."""

from __future__ import annotations

import pytest

JOURNEYS = "/api/v1/journeys"
ARTWORKS = "/api/v1/artworks"
STYLES = ["minimal", "neon", "gradient", "poster", "custom"]
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@pytest.fixture()
def journey_with_points(client, walking_route):
    from tests.conftest import add_demo_points

    journey = client.post(
        JOURNEYS, json={"title": "Artwork journey", "source": "demo"}
    ).json()
    add_demo_points(client, journey["id"], walking_route)
    return journey


def test_style_catalogue(client):
    response = client.get("/api/v1/artwork/styles")
    assert response.status_code == 200
    styles = {item["id"] for item in response.json()}
    assert styles == set(STYLES)


def test_preview_returns_inline_svg_without_persisting(client, journey_with_points):
    response = client.post(
        f"{JOURNEYS}/{journey_with_points['id']}/artwork/preview",
        json={"style": "neon"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["style"] == "neon"
    assert body["svg"].startswith("<?xml")
    assert "<svg" in body["svg"] and "polyline" in body["svg"]
    assert body["processing"]["projection"] == "local equirectangular"
    assert body["processing"]["drawn_points"] > 1

    # A preview must not create an artwork row or files.
    assert client.get(f"{JOURNEYS}/{journey_with_points['id']}/artworks").json() == []


@pytest.mark.parametrize("style", STYLES)
def test_every_style_generates_png_and_svg(client, journey_with_points, style):
    response = client.post(
        f"{JOURNEYS}/{journey_with_points['id']}/artwork",
        json={"style": style, "export_format": "png"},
    )
    assert response.status_code == 201, response.text
    artwork = response.json()
    assert artwork["style"] == style
    assert artwork["width"] >= 400 and artwork["height"] >= 400
    assert artwork["point_count"] > 1
    assert artwork["png_url"].endswith("format=png")

    png = client.get(f"{ARTWORKS}/{artwork['id']}/download", params={"format": "png"})
    assert png.status_code == 200
    assert png.headers["content-type"] == "image/png"
    assert png.content.startswith(PNG_MAGIC)
    assert len(png.content) > 5_000

    svg = client.get(f"{ARTWORKS}/{artwork['id']}/download", params={"format": "svg"})
    assert svg.status_code == 200
    assert "image/svg+xml" in svg.headers["content-type"]
    assert b"<svg" in svg.content


def test_png_dimensions_match_the_requested_canvas(client, journey_with_points):
    from io import BytesIO

    from PIL import Image

    artwork = client.post(
        f"{JOURNEYS}/{journey_with_points['id']}/artwork",
        json={"style": "minimal", "width": 900, "height": 600},
    ).json()
    assert artwork["width"] == 900
    assert artwork["height"] == 600

    png = client.get(f"{ARTWORKS}/{artwork['id']}/download", params={"format": "png"})
    with Image.open(BytesIO(png.content)) as image:
        assert image.size == (900, 600)
        assert image.mode == "RGB"


def test_poster_is_portrait_by_default(client, journey_with_points):
    artwork = client.post(
        f"{JOURNEYS}/{journey_with_points['id']}/artwork", json={"style": "poster"}
    ).json()
    assert artwork["height"] > artwork["width"]

    from app.utils.formatting import format_distance

    svg = client.get(f"{ARTWORKS}/{artwork['id']}/download", params={"format": "svg"}).text
    assert "GEOSKETCH" in svg
    assert "GPS ROUTE ART" in svg
    assert format_distance(artwork["distance_m"]) in svg  # the statistics footer


def test_custom_style_honours_customisation(client, journey_with_points):
    artwork = client.post(
        f"{JOURNEYS}/{journey_with_points['id']}/artwork",
        json={
            "style": "custom",
            "title": "My line",
            "customization": {
                "background": "#101820",
                "route_color": "#ff8800",
                "line_width": 12,
                "glow": False,
                "show_start_marker": True,
                "show_end_marker": True,
                "title": "My line",
            },
        },
    ).json()
    svg = client.get(f"{ARTWORKS}/{artwork['id']}/download", params={"format": "svg"}).text
    assert "#101820" in svg      # custom background
    assert "#ff8800" in svg      # custom route colour
    assert 'stroke-width="12"' in svg
    assert "MY LINE" in svg
    assert artwork["customization"]["background"] == "#101820"


def test_gradient_style_uses_the_selected_palette(client, journey_with_points):
    import re

    artwork = client.post(
        f"{JOURNEYS}/{journey_with_points['id']}/artwork",
        json={"style": "gradient", "palette": "sunset"},
    ).json()
    svg = client.get(f"{ARTWORKS}/{artwork['id']}/download", params={"format": "svg"}).text
    colours = set(re.findall(r'stroke="(#[0-9a-f]{6})"', svg))
    # sunset ramp: #fbbf24 -> #fb7185 -> #7c3aed, sampled along the path.
    assert "#7c3aed" in colours           # the end of the ramp is reached
    assert len(colours) >= 20             # many interpolated steps in between
    assert "#0b1020" not in colours       # not the default background-only render


def test_artwork_can_be_listed_and_fetched(client, journey_with_points):
    created = client.post(
        f"{JOURNEYS}/{journey_with_points['id']}/artwork", json={"style": "minimal"}
    ).json()
    listing = client.get(f"{JOURNEYS}/{journey_with_points['id']}/artworks").json()
    assert [item["id"] for item in listing] == [created["id"]]

    fetched = client.get(f"{ARTWORKS}/{created['id']}").json()
    assert fetched["journey_id"] == journey_with_points["id"]
    assert fetched["segment_count"] >= 1


def test_unknown_style_is_rejected(client, journey_with_points):
    response = client.post(
        f"{JOURNEYS}/{journey_with_points['id']}/artwork", json={"style": "hologram"}
    )
    assert response.status_code == 422


def test_unknown_export_format_is_rejected(client, journey_with_points):
    response = client.get(f"{ARTWORKS}/1/download", params={"format": "pdf"})
    assert response.status_code == 422


def test_artwork_of_empty_journey_is_rejected(client, journey):
    response = client.post(f"{JOURNEYS}/{journey['id']}/artwork", json={"style": "minimal"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "no_route_points"


def test_unknown_artwork_returns_404(client):
    assert client.get(f"{ARTWORKS}/987654").status_code == 404
    assert client.get(f"{ARTWORKS}/987654/download").status_code == 404


def test_artwork_excludes_implausible_points(client, device_headers):
    """A teleporting fix must not be drawn as a straight line across the canvas."""
    from tests.conftest import gps_point

    journey = client.post(
        JOURNEYS, json={"title": "Noisy route", "source": "hardware"}
    ).json()
    payloads = [
        gps_point(18.5204, 73.8567, seconds=0, client_point_id="n0"),
        gps_point(18.52046, 73.8567, seconds=5, client_point_id="n1"),
        gps_point(18.5330, 73.8567, seconds=10, client_point_id="n2"),  # ~1.4 km in 5 s
        # The walk really did continue next to the bad fix: dropping it must
        # still never draw a straight line from n1 to n3.
        gps_point(18.53306, 73.8567, seconds=15, client_point_id="n3"),
        gps_point(18.53312, 73.8567, seconds=20, client_point_id="n4"),
    ]
    for payload in payloads:
        response = client.post(
            "/api/v1/gps/points",
            json={**payload, "journey_id": journey["id"]},
            headers=device_headers,
        )
        assert response.status_code == 201, response.text

    preview = client.post(
        f"{JOURNEYS}/{journey['id']}/artwork/preview", json={"style": "minimal"}
    ).json()
    assert preview["processing"]["excluded_points"] == 1
    assert preview["processing"]["drawn_points"] == 4
    # Dropping the bad fix leaves an impossible distance between the neighbours,
    # so the route is split instead of being drawn across 1.4 km.
    assert preview["processing"]["segments"] == 2
    assert preview["processing"]["jump_cuts"] == 1


def test_artwork_fits_inside_the_canvas(client, journey_with_points):
    """Normalisation must keep every drawn coordinate inside the padded canvas."""
    import re

    artwork = client.post(
        f"{JOURNEYS}/{journey_with_points['id']}/artwork",
        json={"style": "minimal", "width": 800, "height": 800},
    ).json()
    svg = client.get(f"{ARTWORKS}/{artwork['id']}/download", params={"format": "svg"}).text
    coordinates = re.findall(r'points="([^"]+)"', svg)
    assert coordinates
    xs, ys = [], []
    for chunk in coordinates:
        for pair in chunk.split(" "):
            x, y = pair.split(",")
            xs.append(float(x))
            ys.append(float(y))
    assert min(xs) >= 20 and max(xs) <= 780
    assert min(ys) >= 20 and max(ys) <= 780
