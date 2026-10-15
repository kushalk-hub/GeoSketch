# Hardware connections — ESP32-C3 + NEO-6M

Everything you need to wire, power and verify the tracker. Read the
[pin selection rules](#3-pin-selection-rules) before you move a wire: not every ESP32-C3 board
breaks out the same GPIOs, and the firmware pins are configurable for exactly that reason.

## 1. Bill of materials

| Item | Example | Notes |
| --- | --- | --- |
| ESP32-C3 board | ESP32-C3-DevKitM-1 (or any ESP32-C3 DevKit) | ESP32-S3 is **not** required. |
| GPS module | GY-NEO6MV2 (NEO-6M + patch antenna) | 9600 baud NMEA 0183 output. |
| Jumper wires | 4 × female–female | Keep them short (< 20 cm) on a breadboard. |
| USB cable | USB-C or micro-USB matching the board | Must be a **data** cable, not charge-only. |
| Optional | 3.7 V LiPo + charger/boost module | For walking outdoors. |
| Optional | Active antenna with SMA/u.FL | Better reception than the patch in a pocket. |

## 2. Wiring table

| NEO-6M pin | ESP32-C3 pin | Direction | Required | Explanation |
| --- | --- | --- | --- | --- |
| **TX** | **GPIO 4** | GPS → ESP32-C3 | **Yes** | The NMEA data line: the module transmits `$GPGGA`, `$GPRMC`, `$GPGSV`, … continuously at 9600 baud. This GPIO is the UART1 RX in firmware (`GEOSKETCH_GPS_RX_PIN`). |
| **RX** | **GPIO 5** | ESP32-C3 → GPS | Optional | Only used to send configuration sentences (e.g. `$PMTK220` update rate). The firmware wires it so the option stays open (`GEOSKETCH_GPS_TX_PIN`). If you never intend to configure the module, you can leave it disconnected. |
| **GND** | **GND** | Common | **Yes** | UART is referenced to ground. Without it you get garbled or no data — the single most common wiring mistake. |
| **VCC** | **3V3** or **5V** | Power | **Yes** | GY-NEO6MV2 breakouts include a 3.3 V regulator and accept 3.3–5 V. **Bare NEO-6M modules are 3.3 V only — never 5 V.** When unsure, use 3V3. |

### Visual

```
              ESP32-C3                                GY-NEO6MV2
        ┌──────────────────┐                     ┌────────────────────┐
        │                  │                     │  ┌──────────────┐  │
        │   GPIO 4  ◄──────┼───── NMEA 9600 ─────┼──┤ TX           │  │
        │   GPIO 5  ───────┼─── (optional) ──────┼─►│ RX           │  │
        │   GND     ───────┼───────── GND ───────┼──┤ GND          │  │
        │   3V3/5V  ───────┼──────── VCC ────────┼──┤ VCC          │  │
        │                  │                     │  └──────────────┘  │
        │   GPIO 20/21 ────┼── USB serial monitor│   patch antenna ── │──► sky
        └──────────────────┘                     └────────────────────┘
                 │
                 └── USB ──► PC (Arduino IDE, serial monitor @115200)
```

The firmware starts UART1 explicitly, so the USB serial monitor on UART0 keeps working while
the GPS is being read — you can watch fixes arrive while you walk.

## 3. Pin selection rules

The default wiring uses **GPIO4 (RX)** and **GPIO5 (TX)**. Before copying it, check your board's
pinout diagram (`Tools → Board` in Arduino IDE tells you which variant you selected):

| Avoid | Why |
| --- | --- |
| `GPIO20` / `GPIO21` | They are UART0 (USB serial / boot log). Reusing them breaks the serial monitor. |
| `GPIO18` / `GPIO19` | USB D−/D+ on boards that expose the native USB-Serial-JTAG interface. |
| `GPIO2`, `GPIO8`, `GPIO9` | Strapping pins sampled at boot; pulling them can prevent flashing/booting. |
| `GPIO11`–`GPIO17` on some modules | Connected to the SPI flash on certain ESP32-C3 modules/mini boards — not usable as GPIO. |
| Input-only or reserved pads | `GPIO6`…`GPIO11` behaviour varies by module; verify in the datasheet for your exact board. |

Safe choices on nearly every ESP32-C3 board: **GPIO0–GPIO7** (with the caveats above). If your
board does not expose GPIO4/GPIO5, pick two free pins and update `config.h`:

```cpp
#define GEOSKETCH_GPS_RX_PIN  0   // ESP32-C3 pin wired to the GPS TX
#define GEOSKETCH_GPS_TX_PIN  1   // ESP32-C3 pin wired to the GPS RX (optional)
#define GEOSKETCH_GPS_BAUD    9600
```

The firmware creates its UART with `HardwareSerial gpsSerial(1)` and calls
`gpsSerial.begin(GEOSKETCH_GPS_BAUD, SERIAL_8N1, GEOSKETCH_GPS_RX_PIN, GEOSKETCH_GPS_TX_PIN)`,
so any UART-capable GPIO pair works.

## 4. Voltage and logic levels

- ESP32-C3 I/O is **3.3 V**; the NEO-6M UART output is 3.3 V — no level shifter is needed for
  GPS TX → ESP32-C3 RX.
- Module `VCC`: GY-NEO6MV2 accepts 3.3–5 V (onboard regulator + level shifting). Bare modules
  need a clean **3.3 V** supply. Feeding 5 V into a bare module destroys it.
- Current: ≈ 45 mA (peaks ~60 mA at cold start). The board's 3V3 rail handles this comfortably.
- If the serial monitor shows *garbled* characters, the cause is almost always a ground
  mismatch, a baud mismatch, or a browned-out GPS rail — not corrupted NMEA.

## 5. Power for portable operation

| Option | How | Trade-off |
| --- | --- | --- |
| USB power bank | USB → board's USB port | Simplest; 5 V regulator on the board powers the GPS too. |
| 3.7 V LiPo + boost/charger module | LiPo → boost 5 V → board `5V`/`VIN`; GPS from `3V3` | Genuinely portable. Keep the LiPo away from the patch antenna. |
| 3.7 V LiPo on `3V3` directly | Only on boards that tolerate it | Not recommended: the ESP32-C3 browns out during Wi-Fi TX below ~3.0 V. |

The ESP32-C3's Wi-Fi transmit bursts draw ~250–350 mA peaks; use a supply that can deliver that
or the device will reset mid-upload (`[WiFi] disconnected`/reboot in the log).

## 6. Antenna placement

- The ceramic patch antenna needs a **clear view of the sky**. Inside a bag or a pocket it will
  lose lock; on a shoulder strap, a cap or an armband it works well.
- Keep the antenna away from the ESP32-C3 board's metal, the LiPo cell and the USB cable —
  they detune the patch and reduce the satellite count.
- If your module has a u.FL/SMA connector, an external active antenna mounted high improves the
  fix quality dramatically.
- Allow 30–60 s outdoors for the **cold start** (ephemeris download). A hot start (powered
  recently, same place) is usually a few seconds.

## 7. Verifying the wiring step by step

1. **Power only.** With the board on USB and no sketch responsibilities yet, check that the GPS
   module's LED blinks (~1 Hz = no fix, solid = fix).
2. **Serial without Wi-Fi.** Flash the firmware with an empty
   `GEOSKETCH_WIFI_SSID` — it will keep printing GPS status without trying to connect. You
   should see `[GPS] waiting for fix …` with an increasing satellite count, then
   `[GPS] fix acquired  lat=… lon=… sats=… hdop=…`.
3. **Sanity-check the fix.** Put the coordinates into any online map. They must land within a
   few metres of where you are standing.
4. **Movement check.** Walk ~20 m; latitude/longitude must change accordingly and `speed` must
   be plausible. If the coordinates jump by kilometres, satellites are still being acquired —
   wait for `sats ≥ 6`.
5. **Full link.** Fill in Wi-Fi + the backend LAN IP, flash again, and watch for
   `[POST] … -> 201 stored=true` while the dashboard shows the same fix.

Expected serial output for a healthy setup is shown in
[`../firmware/geosketch_esp32c3/README.md`](../firmware/geosketch_esp32c3/README.md).

## 8. Quick troubleshooting (hardware side)

| Symptom | Check |
| --- | --- |
| Nothing but commas/zeros in NMEA | GPS TX and board RX swapped, or GND missing. |
| Garbled characters | Baud ≠ 9600 (`GEOSKETCH_GPS_BAUD`), or a browned-out supply. |
| Never acquires a fix indoors | Expected — go outside, or use DEMO MODE while developing. |
| Fix acquired but `hdop` stays > 4 | Antenna obstructed/detuned; move it away from metal, or use an active antenna. |
| Board resets when Wi-Fi starts | Weak supply; use a USB port/power bank that delivers ≥ 500 mA. |
| Flashing fails after wiring | You are probably using a strapping pin (GPIO2/8/9) — move the GPS to another GPIO. |

See also [`troubleshooting.md`](troubleshooting.md) for software-side symptoms.
