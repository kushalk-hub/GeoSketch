# Family Safe-Trip limitations

- The prototype sends locations over Wi-Fi only. It has no SIM or cellular coverage.
- SIM800L/A7670 connectivity is future work and is not implemented.
- GPS is an estimate (about 2.5 m in favorable open-sky conditions); indoor fixes can be poor or unavailable.
- The ESP32 queue is in RAM and is lost on power failure.
- Offline alerts are driven by missing accepted points and apply only while a hardware journey is recording. Paused and stopped journeys are ignored.
- The rate limiter is in-process and shared across routes, not a dedicated stricter login limiter. Multi-worker deployments do not share its counters.
- Share links are bearer secrets. There is no login on the live page. Revoke or expire a link if it is forwarded accidentally.
- No automatic location or alert retention exists.
- Telegram delivery requires a configured bot token and a parent chat ID; otherwise alerts are logged and remain visible in the app.
- This is a location sharing aid, not a safety guarantee.

