# GeoSketch — GPS Route Art Generation System

**ESP32-C3 + NEO-6M GPS tracker → FastAPI backend → React dashboard → route artwork (PNG / SVG).**

GeoSketch turns a real walk into digital art. A pocket-sized device (ESP32-C3 + NEO-6M GPS
module) reads satellite fixes, validates them, and streams them over Wi-Fi to a FastAPI
backend. The web dashboard plots the journey live on an interactive map, computes journey
statistics, and renders the recorded track as artwork in five styles that can be exported as
PNG and SVG.

```
Physical movement → GPS satellites → NEO-6M → ESP32-C3 → Wi-Fi → FastAPI → SQLite → Web app → Route artwork
```

> **Verification status.** The backend (108 automated tests), the firmware logic, the
> frontend build and the whole software pipeline were verified end to end on this machine,
> including simulated ESP32-C3 HTTP ingestion, artworks in all five styles exported as PNG +
> SVG, and a scripted browser run of the real dashboard (`frontend/scripts/ui-smoke-test.mjs`).
> Steps 1–3 of the acceptance criteria (a physical NEO-6M obtaining real fixes outdoors) can
> only be signed off with the hardware on the bench: see
> [Hardware test procedure](#hardware-test-procedure) and
> [`docs/troubleshooting.md`](docs/troubleshooting.md#verifying-hardware). Anything labelled
> **DEMO MODE** in the UI comes from bundled sample data, never from a device.

---

## Table of contents

- [Features](#features)
- [1. Hardware architecture](#1-hardware-architecture)
- [2. GPS data flow](#2-gps-data-flow)
- [3. Software architecture](#3-software-architecture)
- [4. Journey recording workflow](#4-journey-recording-workflow)
- [Hardware requirements and wiring](#hardware-requirements-and-wiring)
- [ESP32-C3 configuration and flashing](#esp32-c3-configuration-and-flashing)
- [Backend installation](#backend-installation)
- [Frontend installation](#frontend-installation)
- [Database initialisation](#database-initialisation)
- [API documentation](#api-documentation)
- [DEMO MODE](#demo-mode)
- [Route artwork](#route-artwork)
- [Journey statistics](#journey-statistics)
- [Running the tests](#running-the-tests)
- [Hardware test procedure](#hardware-test-procedure)
- [Docker (optional)](#docker-optional)
- [Troubleshooting](#troubleshooting)
- [Known limitations](#known-limitations)
- [Project structure](#project-structure)
- [Documentation index](#documentation-index)

---

## Features

**Embedded (ESP32-C3, Arduino C++)**

- NMEA parsing with **TinyGPSPlus** on a configurable UART (`HardwareSerial`).
- Quality gate before transmission: valid fix, fresh fix, satellites ≥ threshold, HDOP limit.
- Never transmits fabricated coordinates — invalid fixes are counted and reported instead.
- Duplicate/excess-frequency suppression (minimum interval + minimum distance, plus a maximum
  interval so a stationary device still reports liveness).
- RAM ring buffer (oldest first) with exponential-backoff retry, so points recorded while
  offline are sent when Wi-Fi returns.
- HTTP POST with device credentials (`X-Device-Id` / `X-Device-Key`), auto-reconnect and a
  serial-monitor status line (`Initialising → Waiting for fix → Fix acquired → Wi-Fi
  connecting → Connected → Transmission failed → Reconnecting`).

**Backend (Python, FastAPI, SQLAlchemy, SQLite)**

- Device-authenticated GPS ingestion with automatic active-journey resolution.
- Coordinate validation, chronological ordering, duplicate suppression (retry-safe),
  implausible-jump rejection and gap detection.
- Recording state machine, journey persistence, statistics, artwork generation and storage.
- Environment-based configuration, request-size limits, rate limiting, CORS allow-list and
  consistent JSON error bodies.
- SQLAlchemy models with foreign keys + indexes; swapping SQLite → PostgreSQL is a
  `GEOSKETCH_DATABASE_URL` change.

**Frontend (React 19 + Vite + TypeScript + Tailwind v4 + Leaflet)**

- Dark geospatial dashboard: device/GPS status, live coordinates, recording controls,
  journey statistics, point stream and journey history.
- Leaflet map with the recorded route drawn in chronological order, start/end markers,
  direction arrows, direction legend, break detection and fit-to-route.
- Artwork studio: style picker, colour/line/title customisation, instant SVG preview,
  PNG/SVG download and saved artwork metadata.
- DEMO MODE: import a bundled sample route instantly or replay it point-by-point (60× speed)
  so a presentation works indoors with no hardware; all demo data is clearly labelled.

---

## 1. Hardware architecture

```mermaid
graph LR
    SAT["GPS satellites<br/>NMEA 0183"] -->|"1575.42 MHz L1"| ANT["NEO-6M antenna"]
    ANT --> NEO["NEO-6M GPS module<br/>9600 baud UART"]
    NEO -->|"TX → GPIO4 (UART1 RX)"| ESP["ESP32-C3<br/>Arduino C++ / TinyGPSPlus"]
    ESP -->|"Wi-Fi 2.4 GHz + HTTP POST<br/>X-Device-Id / X-Device-Key"| API["FastAPI backend<br/>uvicorn :8000"]
    API --> DB[("SQLite<br/>devices · journeys · gps_points · artworks")]
    API -->|"JSON / PNG / SVG"| UI["React dashboard<br/>Vite :5173"]
    UI --> ART["Route artwork<br/>PNG + SVG export"]
    PWR["USB / 3.7 V LiPo battery"] --> ESP
    PWR --> NEO
```

| Block | Role |
| --- | --- |
| NEO-6M | Receives satellite signals, outputs NMEA sentences (`$GPGGA`, `$GPRMC`, `$GPGSV`, …) at 9600 baud. |
| ESP32-C3 | Parses NMEA, applies the quality gate, deduplicates, buffers, and POSTs JSON over Wi-Fi. |
| FastAPI | Authenticates the device, validates/orders/persists fixes, computes statistics, renders artwork. |
| SQLite | Stores devices, journeys, GPS points and artwork metadata (raw points are never discarded). |
| React app | Live map, recording controls, statistics, artwork studio and exports. |

## 2. GPS data flow

```mermaid
sequenceDiagram
    autonumber
    participant S as GPS satellites
    participant G as NEO-6M
    participant E as ESP32-C3
    participant B as FastAPI backend
    participant D as SQLite
    participant W as React dashboard

    S->>G: Ephemeris + pseudoranges
    G->>E: NMEA sentences (9600 baud, 1 Hz)
    E->>E: TinyGPSPlus parse + quality gate<br/>(valid, fresh, sats >= 4, HDOP <= 8)
    E->>E: Deduplicate (min distance / interval)
    E->>B: POST /api/v1/gps/points (X-Device-Id, X-Device-Key)
    B->>B: Authenticate device, validate coordinates,<br/>check duplicates, jumps and gaps
    B->>D: INSERT gps_point (+ journey row, statistics update)
    B-->>E: 201 {stored: true, sequence, journey_id}
    E->>E: On failure: push to RAM buffer, retry with backoff
    W->>B: GET /api/v1/devices/{id}/status, /journeys/{id}, /journeys/{id}/statistics
    B-->>W: Latest fix, route points, statistics
    W->>W: Draw route on Leaflet map (chronological order, gaps preserved)
    W->>B: POST /api/v1/journeys/{id}/artwork {style, customization}
    B-->>W: PNG/SVG URLs + metadata → download
```

The response body always tells the firmware whether the point was stored. `stored: false`
(duplicate, or recording paused) is **not** an error: the firmware drops the point and moves
on, which is what makes retries safe.

## 3. Software architecture

```mermaid
graph TB
    subgraph FW["firmware/geosketch_esp32c3"]
        INO["geosketch_esp32c3.ino<br/>GPS + Wi-Fi + HTTP + buffer/retry"]
        CFG["config.h (git-ignored)<br/>Wi-Fi, API URL, device key, pins"]
    end

    subgraph BE["backend (FastAPI)"]
        MAIN["app/main.py<br/>CORS · request-size · rate limit · error handlers"]
        API1["app/api/v1<br/>gps · journeys · devices · artworks · demo · meta"]
        SVC["app/services<br/>journey_service · device_service · artwork_service ·<br/>sample_service · geo"]
        ART["app/artwork<br/>geometry · styles · colors · renderers/(svg, png) · engine"]
        UTIL["app/utils<br/>segmentation · formatting · time"]
        MODELS["app/models · app/schemas<br/>SQLAlchemy + Pydantic"]
        DBL["app/database<br/>engine · session · base"]
    end

    subgraph FE["frontend (React + Vite)"]
        PAGES["pages/ Dashboard · Journeys · Studio"]
        COMP["components/ RouteMap · RecordingControls · StatTile ·<br/>StatusPanel · ArtworkStudio · DemoModePanel · JourneyTable"]
        HOOKS["hooks/ useDeviceStatus · useJourney · useRecorder ·<br/>useDemoReplay · useToasts"]
        FAPI["services/api.ts (typed fetch client)"]
    end

    INO --> MAIN
    FAPI --> MAIN
    MAIN --> API1 --> SVC --> MODELS --> DBL
    SVC --> UTIL
    SVC --> ART
    PAGES --> COMP --> HOOKS --> FAPI
    ART -->|"PNG + SVG files"| STORE[("data/artworks/")]
    SAMPLES[("data/sample_routes/*.json")] --> SVC
```

## 4. Journey recording workflow

```mermaid
stateDiagram-v2
    [*] --> recording: POST /journeys (create + start)
    recording --> paused: POST /journeys/{id}/pause
    paused --> recording: POST /journeys/{id}/resume
    recording --> stopped: POST /journeys/{id}/stop or /finish
    paused --> stopped: POST /journeys/{id}/stop or /finish
    stopped --> saved: POST /journeys/{id}/save
    stopped --> [*]: DELETE /journeys/{id} (clear unsaved)
    saved --> [*]

    note right of recording
        Incoming fixes are appended with
        increasing sequence numbers.
    end note
    note right of paused
        The device keeps posting; the API
        answers stored:false, creating a real
        recording gap (no straight line drawn).
    end note
    note right of saved
        Saved journeys are kept for history
        and can be re-rendered as artwork.
    end note
```

Any other transition (for example resuming a `stopped` journey, saving twice, or deleting a
saved journey) is refused with **HTTP 409** and a machine-readable `code`, so the UI can never
put a recording into an impossible state. The dashboard buttons are disabled accordingly.

---

## Hardware requirements and wiring

| Component | Notes |
| --- | --- |
| ESP32-C3 development board | Any ESP32-C3 DevKit exposing UART-capable GPIOs (e.g. ESP32-C3-DevKitM-1). An ESP32-S3 is **not** required. |
| NEO-6M GPS module (with antenna) | Typically a GY-NEO6MV2 breakout with a ceramic patch antenna and a u.FL/SMA connector. |
| Jumper wires | 4 female–female Dupont wires. |
| USB cable | Data-capable (not charge-only) for flashing the ESP32-C3. |
| Computer | Windows 10/11 with Arduino IDE 2.x, Python 3.11+, Node.js 20+. |
| Optional battery | 3.7 V LiPo with a charger/boost module for walking outdoors. |

### Wiring

| NEO-6M | ESP32-C3 | Why |
| --- | --- | --- |
| **TX** | **GPIO 4** (UART1 RX) | NMEA sentences flow *from* the GPS *to* the ESP32-C3. This is the only data line the firmware needs. |
| **RX** | **GPIO 5** (UART1 TX) | Optional. Needed only if you want to send configuration commands (e.g. `$PMTK` rate changes) to the module. Wired by default so the firmware can keep the option. |
| **GND** | **GND** | Common ground is mandatory: UART is referenced to it. |
| **VCC** | **3V3** or **5V** — check your module | GY-NEO6MV2 breakouts have an onboard regulator and accept 3.3–5 V. Bare NEO-6M modules are **3.3 V only**. Never feed 5 V into a bare module. |

Wiring diagram (logic-level sketch):

```
        ESP32-C3                                NEO-6M (GY-NEO6MV2)
   ┌────────────────┐                        ┌────────────────────┐
   │                │      NMEA 9600 baud    │  TX  ──────────────┼──► GPIO 4  (UART1 RX)
   │  GPIO 4  ◄─────┼────────────────────────┘                    │
   │  GPIO 5  ──────┼────────────────────────►  RX  (optional)      │
   │  GND     ──────┼────────────────────────►  GND                │
   │  3V3/5V  ──────┼────────────────────────►  VCC                │
   │  GPIO 20/21 ───┼── USB serial monitor (kept free for debugging)│
   └────────────────┘                        └────────────────────┘
```

Notes and gotchas:

- **Verify your board's pinout before wiring.** Not every ESP32-C3 board breaks out the same
  GPIOs, and some pins are strapping/USB pins (`GPIO18/19` are the native USB D+/D− on many
  boards, `GPIO8`/`GPIO9` are strapping pins). Pick two free GPIOs and update
  `GEOSKETCH_GPS_RX_PIN` / `GEOSKETCH_GPS_TX_PIN` in `config.h`.
- UART0 (`GPIO20`/`GPIO21` on most ESP32-C3 boards) is used by the USB serial monitor, so the
  GPS uses **UART1** in firmware.
- The patch antenna needs a clear view of the sky. Indoors, fix acquisition usually fails —
  that is expected, and it is exactly why DEMO MODE exists.
- Powering the NEO-6M from the board's `3V3` rail is usually fine (≈45 mA peak).

Full pin-by-pin explanation: [`docs/hardware_connections.md`](docs/hardware_connections.md).

---

## ESP32-C3 configuration and flashing

### 1. Arduino IDE setup (Windows)

1. Install **Arduino IDE 2.x** and the **CP210x** or **CH340** USB-serial driver (whichever
   your board uses).
2. `File → Preferences → Additional boards manager URLs` add:

   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```

3. `Tools → Board → Boards Manager…` → search **esp32** → install *esp32 by Espressif
   Systems* (3.x).
4. `Tools → Manage Libraries…` → install **TinyGPSPlus** by Mikal Hart.

### 2. GPS library

GeoSketch uses **TinyGPSPlus** (`TinyGPSPlus.h`) for NMEA parsing — no other third-party GPS
dependency is required. HTTP is done with the bundled `HTTPClient` + `WiFiClient`.

### 3. Create the configuration file

```powershell
cd firmware\geosketch_esp32c3
copy config.h.example config.h
notepad config.h
```

Fill in at minimum:

```cpp
#define GEOSKETCH_WIFI_SSID     "MyHomeWiFi"          // 2.4 GHz only
#define GEOSKETCH_WIFI_PASSWORD "supersecret"
#define GEOSKETCH_API_BASE_URL  "http://192.168.1.50:8000"   // LAN IP of the PC running the backend
#define GEOSKETCH_DEVICE_ID     "geosketch-01"
#define GEOSKETCH_DEVICE_KEY    "CHANGE-ME-device-key-please" // must match GEOSKETCH_DEVICE_KEYS
```

`config.h` is git-ignored (see `.gitignore`); only `config.h.example` is committed. Find the
PC's LAN IP with `ipconfig` (IPv4 Address) and make sure Windows Firewall allows inbound TCP
8000 on private networks.

### 4. Flash

1. Open `firmware/geosketch_esp32c3/geosketch_esp32c3.ino` in Arduino IDE.
2. `Tools → Board → esp32 → ESP32C3 Dev Module`, `Tools → Port → COMx`, `Upload Speed 921600`.
3. Upload and open `Tools → Serial Monitor` at **115200 baud**.

A healthy boot looks like:

```
[GeoSketch] ESP32-C3 + NEO-6M starting
[GeoSketch] GPS UART1 on RX=4 TX=5 @9600 baud
[GPS] waiting for fix ........................ sats=3 hdop=12.4
[GPS] fix acquired  lat=18.520400 lon=73.856700 sats=8 hdop=1.20
[WiFi] connecting to MyHomeWiFi ......
[WiFi] connected  ip=192.168.1.77  rssi=-58 dBm
[POST] journey=12 seq=41 -> 201 stored=true
[STATUS] state=Connected sats=8 sent=41 buffered=0 rejects=2
```

Firmware details, state machine and HTTPS option: [`firmware/geosketch_esp32c3/README.md`](firmware/geosketch_esp32c3/README.md).

---

## Backend installation

Windows (PowerShell or `cmd`):

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Git Bash / macOS / Linux equivalents:

```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `backend\.env`:

```ini
GEOSKETCH_DEVICE_KEYS=geosketch-01:CHANGE-ME-device-key-please
GEOSKETCH_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Generate a real device key instead of the placeholder:

```powershell
python -c "import secrets;print(secrets.token_urlsafe(24))"
```

Then put the same value in the firmware's `GEOSKETCH_DEVICE_KEY`.

Run the API:

```powershell
.venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- `--host 0.0.0.0` is what makes the API reachable from the ESP32-C3 on the LAN.
- Health check: <http://127.0.0.1:8000/api/v1/health>
- Interactive API docs (OpenAPI): <http://127.0.0.1:8000/docs>

All settings are optional except the device key: see the fully commented
[`backend/.env.example`](backend/.env.example).

## Frontend installation

```powershell
cd frontend
npm install
copy .env.example .env
npm run dev
```

Open <http://127.0.0.1:5173>.

`frontend\.env`:

```ini
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_DEVICE_ID=geosketch-01
```

Use the PC's LAN IP for `VITE_API_BASE_URL` when the dashboard is opened from a phone or
another machine. Production build:

```powershell
npm run build     # tsc --noEmit && vite build  ->  frontend/dist
npm run preview
```

## Database initialisation

**No manual step is required.** On startup the backend creates `backend/geosketch.db` (SQLite),
creates every table/index if missing, and bootstraps the devices declared in
`GEOSKETCH_DEVICE_KEYS` (only the SHA-256 digest of each key is stored).

To start from a clean slate, stop the server and delete the database file:

```powershell
cd backend
del geosketch.db geosketch.db-wal geosketch.db-shm
```

To move to PostgreSQL later, only the URL changes (install `psycopg[binary]` first):

```ini
GEOSKETCH_DATABASE_URL=postgresql+psycopg://geosketch:secret@localhost:5432/geosketch
```

Artworks are written to `data/artworks/` and sample routes are read from
`data/sample_routes/`; both paths are configurable (`GEOSKETCH_ARTWORK_DIR`,
`GEOSKETCH_SAMPLE_ROUTES_DIR`).

---

## API documentation

Base URL: `http://<host>:8000/api/v1` · interactive docs: `/docs` · schema: `/api/v1/openapi.json`

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/gps/points` | Ingest one GPS fix from the ESP32-C3 (device auth required). |
| `POST` | `/journeys` | Create **and start** a new journey. |
| `GET` | `/journeys` | List the user's journeys (`?status=`,`?source=`,`?limit=`,`?offset=`). |
| `GET` | `/journeys/{id}` | Journey metadata **and** its recorded GPS points. |
| `PATCH` | `/journeys/{id}` | Rename / annotate a journey. |
| `DELETE` | `/journeys/{id}` | Clear an unsaved journey (`409` once saved). |
| `POST` | `/journeys/{id}/start` \| `/pause` \| `/resume` \| `/stop` \| `/finish` | Recording state machine. |
| `POST` | `/journeys/{id}/save` | Save the journey (`409` if not stopped / already saved). |
| `POST` | `/journeys/{id}/points` | Bulk upload — **demo replay only** (`source: "demo"` journeys). |
| `GET` | `/journeys/{id}/statistics` | Distance, duration, moving time, average speed, points, gaps. |
| `GET` | `/journeys/{id}/device` | Device that recorded the journey (if any). |
| `POST` | `/journeys/{id}/artwork` | Generate artwork, persist files + metadata. |
| `POST` | `/journeys/{id}/artwork/preview` | Inline SVG preview, nothing stored. |
| `GET` | `/journeys/{id}/artworks` | Artworks generated for a journey. |
| `GET` | `/artworks/{id}` | Artwork metadata. |
| `GET` | `/artworks/{id}/download?format=png\|svg` | Download the rendered file. |
| `GET` | `/artwork/styles` | Available styles and palettes. |
| `GET` | `/devices` · `GET /devices/{id}/status` | Registered devices and live connection status. |
| `POST` | `/devices/register` · `/devices/heartbeat` · `/devices/sync` | Device lifecycle (fan-out of the configured keys). |
| `GET` | `/demo/routes` · `GET /demo/routes/{id}` | Bundled sample routes. |
| `POST` | `/demo/routes/{id}/import` | Import a sample route as a finished **demo** journey. |
| `GET` | `/health` | Health check with database and device counts. |

### Device authentication

GPS ingestion is authenticated with two headers, exactly as the firmware sends them:

```
X-Device-Id: geosketch-01
X-Device-Key: <the plaintext key from GEOSKETCH_DEVICE_KEYS>
```

Keys are compared in constant time against a stored SHA-256 digest; a wrong key is `401`, a
`device_id` that does not match the authenticated device is `403`. Journeys are scoped to an
owner (single-tenant `local` by default, overridable per request with `X-Owner-Key`), so
journey data is never public by default.

### Example: a fix exactly as the firmware sends it

```bash
curl -X POST http://127.0.0.1:8000/api/v1/gps/points \
  -H "Content-Type: application/json" \
  -H "X-Device-Id: geosketch-01" \
  -H "X-Device-Key: CHANGE-ME-device-key-please" \
  -d "{\"latitude\":18.5204,\"longitude\":73.8567,\"altitude\":560.0,\"speed_kmh\":4.5,\"satellites\":8,\"timestamp\":\"2026-10-15T10:30:00Z\",\"client_point_id\":\"boot7-1041\"}"
```

```json
{
  "stored": true,
  "reason": null,
  "point_id": 418,
  "journey_id": 12,
  "sequence": 41,
  "recorded_at": "2026-10-15T10:30:00Z",
  "duplicate": false
}
```

`stored: false` with `reason: "duplicate"` (a retried `client_point_id`) or
`reason: "journey_paused"` means *do not retry* — the firmware drops the point. Invalid
coordinates, timestamps far in the future, or payloads above the request-size limit are
rejected with `422`/`413` and a consistent error body:

```json
{ "error": { "code": "validation_error", "message": "latitude must be between -90 and 90",
             "details": [{"field": "latitude", "message": "..."}] } }
```

### Example: artwork generation

```bash
curl -X POST http://127.0.0.1:8000/api/v1/journeys/12/artwork \
  -H "Content-Type: application/json" \
  -d "{\"style\":\"poster\",\"title\":\"Morning Walk\",\"export_format\":\"png\",\"customization\":{\"background\":\"#0b1020\",\"route_color\":\"#22d3ee\",\"line_width\":3,\"show_start_marker\":true,\"show_end_marker\":true}}"
```

---

## DEMO MODE

DEMO MODE exists so the project can be demonstrated and developed without GPS reception
(classrooms are indoors). It never pretends to be hardware:

- Sample journeys are stored with `source = "demo"`; hardware journeys use `source = "device"`.
- The API refuses to mix them: demo points can only go to demo journeys
  (`422 source_mismatch`) and demo routes can only be replayed into demo journeys.
- The dashboard shows a **DEMO DATA** badge, the status panel says *"Simulated — demo data, no
  hardware involved"*, and the map footer repeats it.

To use it, open the dashboard, pick a sample route in the **DEMO MODE** card and either:

- **Import instantly** — the whole route is stored as a finished demo journey (fast, ideal for
  jumping straight to statistics and artwork), or
- **Replay on the map** — points are streamed into a fresh recording at 60× real time, so a
  45-minute walk appears in ~45 seconds with live map, statistics and point stream. Replay
  stops the recording automatically at the end; press **Save** to keep the journey.

| Sample route | Points | Distance | Duration | Demonstrates |
| --- | --- | --- | --- | --- |
| `city_grid_walk` | 407 | 2.73 km | 33.9 min | Grid streets, one deliberate rest stop (gap). |
| `hill_switchbacks` | 541 | 3.38 km | 45.1 min | Tight switchbacks and elevation change. |
| `marine_drive_loop` | 521 | 3.73 km | 43.4 min | A closed loop (start ≈ end). |
| `riverfront_walk` | 232 | 2.06 km | 24.3 min | A simulated GPS outage (multi-segment route). |

These JSON files live in `data/sample_routes/` and can be regenerated with
`python data/sample_routes/generate_sample_routes.py`.

## Route artwork

Five styles, all rendered by GeoSketch's own code (no paid API, no ML model):

| Style | Description |
| --- | --- |
| **Minimal Route** | Clean, thin line drawing on a light or dark canvas. |
| **Neon Trail** | Glowing layered strokes with a bloom effect on near-black. |
| **Gradient Journey** | Colour gradient along the path (start → end) representing progression. |
| **Artistic Poster** | Route plus title, distance, duration and recording date in a poster layout. |
| **Custom Art** | Background, route colour, accent colour, line width, glow, title/subtitle, marker toggles, canvas size. |

Coordinate processing pipeline (implemented in `backend/app/artwork/geometry.py`):

1. validate each fix (range, timestamp, duplicates),
2. keep the recordings' original chronological sequence,
3. drop redundant consecutive points below `GEOSKETCH_MIN_POINT_DISTANCE_M`,
4. cut the route at implausible jumps (`GEOSKETCH_MAX_PLAUSIBLE_SPEED_KMH`) and at recording
   gaps (`GEOSKETCH_MAX_GAP_SECONDS`) instead of drawing a straight line across them,
5. project to local metres (equirectangular around the route centre),
6. normalise into the canvas with padding, **preserving aspect ratio**,
7. simplify (Douglas–Peucker on a copy) only for drawing, keeping the real shape,
8. emit SVG directly and rasterise PNG with Pillow at 1×/2× scale.

Raw GPS points are never modified — the processed route is a separate object, which is why any
artwork can be regenerated later from the stored journey.

Exports are written to `data/artworks/` as
`journey<id>-<style>-<hash>.png` / `.svg` and downloaded through
`GET /api/v1/artworks/{id}/download?format=png|svg`.

> A recorded route only becomes a recognisable shape (a heart, an animal, …) if the *walk
> itself* traces that shape or an explicit transformation is applied. GeoSketch draws the
> track you actually walked — it does not claim to invent shapes.

## Journey statistics

`GET /api/v1/journeys/{id}/statistics` returns:

| Field | Meaning |
| --- | --- |
| `distance_m` | Sum of Haversine distances over accepted consecutive fixes (breaks excluded). |
| `duration_seconds` | `ended_at - started_at` (or now, while recording), including pauses. |
| `moving_seconds` | Time during which the route actually progressed (used for average speed). |
| `average_speed_kmh` | Moving distance ÷ moving time; `null` when it is not meaningful (< 2 fixes / ~0 moving time). |
| `point_count`, `accepted_points`, `rejected_points` | Raw stored fixes vs used/filtered ones. |
| `segment_count`, `gaps` | How many continuous segments the route has and where the breaks are. |
| `start_point`, `end_point` | First/last accepted coordinates. |
| `started_at`, `ended_at` | Recording window. |

**GPS distance is an estimate.** Satellite noise, filtering of redundant points, rejected jumps
and paused recordings all make the GPS-derived distance differ (usually slightly less) from the
true walked distance. The dashboard labels every distance as *“GPS estimate”* and shows the
counts of used/filtered points and gaps next to it. Please do not present it as a land-survey
measurement.

---

## Running the tests

Backend (108 tests — validation, parsing, distance, duplicates, jump detection, journey
lifecycle, artwork, PNG/SVG export, API errors):

```powershell
cd backend
.venv\Scripts\python -m pytest -q          # 108 passed
```

| File | Tests | Covers |
| --- | --- | --- |
| `tests/test_geo.py` | 21 | Haversine distance, bearing, coordinate validation, projection/normalisation. |
| `tests/test_segmentation.py` | 10 | Gap detection, jump detection, redundant-point removal, segment reconstruction. |
| `tests/test_ingest.py` | 17 | Payload parsing, invalid coordinates, duplicate suppression, pause handling, device auth. |
| `tests/test_journeys.py` | 23 | Recording state machine, lifecycle guards (409s), statistics, persistence. |
| `tests/test_artwork.py` | 18 | All five styles, customisation, SVG/PNG rendering, no-canvas/empty-route edge cases. |
| `tests/test_demo_and_api.py` | 19 | Sample routes, demo provenance isolation, health/docs, error contract, rate limiting. |

Frontend:

```powershell
cd frontend
npm run typecheck
npm run build
```

Browser UI smoke test (drives the real dashboard through Chrome DevTools Protocol — recording
controls, demo replay, artwork studio and downloads):

```powershell
# 1. start the backend and `npm run dev`, then a debug Chrome:
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --headless=new `
    --remote-debugging-port=9222 --user-data-dir="$env:TEMP\geosketch-chrome" `
    http://127.0.0.1:5173
# 2. run the checks
cd frontend
npm run ui:smoke
```

Test plan, mock-GPS strategy and the outdoor procedure:
[`docs/testing.md`](docs/testing.md).

## Hardware test procedure

Run this **outdoors** (or at least in a window with a clear sky view) and work top to bottom.
Each step has an explicit pass condition.

1. **Wiring** — power off, recheck the four wires against your board's pinout (TX→GPIO4,
   VCC→3V3/5V, GND→GND). Pass: no heat, no smoke, the module's LED blinks.
2. **Serial, no Wi-Fi** — flash with the Wi-Fi SSID blank; the monitor must log
   `waiting for fix …` with a growing satellite count and then
   `fix acquired lat=… lon=…`. **Pass:** coordinates that change when you walk ~20 m and match
   the phone's map within a few metres.
3. **Cold start** — with the antenna outdoors, time from power-on to first fix.
   **Pass:** < 60 s (hot start a few seconds). 30+ s outdoors usually means obstruction.
4. **Fix quality** — walk 50 m in a straight line. **Pass:** `sats ≥ 6`, `hdop < 2`, `speed`
   plausible when moving and ≈0 when standing still.
5. **Wi-Fi + ingest** — set the LAN IP of the backend PC in `config.h`, flash the full firmware
   and watch the monitor for `[POST] … -> 201 stored=true`. **Pass:** the dashboard shows the
   point within ~1 s (`GET /devices/geosketch-01/status` agrees) and the coordinate is inside
   your neighbourhood, not a placeholder.
6. **Recording** — press **Start Recording**, walk ~200 m, press **Stop** then **Save**.
   **Pass:** the map shows only the walked track, distance is within ~10–15 % of a phone
   fitness app, no straight line across any break.
7. **Outage handling** — walk out of Wi-Fi range for a minute, come back. **Pass:**
   `buffered=…` grows in the monitor, then drops to 0 and the missed points appear on the map
   (ordered, with a gap — no teleport line).
8. **Duplicate safety** — kill the backend mid-walk and restart it. **Pass:** no point is
   stored twice (`duplicate: true` responses) and sequence numbers stay increasing.
9. **Artwork** — generate all five styles from the walk and download PNG + SVG.
   **Pass:** the artwork is recognisable as the walked route; PNG opens in any viewer, SVG opens
   in a browser and scales without blur.
10. **Summary** — capture the serial log and the exported artwork as evidence for the report.

Record the date, weather, sats/HDOP, and distance-vs-phone-app comparison. Steps 1–4 need only
the device and a serial monitor; steps 5–9 additionally need the backend running.

## Docker (optional)

Docker is **not** required for local development. If you prefer containers:

```powershell
docker compose up --build
```

- API on <http://127.0.0.1:8000/docs>, dashboard on <http://127.0.0.1:5173>.
- The database, artwork exports and sample routes are bind-mounted from the repository, so a
  `docker compose up` starts with the same data you had on the host.
- USB flashing still happens on the host with Arduino IDE — Docker only runs the backend and
  the frontend.

## Troubleshooting

| Symptom | Likely cause / fix |
| --- | --- |
| Dashboard says *Tracker not reporting* | Expected after ~30 s without a fix: the device is offline but the **last known** position and its timestamp stay visible. Check the firmware monitor and `GET /devices/geosketch-01/status`. |
| `401 invalid_device_key` from `/gps/points` | `GEOSKETCH_DEVICE_KEY` in `config.h` must equal the plaintext key in `GEOSKETCH_DEVICE_KEYS` (restart the backend after editing `.env`). |
| `connection refused` on the ESP32-C3 | Wrong LAN IP/port, the backend is bound to `127.0.0.1` (use `--host 0.0.0.0`), or Windows Firewall is blocking inbound TCP 8000. |
| No NMEA data, latitude stays `0.000000` | GPS TX not wired to the configured RX pin, baud mismatch (9600), GND not common, or the module is powered from a 3.3 V rail that browns out. |
| Fix never acquired | Indoors / antenna obstructed — the NEO-6M needs sky view (first fix outdoors can take 30–60 s). Use DEMO MODE while developing inside. |
| Route shows a long straight line across a gap | Should not happen: the backend segments the route and the map draws segments separately. Check `segment_count`/`gaps` in `/statistics`. |
| `409 invalid_transition` when pressing Save/Resume | Working as intended — the state machine forbids it. Finish the recording (Stop) before saving. |
| Artwork looks flat or empty | A very short route (< ~10 points) or all points identical. Try a longer journey or a sample route in DEMO MODE. |
| `413 request_too_large` | The payload exceeded `GEOSKETCH_MAX_REQUEST_BYTES` (64 kB) — the firmware sends one point per request, so this normally means a mis-built request. |
| `429 rate_limited` | More than `GEOSKETCH_RATE_LIMIT_REQUESTS` (240/min) from one client; raise it for load testing. |

More: [`docs/troubleshooting.md`](docs/troubleshooting.md).

## Known limitations

- **GPS is an estimate.** Distance/speed come from satellite fixes; expect a few percent of
  error versus a surveyed distance, plus larger errors under tree cover or between buildings.
- **The NEO-6M is 1 Hz, ~2.5 m CEP.** It is not RTK; the artwork therefore reflects a smoothed
  track, not centimetre-accurate geometry.
- **Indoor reception does not work** (as with any GNSS receiver). Use DEMO MODE for development
  and presentation indoors.
- **The ESP32-C3 is 2.4 GHz only** — it cannot join a 5 GHz-only network. Use a phone hotspot if
  needed.
- **Plain HTTP on the LAN** by default. HTTPS is possible (`WiFiClientSecure` + the callbacks in
  `TinyGPSPlus`-free `HTTPClient` setup); see the firmware README. Do not use plain HTTP over an
  untrusted network.
- **Single-tenant by default.** There is no user login: journeys belong to the configured owner
  (`local`). Add authentication before exposing the API to the internet.
- **Raw points are kept forever.** GeoSketch stores every accepted fix, so a long-running
  installation grows the SQLite file; prune old journeys if that matters (no automatic
  retention policy is implemented).
- **Demo data is simulated.** Sample routes are generated procedurally
  (`data/sample_routes/generate_sample_routes.py`) and are always labelled in the API and UI.
- **Physical-hardware acceptance items are pending** until the procedure above is run with a
  real ESP32-C3 + NEO-6M (see the verification status note at the top).
- `python-multipart` and `httpx` are installed for FastAPI form handling and tests; a
  `starlette.testclient` deprecation warning about `httpx` appears during the test run —
  harmless for this version.

## Project structure

```
GeoSketch/
├── firmware/
│   └── geosketch_esp32c3/
│       ├── geosketch_esp32c3.ino     # GPS + Wi-Fi + HTTP + buffer/retry firmware
│       ├── config.h.example          # Wi-Fi / API URL / device key / pins (copy to config.h)
│       └── README.md
├── backend/
│   ├── app/
│   │   ├── main.py                   # FastAPI app, middleware, error handlers, lifespan
│   │   ├── api/                      # deps.py + v1/ routers (gps, journeys, devices, artworks, demo, meta)
│   │   ├── core/                     # config, security, errors, middleware
│   │   ├── models/                   # SQLAlchemy: device, journey, gps_point, artwork
│   │   ├── schemas/                  # Pydantic request/response models
│   │   ├── services/                 # journey, device, artwork, sample, geo
│   │   ├── artwork/                  # geometry, styles, colors, renderers/{svg,png}, engine, generator
│   │   ├── database/                 # engine, session, base
│   │   └── utils/                    # segmentation, formatting, time
│   ├── tests/                        # pytest suite (108 tests)
│   ├── requirements.txt
│   ├── pytest.ini
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/               # RouteMap, RecordingControls, StatTile, StatusPanel,
│   │   │                             # ArtworkStudio, DemoModePanel, JourneyTable, …
│   │   ├── pages/                    # DashboardPage, JourneysPage, StudioPage
│   │   ├── hooks/                    # useDeviceStatus, useJourney, useRecorder, useDemoReplay, useToasts
│   │   ├── services/api.ts           # typed API client
│   │   ├── types/                    # shared API types
│   │   └── utils/                    # format, geo
│   ├── scripts/ui-smoke-test.mjs     # scripted browser smoke test
│   ├── package.json
│   └── vite.config.ts
├── data/
│   ├── sample_routes/                # bundled demo routes + generator
│   └── artworks/                     # generated PNG/SVG exports (runtime output)
├── docs/
│   ├── architecture.md
│   ├── hardware_connections.md
│   ├── setup_guide.md
│   ├── testing.md
│   └── troubleshooting.md
├── docker-compose.yml
├── .gitignore
└── README.md
```

## Documentation index

| Document | Contents |
| --- | --- |
| [`docs/architecture.md`](docs/architecture.md) | Component responsibilities, data model, request lifecycle, design decisions, PostgreSQL migration path. |
| [`docs/hardware_connections.md`](docs/hardware_connections.md) | Pin-by-pin wiring, voltage/level notes, power options, antenna placement, pin-selection rules. |
| [`docs/setup_guide.md`](docs/setup_guide.md) | Step-by-step Windows setup, from Arduino IDE to a first recorded journey, with checks at each step. |
| [`docs/testing.md`](docs/testing.md) | Automated test inventory, mock GPS strategy, outdoor hardware procedure, what each test proves. |
| [`docs/troubleshooting.md`](docs/troubleshooting.md) | Symptom → cause → fix tables for firmware, backend, frontend and GPS reception. |
| [`firmware/geosketch_esp32c3/README.md`](firmware/geosketch_esp32c3/README.md) | Firmware architecture, state machine, configuration reference, HTTPS option. |

---

Built as a full-stack, hardware-based project: real GPS hardware in, real artwork out — no paid
APIs and no fabricated coordinates anywhere in the pipeline.
