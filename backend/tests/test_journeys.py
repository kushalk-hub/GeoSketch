"""Journey lifecycle, recording state machine and statistics."""

from __future__ import annotations

from datetime import UTC

import pytest

from tests.conftest import add_demo_points, gps_point

JOURNEYS = "/api/v1/journeys"


# ---------------------------------------------------------------------------
# creation / retrieval
# ---------------------------------------------------------------------------
def test_create_journey_starts_recording(client):
    response = client.post(JOURNEYS, json={"title": "Morning walk", "source": "hardware"})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["title"] == "Morning walk"
    assert body["status"] == "recording"
    assert body["source"] == "hardware"
    assert body["point_count"] == 0
    assert body["id"] > 0


def test_create_journey_without_start_is_paused(client):
    body = client.post(JOURNEYS, json={"start_immediately": False}).json()
    assert body["status"] == "paused"


def test_demo_journey_can_pin_its_start_time(client):
    """Demo replay/import pins the start so the sample's duration is realistic."""
    from datetime import datetime, timedelta

    start = (datetime.now(UTC) - timedelta(minutes=40)).replace(microsecond=0)
    stamp = start.isoformat().replace("+00:00", "Z")
    body = client.post(JOURNEYS, json={"source": "demo", "started_at": stamp}).json()
    assert body["started_at"] == stamp
    assert body["source"] == "demo"


def test_hardware_journey_cannot_pin_its_start_time(client):
    response = client.post(
        JOURNEYS,
        json={"source": "hardware", "started_at": "2026-10-15T10:30:00Z"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "started_at_not_allowed"


def test_demo_start_time_cannot_be_in_the_future(client):
    from datetime import datetime, timedelta

    future = (datetime.now(UTC) + timedelta(hours=3)).isoformat().replace("+00:00", "Z")
    response = client.post(JOURNEYS, json={"source": "demo", "started_at": future})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "started_at_in_future"


def test_create_journey_with_unknown_device_fails(client):
    response = client.post(JOURNEYS, json={"device_id": "ghost-device"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "device_not_found"


def test_get_unknown_journey_returns_404(client):
    response = client.get(f"{JOURNEYS}/999999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "journey_not_found"


def test_list_and_filter_journeys(client, journey):
    listing = client.get(JOURNEYS).json()
    assert any(item["id"] == journey["id"] for item in listing)

    saved_only = client.get(JOURNEYS, params={"saved_only": True}).json()
    assert all(item["status"] == "saved" for item in saved_only)

    demo = client.get(JOURNEYS, params={"source": "demo"}).json()
    assert all(item["source"] == "demo" for item in demo)


def test_update_journey_title(client, journey):
    response = client.patch(f"{JOURNEYS}/{journey['id']}", json={"title": "Renamed walk"})
    assert response.status_code == 200
    assert response.json()["title"] == "Renamed walk"


# ---------------------------------------------------------------------------
# state machine
# ---------------------------------------------------------------------------
def test_pause_resume_stop_save_sequence(client, journey, walking_route):
    journey_id = journey["id"]
    add_demo_points(client, journey_id, walking_route)
    assert client.post(f"{JOURNEYS}/{journey_id}/pause").json()["status"] == "paused"
    assert client.post(f"{JOURNEYS}/{journey_id}/resume").json()["status"] == "recording"
    assert client.post(f"{JOURNEYS}/{journey_id}/stop").json()["status"] == "stopped"
    assert client.post(f"{JOURNEYS}/{journey_id}/finish").status_code == 409  # already stopped
    assert client.post(f"{JOURNEYS}/{journey_id}/save").json()["status"] == "saved"


def test_finish_is_an_alias_of_stop(client, journey):
    body = client.post(f"{JOURNEYS}/{journey['id']}/finish").json()
    assert body["status"] == "stopped"
    assert body["finished_at"] is not None


def test_cannot_resume_a_finished_journey(client, journey):
    journey_id = journey["id"]
    client.post(f"{JOURNEYS}/{journey_id}/stop")
    response = client.post(f"{JOURNEYS}/{journey_id}/resume")
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "invalid_transition"
    assert error["details"]["current"] == "stopped"


def test_cannot_pause_a_stopped_journey(client, journey):
    journey_id = journey["id"]
    client.post(f"{JOURNEYS}/{journey_id}/stop")
    assert client.post(f"{JOURNEYS}/{journey_id}/pause").status_code == 409


def test_cannot_save_twice(client, journey, walking_route):
    journey_id = journey["id"]
    add_demo_points(client, journey_id, walking_route)
    client.post(f"{JOURNEYS}/{journey_id}/stop")
    assert client.post(f"{JOURNEYS}/{journey_id}/save").status_code == 200
    assert client.post(f"{JOURNEYS}/{journey_id}/save").status_code == 409


def test_cannot_save_an_empty_journey(client, journey):
    journey_id = journey["id"]
    client.post(f"{JOURNEYS}/{journey_id}/stop")
    response = client.post(f"{JOURNEYS}/{journey_id}/save")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "empty_journey"


def test_clear_unsaved_journey(client, journey):
    journey_id = journey["id"]
    assert client.delete(f"{JOURNEYS}/{journey_id}").status_code == 200
    assert client.get(f"{JOURNEYS}/{journey_id}").status_code == 404


def test_saved_journey_cannot_be_cleared(
    client, device_headers, walking_route, hardware_journey
):
    journey_id = hardware_journey["id"]
    for payload in walking_route[:3]:
        client.post(
            "/api/v1/gps/points",
            json={**payload, "journey_id": journey_id},
            headers=device_headers,
        )
    client.post(f"{JOURNEYS}/{journey_id}/stop")
    client.post(f"{JOURNEYS}/{journey_id}/save")
    response = client.delete(f"{JOURNEYS}/{journey_id}")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "journey_saved"


# ---------------------------------------------------------------------------
# statistics
# ---------------------------------------------------------------------------
def test_statistics_are_derived_from_recorded_points(
    client, device_headers, hardware_journey, walking_route
):
    for payload in walking_route:
        client.post(
            "/api/v1/gps/points",
            json={**payload, "journey_id": hardware_journey["id"]},
            headers=device_headers,
        )

    stats = client.get(f"{JOURNEYS}/{hardware_journey['id']}/statistics").json()
    assert stats["total_points"] == len(walking_route)
    assert stats["used_points"] == len(walking_route)
    assert 60 < stats["distance_m"] < 90          # ~77 m of walking
    assert stats["distance_km"] == pytest.approx(stats["distance_m"] / 1000, abs=1e-6)
    assert stats["duration_seconds"] == pytest.approx(55, abs=1)
    assert stats["moving_seconds"] == pytest.approx(55, abs=1)
    assert 4.0 < stats["average_speed_kmh"] < 6.0
    assert stats["start_latitude"] == pytest.approx(walking_route[0]["latitude"])
    assert stats["end_latitude"] == pytest.approx(walking_route[-1]["latitude"])
    assert stats["is_estimate"] is True
    assert "estimate" in stats["note"]


def test_statistics_of_empty_journey_are_zero(client, journey):
    stats = client.get(f"{JOURNEYS}/{journey['id']}/statistics").json()
    assert stats["total_points"] == 0
    assert stats["distance_m"] == 0
    assert stats["average_speed_kmh"] is None


def test_gap_is_excluded_from_distance(client, device_headers, hardware_journey):
    """A 10-minute outage must not add the straight-line jump to the distance."""
    # 3 fixes within 10 m, then a fix 400 m away after a 10 minute gap.
    points = [
        gps_point(18.5204, 73.8567, seconds=0, client_point_id="g0"),
        gps_point(18.52046, 73.8567, seconds=5, client_point_id="g1"),
        gps_point(18.52052, 73.8567, seconds=10, client_point_id="g2"),
        gps_point(18.5241, 73.8567, seconds=610, client_point_id="g3"),
    ]
    for payload in points:
        client.post(
            "/api/v1/gps/points",
            json={**payload, "journey_id": hardware_journey["id"]},
            headers=device_headers,
        )

    stats = client.get(f"{JOURNEYS}/{hardware_journey['id']}/statistics").json()
    assert stats["gap_count"] == 1
    assert stats["distance_m"] < 30  # only the two short segments count


# ---------------------------------------------------------------------------
# bulk points (demo replay)
# ---------------------------------------------------------------------------
def test_bulk_upload_accepts_demo_points(client, journey, walking_route):
    body = add_demo_points(client, journey["id"], walking_route)
    assert body["received"] == len(walking_route)
    assert body["stored"] == len(walking_route)

    # Retrying the same batch must not double the points.
    again = client.post(
        f"{JOURNEYS}/{journey['id']}/points",
        json={"points": walking_route, "source": "demo"},
    ).json()
    assert again["stored"] == 0
    assert again["duplicates"] == len(walking_route)


def test_bulk_upload_refuses_hardware_source(client, journey, walking_route):
    response = client.post(
        f"{JOURNEYS}/{journey['id']}/points",
        json={"points": walking_route, "source": "hardware"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "hardware_source_not_allowed"


def test_bulk_upload_rejects_empty_list(client, journey):
    response = client.post(f"{JOURNEYS}/{journey['id']}/points", json={"points": []})
    assert response.status_code == 422
