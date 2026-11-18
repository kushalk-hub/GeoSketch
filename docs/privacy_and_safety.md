# Privacy and safety

GeoSketch Family Safe-Trip is a **location sharing aid**, not a safety guarantee.

## Stored data

Parent accounts store a lowercased email address, a scrypt password hash with a per-account salt, an optional Telegram chat ID and creation time. Share records store a SHA-256 token digest, device reference, display label, expiry, revocation and last-viewed timestamps. The plaintext share token is returned only when the link is created. GPS fixes and safe-zone definitions remain in the existing database; alert records retain messages, timestamps and delivery results.

There is no automatic GPS or alert retention policy. Back up and delete the SQLite database according to your family's needs.

## Access and links

Parents must sign in to manage links, zones and alerts. Anyone with a valid live URL can see that link's device position, recent trail, status and the creating parent's zones. The live page does not require login: possession of the URL grants access. Treat it like a password. Revoke a link to end access immediately; expiry also ends access.

The public response omits device credentials, owner data, database IDs and unrelated journeys. HTTPS is required whenever a link leaves a trusted local network. HTTP can expose credentials and location data to anyone who can observe the traffic.

GPS positions are estimates (typically around 2.5 m in good outdoor conditions, often worse indoors). The tracker needs Wi-Fi and has no cellular connection. A stale or offline indicator describes received data; it cannot establish a child's actual condition or location.

