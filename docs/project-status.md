# GeoSketch — Project Status & Roadmap

**Snapshot date:** 2026-10-15 · **Verified on this machine** (backend tests + frontend build rerun for this document).

---

## Executive summary

| Area | State |
| --- | --- |
| Firmware (ESP32-C3 + NEO-6M) | ✅ Written (580 lines), ⚠️ `config.h` absent — cannot be compiled as-is |
| Backend (FastAPI) | ✅ Built, ✅ **108/108 tests pass** (9.4 s) |
| Frontend (React 19 + Vite) | ✅ Built, ✅ typecheck + production build pass |
| Artwork pipeline (5 styles, PNG/SVG) | ✅ Built, ✅ evidence on disk (20 export files) |
| Documentation | ✅ README (804 lines) + 5 docs + firmware README |
| Version control (git) | ❌ **No commits exist — the project has never been committed** |
| Physical hardware acceptance | ❌ Pending — needs ESP32-C3 + NEO-6M outdoors |
| CI / linting | ❌ None configured |

**Bottom line:** the software is feature-complete and freshly verified; the two real risks are (1) zero version-control history and (2) the hardware never having been tested end to end.

---

## 1. What is built

```
Physical movement → GPS satellites → NEO-6M → ESP32-C3 → Wi-Fi → FastAPI → SQLite → React dashboard → Route artwork
```

### 1.1 Firmware — `firmware/geosketch_esp32c3/`

| Item | Detail |
| --- | --- |
| Source | `geosketch_esp32c3.ino` (580 lines, Arduino C++), `config.h.example`, `README.md` |
| Parsing | TinyGPSPlus NMEA parsing on UART1 (RX=GPIO4, TX=GPIO5, 9600 baud) |
| Quality gate | valid fix · fresh fix · satellites ≥ threshold · HDOP ≤ limit — never sends fabricated coordinates |
| Reliability | min-interval/min-distance dedup, RAM ring buffer, exponential-backoff retry, auto Wi-Fi reconnect |
| Transport | HTTP POST with `X-Device-Id` / `X-Device-Key`; serial status line through 8 states |
| Status | ⚠️ `config.h` **does not exist** on this machine (git-ignored by design — must be created per README §3) |

### 1.2 Backend — `backend/` (Python 3.11, FastAPI, SQLAlchemy, SQLite)

| Item | Detail |
| --- | --- |
| Code | 50 Python files under `app/` |
| Modules | `api/v1` (gps, journeys, devices, artworks, demo, meta) · `services` · `artwork` (geometry, styles, renderers/svg+png, engine) · `models` · `schemas` · `utils` · `core` · `database` |
| Ingestion | device-authenticated (`X-Device-Id`/`X-Device-Key`, constant-time digest compare), validation, dedup (retry-safe), jump rejection, gap detection |
| Journey lifecycle | full state machine — create/start/pause/resume/stop/finish/save with 409 guards on illegal transitions |
| Artwork | 5 styles (Minimal, Neon, Gradient, Poster, Custom) rendered by own SVG + Pillow code, exported to `data/artworks/` |
| Stats | Haversine distance, duration, moving time, avg speed, segment/gap counts |
| Ops | env config, CORS allow-list, rate limiting, request-size limit, consistent JSON error bodies |
| Status | ✅ `.env` absent locally (runs on defaults from `.env.example` values baked into config — see §3.3) |

### 1.3 Frontend — `frontend/` (React 19, Vite 7, TypeScript 5.7, Tailwind v4, Leaflet)

| Item | Detail |
| --- | --- |
| Code | 24 files in `src/` — 3 pages (Dashboard, Journeys, Studio), components, hooks, typed API client |
| Features | live map (chronological route, direction arrows, break detection, fit-to-route), recording controls, statistics, journey history, artwork studio with instant SVG preview and PNG/SVG download |
| DEMO MODE | import or 60× replay of 4 bundled sample routes — always labelled as simulated |
| Scripts | `dev`, `build` (`tsc --noEmit && vite build`), `typecheck`, `preview`, `ui:smoke` |
| Status | ✅ `.env` absent locally; defaults to `VITE_API_BASE_URL=http://127.0.0.1:8000` |

### 1.4 Data, docs, tooling

- **Sample routes:** 4 JSON routes (`city_grid_walk`, `hill_switchbacks`, `marine_drive_loop`, `riverfront_walk`) + regenerator script.
- **Artwork outputs:** 20 files already on disk (5 styles × PNG+SVG across journeys 1/3/6/9/17/23/26) — proof the whole pipeline has run.
- **Docs:** `docs/architecture.md`, `hardware_connections.md`, `setup_guide.md`, `testing.md`, `troubleshooting.md`, plus the root README.
- **Docker (optional):** `docker-compose.yml` runs backend + frontend with healthcheck; bind-mounts DB, samples and artworks.
- **Database:** auto-created `backend/geosketch.db` (tables/indexes/devices bootstrapped on startup, no manual step).

---

## 2. What is tested

### 2.1 Verified just now (2026-10-15)

| Check | Command | Result |
| --- | --- | --- |
| Backend suite | `.venv\Scripts\python -m pytest -q` | ✅ **108 passed** in 9.38 s (1 harmless Starlette deprecation warning) |
| Frontend typecheck | `npm run typecheck` | ✅ 0 errors |
| Frontend build | `npm run build` | ✅ built in 24.4 s — `dist/` = 451.88 kB JS (136.48 kB gzip), 43.01 kB CSS |
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

### 2.3 Not run / not existing

| Gap | Notes |
| --- | --- |
| UI smoke test (`npm run ui:smoke`) | Exists but needs backend + `npm run dev` + debug Chrome on port 9222; not rerun today |
| Hardware procedure steps 1–10 | Requires the physical device outdoors — see README "Hardware test procedure" |
| Frontend unit tests | **None** — only the scripted browser smoke test |
| Code coverage | Not measured (no `pytest-cov`) |
| Linting | No ruff / eslint / prettier config anywhere |
| CI | No `.github/` — nothing runs the tests automatically |

---

## 3. Issues found during this analysis

### 3.1 🔴 P0 — The git repository is broken for this project

- The repo root is **`C:\Users\kusha` (your entire home directory)**, not `GeoSketch/`.
- It has **zero commits** (`fatal: your current branch 'main' does not have any commits yet`).
- `git status` reports ~95 untracked entries across the home folder (`.claude/`, `.docker/`, `.cursor/`, …) and prints permission warnings for `AppData` junctions.
- **Consequence:** GeoSketch has no history, no backup, and the next `git add .` from the home directory could stage your whole home folder.

**Fix (recommended):** retire the home-directory repo and initialize git *inside* GeoSketch:

```powershell
Remove-Item C:\Users\kusha\.git -Recurse -Force     # only if nothing else relies on it
cd C:\Users\kusha\GeoSketch
git init
git add .
git commit -m "GeoSketch: initial commit"
```

If you *do* need the home-level repo, keep it but commit **only** `git add GeoSketch` — and still fix 3.2 first.

### 3.2 🟠 P1 — `.gitignore` misses SQLite WAL/SHM files

Verified with `git check-ignore`:

| File | Ignored? |
| --- | --- |
| `backend/geosketch.db` | ✅ yes (`*.db`) |
| `backend/geosketch.db-wal` | ❌ **NO** |
| `backend/geosketch.db-shm` | ❌ **NO** |

Both files exist right now, so a first commit would include live database fragments. Add to `GeoSketch/.gitignore`:

```gitignore
*.db-wal
*.db-shm
```

(Also worth adding `*.db-journal` already present — keep it.)

### 3.3 🟡 P1 — Local configuration files are absent

| File | Status | Why it matters |
| --- | --- | --- |
| `firmware/geosketch_esp32c3/config.h` | ❌ missing | Firmware cannot compile; copy from `config.h.example` |
| `backend/.env` | ❌ missing | Backend falls back to config defaults; placeholder device key `CHANGE-ME-device-key-please` |
| `frontend/.env` | ❌ missing | Falls back to `http://127.0.0.1:8000` (fine for local dev) |

These are git-ignored by design — create them from the `.example` files before any real run:

```powershell
cd backend;   copy .env.example .env      # then set a real GEOSKETCH_DEVICE_KEYS value
cd ..\frontend; copy .env.example .env
cd ..\firmware\geosketch_esp32c3; copy config.h.example config.h   # then fill Wi-Fi + API URL + key
```

### 3.4 🟡 P1 — Hardware acceptance is unverified

Everything GPS-related that can be tested in software has been; steps 1–10 of the README's outdoor procedure (real fixes, satellite count, Wi-Fi ingest from the bench, outage buffering, duplicate safety) remain **pending**. Nothing in the code suggests they will fail, but they are unproven.

### 3.5 🔵 P2 — Hygiene gaps

- No CI (`.github/workflows/`) — regressions would go unnoticed.
- No linters (ruff for Python, eslint/prettier for TS).
- `docker-compose.yml` defaults to the `CHANGE-ME-device-key-please` placeholder if the env var is unset.
- Frontend has zero unit tests; critical hooks (`useRecorder`, `useDemoReplay`) are untested outside the smoke run.
- No coverage measurement on the backend.

---

## 4. What next — prioritized roadmap

### Phase 1 — Secure the project (do now, ~30 min)

1. **Fix git** (§3.1): move the repo into `GeoSketch/`, make the first commit.
2. **Fix `.gitignore`** (§3.2): add `*.db-wal` / `*.db-shm` *before* committing.
3. **Create `.env` + `config.h`** from examples with a real device key
   (`python -c "import secrets;print(secrets.token_urlsafe(24))"`).
4. **Smoke the stack once:** backend on `:8000` → `npm run dev` → `npm run ui:smoke`.

### Phase 2 — Verification hardening (this week)

5. **Hardware bench test** — run README steps 1–10 outdoors; capture serial log + distance-vs-phone comparison as evidence. This is the last unverified acceptance item.
6. **CI pipeline** — GitHub Actions running on push:
   `pytest -q` + `npm run typecheck` + `npm run build` (all three are already green, so CI starts green).
7. **Linting** — add `ruff check` to the backend and `eslint` to the frontend; wire both into CI.
8. **Coverage** — add `pytest-cov`, set a floor (e.g. 85%) for `app/services` and `app/artwork`.

### Phase 3 — Product next steps (after hardware sign-off)

9. **Authentication before any internet exposure** — today the API is single-tenant (`local` owner) with no login; add user accounts/sessions before opening port 8000 beyond the LAN.
10. **Data retention** — raw points are stored forever; implement a pruning/archival policy (or make it configurable) so the SQLite file doesn't grow unbounded.
11. **PostgreSQL migration** — the URL swap is already supported (`GEOSKETCH_DATABASE_URL`); validate it under load and move rate limiting to Redis (noted in `docs/architecture.md`).
12. **HTTPS on the device** — switch the firmware to `WiFiClientSecure` before using anything but a trusted LAN.
13. **Frontend unit tests** — vitest + testing-library for `useRecorder`, `useDemoReplay` and the recording state-machine UI (button disable logic).
14. **Artwork studio growth** — gallery page for saved artworks, shareable links, additional styles (e.g. satellite-free typographic layout), higher-resolution PNG export.
15. **Multi-segment editing** — let users label break points (rest stops) and include them in statistics/artwork captions.

### Suggested order at a glance

| # | Task | Effort | Risk reduced |
| --- | --- | --- | --- |
| 1 | First git commit + `.gitignore` fix | 30 min | total loss of work |
| 2 | `.env` / `config.h` from examples | 10 min | can't run real device |
| 3 | End-to-end demo smoke run | 30 min | broken integration |
| 4 | Hardware procedure 1–10 | 1–2 h (outdoors) | unverified core claim |
| 5 | CI (pytest + tsc + build) | 1 h | silent regressions |
| 6 | ruff + eslint | 1 h | code drift |
| 7–15 | product/infra items | days–weeks | scope/robustness |

---

## Appendix — verification commands

```powershell
# Backend (108 tests)
cd C:\Users\kusha\GeoSketch\backend
.venv\Scripts\python.exe -m pytest -q

# Frontend (typecheck + production build)
cd C:\Users\kusha\GeoSketch\frontend
npm run typecheck
npm run build

# Full stack
cd backend;   .venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# new terminal:
cd frontend;  npm run dev
# health: http://127.0.0.1:8000/api/v1/health · docs: http://127.0.0.1:8000/docs · UI: http://127.0.0.1:5173

# UI smoke test (needs a debug Chrome on :9222 — see README "Running the tests")
npm run ui:smoke
```
