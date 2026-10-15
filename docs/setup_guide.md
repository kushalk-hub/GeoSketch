# Setup guide (Windows)

From a fresh clone to your first recorded journey with artwork. Every step ends with a **check**
so a failure is caught where it happens instead of three steps later. Commands are PowerShell
unless noted; Git Bash equivalents are given where they differ.

Total time: ~30 minutes (plus the first outdoor walk).

| Step | What you get |
| --- | --- |
| [0. Prerequisites](#0-prerequisites) | Python, Node.js, Arduino IDE |
| [1. Backend](#1-backend-fastapi--sqlite) | API on `http://127.0.0.1:8000` |
| [2. Frontend](#2-frontend-react--vite) | Dashboard on `http://127.0.0.1:5173` |
| [3. DEMO MODE](#3-demo-mode-no-hardware-needed) | A full journey without hardware |
| [4. Firmware](#4-firmware-esp32-c3) | Device reading real GPS fixes |
| [5. Live walk](#5-first-live-walk) | Hardware journey + artwork |
| [6. Optional](#6-optional-docker-and-production-build) | Docker, production build |

---

## 0. Prerequisites

| Tool | Version | Install / check |
| --- | --- | --- |
| Python | 3.11+ | `python --version` (from python.org; tick *Add python.exe to PATH*) |
| Node.js | 20+ | `node --version` and `npm --version` (from nodejs.org LTS) |
| Arduino IDE | 2.x | arduino.cc; plus the CP210x **or** CH340 USB-serial driver for your board |
| Git | any | `git --version` |
| Browser | Chrome/Edge/Firefox | Leaflet needs nothing extra |

Optional but recommended: a phone with GPS to sanity-check distances, and a Wi-Fi network you
control (the ESP32-C3 only supports **2.4 GHz**).

---

## 1. Backend (FastAPI + SQLite)

```powershell
git clone <your-repo-url> GeoSketch
cd GeoSketch\backend

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env
```

Generate a real device key and put it in `.env`:

```powershell
python -c "import secrets;print(secrets.token_urlsafe(24))"
notepad .env
```

```ini
GEOSKETCH_DEVICE_KEYS=geosketch-01:<paste-the-generated-key>
GEOSKETCH_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Start the API (leave this window open — `--host 0.0.0.0` is what makes it reachable from the
ESP32-C3 on your LAN):

```powershell
.venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Check**

```powershell
curl http://127.0.0.1:8000/api/v1/health
```

```json
{
  "status": "ok",
  "service": "GeoSketch API",
  "time": "2026-10-15T15:49:29.288153Z",
  "database": "sqlite",
  "devices": 1,
  "journeys": 0,
  "device_offline_after_seconds": 30,
  "artwork_styles": ["minimal", "neon", "gradient", "poster", "custom"]
}
```

The `devices: 1` count is your bootstrapped `geosketch-01` device — proof the key from `.env`
was loaded.

Also open <http://127.0.0.1:8000/docs> — the OpenAPI page lists every endpoint.

Firewall: the first launch asks to allow Python on private networks → **Allow**, otherwise the
ESP32-C3 cannot reach the API. Allow inbound TCP 8000 for private networks if you answered
differently. Find your LAN IP with `ipconfig` (IPv4 Address of the Wi-Fi adapter) — you will
need it in step 4.

**Git Bash equivalent**

```bash
python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt && cp .env.example .env
.venv/Scripts/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 2. Frontend (React + Vite)

In a **second** terminal:

```powershell
cd GeoSketch\frontend
npm install
copy .env.example .env
npm run dev
```

`frontend\.env`:

```ini
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_DEVICE_ID=geosketch-01
```

**Check**: open <http://127.0.0.1:5173>. You should see the dark dashboard with the Leaflet map,
the *Tracker not reporting* status card (correct — no device has sent anything yet) and the
**DEMO MODE** card listing four sample routes.

---

## 3. DEMO MODE (no hardware needed)

Do this before touching the ESP32-C3: it proves the whole software path.

1. Open the dashboard.
2. In **DEMO MODE**, select *City Grid Walk (with rest stop)*.
3. Press **Import instantly** → a finished demo journey appears in the map/statistics.
4. Switch to the **Studio** tab → pick each of the five styles → **Generate** →
   **Download PNG** and **Download SVG**.
5. Optionally go back and press **Replay on the map** to watch points stream in at 60×.

**Check**

- The map shows the route with start/end markers and direction arrows; the header shows
  **· X km · N points**; the statistics card shows distance, duration and average speed.
- The **DEMO DATA** badge is visible everywhere the journey is shown (this is enforced by the
  API: demo points cannot enter a hardware journey).
- `data\artworks\` contains `journey<id>-<style>-<hash>.png` and `.svg` files that open in a
  browser/image viewer.

---

## 4. Firmware (ESP32-C3)

### 4.1 Arduino IDE

1. Install Arduino IDE 2.x and the USB-serial driver for your board.
2. `File → Preferences → Additional boards manager URLs`:

   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```

3. `Tools → Board → Boards Manager…` → install **esp32 by Espressif Systems** (3.x).
4. `Tools → Manage Libraries…` → install **TinyGPSPlus** (Mikal Hart).

### 4.2 Configure and flash

```powershell
cd GeoSketch\firmware\geosketch_esp32c3
copy config.h.example config.h
notepad config.h
```

Fill in Wi-Fi, the **LAN IP** of the backend PC, and the same device key you put in
`backend\.env`:

```cpp
#define GEOSKETCH_WIFI_SSID     "MyHomeWiFi"        // 2.4 GHz only
#define GEOSKETCH_WIFI_PASSWORD "supersecret"
#define GEOSKETCH_API_BASE_URL  "http://192.168.1.50:8000"
#define GEOSKETCH_DEVICE_ID     "geosketch-01"
#define GEOSKETCH_DEVICE_KEY    "<same key as backend/.env>"
#define GEOSKETCH_GPS_RX_PIN    4   // ESP32-C3 pin wired to the GPS TX
#define GEOSKETCH_GPS_TX_PIN    5   // ESP32-C3 pin wired to the GPS RX (optional)
```

Wire the module (details in [`hardware_connections.md`](hardware_connections.md)):
**NEO-6M TX → GPIO4**, **RX → GPIO5** (optional), **GND → GND**, **VCC → 3V3**.

Then: open `geosketch_esp32c3.ino`, select `Tools → Board → esp32 → ESP32C3 Dev Module` and the
right `Port`, and press **Upload**. Open `Tools → Serial Monitor` at **115200 baud**.

**Check (indoors, no fix expected)**

```
[GeoSketch] ESP32-C3 + NEO-6M starting
[GeoSketch] GPS UART1 on RX=4 TX=5 @9600 baud
[GPS] waiting for fix ........................ sats=3 hdop=12.4
[WiFi] connected  ip=192.168.1.77  rssi=-58 dBm
[STATUS] state=Waiting-for-fix sats=3 sent=0 buffered=0 rejects=0
```

`waiting for fix` indoors is normal and correct behaviour: the firmware does **not** invent
coordinates. Take the device outside (or to a large window) for the real test.

---

## 5. First live walk

1. Take the board outside, keep the patch antenna facing the sky.
2. Wait for `[GPS] fix acquired lat=… lon=… sats=8 hdop=1.20`.
3. In the dashboard press **Start Recording** (a journey is created and started).
4. Walk ~200–400 m. Watch the route grow on the map and the point stream update.
5. Press **Stop**, then **Save**. Rename the journey if you like.
6. Open the **Studio** tab, pick a style, generate and download PNG + SVG.

**Check**

| What | Expected |
| --- | --- |
| Map | Only the walked track, with a start marker, an end marker and direction arrows. No straight line across any break. |
| Statistics | Distance within roughly 10–15 % of a phone fitness app; duration ≈ your walk; average speed plausible for walking. |
| Point stream | Newest fix first, with satellites and relative time. |
| Artwork | All five styles render; the PNG opens in any viewer; the SVG scales without blur. |
| Device status | *Connected*, last update a few seconds old. |

Stop the device (unplug) and the dashboard switches to *Tracker not reporting* while keeping the
**last known** position and its timestamp — that distinction is intentional.

---

## 6. Optional: Docker and production build

Docker (containers only; USB flashing stays on the host):

```powershell
cd GeoSketch
$env:GEOSKETCH_DEVICE_KEYS = "geosketch-01:<your-key>"
docker compose up --build
# API :8000/docs · dashboard :5173
```

Production frontend:

```powershell
cd frontend
npm run build      # tsc --noEmit && vite build
npm run preview    # serves frontend/dist on :5173
```

Serve `frontend/dist` behind any static host and point `VITE_API_BASE_URL` at the API host.
Keep the API bound to `0.0.0.0` (or a reverse proxy) if the ESP32-C3 must reach it.

---

## Environment variables at a glance

Backend (`backend/.env`, prefix `GEOSKETCH_`):

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./geosketch.db` | Swap for PostgreSQL later. |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated allowed browser origins. |
| `DEVICE_KEYS` | `geosketch-01:change-me-device-key` | `device_id:api_key` pairs; hashed on startup. |
| `DEFAULT_OWNER` | `local` | Owner scope for journeys (single-tenant). |
| `DEVICE_OFFLINE_AFTER_SECONDS` | `30` | When a device is reported offline. |
| `MAX_REQUEST_BYTES` | `65536` | Request-body limit. |
| `RATE_LIMIT_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS` | `240` / `60` | Per-client rate limit. |
| `MIN_POINT_DISTANCE_M` | `1.0` | Redundant-point threshold for artwork. |
| `MAX_PLAUSIBLE_SPEED_KMH` | `200.0` | Jump rejection threshold. |
| `MAX_GAP_SECONDS` | `180` | Gap → new route segment. |
| `REANCHOR_AFTER_REJECTS` | `3` | Consecutive rejections before a fix is trusted again (never stalls a recording). |
| `ARTWORK_DIR` / `SAMPLE_ROUTES_DIR` | `../data/artworks` / `../data/sample_routes` | Storage paths. |

Frontend (`frontend/.env`, prefix `VITE_`): `API_BASE_URL`, `DEVICE_ID`.

Firmware (`firmware/geosketch_esp32c3/config.h`): Wi-Fi SSID/password, `API_BASE_URL`,
`API_PATH`, `DEVICE_ID`, `DEVICE_KEY`, GPS pins/baud, send policy, quality gate, buffer/retry
sizes — every knob is commented in the file.

**Never commit** `backend/.env`, `frontend/.env` or `firmware/geosketch_esp32c3/config.h`; the
`.gitignore` already excludes them, and only `*.example` files are tracked.
