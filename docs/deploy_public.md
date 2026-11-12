# Public deployment

Use HTTPS for every public endpoint. Generate `GEOSKETCH_AUTH_SECRET` with a cryptographically random value (for example `python -c "import secrets; print(secrets.token_urlsafe(48))"`). Set `GEOSKETCH_CORS_ORIGINS` to the exact public frontend origin, `VITE_API_BASE_URL` to the public HTTPS API URL, and `GEOSKETCH_PUBLIC_BASE_URL` to the public frontend origin. Set the ESP32 `GEOSKETCH_API_BASE_URL` to the public HTTPS API URL; see the firmware README's HTTPS configuration.

## Quick demonstration

Run the backend and frontend locally, then expose them through Cloudflare Tunnel or ngrok with HTTPS. Configure the public URLs above before creating share links. Stop the tunnel after the demonstration.

## Hosted option

A small free web service can host the API and frontend, but verify its sleep behavior, persistent disk, outbound Telegram access, HTTPS and database persistence before relying on it. SQLite on ephemeral storage loses data when the instance restarts.

## Exposure warning

The existing owner-scoped journey routes use `X-Owner-Key` as a scope selector, not an authenticated user credential. Do not expose those routes publicly without understanding that limitation. This application does not enforce a proxy path allow-list. If the host cannot restrict paths, the existing unauthenticated owner-scoped routes may also be reachable; use a deployment boundary that blocks them or do not expose the service publicly. Intended public paths are `/api/v1/live/*`, `/api/v1/parent/*`, `/api/v1/gps/points` and `/api/v1/health`.


## Free hosted demonstration: Render

Render offers a free web service and static-site tier for hobby demonstrations. Free web services spin down after 15 minutes without inbound traffic and use an ephemeral filesystem, so a local SQLite database is lost on restart, redeploy or spin-down. Treat this as a temporary demo only; do not use it for dependable tracking. Check the current [Render free-service limits](https://render.com/docs/free) before deployment.
