# GeoSketch architecture

This document explains how the three deliverables (firmware, backend, frontend) fit together,
where responsibilities are drawn, and the reasoning behind the decisions that are easy to get
wrong (ordering, duplicates, gaps, provenance, coordinates → canvas).

```
Firmware ──HTTP/JSON──► Backend ──SQLAlchemy──► SQLite
   (device)              (FastAPI)                 │
                             │◄────────────────────┘
                             │ JSON · PNG · SVG
                             ▼
                         Frontend (React)
```

## 1. Component responsibilities

| Layer | Owns | Deliberately does **not** own |
| --- | --- | --- |
| **Firmware** (`firmware/geosketch_esp32c3`) | NMEA parsing, fix quality gate, deduplication, retry/buffering, Wi-Fi reconnect, serial diagnostics. | Statistics, route segmentation, storage, artwork. It only reports *fixes*. |
| **Backend** (`backend/app`) | Device auth, validation, ordering, deduplication, gap/jump detection, the recording state machine, statistics, artwork rendering, persistence. | Presentation. It returns data and files, never HTML. |
| **Frontend** (`frontend/src`) | Live map, recording controls (calls the state machine), statistics presentation, artwork customisation UI, downloads. | It never invents coordinates, never reorders points and never stores its own source of truth: every render comes from an API response. |
| **Sample routes** (`data/sample_routes`) | Realistic demo input (procedurally generated, documented). | They are never presented as hardware data. |

## 2. Backend layout

```
app/
├── main.py            # app factory + lifespan (create tables, bootstrap devices, load samples)
├── api/
│   ├── deps.py        # get_db, require_device, require_owner, COMMON_ERROR_RESPONSES
│   └── v1/
│       ├── gps.py       POST /gps/points            (device auth)
│       ├── journeys.py  lifecycle, statistics, artwork generation, point stream
│       ├── devices.py   register / heartbeat / status / sync
│       ├── artworks.py  metadata + file download
│       ├── demo.py      sample routes, instant import, demo replay upload
│       └── meta.py      /health, project banner
├── core/
│   ├── config.py      # pydantic-settings, GEOSKETCH_* env vars, directory resolution
│   ├── security.py    # key generation, SHA-256 hashing, constant-time verify, owner scope
│   ├── errors.py      # AppError hierarchy + consistent {"error": {...}} bodies
│   └── middleware.py  # request-size limit, rate limiting, request id
├── models/            # SQLAlchemy 2.x (Mapped[...]) — device, journey, gps_point, artwork
├── schemas/           # Pydantic v2 request/response models
├── services/
│   ├── geo.py             # Haversine, bearing, validation
│   ├── journey_service.py # ingest_point, state machine, statistics
│   ├── device_service.py  # bootstrap/heartbeat/status/online window
│   ├── artwork_service.py # orchestration: journey -> processed route -> renderer -> files
│   └── sample_service.py  # load/validate sample routes
├── artwork/
│   ├── geometry.py    # validation, simplification, segmentation, projection, normalisation
│   ├── styles.py      # style + palette catalogue, style defaults
│   ├── colors.py      # colour maths (gradients, glow, contrast)
│   ├── engine.py      # style -> drawing instructions (single source of truth)
│   ├── generator.py   # high-level generate/save helpers
│   └── renderers/
│       ├── svg.py     # SVG document emitter
│       └── png.py     # Pillow rasteriser
├── database/          # engine, session factory (SQLite pragmas), declarative base
└── utils/             # segmentation (shared with statistics), formatting, time
```

The important structural rule: **route processing lives in one place** (`artwork/geometry.py`
and `utils/segmentation.py`) and both statistics and rendering consume it. The frontend mirrors
the *segmentation* rule in `src/utils/geo.ts` for drawing only, so the drawn route and the
reported numbers always agree.

## 3. Data model

```mermaid
erDiagram
    DEVICE ||--o{ JOURNEY : records
    DEVICE ||--o{ GPS_POINT : reports
    JOURNEY ||--o{ GPS_POINT : contains
    JOURNEY ||--o{ ARTWORK : "is rendered as"

    DEVICE {
        string device_id PK
        string name
        string api_key_hash "SHA-256 digest only"
        datetime last_seen_at
        string firmware_version
        string owner "single-tenant scope"
    }
    JOURNEY {
        int id PK
        string title
        string device_id FK "nullable (manual/demo)"
        string source "device | demo | manual"
        string status "recording | paused | stopped | saved"
        datetime started_at
        datetime ended_at
        float total_distance_m
        float duration_seconds
        string notes
    }
    GPS_POINT {
        int id PK
        int journey_id FK
        string device_id FK "nullable"
        int sequence "per journey, increasing"
        float latitude
        float longitude
        float altitude "nullable"
        float speed_kmh "nullable"
        int satellites "nullable"
        datetime gps_timestamp
        datetime server_timestamp
        string source "device | demo"
        bool is_plausible
        string rejected_reason "nullable"
        string client_point_id "unique per journey + source"
    }
    ARTWORK {
        int id PK
        int journey_id FK
        string title
        string style
        string export_format
        int width
        int height
        int point_count
        int segment_count
        float distance_m
        string customization "JSON text"
        string png_path
        string svg_path
        datetime created_at
    }
```

Indexes/constraints that matter:

- `gps_points(journey_id, sequence)` — point stream and route assembly.
- `gps_points(journey_id, client_point_id)` **unique** — the whole retry-safety guarantee.
- `gps_points(device_id, gps_timestamp)` — device timeline/status queries.
- `journeys(status)`, `journeys(started_at)` — history listing and active-journey lookup.
- Foreign keys are enforced (`PRAGMA foreign_keys=ON` on SQLite).

## 4. Request lifecycle: one GPS fix

1. Firmware POSTs to `/api/v1/gps/points` with `X-Device-Id` / `X-Device-Key`.
2. `middleware.py` checks the body size; the rate limiter counts the request per client.
3. `deps.require_device` hashes the presented key and compares it in constant time with the
   stored digest → `401` on failure; body `device_id` mismatches → `403`.
4. `journey_service.ingest_point` runs the guards **in order**:
   a. coordinate/timestamp validation (`schemas/gps.py` + `services/geo.py`) → `422`;
   b. payload `source` must match the target journey's source (no demo↔device mixing) → `422`;
   c. duplicate `client_point_id` → `stored: false, duplicate: true` (no insert, no retry);
   d. journey not `recording` → `stored: false, journey_paused` (this is what creates a *real*
      gap rather than a straight line);
   e. plausibility: implied speed over the previous accepted fix; implausible fixes are stored
      with `is_plausible = false` + `rejected_reason` (kept as evidence, excluded from the route
      and statistics). After `GEOSKETCH_REANCHOR_AFTER_REJECTS` consecutive rejections the fix
      is trusted again, so a genuine relocation (GPS drift correction) can never freeze a
      recording;
   f. insert with `sequence = last + 1`, refresh journey aggregates and the device `last_seen_at`.
5. Response: `201` with `stored`, `reason`, `sequence`, `journey_id` — always safe to interpret
   as "do not retry this exact point".

## 5. Request lifecycle: artwork

```mermaid
sequenceDiagram
    participant UI as Studio (React)
    participant API as /journeys/{id}/artwork
    participant SVC as artwork_service
    participant GEO as artwork/geometry
    participant ENG as artwork/engine
    participant R as renderers (svg, png)

    UI->>API: {style, title, export_format, width, height, customization}
    API->>SVC: generate(journey, request)
    SVC->>SVC: load raw points (chronological, accepted only)
    SVC->>GEO: validate -> project -> segment -> normalise (aspect preserved)
    GEO-->>SVC: processed route (segments, bounds, stats, processing report)
    SVC->>ENG: build(style, route, customization)
    ENG-->>SVC: drawing instructions (paths, gradients, glow layers, typography)
    SVC->>R: render SVG document
    R-->>SVC: svg text
    SVC->>R: rasterise PNG with Pillow
    R-->>SVC: png bytes
    SVC->>SVC: write files to data/artworks/, insert Artwork row
    SVC-->>API: ArtworkOut (urls + metadata)
    API-->>UI: preview SVG / metadata
```

`POST /artwork/preview` returns the same geometry result as inline SVG **without** writing files,
which is what makes the studio feel instant while dragging a colour picker.

## 6. Recording state machine

Guarded transitions (see `journey_service.TRANSITIONS`) — everything else is `409
invalid_transition` with the current status in the body:

| From | Allowed | Result |
| --- | --- | --- |
| `recording` | `pause`, `stop`, `finish` | `paused` / `stopped` |
| `paused` | `resume`, `stop`, `finish` | `recording` / `stopped` |
| `stopped` | `save`, delete | `saved` / removed |
| `saved` | — | terminal (delete refused) |

Why the frontend cannot drift out of sync: it does not compute the state itself. Every control
calls the endpoint and re-renders from the returned journey; buttons whose transition is not in
the table are disabled. A second browser tab therefore shows the same truth.

## 7. Statistics and route processing

- Distance = Σ Haversine(accepted consecutive fixes inside a segment). Breaks (jumps, gaps,
  paused periods) contribute nothing — no fake straight-line distance.
- Duration = wall clock of the recording window; moving time only counts intervals where the
  route actually progressed, and average speed uses moving time (or is `null` when meaningless).
- Segmentation rules are centralised in `utils/segmentation.py`, used by statistics, artwork and
  (mirrored) by the frontend map, so a break is never drawn as a movement.

## 8. Provenance and safety invariants

1. **No fabricated coordinates.** The backend never synthesises a point for a device journey;
   sample data is written only into journeys with `source = "demo"`, and both the API
   (`422 source_mismatch`) and the UI badges enforce the separation.
2. **Retry safety.** Every point carries a `client_point_id`; a retransmission is acknowledged
   with `stored: false` instead of duplicating a row.
3. **No credentials in source.** Device keys live in `.env` (git-ignored) and firmware
   `config.h` (git-ignored); only SHA-256 digests are persisted.
4. **Raw data is immutable.** Route processing works on copies; the journey keeps every accepted
   fix (plus rejected ones with their reason) so artwork is reproducible.
5. **Bounded input.** Request-size limit, rate limit, coordinate/timestamp validation and
   pagination on list endpoints.

## 9. Scaling out (SQLite → PostgreSQL)

The data layer is SQLAlchemy 2.x with portable types (no SQLite-specific SQL in queries), so the
migration is:

1. `pip install "psycopg[binary]"`.
2. `GEOSKETCH_DATABASE_URL=postgresql+psycopg://user:pass@host:5432/geosketch`.
3. Point the same app at it (`create_all` runs on startup; Alembic can be added for versioned
   migrations).

Everything else (services, artwork engine, API, frontend) is storage-agnostic. For higher
ingest rates, the next steps would be swapping the in-process rate limiter for Redis, moving
artwork rendering to a background worker, and serving `data/artworks` from object storage —
none of which changes the interfaces described above.
