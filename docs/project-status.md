# GeoSketch — Project Status & Roadmap

**Snapshot date:** 2026-10-15 · **Post-remediation** — the issues raised in the first analysis of
this document have been fixed and re-verified on this machine.

---

## Executive summary

| Area | State |
| --- | --- |
| Firmware (ESP32-C3 + NEO-6M) | ✅ Written (580 lines), ✅ `config.h` created with a real device key |
| Backend (FastAPI) | ✅ Built, ✅ **108/108 tests pass**, ✅ Ruff-clean, ✅ **92.31 % coverage** |
| Frontend (React 19 + Vite) | ✅ Built, ✅ typecheck + build pass, ✅ ESLint-clean, ✅ **65 unit tests** |
| Artwork pipeline (5 styles, PNG/SVG) | ✅ Built, ✅ evidence on disk (20 export files) |
| Documentation | ✅ README + 5 docs + firmware README (+ this status doc) |
| Version control (git) | ✅ Repo initialised in `GeoSketch/`, ✅ 3 commits, ✅ secrets/artifacts ignored |
| Linting | ✅ Ruff (backend) + ESLint (frontend) configured and clean |
| Coverage gates | ✅ pytest-cov ≥ 85 % (backend), vitest v8 (frontend) |
| CI | ✅ GitHub Actions — backend lint+tests, frontend lint+types+tests+build |
| Physical hardware acceptance | ❌ Pending — needs ESP32-C3 + NEO-6M outdoors |

**Bottom line:** the software is feature-complete, freshly verified, **version-controlled, linted,
coverage-gated and CI-driven**. The single remaining risk is the hardware never having been tested
end to end (it cannot be, without the physical device).

---

## 1. What is built

```
Physical movement → GPS satellites → NEO-6M → ESP32-C3 → Wi-Fi → FastAPI → SQLite → React dashboard → Route artwork
```

### 1.1 Firmware — `firmware/geosketch_esp32c3/`

| Item | Detail |
| --- | --- |
| Source | `geosketch_esp32c3.ino` (580 lines, Arduino C++), `config.h`, `config.h.example`, `README.md` |
| Parsing | TinyGPSPlus NMEA parsing on UART1 (RX=GPIO4, TX=GPIO5, 9600 baud) |
| Quality gate | valid fix · fresh fix · satellites ≥ threshold · HDOP ≤ limit — never sends fabricated coordinates |
| Reliability | min-interval/min-distance dedup, RAM ring buffer, exponential-backoff retry, auto Wi-Fi reconnect |
| Transport | HTTP POST with `X-Device-Id` / `X-Device-Key`; serial status line through 8 states |
| Config | ✅ `config.h` created (git-ignored) with device key for `geosketch-01`; **Wi-Fi SSID/password + API base URL remain placeholders to fill before flashing** |

### 1.2 Backend — `backend/` (Python 3.11+, FastAPI, SQLAlchemy, SQLite)

| Item | Detail |
| --- | --- |
| Code | 50 Python files under `app/` |
| Modules | `api/v1` (gps, journeys, devices, artworks, demo, meta) · `services` · `artwork` (geometry, styles, renderers/svg+png, engine) · `models` · `schemas` · `utils` · `core` · `database` |
| Ingestion | device-authenticated (`X-Device-Id`/`X-Device-Key`, constant-time digest compare), validation, dedup (retry-safe), jump rejection, gap detection |
| Journey lifecycle | full state machine — create/start/pause/resume/stop/finish/save with 409 guards on illegal transitions |
| Artwork | 5 styles (Minimal, Neon, Gradient, Poster, Custom) rendered by own SVG + Pillow code, exported to `data/artworks/` |
| Stats | Haversine distance, duration, moving time, avg speed, segment/gap counts |
| Ops | env config, CORS allow-list, rate limiting, request-size limit, consistent JSON error bodies |
| Tooling | ✅ `ruff.toml` (E,W,F,I,B,C4,SIM,UP,RUF) · ✅ `pytest.ini` with coverage gate · ✅ `requirements.txt` pins pytest-cov + ruff |
| Config | ✅ `.env` created (git-ignored) with a generated device key |

### 1.3 Frontend — `frontend/` (React 19, Vite 7, TypeScript 5.7, Tailwind v4, Leaflet)

| Item | Detail |
| --- | --- |
| Code | 24 files in `src/` — 3 pages (Dashboard, Journeys, Studio), components, hooks, typed API client |
| Features | live map (chronological route, direction arrows, break detection, fit-to-route), recording controls, statistics, journey history, artwork studio with instant SVG preview and PNG/SVG download |
| DEMO MODE | import or 60× replay of 4 bundled sample routes — always labelled as simulated |
| Tooling | ✅ `eslint.config.js` (flat, typescript-eslint + react-hooks + react-refresh) · ✅ vitest + jsdom + testing-library · ✅ coverage gate in `vite.config.ts` |
| Scripts | `dev`, `build`, `typecheck`, `preview`, `ui:smoke`, **`lint`, `test`, `test:watch`, `coverage`** |
| Config | ✅ `.env` created (git-ignored); defaults to `VITE_API_BASE_URL=http://127.0.0.1:8000` |

### 1.4 Data, docs, tooling

- **Sample routes:** 4 JSON routes (`city_grid_walk`, `hill_switchbacks`, `marine_drive_loop`, `riverfront_walk`) + regenerator script.
- **Artwork outputs:** 20 files on disk (5 styles × PNG+SVG) — proof the whole pipeline has run.
- **Docs:** `docs/architecture.md`, `hardware_connections.md`, `setup_guide.md`, `testing.md`, `troubleshooting.md`, plus the root README.
- **Docker (optional):** `docker-compose.yml` runs backend + frontend with healthcheck; the device key is now **required** (`${GEOSKETCH_DEVICE_KEYS:?…}` fails fast instead of defaulting to a placeholder).
- **CI:** `.github/workflows/ci.yml` — backend (Python 3.11 + 3.12 matrix: Ruff + pytest with coverage gate) and frontend (Node 22: ESLint + tsc + vitest coverage + build).
- **Database:** auto-created `backend/geosketch.db` (tables/indexes/devices bootstrapped on startup, no manual step).

---

## 2. What is tested

### 2.1 Verified after remediation (2026-10-15)

| Check | Command | Result |
| --- | --- | --- |
| Backend lint | `ruff check app tests` | ✅ All checks passed |
| Backend suite | `.venv\Scripts\python -m pytest -q` | ✅ **108 passed**, ✅ **92.31 % coverage** (gate 85 %) |
| Frontend lint | `npm run lint` | ✅ 0 problems |
| Frontend typecheck | `npm run typecheck` | ✅ 0 errors |
| Frontend unit tests | `npm run coverage` | ✅ **65 passed**; 90.86 / 81.48 / 77.55 / 91.91 % (stmt/branch/func/line) |
| Frontend build | `npm run build` | ✅ 451.88 kB JS (136.48 kB gzip), 43.01 kB CSS |
| Artwork evidence | `data/artworks/` | ✅ 20 PNG/SVG exports present across all 5 styles |
| TODO/FIXME scan | repo-wide grep | ✅ none found |

### 2.2 Test inventory (backend, 108 tests)

| File | Tests | Covers |
| --- | --- | --- |
| `tests/test_geo.py` | 21 | Haversine, bearing, coordinate validation, projection/normalisation |
| `tests/test_segmentation.py` | 10 | Gap/jump detection, redundant-point removal, segment reconstruction |
| `tests/test_ingest.py` | 17 | Payload parsing, invalid coordinates, duplicates, pause handling, device auth |
| `tests/test_journeys.py` | 23 | State machine, 409 lifecycle guards, statistics, persistence |
| `tests/test_artwork.py` | 18 | All 5 styles, customisation, SVG/PNG rendering, empty-route edge cases |
| `tests/test_demo_and_api.py` | 19 | Sample routes, demo/device isolation, health/docs, error contract, rate limiting |

### 2.3 Test inventory (frontend, 65 unit tests)

| File | Tests | Covers |
| --- | --- | --- |
| `src/utils/geo.test.ts` | 17 | Haversine, bearing, drawability, segmentation, distance/bounds, arrow angles |
| `src/utils/format.test.ts` | 16 | Distance/duration/speed/coordinate formatting, relative time, fallbacks |
| `src/services/api.test.ts` | 8 | Typed fetch client, error envelope → `ApiError`, query strings, JSON bodies |
| `src/hooks/useToasts.test.tsx` | 5 | Toast queue cap + timed dismissal |
| `src/hooks/useDeviceStatus.test.tsx` | 2 | Polling load + error path |
| `src/hooks/useJourney.test.tsx` | 3 | Reset, detail+stats load, polling failure |
| `src/hooks/useRecorder.test.tsx` | 9 | Recording state machine + 409 handling + no-journey guard |
| `src/hooks/useDemoReplay.test.tsx` | 4 | 60× replay streaming, auto-stop, refusal, re-entrancy guard |

### 2.4 Not run / not automatable

| Gap | Notes |
| --- | --- |
| UI smoke test (`npm run ui:smoke`) | Exists but needs backend + `npm run dev` + debug Chrome on port 9222 |
| Hardware procedure steps 1–13 | Requires the physical device outdoors — see README "Hardware test procedure" |

---

## 3. Issues found & resolved in this remediation

### 3.1 🔴 → ✅ P0 — Git repository
- The repo root was `C:\Users\kusha` (home directory) with **zero commits** and ~95 untracked
  entries across the home folder.
- **Resolved:** retired the empty home-directory repo, ran `git init -b main` **inside
  `GeoSketch/`**, added `.gitattributes` (`* text=auto eol=lf` + binary rules), and made the
  initial commit `373892d` (115 files; no secrets, no build artifacts, no DB files).

### 3.2 🟠 → ✅ P1 — `.gitignore` missed SQLite WAL/SHM files
- `backend/geosketch.db-wal` and `.db-shm` were **not** ignored.
- **Resolved:** added `*.db-wal` / `*.db-shm` (plus `coverage/`, `frontend/coverage/`) to
  `.gitignore` before the first commit.

### 3.3 🟡 → ✅ P1 — Local configuration files absent
- **Resolved:** created `firmware/geosketch_esp32c3/config.h`, `backend/.env`, `frontend/.env`
  from their `.example` files. Generated a device key
  (`pP3h7GQEYnHEgYhcILwutf6wlAVumPcG` for `geosketch-01`) and used it consistently across
  firmware + backend. Device-key digests refresh on startup (`device_service.py`), so no DB reset
  is needed. Wi-Fi SSID/password in `config.h` remain for the user to fill.

### 3.4 🟡 → ✅ P1 — Linting, coverage, CI absent
- **Resolved:** added Ruff (`backend/ruff.toml`; 450 findings → 0, with 5 hand-fixes for
  `B023`/`RUF012`/`B904`/`SIM102` and modernised typing to `StrEnum`/PEP 585/604/`itertools.pairwise`),
  ESLint (flat config), a backend coverage gate (`--cov-fail-under=85`), a frontend coverage gate,
  65 frontend unit tests, and `.github/workflows/ci.yml`.

### 3.5 🔵 → ✅ P2 — Hygiene gaps
- **Resolved:** CI added; Ruff + ESLint added; `docker-compose.yml` now **requires**
  `GEOSKETCH_DEVICE_KEYS` instead of defaulting to the placeholder; frontend hooks now unit-tested;
  backend coverage measured and enforced.

### 3.6 ❌ P1 — Hardware acceptance (still open)
Everything GPS-related that can be tested in software has been. Steps 1–13 of the README's
outdoor procedure (real fixes, satellite count, Wi-Fi ingest from the bench, outage buffering,
duplicate safety) remain **pending** — they require the physical device. Nothing in the code
suggests they will fail, but they are unproven.

---

## 4. What next — prioritized roadmap

### Phase 1 — Hardware sign-off (the one remaining verification item)
1. Fill `config.h` Wi-Fi SSID/password + LAN API URL, flash the ESP32-C3.
2. Run README hardware steps 1–13 outdoors; capture the serial log and a distance-vs-phone
   comparison as evidence.

### Phase 2 — Product next steps (after hardware sign-off)
3. **Authentication before any internet exposure** — the API is single-tenant (`local` owner)
   with no login; add accounts/sessions before opening port 8000 beyond the LAN.
4. **Data retention** — raw points are stored forever; add a pruning/archival policy.
5. **PostgreSQL migration** — the URL swap is already supported
   (`GEOSKETCH_DATABASE_URL`); validate under load and move rate limiting to Redis
   (noted in `docs/architecture.md`).
6. **HTTPS on the device** — switch the firmware to `WiFiClientSecure` before anything but a
   trusted LAN.
7. **Broaden frontend component tests** — cover the recording control button-disable logic in
   the smoke harness or with component tests.
8. **Artwork studio growth** — gallery page for saved artworks, shareable links, extra styles,
   higher-resolution PNG export.
9. **Multi-segment editing** — let users label break points (rest stops) and include them in
   statistics/artwork captions.

### Suggested order at a glance

| # | Task | Effort | Risk reduced |
| --- | --- | --- | --- |
| 1 | Fill `config.h` Wi-Fi + flash | 15 min | can't run the real device |
| 2 | Hardware procedure 1–13 | 1–2 h (outdoors) | unverified core claim |
| 3 | Auth / retention / Postgres / HTTPS | days–weeks | scope/robustness/security |

---

## Appendix — verification commands

```powershell
# Backend (lint + 108 tests + coverage gate)
cd C:\Users\kusha\GeoSketch\backend
.venv\Scripts\python.exe -m ruff check app tests
.venv\Scripts\python.exe -m pytest -q

# Frontend (lint + typecheck + 65 unit tests + build)
cd C:\Users\kusha\GeoSketch\frontend
npm run lint
npm run typecheck
npm run coverage
npm run build

# Full stack
cd backend;   .venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# new terminal:
cd frontend;  npm run dev
# health: http://127.0.0.1:8000/api/v1/health · docs: http://127.0.0.1:8000/docs · UI: http://127.0.0.1:5173

# UI smoke test (needs a debug Chrome on :9222 — see README "Running the tests")
npm run ui:smoke
```
