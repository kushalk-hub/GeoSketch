# Family Safe-Trip demo script

1. Create a parent account, add a home safe zone and start a recording hardware journey.
2. Simulate a walk out of the home zone and show the arrived/left event and live trail.
3. Add a school safe zone and simulate arrival.
4. Stop incoming updates long enough to cross the offline threshold, then resume them and show one offline and one back-online event.
5. If optional SOS hardware is installed, long-press the button and confirm the alert.

## Likely questions

**Is this as dependable as Life360 or a cellular kids' watch?** No. This prototype depends on the ESP32, Wi-Fi, sky view and a reachable server. It has no cellular radio or safety guarantee.

**Does the child need a phone?** No; the tracker is an ESP32-C3 with a GPS module. The parent needs a browser and a live share link.

**Who owns the data?** The family hosting the backend. There is no automatic retention policy.

**Can anyone open the live view?** Anyone holding a valid link can. Links expire and can be revoked.

