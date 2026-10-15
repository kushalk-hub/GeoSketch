# Bundled sample routes (DEMO MODE)

Procedurally generated GPS traces used by **DEMO MODE** so the project can be developed,
tested and demonstrated indoors, where a NEO-6M cannot obtain a fix.

These files are **simulated data**. They are loaded by the backend at startup and are only ever
written into journeys with `source = "demo"` — the API refuses to mix them with device
recordings (`422 source_mismatch`), and the dashboard labels them with a **DEMO DATA** badge.

| File | Route | Points | Distance | Duration | Designed to exercise |
| --- | --- | --- | --- | --- | --- |
| `city_grid_walk.json` | City Grid Walk (with rest stop) | 407 | 2.73 km | 33.9 min | Grid streets and one recording gap (a pause) — no straight line across the break. |
| `hill_switchbacks.json` | Hill Switchbacks | 541 | 3.38 km | 45.1 min | Tight switchbacks and altitude change — vertical profile plus dense point cloud. |
| `marine_drive_loop.json` | Marine Drive Loop | 521 | 3.73 km | 43.4 min | A closed loop (start ≈ end) — aspect-ratio and poster layout checks. |
| `riverfront_walk.json` | Riverfront Walk (with GPS outage) | 232 | 2.06 km | 24.3 min | A simulated multi-minute GPS outage — multi-segment routes and gap statistics. |

Each file contains metadata plus a `points` array, matching what the firmware sends:

```json
{
  "id": "riverfront_walk",
  "name": "Riverfront Walk (with GPS outage)",
  "description": "…",
  "source": "demo",
  "distance_m": 2055.1,
  "duration_seconds": 1460.0,
  "point_count": 232,
  "points": [
    {
      "t": 5.0,
      "latitude": 18.5204084,
      "longitude": 73.8567144,
      "altitude": 560.4,
      "speed_kmh": 4.86,
      "satellites": 10
    }
  ]
}
```

- `t` is seconds from the start of the recording; the replay uses it to schedule points, and the
  API timestamp of each point is derived as `recording_start + t` so statistics stay realistic.
- Every point carries `altitude`, `speed_kmh` and `satellites`; the simulated **GPS outage** in
  `riverfront_walk` is expressed as a jump in `t` (a multi-minute gap), which is exactly how a
  real outage appears in the data.

## Regenerating

```powershell
cd data\sample_routes
python generate_sample_routes.py        # rewrites all four JSON files
python generate_sample_routes.py --help
```

The generator is deterministic (fixed seeds), living in
[`generate_sample_routes.py`](generate_sample_routes.py). Once written, restart the backend (or
call `POST /api/v1/devices/sync`) — sample routes are read on startup; the files themselves are
plain JSON, so you can also hand-edit them to craft a specific demo shape.

## Using them

- Dashboard → **DEMO MODE** → pick a route → **Import instantly** (finished journey) or
  **Replay on the map** (streamed at 60× with live statistics).
- API: `GET /api/v1/demo/routes`, `GET /api/v1/demo/routes/{id}`,
  `POST /api/v1/demo/routes/{id}/import`.
- Tests: `tests/test_demo_and_api.py` validates loading, metadata and provenance isolation.
