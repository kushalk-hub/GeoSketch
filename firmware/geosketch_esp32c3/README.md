# GeoSketch firmware — ESP32-C3 + NEO-6M

Turns a NEO-6M GPS module into a Wi-Fi GPS tracker that streams validated fixes to
the GeoSketch backend. No ESP32-S3, no cloud service, no fake coordinates.

```
NEO-6M --UART1(9600 8N1)--> ESP32-C3 --Wi-Fi/HTTP POST--> FastAPI backend
```

## 1. Files

| File | Purpose |
| ---- | ------- |
| `geosketch_esp32c3.ino` | The firmware (Arduino C++, TinyGPSPlus + ArduinoJson) |
| `config.h.example` | Template for credentials and pin mapping |
| `config.h` | **You create this** — git-ignored, holds real credentials |

## 2. Prerequisites

* **Arduino IDE 2.x** (or `arduino-cli`).
* **ESP32 board support**: Boards Manager → search `esp32` by Espressif →
  install **3.x**. This provides `esp32:esp32:esp32c3`.
* Two libraries, via Library Manager (Sketch → Include Library → Manage Libraries):
  * **TinyGPSPlus** by Mikal Hart (NMEA parsing)
  * **ArduinoJson** by Benoit Blanchon, **version 7.x** (payload building)

  The ESP32 core already ships `WiFi.h`, `HTTPClient.h` and `Preferences.h`.

## 3. Configure

```bash
cd firmware/geosketch_esp32c3
cp config.h.example config.h     # Windows: copy config.h.example config.h
```

Edit `config.h`:

| Setting | Notes |
| ------- | ----- |
| `GEOSKETCH_WIFI_SSID` / `_PASSWORD` | **2.4 GHz only** — the ESP32-C3 cannot see 5 GHz |
| `GEOSKETCH_API_BASE_URL` | LAN IP of the backend PC, e.g. `http://192.168.1.50:8000`. `localhost` does **not** work from the board |
| `GEOSKETCH_DEVICE_ID` | Must match an entry in the backend `GEOSKETCH_DEVICE_KEYS` |
| `GEOSKETCH_DEVICE_KEY` | The plaintext key for that device |
| `GEOSKETCH_GPS_RX_PIN` / `_TX_PIN` | Defaults 4 / 5 — change if your board does not expose them |

Find the PC's LAN IP with `ipconfig` (Windows) and make sure the backend is
started with `--host 0.0.0.0` so the board can reach it (`uvicorn app.main:app
--host 0.0.0.0 --port 8000`).

## 4. Board settings (Arduino IDE)

| Setting | Value |
| ------- | ----- |
| Board | **ESP32C3 Dev Module** |
| USB CDC On Boot | **Enabled** (so `Serial` is the USB monitor) |
| CPU Frequency | 160 MHz |
| Flash Size | 4 MB (match your board) |
| Upload Speed | 921600 (drop to 115200 if uploads fail) |
| Port | the COM port that appears when the board is plugged in |

If no COM port appears, hold **BOOT**, tap **RESET**, release **BOOT** to enter
the ROM bootloader, then upload.

## 5. Flash

1. Open `geosketch_esp32c3.ino` in the Arduino IDE (the folder name must match
   the sketch name — it does).
2. Verify the board/port settings above, then **Upload**.
3. Open **Serial Monitor** at **115200 baud** with *Newline* line ending.

Expected output:

```
===============================================================
 GeoSketch - ESP32-C3 + NEO-6M GPS route art tracker
 firmware 1.0.0 | device_id geosketch-01
===============================================================
[init] boot #3 (client ids look like 3-1)
[init] GPS UART1 on RX=GPIO4 TX=GPIO5 @ 9600 baud
[state] INITIALIZING -> WIFI_CONNECTING
[wifi] connecting to "MyWifi" ...
[wifi] connected - IP 192.168.1.23  RSSI -58 dBm
[gps] waiting for a usable fix: no valid position (sats 0, hdop 99.9)
[state] WAITING_FOR_GPS_FIX -> GPS_FIX_ACQUIRED
[gps] fix captured: 18.5204000, 73.8567000  alt 560.0  spd 4.5  sats 8  time 2026-10-15T10:30:00Z  queue 1  (3-1)
[http] 201 stored yes (seq 3-1)
[state] GPS_FIX_ACQUIRED -> CONNECTED
```

The first fix outdoors typically takes **30–60 s** (cold start). Indoors you may
never get one — use **DEMO MODE** in the web app instead of faking data.

## 6. Serial commands

Type a letter + Enter in the Serial Monitor:

| Key | Action |
| --- | ------ |
| `s` | Full status report (state, Wi-Fi, GPS, queue, counters) |
| `g` | Raw GPS detail (position, satellites, HDOP, date/time) |
| `q` | List the buffered points |
| `f` | Force an immediate upload attempt |
| `c` | Clear the send queue |
| `r` | Force a Wi-Fi reconnect |

## 7. What the firmware guarantees

| Requirement | Implementation |
| ----------- | -------------- |
| Read NMEA from the NEO-6M | `Serial1` @ 9600 8N1, `gps.encode()` for every byte |
| Validate the fix | valid position, `age < 2500 ms`, satellites ≥ 4, HDOP ≤ 8, rejects the 0,0 no-fix sentinel |
| Never fabricate data | no fix ⇒ nothing is transmitted; unavailable fields are sent as `null` |
| Reject invalid readings | out-of-range/empty payloads are refused by the backend with 422 and dropped locally |
| Avoid duplicates / spam | transmit when moved ≥ 8 m **and** ≥ 5 s elapsed, plus a 30 s liveness heartbeat |
| Retry failures | exponential backoff 2 s → 60 s for network errors, 429 and 5xx |
| Buffer unsent points | 50-slot RAM ring buffer, oldest points dropped first when full |
| Duplicate-proof retries | `client_point_id` = `bootId-sequence` (NVS boot counter) → idempotent on the backend |
| Survive network drops | auto reconnect with 2 s → 30 s backoff; the queue keeps filling |
| Diagnostics | state machine transitions, per-point logs, 10 s heartbeat, `s` report |

Because the buffer lives in RAM, a power cut loses the unsent points. That is a
deliberate trade-off (the ESP32-C3 has no PSRAM); the backend de-duplicates
anything that is re-sent.

## 8. Hardware test procedure (outdoors)

1. Start the backend and note the device timestamp:
   `curl http://127.0.0.1:8000/api/v1/devices/geosketch-01/status`
2. Power the board with the NEO-6M connected and take it outdoors with a clear
   sky view. Wait for `GPS_FIX_ACQUIRED` (30–60 s cold, a few seconds warm).
3. Walk 100–200 m. You should see `[gps] fix captured` followed by
   `[http] 201 stored yes` roughly every 5 s.
4. Re-check the status endpoint: `connected: true`, `last_seen_at` recent,
   `latest_point` showing real coordinates.
5. In the dashboard, press **Start recording** and watch the route draw itself.
6. Walk into a building or unplug the router for 30 s: the state becomes
   `TRANSMISSION_FAILED`/`RECONNECTING`, the queue grows, and buffered points are
   uploaded in order once the link returns.
7. Stop and save the journey, then generate an artwork (PNG + SVG).

Record the observed latitude/longitude and compare it with a phone map — see
`docs/troubleshooting.md` if the position looks wrong.
