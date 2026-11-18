# GeoSketch — ESP32 Connection Troubleshooting & New Features Guide

## Part 1: Why the ESP32 Was Not Connecting (Root Cause Analysis & Fixes)

After inspecting the firmware (`firmware/geosketch_esp32c3/config.h` and `geosketch_esp32c3.ino`) and backend (`backend/app/api/v1/devices.py`), **five distinct issues** were preventing the ESP32-C3 from showing as connected:

### 1. Outdated LAN IP Address in `config.h`
- **Problem**: `firmware/geosketch_esp32c3/config.h` had:
  ```cpp
  #define GEOSKETCH_API_BASE_URL "http://10.244.228.34:8000"
  ```
  However, your computer's current Wi-Fi IPv4 address (`ipconfig`) on the hotspot is **`10.224.116.34`** (mobile hotspots reassign subnets when reconnected). Because of this mismatch, every HTTP request from the ESP32 was timing out trying to reach `10.244.228.34`.
- **Fix Applied**: Updated `GEOSKETCH_API_BASE_URL` in `config.h` to `"http://10.224.116.34:8000"`. *(Note: Whenever you restart your phone hotspot in the future, run `ipconfig` in PowerShell to verify if the IPv4 address changed.)*

### 2. Firmware Never Sent a Heartbeat Before Acquiring 4 GPS Satellites
- **Problem**: In `geosketch_esp32c3.ino`, the main `loop()` called `maybeCaptureFix()`, which immediately exited if `fixIsGood()` returned `false` (for example, when testing indoors or before the NEO-6M locks onto 4+ satellites). As a result, **even when Wi-Fi was connected, the ESP32 sent zero HTTP packets to the backend** until it had an outdoor satellite lock.
- **Fix Applied**: Added `sendHeartbeat()` and `maintainHeartbeat()` to `geosketch_esp32c3.ino`. As soon as the ESP32 connects to Wi-Fi, it immediately posts a heartbeat to `/api/v1/devices/heartbeat` and repeats every 20 seconds while waiting for a GPS fix.

### 3. Backend `/api/v1/devices/heartbeat` Did Not Mark the Device Online
- **Problem**: In `backend/app/api/v1/devices.py`, the `POST /api/v1/devices/heartbeat` endpoint only updated `device.firmware_version` and forgot to update `device.last_seen_at = utcnow()` and `device.connection_status = DeviceStatus.ONLINE.value`. Because the backend checks `(now - device.last_seen_at) <= 30s` to decide if a device is live, heartbeats did not turn the dashboard status green.
- **Fix Applied**: Updated `POST /api/v1/devices/heartbeat` in `backend/app/api/v1/devices.py` to set `device.last_seen_at = utcnow()` and `device.connection_status = DeviceStatus.ONLINE.value`.

### 4. Backend Host Binding (`127.0.0.1` vs `0.0.0.0`)
- **Problem**: When FastAPI/Uvicorn is started with `--host 127.0.0.1`, it only accepts connections from the same PC and blocks external devices on the Wi-Fi LAN (such as the ESP32).
- **Fix Applied**: Always run Uvicorn with `--host 0.0.0.0 --port 8000` so the PC accepts requests on both `127.0.0.1:8000` (browser) and `10.224.116.34:8000` (ESP32).

### 5. SOS Button Pin (`GEOSKETCH_SOS_PIN`) & Immediate Transmission
- **Problem**: `config.h` did not define `GEOSKETCH_SOS_PIN` (defaulting to `-1`, disabled), and `maybeCaptureFix()` waited for the 8 m movement or 30 s timer before sending a queued SOS.
- **Fix Applied**: Configured `#define GEOSKETCH_SOS_PIN 9` in `config.h` (GPIO9 is the built-in `BOOT` button on ESP32-C3 boards, or you can wire an external button between GPIO9 and GND) and updated `geosketch_esp32c3.ino` so an SOS press triggers an immediate upload.

---

### How to Re-Flash Your ESP32-C3 Now
1. Open `D:\Projects\DSM cp\firmware\geosketch_esp32c3\geosketch_esp32c3.ino` in **Arduino IDE**.
2. Make sure your mobile hotspot (`motoedge60fusion_9239`) is on and your laptop is connected to it.
3. Click **Upload** to flash the updated firmware onto the ESP32-C3.
4. Open the **Serial Monitor** at `115200` baud — as soon as Wi-Fi connects, you will see:
   `[http] heartbeat OK (device online)`
   and the website Dashboard, Parent Portal, and Child Companion will immediately show **Online / Connected**!

---

## Part 2: How the New "Family Safe-Trip" Features Work

GeoSketch now includes the **Family Safe-Trip** suite alongside the GPS Route Artwork Studio. Below is an end-to-end explanation of every new feature and how the frontend, backend, and hardware work together.

---

### 1. Dashboard Cards & Direct Navigation (`DashboardPage.tsx`, `AppShell.tsx`, `App.tsx`)
- **What it does**:
  - On the main **Dashboard**, right below the Journey Recording Controls, there is a **Family Safe-Trip** section containing two cards:
    1. **Parent Portal** (`/parent` or `?tab=parent`)
    2. **Child Companion** (`/child` or `?tab=child`)
  - Both pages are also accessible anytime from the top navigation bar (`Parent` and `Child` tabs).
- **How it works**:
  - Clicking either card opens the feature page **directly without blocking behind a login screen**.
  - The Parent Portal automatically provisions or reuses a parent session token in the background (`useParentSession`), while offering an optional **"Account & Telegram"** button in the header if you want to customize credentials or link a Telegram Bot chat ID.

---

### 2. Parent Portal (`ParentPage.tsx`)
The Parent Portal (`http://127.0.0.1:5173/parent`) is the central command center for monitoring the tracker and managing safety boundaries. It consists of four modules:

#### A. Live Tracker Device Status Card (`useDeviceStatus`)
- Polls `GET /api/v1/devices/geosketch-01/status` every 5 seconds.
- Displays:
  - **Connection State**: `Online` (green) if the ESP32 sent a GPS point or heartbeat within the last 30 seconds (`GEOSKETCH_DEVICE_OFFLINE_AFTER_SECONDS=30`), or `Offline` (amber) otherwise.
  - **GPS Fix State**: `Fix acquired` (with satellite count and speed) vs `No fix`.
  - **Coordinates & Last Update**: Latest latitude, longitude, and relative timestamp (e.g., `5s ago`).

#### B. Safe Zones / Geofences Manager (`useGeofences` + `safe_trip_service.py`)
- Allows parents to create circular safe zones (e.g., **Home**, **School**, **Grandma's House**) with:
  - **Name**
  - **Center Latitude & Longitude** (can be typed or clicked/previewed on the interactive Leaflet map)
  - **Radius in meters** (slider from `50 m` to `2000 m`)
  - **Active / Paused toggle** and **Delete** action
- **How Backend Geofence Evaluation & Hysteresis Work (`backend/app/services/safe_trip_service.py`)**:
  - Every time the ESP32 uploads a plausible GPS fix (`POST /api/v1/gps/points`) with at least 4 satellites and HDOP ≤ 5.0, the backend calculates the **Haversine distance** $d$ (in meters) between the tracker and each active Safe Zone center.
  - To prevent noisy GPS drift at the edge of a circle from spamming false alerts, the backend uses **20-meter + 2-fix hysteresis**:
    - **Entering a zone**: If the child was outside, they must record **2 consecutive GPS fixes** inside the radius ($d \le R$) before the state flips to `INSIDE` and triggers a `safe_zone_enter` alert.
    - **Exiting a zone**: If the child was inside, they must record **2 consecutive GPS fixes** at least **20 meters outside** the radius ($d > R + 20\text{ m}$) before the state flips to `OUTSIDE` and triggers a `safe_zone_exit` alert.

#### C. Read-Only Share Links Manager (`useShareLinks` + `LivePage.tsx`)
- Parents can generate temporary, revocable **Live Share Links** (e.g., `Label: "Grandma"`, `TTL: 24 hours`).
- **Security model**:
  - When `POST /api/v1/parent/share-links` is called, the backend generates a random cryptographic token, returns the full `/live/<token>` URL **once**, and stores only its **SHA-256 hash** (`token_hash`) in SQLite.
  - Anyone with the link can open `/live/<token>` (`LivePage.tsx`) without logging in to see a read-only map of the child's live location, recent trail, and safe zones.
  - Clicking **Revoke** (`DELETE /api/v1/parent/share-links/{id}`) immediately invalidates the link, or it expires automatically when `expires_at` passes.

#### D. Alerts Feed & Telegram Push Notifications (`useAlerts` + `notifier.py`)
- Displays a chronological feed of all safety events:
  - `sos` — Triggered when the physical SOS button on the ESP32 is held down.
  - `safe_zone_enter` — Triggered when entering a Safe Zone.
  - `safe_zone_exit` — Triggered when leaving a Safe Zone.
  - `device_offline` — Triggered if the optional offline watcher detects the tracker stopped reporting during an active journey.
- **Acknowledge button**: Parents can click **Acknowledge** (`POST /api/v1/parent/alerts/{id}/ack`) to mark an alert as handled (`acknowledged_at` timestamp).
- **Telegram Bot integration**: If `GEOSKETCH_TELEGRAM_BOT_TOKEN` is set in `backend/.env` and the parent enters their `telegram_chat_id` in the Parent Portal settings, the backend automatically sends an instant Telegram message whenever an alert is created.

---

### 3. Child Companion View (`ChildPage.tsx`)
The Child Companion (`http://127.0.0.1:5173/child`) is a mobile-friendly status and safety screen designed around what the backend genuinely supports for the child's tracker (`geosketch-01`):

1. **Dynamic Safety Status Banner**:
   - **Green (`Safe Zone: Inside <Zone Name>`)**: Shown when the tracker's coordinates are within an active Safe Zone radius.
   - **Blue (`On the Move · Outside Safe Zones`)**: Shown when the tracker is live and moving between safe zones.
   - **Neutral (`Tracker Waiting for Signal`)**: Shown when the ESP32 is offline or waiting for a satellite fix.
2. **Live Companion Map & Telemetry Tiles**:
   - Displays current tracker status (`Live` / `Waiting`), current **Safe Zone name** (or distance to the nearest zone), **Speed (km/h)**, and **GPS Coordinates** (`lat, lon` + satellite count).
   - Interactive Leaflet map showing the child's marker and all active green Safe Zone circles.
3. **Safe Zone Proximity List**:
   - Computes real-time Haversine distance from the child's current location to every configured Safe Zone, showing an `Inside` badge or the exact distance away (e.g., `340 m away`).
4. **Hardware Emergency SOS Guide & Active Alert Indicator**:
   - Shows clear step-by-step instructions for triggering an emergency alert on the physical ESP32-C3 tracker (**press and hold the SOS button for 2–3 seconds**).
   - If there is an unacknowledged SOS alert in the backend, displays a prominent red alert banner so the child knows their parent has been notified.
5. **Backend Scope & Privacy Disclosure**:
   - Explicitly documents that the child is represented by the physical ESP32-C3 hardware node (`geosketch-01`) — there is no separate child login password, no two-way web chat, and SOS alerts are authenticated by the hardware device key (`X-Device-Key`).
