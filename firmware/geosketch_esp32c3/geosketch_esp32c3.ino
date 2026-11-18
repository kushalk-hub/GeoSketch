/* ===========================================================================
 * GeoSketch - ESP32-C3 + NEO-6M GPS tracker firmware
 * ---------------------------------------------------------------------------
 * Physical movement -> GPS satellites -> NEO-6M -> ESP32-C3 -> Wi-Fi -> backend
 *
 * Responsibilities
 *   1. read NMEA sentences from the NEO-6M over UART1,
 *   2. parse them with TinyGPSPlus and validate the fix (fresh, enough sats),
 *   3. NEVER transmit a fabricated or stale position,
 *   4. throttle duplicate/over-frequent fixes (distance + interval rules),
 *   5. POST each fix to the GeoSketch backend with retry + RAM buffering,
 *   6. survive Wi-Fi drops and reconnect automatically,
 *   7. print clear diagnostics on the USB serial monitor.
 *
 * Board:  ESP32-C3 (Arduino core 3.x).  No ESP32-S3 required.
 * Wiring: see docs/hardware_connections.md (NEO-6M TX -> GPIO4, RX -> GPIO5).
 *
 * Serial commands (115200 baud):
 *   s  print status        c  clear the send queue      f  force send
 *   g  print GPS detail    q  print queue contents      r  reconnect Wi-Fi
 * ===========================================================================
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClient.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <TinyGPSPlus.h>
#include <ArduinoJson.h>
#include "firmware_types.h"

#if !__has_include("config.h")
#error "Create firmware/geosketch_esp32c3/config.h from config.h.example and fill in your credentials."
#endif
#include "config.h"
#ifndef GEOSKETCH_SOS_PIN
#define GEOSKETCH_SOS_PIN -1
#endif
#ifndef GEOSKETCH_WARMUP_FIXES
#define GEOSKETCH_WARMUP_FIXES 3
#endif

/* --------------------------------------------------------------------------
 * Tunables that are rarely changed (kept here so config.h stays readable)
 * ------------------------------------------------------------------------ */
static const char *FIRMWARE_VERSION = "1.0.0";
//: Wi-Fi reconnect backoff bounds.
static const uint32_t WIFI_RETRY_MIN_MS = 2000;
static const uint32_t WIFI_RETRY_MAX_MS = 30000;
//: Minimum distance (metres) for the very first fix of a journey.
static const double FIRST_FIX_ALWAYS = 0.0;

/* --------------------------------------------------------------------------
 * Device state machine (mirrors the states used by the dashboard)
 * ------------------------------------------------------------------------ */
enum DeviceState {
  STATE_INIT = 0,
  STATE_WIFI_CONNECTING,
  STATE_WAITING_FOR_FIX,
  STATE_FIX_ACQUIRED,
  STATE_CONNECTED,
  STATE_TRANSMISSION_FAILED,
  STATE_RECONNECTING
};

static const char *stateName(DeviceState state) {
  switch (state) {
    case STATE_INIT:                return "INITIALIZING";
    case STATE_WIFI_CONNECTING:     return "WIFI_CONNECTING";
    case STATE_WAITING_FOR_FIX:     return "WAITING_FOR_GPS_FIX";
    case STATE_FIX_ACQUIRED:        return "GPS_FIX_ACQUIRED";
    case STATE_CONNECTED:           return "CONNECTED";
    case STATE_TRANSMISSION_FAILED: return "TRANSMISSION_FAILED";
    case STATE_RECONNECTING:        return "RECONNECTING";
  }
  return "UNKNOWN";
}

/* --------------------------------------------------------------------------
 * Circular GPS queue (RAM only - the ESP32-C3 has no PSRAM)
 * ------------------------------------------------------------------------ */
struct GPSRecord {
  double   latitude;
  double   longitude;
  bool     hasAltitude;
  float    altitude;
  bool     hasSpeed;
  float    speedKmh;
  uint8_t  satellites;
  bool     hasHdop;
  float    hdop;
  bool     hasTimestamp;
  char     timestamp[21];  // "2026-10-15T10:30:00Z" + NUL
  char     clientPointId[32];
  bool     sos;
};

static GPSRecord queueBuffer[GEOSKETCH_QUEUE_SIZE];
static uint16_t queueHead = 0;   // next slot to read
static uint16_t queueTail = 0;   // next slot to write
static uint16_t queueCount = 0;
static uint32_t queueDropped = 0;
static uint32_t pointsSent = 0;
static uint32_t pointsFailed = 0;

/* --------------------------------------------------------------------------
 * Module instances and runtime state
 * ------------------------------------------------------------------------ */
static TinyGPSPlus gps;
static HardwareSerial gpsSerial(1);
static Preferences preferences;
static WiFiClient wifiClient;
static WiFiClientSecure wifiClientSecure;

static DeviceState deviceState = STATE_INIT;
static uint32_t bootId = 0;
static uint32_t pointSequence = 0;

static uint32_t lastSendAttemptMs = 0;
static uint32_t retryDelayMs = GEOSKETCH_RETRY_MIN_MS;
static uint32_t lastStatusPrintMs = 0;
static uint32_t lastWifiAttemptMs = 0;
static uint32_t wifiRetryDelayMs = WIFI_RETRY_MIN_MS;

static bool     haveLastSent = false;
static double   lastSentLat = 0.0;
static double   lastSentLon = 0.0;
static uint32_t lastSentMs = 0;
static uint32_t lastFixSeenMs = 0;
static double   lastFixLat = 0.0;
static double   lastFixLon = 0.0;
static uint32_t fixesSeen = 0;
static uint16_t goodEpochCount = 0;
static uint32_t lastGoodEpochMs = 0;
static bool sosPending = false;
#if GEOSKETCH_SOS_PIN >= 0
static int sosRawState = HIGH;
static int sosStableState = HIGH;
static uint32_t sosRawChangedMs = 0;
static uint32_t sosPressedMs = 0;
static bool sosTriggeredForPress = false;
#endif

/* --------------------------------------------------------------------------
 * Small helpers
 * ------------------------------------------------------------------------ */
#define LOG(...)      do { if (GEOSKETCH_DEBUG) { Serial.printf(__VA_ARGS__); Serial.println(); } } while (0)
#define LOGF(...)     do { if (GEOSKETCH_DEBUG) { Serial.printf(__VA_ARGS__); } } while (0)

static void setState(DeviceState next) {
  if (next == deviceState) {
    return;
  }
  LOG("[state] %s -> %s", stateName(deviceState), stateName(next));
  deviceState = next;
}

/** Haversine distance in metres - must match the backend's formula. */
static double distanceMeters(double lat1, double lon1, double lat2, double lon2) {
  const double earthRadius = 6371008.8;
  const double toRad = PI / 180.0;
  double phi1 = lat1 * toRad;
  double phi2 = lat2 * toRad;
  double dPhi = (lat2 - lat1) * toRad;
  double dLambda = (lon2 - lon1) * toRad;
  double a = sin(dPhi / 2.0) * sin(dPhi / 2.0) +
             cos(phi1) * cos(phi2) * sin(dLambda / 2.0) * sin(dLambda / 2.0);
  if (a < 0.0) a = 0.0;
  if (a > 1.0) a = 1.0;
  return 2.0 * earthRadius * asin(sqrt(a));
}

/** WGS84 -> ISO-8601 UTC string, using the module's own date/time. */
static bool buildTimestamp(char *out, size_t outSize) {
  if (!gps.date.isValid() || !gps.time.isValid()) {
    return false;
  }
  int year = gps.date.year();
  if (year < 2020) {
    // The NEO-6M reports 2000-01-01 until it has downloaded the almanac.
    return false;
  }
  int month = gps.date.month();
  int day = gps.date.day();
  int hour = gps.time.hour();
  int minute = gps.time.minute();
  int second = gps.time.second();
  if (month < 1 || month > 12 || day < 1 || day > 31 ||
      hour > 23 || minute > 59 || second > 60) {
    return false;
  }
  snprintf(out, outSize, "%04d-%02d-%02dT%02d:%02d:%02dZ",
           year, month, day, hour, minute, second);
  return true;
}

/** True when the current fix is valid, fresh and of acceptable quality. */
static bool fixIsGood(String &why) {
  if (!gps.location.isValid()) {
    why = "no valid position";
    return false;
  }
  if (gps.location.age() > GEOSKETCH_MAX_FIX_AGE_MS) {
    why = "fix is stale";
    return false;
  }
  // 0,0 is what the module streams before it has a fix - never trust it.
  if (fabs(gps.location.lat()) < 1e-7 && fabs(gps.location.lng()) < 1e-7) {
    why = "position is the 0,0 no-fix sentinel";
    return false;
  }
  // Require fresh satellite count and HDOP from $GPGGA/$GNGGA so a lone
  // $GPRMC frame or stale GGA cannot bypass the geometry quality gate.
  if (!gps.satellites.isValid() || gps.satellites.age() > GEOSKETCH_MAX_FIX_AGE_MS * 2) {
    why = "satellite count unavailable/stale";
    return false;
  }
  if (gps.satellites.value() < GEOSKETCH_MIN_SATELLITES) {
    why = "too few satellites";
    return false;
  }
  if (!gps.hdop.isValid() || gps.hdop.age() > GEOSKETCH_MAX_FIX_AGE_MS * 2) {
    why = "HDOP unavailable/stale";
    return false;
  }
  double hdop = gps.hdop.hdop();
  if (hdop <= 0.0 || hdop > GEOSKETCH_MAX_HDOP) {
    why = "HDOP too high";
    return false;
  }
  return true;
}

static void feedGps();

/* --------------------------------------------------------------------------
 * Queue management (FIFO so the backend always receives chronological order)
 * ------------------------------------------------------------------------ */
static bool queuePush(const GPSRecord &record) {
  if (queueCount >= GEOSKETCH_QUEUE_SIZE) {
    // Drop the oldest point: the newest data is what the dashboard needs.
    queueHead = (queueHead + 1) % GEOSKETCH_QUEUE_SIZE;
    queueCount--;
    queueDropped++;
    LOG("[queue] full - dropped the oldest buffered point (%lu dropped so far)",
        (unsigned long)queueDropped);
  }
  queueBuffer[queueTail] = record;
  queueTail = (queueTail + 1) % GEOSKETCH_QUEUE_SIZE;
  queueCount++;
  return true;
}

static bool queuePushFront(const GPSRecord &record) {
  if (queueCount >= GEOSKETCH_QUEUE_SIZE) {
    queueHead = (queueHead + 1) % GEOSKETCH_QUEUE_SIZE;
    queueCount--;
    queueDropped++;
  }
  queueHead = (queueHead + GEOSKETCH_QUEUE_SIZE - 1) % GEOSKETCH_QUEUE_SIZE;
  queueBuffer[queueHead] = record;
  queueCount++;
  return true;
}
static bool queuePeek(GPSRecord &out) {
  if (queueCount == 0) {
    return false;
  }
  out = queueBuffer[queueHead];
  return true;
}

static void queuePop() {
  if (queueCount == 0) {
    return;
  }
  queueHead = (queueHead + 1) % GEOSKETCH_QUEUE_SIZE;
  queueCount--;
}

static void queueClear() {
  queueHead = queueTail = queueCount = 0;
  LOG("[queue] cleared");
}

/* --------------------------------------------------------------------------
 * Wi-Fi
 * ------------------------------------------------------------------------ */
static bool wifiConnected() {
  return WiFi.status() == WL_CONNECTED;
}

static void startWifi() {
  LOG("[wifi] connecting to \"%s\" ...", GEOSKETCH_WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.setSleep(false);  // lower latency, helps the HTTP round trip
  WiFi.begin(GEOSKETCH_WIFI_SSID, GEOSKETCH_WIFI_PASSWORD);
  lastWifiAttemptMs = millis();
  setState(STATE_WIFI_CONNECTING);
}

static void maintainWifi() {
  if (wifiConnected()) {
    if (deviceState == STATE_WIFI_CONNECTING || deviceState == STATE_RECONNECTING) {
      LOG("[wifi] connected - IP %s  RSSI %d dBm",
          WiFi.localIP().toString().c_str(), WiFi.RSSI());
      wifiRetryDelayMs = WIFI_RETRY_MIN_MS;
      setState(haveLastSent ? STATE_CONNECTED : STATE_FIX_ACQUIRED);
    }
    return;
  }

  if (deviceState != STATE_RECONNECTING && deviceState != STATE_WIFI_CONNECTING) {
    setState(STATE_RECONNECTING);
  }

  uint32_t now = millis();
  if (now - lastWifiAttemptMs >= wifiRetryDelayMs) {
    lastWifiAttemptMs = now;
    LOG("[wifi] reconnecting (attempt backoff %lu ms)", (unsigned long)wifiRetryDelayMs);
    WiFi.disconnect();
    WiFi.begin(GEOSKETCH_WIFI_SSID, GEOSKETCH_WIFI_PASSWORD);
    wifiRetryDelayMs = min(wifiRetryDelayMs * 2, (uint32_t)WIFI_RETRY_MAX_MS);
  }
}

/* --------------------------------------------------------------------------
 * HTTP transmission
 * ------------------------------------------------------------------------ */
enum SendResult : int { SEND_OK, SEND_RETRY, SEND_DROP };

static bool beginHttp(HTTPClient &http, const String &url) {
  http.setReuse(false);
  http.setConnectTimeout(GEOSKETCH_HTTP_TIMEOUT_MS);
  http.setTimeout(GEOSKETCH_HTTP_TIMEOUT_MS);
  if (url.startsWith("https://")) {
    wifiClientSecure.stop();
    wifiClientSecure.setInsecure();
    return http.begin(wifiClientSecure, url);
  }
  return http.begin(wifiClient, url);
}

static SendResult sendRecord(const GPSRecord &record) {
  String url = String(GEOSKETCH_API_BASE_URL) + GEOSKETCH_API_PATH;

  JsonDocument doc;
  doc["device_id"] = GEOSKETCH_DEVICE_ID;
  doc["latitude"] = serialized(String(record.latitude, 7));
  doc["longitude"] = serialized(String(record.longitude, 7));
  if (record.hasAltitude) {
    doc["altitude"] = serialized(String(record.altitude, 1));
  } else {
    doc["altitude"] = nullptr;  // unknown must stay unknown, never invented
  }
  if (record.hasSpeed) {
    doc["speed_kmh"] = serialized(String(record.speedKmh, 2));
  } else {
    doc["speed_kmh"] = nullptr;
  }
  if (record.satellites > 0) {
    doc["satellites"] = record.satellites;
  } else {
    doc["satellites"] = nullptr;
  }
  if (record.hasHdop) {
    doc["hdop"] = serialized(String(record.hdop, 2));
  } else {
    doc["hdop"] = nullptr;
  }
  if (record.hasTimestamp) {
    doc["timestamp"] = record.timestamp;
  } else {
    doc["timestamp"] = nullptr;
  }
  doc["client_point_id"] = record.clientPointId;
  if (record.sos) {
    doc["sos"] = true;
  }

  String body;
  serializeJson(doc, body);

  HTTPClient http;
  if (!beginHttp(http, url)) {
    LOG("[http] could not start the request to %s", url.c_str());
    return SEND_RETRY;
  }

  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Id", GEOSKETCH_DEVICE_ID);
  http.addHeader("X-Device-Key", GEOSKETCH_DEVICE_KEY);
  http.addHeader("Connection", "close");

  int status = http.POST(body);
  String response = (status > 0) ? http.getString() : String("");
  http.end();
  feedGps();

  if (status == 200 || status == 201) {
    LOG("[http] %d stored %s (seq %s)", status,
        response.indexOf("\"stored\":true") >= 0 ? "yes" : "no",
        record.clientPointId);
    return SEND_OK;
  }

  if (status == 401 || status == 403) {
    LOG("[http] %d AUTHENTICATION FAILED - check GEOSKETCH_DEVICE_ID/KEY and "
        "GEOSKETCH_DEVICE_KEYS on the backend", status);
    return SEND_DROP;  // retrying cannot fix a key mismatch
  }
  if (status == 413) {
    LOG("[http] 413 payload rejected by the server - dropping the point");
    return SEND_DROP;
  }
  if (status == 422 || status == 409) {
    LOG("[http] %d point rejected by the server: %s", status, response.c_str());
    return SEND_DROP;  // the payload will never become valid
  }
  if (status == 429) {
    LOG("[http] 429 rate limited - will retry later");
    return SEND_RETRY;
  }
  if (status <= 0) {
    LOG("[http] network error (%s)", http.errorToString(status).c_str());
    return SEND_RETRY;
  }

  LOG("[http] unexpected status %d: %s", status, response.c_str());
  return SEND_RETRY;
}

#ifndef GEOSKETCH_HEARTBEAT_PATH
#define GEOSKETCH_HEARTBEAT_PATH "/api/v1/devices/heartbeat"
#endif

static uint32_t lastHeartbeatMs = 0;

/** Report device online to the backend even before a GPS fix is acquired. */
static void sendHeartbeat() {
  if (!wifiConnected()) {
    return;
  }
  String url = String(GEOSKETCH_API_BASE_URL) + GEOSKETCH_HEARTBEAT_PATH +
               "?firmware_version=" + FIRMWARE_VERSION;
  HTTPClient http;
  if (!beginHttp(http, url)) {
    return;
  }
  http.addHeader("X-Device-Id", GEOSKETCH_DEVICE_ID);
  http.addHeader("X-Device-Key", GEOSKETCH_DEVICE_KEY);
  http.addHeader("Content-Length", "0");
  http.addHeader("Connection", "close");
  int status = http.POST("");
  http.end();
  feedGps();
  if (status == 200 || status == 201) {
    LOG("[http] heartbeat OK (device online)");
  } else {
    LOG("[http] heartbeat failed (%d) -> %s", status, url.c_str());
  }
}

static void maintainHeartbeat() {
  if (!wifiConnected()) {
    return;
  }
  uint32_t now = millis();
  if (lastHeartbeatMs == 0 || (now - lastHeartbeatMs >= 20000UL && now - lastSentMs >= 20000UL)) {
    lastHeartbeatMs = now;
    sendHeartbeat();
  }
}

/** Try to upload buffered points.  Stops at the first retryable failure. */
static void flushQueue() {
  if (queueCount == 0 || !wifiConnected()) {
    return;
  }
  uint32_t now = millis();
  if (now - lastSendAttemptMs < retryDelayMs) {
    return;
  }
  lastSendAttemptMs = now;

  uint8_t sentThisPass = 0;
  while (queueCount > 0 && sentThisPass < GEOSKETCH_FLUSH_BATCH && wifiConnected()) {
    GPSRecord record;
    if (!queuePeek(record)) {
      break;
    }

    SendResult result = sendRecord(record);
    if (result == SEND_OK) {
      queuePop();
      sentThisPass++;
      pointsSent++;
      retryDelayMs = GEOSKETCH_RETRY_MIN_MS;
      haveLastSent = true;
      lastSentLat = record.latitude;
      lastSentLon = record.longitude;
      lastSentMs = millis();
      if (deviceState == STATE_TRANSMISSION_FAILED || deviceState == STATE_FIX_ACQUIRED) {
        setState(STATE_CONNECTED);
      }
    } else if (result == SEND_DROP) {
      queuePop();
      sentThisPass++;
      pointsFailed++;
    } else {
      pointsFailed++;
      retryDelayMs = min(retryDelayMs * 2, (uint32_t)GEOSKETCH_RETRY_MAX_MS);
      LOG("[http] retrying in %lu ms (%u point(s) buffered)",
          (unsigned long)retryDelayMs, queueCount);
      setState(STATE_TRANSMISSION_FAILED);
      break;
    }
  }
}

/* --------------------------------------------------------------------------
 * GPS handling
 * ------------------------------------------------------------------------ */
static void handleSosButton() {
#if GEOSKETCH_SOS_PIN >= 0
  uint32_t now = millis();
  int reading = digitalRead(GEOSKETCH_SOS_PIN);
  if (reading != sosRawState) {
    sosRawState = reading;
    sosRawChangedMs = now;
  } else if (reading != sosStableState && now - sosRawChangedMs >= 50) {
    sosStableState = reading;
    if (sosStableState == LOW) {
      sosPressedMs = now;
      sosTriggeredForPress = false;
    } else {
      sosTriggeredForPress = false;
    }
  }
  if (sosStableState == LOW && !sosTriggeredForPress && now - sosPressedMs >= 2000) {
    sosPending = true;
    sosTriggeredForPress = true;
    LOG("[sos] long press detected; SOS will go with the next GPS fix");
  }
#endif
}
static bool echoRawNmea = false;

static void feedGps() {
  while (gpsSerial.available() > 0) {
    char c = (char)gpsSerial.read();
    if (echoRawNmea) {
      Serial.write(c);
    }
    gps.encode(c);
  }
}

/** Decide whether the current fix should be transmitted, and enqueue it. */
static void maybeCaptureFix() {
  bool locationUpdated = gps.location.isUpdated();
  String why;
  if (!fixIsGood(why)) {
    goodEpochCount = 0;
    if (deviceState != STATE_TRANSMISSION_FAILED && deviceState != STATE_RECONNECTING) {
      setState(STATE_WAITING_FOR_FIX);
    }
    static uint32_t lastReasonMs = 0;
    if (millis() - lastReasonMs > 15000) {
      lastReasonMs = millis();
      LOG("[gps] waiting for a usable fix: %s (sats %lu, hdop %.1f)",
          why.c_str(),
          (unsigned long)(gps.satellites.isValid() ? gps.satellites.value() : 0),
          gps.hdop.isValid() ? gps.hdop.hdop() : 99.9);
    }
    return;
  }

  uint32_t now = millis();
  if (locationUpdated && (lastGoodEpochMs == 0 || now - lastGoodEpochMs >= 800)) {
    lastGoodEpochMs = now;
    if (goodEpochCount < GEOSKETCH_WARMUP_FIXES) {
      goodEpochCount++;
    }
  }

  if (deviceState == STATE_WAITING_FOR_FIX || deviceState == STATE_INIT) {
    setState(STATE_FIX_ACQUIRED);
  }

  if (goodEpochCount < GEOSKETCH_WARMUP_FIXES && !sosPending) {
    return;
  }

  lastFixSeenMs = now;
  lastFixLat = gps.location.lat();
  lastFixLon = gps.location.lng();
  fixesSeen++;

  // --- transmission policy: distance + interval, with a liveness heartbeat ---
  double moved = haveLastSent
                     ? distanceMeters(lastSentLat, lastSentLon, lastFixLat, lastFixLon)
                     : FIRST_FIX_ALWAYS;
  uint32_t sinceLast = haveLastSent ? (now - lastSentMs) : GEOSKETCH_MAX_SEND_INTERVAL_MS;

  bool firstFix = !haveLastSent;
  bool movedEnough = firstFix || (moved >= GEOSKETCH_MIN_SEND_DISTANCE_M);
  bool waitedEnough = firstFix || (sinceLast >= GEOSKETCH_MIN_SEND_INTERVAL_MS);
  bool heartbeatDue = sinceLast >= GEOSKETCH_MAX_SEND_INTERVAL_MS;

  // Transmit when the device has moved far enough and the minimum interval has
  // passed, or when the liveness heartbeat is due (which also carries the very
  // first fix and the "parked at the cafe" case).
  if (!(firstFix || sosPending || heartbeatDue || (movedEnough && waitedEnough))) {
    return;
  }

  GPSRecord record;
  memset(&record, 0, sizeof(record));
  record.latitude = lastFixLat;
  record.longitude = lastFixLon;
  record.hasAltitude = gps.altitude.isValid();
  record.altitude = record.hasAltitude ? (float)gps.altitude.meters() : 0.0f;
  record.hasSpeed = gps.speed.isValid();
  record.speedKmh = record.hasSpeed ? (float)gps.speed.kmph() : 0.0f;
  record.satellites = gps.satellites.isValid() ? (uint8_t)min(gps.satellites.value(), (uint32_t)255) : 0;
  record.hasHdop = gps.hdop.isValid();
  record.hdop = record.hasHdop ? (float)gps.hdop.hdop() : 0.0f;
  record.hasTimestamp = buildTimestamp(record.timestamp, sizeof(record.timestamp));
  if (!record.hasTimestamp) {
    record.timestamp[0] = '\0';
  }
  record.sos = sosPending;
  snprintf(record.clientPointId, sizeof(record.clientPointId), "%lu-%lu",
           (unsigned long)bootId, (unsigned long)(++pointSequence));

  if (record.sos) {
    queuePushFront(record);
    sosPending = false;
  } else {
    queuePush(record);
  }

  LOG("[gps] fix captured: %.7f, %.7f  alt %s  spd %s  sats %u  hdop %.1f  time %s  queue %u  (%s)",
      record.latitude, record.longitude,
      record.hasAltitude ? String(record.altitude, 1).c_str() : "n/a",
      record.hasSpeed ? String(record.speedKmh, 1).c_str() : "n/a",
      record.satellites,
      record.hasHdop ? record.hdop : 99.9f,
      record.hasTimestamp ? record.timestamp : "unavailable",
      queueCount, record.clientPointId);

  // Remember the transmission reference immediately: a buffered point must not
  // be captured again while it is still waiting to be uploaded.
  haveLastSent = true;
  lastSentLat = record.latitude;
  lastSentLon = record.longitude;
  lastSentMs = now;

  // One upload attempt right away so the dashboard sees movement immediately.
  retryDelayMs = GEOSKETCH_RETRY_MIN_MS;
  flushQueue();
}

/* --------------------------------------------------------------------------
 * Diagnostics
 * ------------------------------------------------------------------------ */
static void printStatus() {
  Serial.println(F("---------------------------------------------------------------"));
  LOG("GeoSketch firmware %s | state %s | uptime %.1f min",
      FIRMWARE_VERSION, stateName(deviceState), millis() / 60000.0);
  LOG("device_id %s | Wi-Fi %s | IP %s | RSSI %d dBm",
      GEOSKETCH_DEVICE_ID,
      wifiConnected() ? "connected" : "disconnected",
      wifiConnected() ? WiFi.localIP().toString().c_str() : "-",
      wifiConnected() ? WiFi.RSSI() : 0);
  LOG("GPS bytes %lu | NMEA valid sentences: %lu (checksum errors: %lu) | 3D fixes: %lu | last fix: %s",
      (unsigned long)gps.charsProcessed(),
      (unsigned long)gps.passedChecksum(),
      (unsigned long)gps.failedChecksum(),
      (unsigned long)gps.sentencesWithFix(),
      gps.location.isValid() ? "valid" : "none");
  if (gps.location.isValid()) {
    LOG("position %.7f, %.7f | age %lu ms | sats %lu | hdop %.1f | alt %s m | spd %s km/h",
        gps.location.lat(), gps.location.lng(),
        (unsigned long)gps.location.age(),
        (unsigned long)gps.satellites.value(),
        gps.hdop.isValid() ? gps.hdop.hdop() : 0.0,
        gps.altitude.isValid() ? String(gps.altitude.meters(), 1).c_str() : "n/a",
        gps.speed.isValid() ? String(gps.speed.kmph(), 1).c_str() : "n/a");
  }
  LOG("queue %u/%d | sent %lu | failed %lu | dropped %lu",
      queueCount, GEOSKETCH_QUEUE_SIZE,
      (unsigned long)pointsSent, (unsigned long)pointsFailed,
      (unsigned long)queueDropped);
  if (gps.charsProcessed() < 10 && millis() > 15000) {
    Serial.println(F("!! No NMEA data received - check the NEO-6M wiring, the "
                     "baud rate (9600) and the TX/RX pin numbers in config.h"));
  }
}

static void handleSerialCommands() {
  while (Serial.available() > 0) {
    char command = (char)Serial.read();
    switch (command) {
      case 's': printStatus(); break;
      case 'n':
        echoRawNmea = !echoRawNmea;
        LOG("[cmd] raw NMEA live stream: %s (press 'n' + Enter again to toggle)",
            echoRawNmea ? "ENABLED" : "DISABLED");
        break;
      case 'g':
        LOG("raw: lat %s lon %s sats %lu hdop %.2f date %04d-%02d-%02d time %02d:%02d:%02d",
            String(gps.location.lat(), 7).c_str(), String(gps.location.lng(), 7).c_str(),
            (unsigned long)gps.satellites.value(),
            gps.hdop.isValid() ? gps.hdop.hdop() : 0.0,
            gps.date.year(), gps.date.month(), gps.date.day(),
            gps.time.hour(), gps.time.minute(), gps.time.second());
        break;
      case 'c': queueClear(); break;
      case 'f':
        LOG("[cmd] forcing upload of %u buffered point(s)", queueCount);
        retryDelayMs = 0;
        lastSendAttemptMs = 0;
        flushQueue();
        break;
      case 'q':
        LOG("[cmd] %u point(s) buffered:", queueCount);
        for (uint16_t i = 0; i < queueCount; i++) {
          const GPSRecord &r = queueBuffer[(queueHead + i) % GEOSKETCH_QUEUE_SIZE];
          LOG("   %s  %.7f, %.7f  sats %u  %s", r.clientPointId, r.latitude, r.longitude,
              r.satellites, r.hasTimestamp ? r.timestamp : "no time");
        }
        break;
      case 'r':
        LOG("[cmd] manual Wi-Fi reconnect");
        WiFi.disconnect();
        wifiRetryDelayMs = WIFI_RETRY_MIN_MS;
        lastWifiAttemptMs = 0;
        break;
      case '\r': case '\n': case ' ': break;
      default:
        Serial.println(F("commands: s=status g=gps c=clear f=force q=queue r=reconnect"));
        break;
    }
  }
}

/* --------------------------------------------------------------------------
 * Arduino entry points
 * ------------------------------------------------------------------------ */
void setup() {
  Serial.begin(GEOSKETCH_SERIAL_BAUD);
  delay(400);  // let the USB CDC serial port come up
  Serial.println();
  Serial.println(F("==============================================================="));
  Serial.println(F(" GeoSketch - ESP32-C3 + NEO-6M GPS route art tracker"));
  LOG(" firmware %s | device_id %s", FIRMWARE_VERSION, GEOSKETCH_DEVICE_ID);
  Serial.println(F("==============================================================="));

  setState(STATE_INIT);
#if GEOSKETCH_SOS_PIN >= 0
  pinMode(GEOSKETCH_SOS_PIN, INPUT_PULLUP);
  sosRawState = sosStableState = digitalRead(GEOSKETCH_SOS_PIN);
  sosRawChangedMs = millis();
#endif

  // Persistent boot counter: keeps client_point_id unique across reboots, so a
  // point that was buffered before a power cut is still de-duplicated by the
  // backend when the retry arrives later.
  preferences.begin("geosketch", false);
  bootId = preferences.getUInt("bootId", 0) + 1;
  preferences.putUInt("bootId", bootId);
  LOG("[init] boot #%lu (client ids look like %lu-1)", (unsigned long)bootId, (unsigned long)bootId);

  gpsSerial.setRxBufferSize(2048);
  gpsSerial.begin(GEOSKETCH_GPS_BAUD, SERIAL_8N1, GEOSKETCH_GPS_RX_PIN, GEOSKETCH_GPS_TX_PIN);
  LOG("[init] GPS UART1 on RX=GPIO%d TX=GPIO%d @ %d baud",
      GEOSKETCH_GPS_RX_PIN, GEOSKETCH_GPS_TX_PIN, GEOSKETCH_GPS_BAUD);

  retryDelayMs = GEOSKETCH_RETRY_MIN_MS;
  startWifi();

  setState(STATE_WAITING_FOR_FIX);
  LOG("[init] ready. Type 's' + Enter for a status report.");
}

void loop() {
  feedGps();
  handleSerialCommands();
  handleSosButton();
  maintainWifi();
  maintainHeartbeat();
  maybeCaptureFix();

  if (queueCount > 0 && wifiConnected()) {
    flushQueue();
  }

  uint32_t now = millis();
  if (GEOSKETCH_DEBUG && now - lastStatusPrintMs >= GEOSKETCH_STATUS_INTERVAL_MS) {
    lastStatusPrintMs = now;
    LOG("[hb] %s | queue %u | sats %lu | fixes %lu | sent %lu | rssi %d",
        stateName(deviceState), queueCount,
        (unsigned long)(gps.satellites.isValid() ? gps.satellites.value() : 0),
        (unsigned long)fixesSeen, (unsigned long)pointsSent,
        wifiConnected() ? WiFi.RSSI() : 0);
  }

  delay(1);  // yield to the Wi-Fi stack and the IDLE task
}
