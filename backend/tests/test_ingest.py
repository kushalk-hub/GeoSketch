"""Device ingestion: authentication, payload parsing, dedupe and rejects."""

from __future__ import annotations

from tests.conftest import gps_point

GPS_ENDPOINT = "/api/v1/gps/points"


def test_ingest_requires_device_credentials(client, walking_route):
    assert client.post(GPS_ENDPOINT, json=walking_route[0]).status_code == 401
    response = client.post(
        GPS_ENDPOINT,
        json=walking_route[0],
        headers={"X-Device-Id": "geosketch-01"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_device_key"


def test_ingest_rejects_wrong_api_key(client, walking_route):
    response = client.post(
        GPS_ENDPOINT,
        json=walking_route[0],
        headers={"X-Device-Id": "geosketch-01", "X-Device-Key": "nope"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_device_credentials"


def test_ingest_rejects_unknown_device(client, walking_route):
    response = client.post(
        GPS_ENDPOINT,
        json=walking_route[0],
        headers={"X-Device-Id": "unknown-tracker", "X-Device-Key": "anything"},
    )
    assert response.status_code == 401


def test_ingest_creates_a_journey_automatically(client, device_headers, walking_route):
    response = client.post(GPS_ENDPOINT, json=walking_route[0], headers=device_headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["accepted"] and body["stored"] and not body["duplicate"]
    assert body["sequence"] == 1
    assert body["point_id"] is not None

    journey = client.get(f"/api/v1/journeys/{body['journey_id']}").json()
    assert journey["source"] == "hardware"
    assert journey["status"] == "recording"
    assert journey["device_id"] == "geosketch-01"
    assert len(journey["points"]) == 1


def test_retried_request_does_not_duplicate_the_point(client, device_headers, walking_route):
    first = client.post(GPS_ENDPOINT, json=walking_route[0], headers=device_headers)
    assert first.status_code == 201

    retry = client.post(GPS_ENDPOINT, json=walking_route[0], headers=device_headers)
    assert retry.status_code == 200
    body = retry.json()
    assert body["accepted"] is True
    assert body["stored"] is False
    assert body["duplicate"] is True
    assert body["point_id"] == first.json()["point_id"]

    # Retry five more times: still exactly one stored point.
    for _ in range(5):
        client.post(GPS_ENDPOINT, json=walking_route[0], headers=device_headers)

    statistics = client.get(
        f"/api/v1/journeys/{body['journey_id']}/statistics"
    ).json()
    assert statistics["total_points"] == 1


def test_distinct_points_are_all_stored_and_ordered(client, device_headers, walking_route):
    journey_id = None
    for payload in walking_route:
        response = client.post(GPS_ENDPOINT, json=payload, headers=device_headers)
        assert response.status_code == 201, response.text
        journey_id = response.json()["journey_id"]

    journey = client.get(f"/api/v1/journeys/{journey_id}").json()
    assert journey["point_count"] == len(walking_route)
    sequences = [point["sequence"] for point in journey["points"]]
    assert sequences == sorted(sequences)
    assert sequences == list(range(1, len(walking_route) + 1))


def test_point_is_attached_to_the_device_active_journey(client, device_headers, walking_route):
    created = client.post(
        "/api/v1/journeys",
        json={"title": "Device journey", "device_id": "geosketch-01", "source": "hardware"},
    ).json()
    response = client.post(GPS_ENDPOINT, json=walking_route[0], headers=device_headers)
    assert response.status_code == 201
    assert response.json()["journey_id"] == created["id"]


def test_paused_journey_drops_points_without_error(
    client, device_headers, walking_route, hardware_journey
):
    client.post(f"/api/v1/journeys/{hardware_journey['id']}/pause")
    response = client.post(
        GPS_ENDPOINT,
        json={**walking_route[0], "journey_id": hardware_journey["id"]},
        headers=device_headers,
    )
    # accepted:false / stored:false but still a 2xx, so the firmware does not
    # retry the point forever while recording is paused.
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is False
    assert body["stored"] is False
    assert body["reason"] == "journey_paused"

    statistics = client.get(f"/api/v1/journeys/{hardware_journey['id']}/statistics").json()
    assert statistics["total_points"] == 0


def test_finished_journey_is_not_recorded_into(
    client, device_headers, walking_route, hardware_journey
):
    for payload in walking_route[:3]:
        client.post(
            GPS_ENDPOINT,
            json={**payload, "journey_id": hardware_journey["id"]},
            headers=device_headers,
        )
    assert client.post(f"/api/v1/journeys/{hardware_journey['id']}/stop").status_code == 200

    response = client.post(
        GPS_ENDPOINT,
        json={**walking_route[3], "journey_id": hardware_journey["id"]},
        headers=device_headers,
    )
    assert response.status_code == 200
    assert response.json()["reason"] == "journey_not_recording"

    journey_detail = client.get(f"/api/v1/journeys/{hardware_journey['id']}").json()
    assert journey_detail["point_count"] == 3


def test_device_cannot_post_into_a_demo_journey(client, device_headers, walking_route, journey):
    response = client.post(
        GPS_ENDPOINT,
        json={**walking_route[0], "journey_id": journey["id"]},
        headers=device_headers,
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "journey_source_mismatch"


def test_invalid_coordinates_are_rejected(client, device_headers):
    bad = [
        {"latitude": 91.0, "longitude": 73.0},
        {"latitude": -91.0, "longitude": 73.0},
        {"latitude": 18.0, "longitude": 181.0},
        {"latitude": "abc", "longitude": 73.0},
    ]
    for payload in bad:
        response = client.post(GPS_ENDPOINT, json=payload, headers=device_headers)
        assert response.status_code == 422, payload
        assert response.json()["error"]["code"] == "validation_failed"


def test_missing_fix_sentinel_is_rejected(client, device_headers):
    """A NEO-6M without a fix streams 0,0 and must never be stored."""
    response = client.post(
        GPS_ENDPOINT, json={"latitude": 0.0, "longitude": 0.0}, headers=device_headers
    )
    assert response.status_code == 422
    assert "no fix" in response.json()["error"]["details"]["errors"][0]["msg"].lower()


def test_optional_fields_may_be_absent(client, device_headers):
    """Altitude/speed/satellites/timestamp are all optional in the payload."""
    response = client.post(
        GPS_ENDPOINT,
        json={"latitude": 18.5204, "longitude": 73.8567, "client_point_id": "minimal-1"},
        headers=device_headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    journey = client.get(f"/api/v1/journeys/{body['journey_id']}").json()
    point = journey["points"][0]
    assert point["altitude"] is None
    assert point["speed_kmh"] is None
    assert point["gps_timestamp"] is None
    assert point["server_timestamp"] is not None


def test_unknown_fields_are_rejected(client, device_headers):
    response = client.post(
        GPS_ENDPOINT,
        json={"latitude": 18.52, "longitude": 73.85, "banana": 1},
        headers=device_headers,
    )
    assert response.status_code == 422


def test_implausible_jump_is_flagged_but_stored(client, device_headers):
    response = client.post(
        GPS_ENDPOINT,
        json=gps_point(18.5204, 73.8567, seconds=0, client_point_id="a"),
        headers=device_headers,
    )
    journey_id = response.json()["journey_id"]

    # ~11 km north in 5 seconds: impossible for a pedestrian.
    client.post(
        GPS_ENDPOINT,
        json=gps_point(18.6204, 73.8567, seconds=5, client_point_id="b"),
        headers=device_headers,
    )

    journey = client.get(f"/api/v1/journeys/{journey_id}").json()
    assert journey["points"][1]["is_plausible"] is False
    assert journey["points"][1]["rejected_reason"] == "implausible_jump"

    statistics = client.get(f"/api/v1/journeys/{journey_id}/statistics").json()
    assert statistics["rejected_points"] == 1
    assert statistics["used_points"] == 1
    assert statistics["distance_m"] < 1.0


def test_device_status_reports_live_connection(client, device_headers, walking_route):
    client.post(GPS_ENDPOINT, json=walking_route[0], headers=device_headers)
    status = client.get("/api/v1/devices/geosketch-01/status").json()
    assert status["connected"] is True
    assert status["device"]["is_live"] is True
    assert status["device"]["last_seen_at"] is not None
    assert status["device"]["last_latitude"] == walking_route[0]["latitude"]
    assert status["latest_point"]["satellites"] == 8
    assert status["active_journey_id"] is not None


def test_device_list_and_unknown_device(client):
    devices = client.get("/api/v1/devices").json()
    assert {device["device_id"] for device in devices} >= {"geosketch-01", "geosketch-02"}
    assert client.get("/api/v1/devices/does-not-exist/status").status_code == 404
