# Troubleshooting

Symptom → cause → fix. Start with [the 30-second triage](#30-second-triage), then jump to the
section that matches where the problem appears.

## 30-second triage

| Question | If no → |
| --- | --- |
| Does `http://127.0.0.1:8000/api/v1/health` return `"status": "ok"`? | [Backend does not start](#2-backend) |
| Does the dashboard load at `http://127.0.0.1:5173`? | [Frontend](#3-frontend) |
| Does the serial monitor show `fix acquired`? | [GPS reception](#1-gps-reception-and-firmware) |
| Does the monitor show `-> 201 stored=true` after a fix? | [Device → backend link](#4-device--backend-link) |
| Does the fix appear on the map within a second? | [Data flow / frontend state](#5-data-not-appearing-in-the-ui) |

---

## 1. GPS reception and firmware

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Console shows commas and empty fields; `lat=0.000000` | No NMEA arriving | GPS **TX** must go to the configured RX pin (default GPIO4); check GND is shared; confirm `GEOSKETCH_GPS_BAUD 9600`. |
| Garbled/random characters instead of `$GPGGA,…` | Baud mismatch or floating RX pin | Set 9600 baud (NEO-6M default). If the RX pin is unconnected, the firmware still parses TX only — verify you did not swap TX/RX. |
| `waiting for fix` forever, `sats=0` | Antenna obstructed (indoors) or module unpowered | Go outside with a clear sky view; check `VCC` and the module LED; cold start can take 30–60 s. |
| Fix acquired, then lost when moving | Antenna detuned/bad placement | Keep the patch away from the LiPo, USB cable and the board's metal; use an external active antenna if needed. |
| `sats` 4–5, `hdop > 4` | Marginal reception | Wait for a better constellation; the firmware's quality gate (`MIN_SATELLITES 4`, `MAX_HDOP 8`) intentionally refuses poor fixes. |
| Points only sent when you stop or the speed looks wrong | Send policy | The firmware sends when moved ≥ `GEOSKETCH_MIN_SEND_DISTANCE_M` (8 m) **and** ≥ 5 s elapsed, or at least every 30 s. Lower the distance for dense urban routes. |
| Board reboots when Wi-Fi starts | Supply cannot deliver Wi-Fi current peaks | Use a 500 mA+ USB port/power bank; avoid powering the board from a weak LiPo without a boost converter. |
| Upload fails / port not found | Charge-only USB cable or missing driver | Use a data cable; install the CP210x or CH340 driver. |
| Cannot flash after wiring the GPS | You used a strapping/boot pin | Move the GPS to another GPIO (avoid GPIO2/8/9, 18/19, 20/21). |
| `[GPS] fix acquired` but nothing is POSTed | Journey paused, or no active journey and auto-create is blocked | Check the dashboard's recording state; the API answers `stored:false, journey_paused` by design while paused. |

## 2. Backend

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `ModuleNotFoundError: fastapi` | Virtualenv not activated / dependencies missing | `.venv\Scripts\activate` then `pip install -r requirements.txt`. |
| `Address already in use` on port 8000 | Another uvicorn/backend instance | Stop it, or run with `--port 8001` and update the frontend `.env` + firmware URL. |
| Startup crash mentioning a list/JSON parse for CORS | Malformed `GEOSKETCH_CORS_ORIGINS` | Use the documented comma-separated form (`http://localhost:5173,http://127.0.0.1:5173`) or a JSON list. |
| `401 invalid_device_key` on `/gps/points` | Firmware key ≠ `GEOSKETCH_DEVICE_KEYS` | Copy the exact plaintext key into `config.h`, restart the backend (keys are hashed at startup). |
| `403 device_id_mismatch` | Body `device_id` ≠ authenticated `X-Device-Id` | Send the header only, or make both identical. |
| `422 validation_error` with a field list | Bad coordinates/timestamp/payload | Inspect `error.details`; latitude ∈ [-90, 90], longitude ∈ [-180, 180], timestamps not in the future. |
| `422 source_mismatch` | Demo points sent to a device journey (or vice versa) | This is the provenance guard working. Use a journey with the matching `source`. |
| `413 request_too_large` | Body > `GEOSKETCH_MAX_REQUEST_BYTES` | The firmware sends one point per request; check your own client's payload. |
| `429 rate_limited` | More than `RATE_LIMIT_REQUESTS` per window | Slow the client or raise the limit (only for load testing). |
| `409 invalid_transition` | Illegal state change (e.g. save while recording, resume after stop) | Follow the state machine: Stop before Save; Resume only from Paused. |
| Database "locked" errors | Two servers (or server + long CLI) on the same SQLite file | Run one instance; WAL mode is already enabled for concurrent reads. |
| Data disappeared | The database file was deleted while the server was running | Stop the server, delete `geosketch.db*`, restart (tables and devices are recreated). |
| Postgres connection error after switching `DATABASE_URL` | Driver not installed / wrong URL | `pip install "psycopg[binary]"` and use `postgresql+psycopg://user:pass@host:5432/db`. |

## 3. Frontend

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Blank page, console shows a failed API request | Wrong `VITE_API_BASE_URL` | Point it at the API host/port (`http://127.0.0.1:8000`) and restart `npm run dev` (Vite bakes env vars at startup). |
| `CORS` errors in the browser console | Origin not in `GEOSKETCH_CORS_ORIGINS` | Add the exact origin (`http://127.0.0.1:5173` **and** `http://localhost:5173` are both allowed by default) and restart the backend. |
| Mocked/failed request when opening from a phone | Phone uses the PC's LAN IP, not localhost | Set `VITE_API_BASE_URL=http://<PC-LAN-IP>:8000`, keep the backend on `--host 0.0.0.0`, allow TCP 8000 in the firewall. |
| Map tiles are blank or show "API KEY REQUIRED" | No internet access to the tile server, **or** a tile provider started requiring a key | GeoSketch uses keyless **OpenStreetMap** tiles (`https://tile.openstreetmap.org/{z}/{x}/{y}.png`). CARTO basemaps (`*.basemaps.cartocdn.com`) now return an "API KEY REQUIRED" watermark, so they are no longer used. An offline LAN shows the route but no basemap; coordinates, statistics and artwork still work. |
| `npm run dev` fails: port 5173 in use | Another dev server | Stop it or change `server.port` in `vite.config.ts`. |
| `npm install` fails behind a proxy/registry | Corporate proxy | Configure the npm registry/proxy (`npm config set proxy …`) or install on another network. |
| Route does not appear although points exist | Journey not selected / active journey changed | The dashboard follows the active journey; use the journey table to open the intended one. Also confirm the points are not all rejected (see statistics `filtered`). |
| Status says *Tracker not reporting* | No fix for > 30 s | Expected when the device is off/indoors. The **last known** position and its timestamp remain visible on purpose — GeoSketch never fabricates a live position. |

## 4. Device → backend link

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `[WiFi] connect failed` repeatedly | 5 GHz network or wrong credentials | The ESP32-C3 is **2.4 GHz only**; use a 2.4 GHz SSID or a phone hotspot. Passwords are case-sensitive. |
| `WiFi.status()` connected but POST fails with `connection refused` | Wrong IP/port, backend on `127.0.0.1`, or firewall | Use the PC's LAN IPv4 (`ipconfig`), start uvicorn with `--host 0.0.0.0`, allow inbound TCP 8000 on private networks. |
| `connection timed out` after a while | Router client isolation or the PC changed IP (DHCP) | Disable AP isolation or reserve a static IP for the PC; update `GEOSKETCH_API_BASE_URL`. |
| Intermittent 5xx | Backend restarting (e.g. `--reload` while editing) | The firmware keeps points in its RAM buffer and retries with backoff; `buffered=…` drains afterwards. |
| Points arrive out of order on the map | Client-side clock/timezone issues | The backend stores server time plus the GPS timestamp and sorts by `sequence`; check `gps_timestamp` values in the serial log for a wrong date. |
| Some fixes are missing in the DB but the walk was continuous | Quality gate or plausibility rejection | Look at the statistics `filtered`/`rejected_points` and `rejected_reason` — rejected fixes are stored as evidence, not drawn. |

## 5. Data not appearing in the UI

1. `GET /api/v1/devices/geosketch-01/status` — is `online` true and `last_point` recent?
2. `GET /api/v1/journeys?limit=5` — is there an active journey, and is its `status` `recording`?
3. `GET /api/v1/journeys/{id}` — how many points does the journey contain, and are they
   `is_plausible: true`?
4. `GET /api/v1/journeys/{id}/statistics` — `rejected_points`/`gaps` explain missing geometry.
5. In the UI, confirm the DEMO badge is *not* shown for a hardware journey (if it is, you are
   looking at a demo journey — the API refuses to mix the two).

Common causes in order of frequency: the journey is paused (points answered with
`stored:false`), the device is offline (see step 1), or the browser's API base URL points at a
different backend than the one receiving the fixes.

## 6. Artwork issues

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `422` on artwork generation | Bad colour/size | Colours must be `#rgb`/`#rrggbb`, width/height 400–4000, `export_format` `png` or `svg`. |
| PNG missing / `404` on download | Files were moved or `GEOSKETCH_ARTWORK_DIR` changed | Regenerate the artwork; the DB stores metadata, the file lives in `data/artworks/`. |
| Artwork looks squashed or too small | Extreme route aspect (very long and thin) with padding | Expected: the aspect ratio is preserved deliberately. Reduce padding via a custom canvas size. |
| All five styles look identical | Only customisation differs for the `custom` style | Pick another `style` value; each style has its own defaults (`GET /api/v1/artwork/styles`). |
| Route drawn as one straight line | Very few accepted points (short/failed walk) | Check statistics: a few points cannot define a route shape. Walk longer, or try a sample route. |

## Verifying hardware

If you are unsure whether the problem is the device or the software, split it:

1. **Device only (no Wi-Fi):** blank the SSID in `config.h`. If fixes never appear in the serial
   monitor, the problem is hardware/wiring/reception — not the app.
2. **Software only (no device):** import or replay a sample route in DEMO MODE. If the map,
   statistics and artwork work there, the app is fine and the remaining problem is hardware.
3. **The link:** with both working individually, the only remaining variables are the LAN IP,
   port, firewall and the device key. `curl` the same POST the firmware makes (see the README's
   example) from the PC first; if that succeeds while the device fails, the LAN path/credentials
   are at fault.

Still stuck? Capture (a) the serial log from power-on, (b) the full JSON body of the failing
response and (c) the backend startup log — those three answer almost every question.
