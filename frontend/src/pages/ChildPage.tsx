import { useMemo } from 'react'
import { Circle, MapContainer, Marker, TileLayer } from 'react-leaflet'
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Compass,
  Cpu,
  HelpCircle,
  MapPin,
  Navigation,
  Radio,
  Satellite,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Wifi,
  WifiOff,
} from 'lucide-react'
import 'leaflet/dist/leaflet.css'

import StatTile from '../components/StatTile'
import MapAutoCenter from '../components/MapAutoCenter'
import { useAlerts } from '../hooks/useAlerts'
import { useDeviceStatus } from '../hooks/useDeviceStatus'
import { useGeofences } from '../hooks/useGeofences'
import { useParentSession } from '../hooks/useParentSession'
import { CONFIGURED_DEVICE_ID } from '../services/api'
import { formatCoordinate, formatRelative, formatSpeed } from '../utils/format'
import { haversineMeters, latestDevicePosition } from '../utils/geo'

interface Props {
  onBackToDashboard?: () => void
}

export default function ChildPage({ onBackToDashboard }: Props) {
  const session = useParentSession()
  const effectiveToken = session.token || 'parent-session'

  const { status: deviceStatus } = useDeviceStatus(CONFIGURED_DEVICE_ID, 2000)
  const { zones } = useGeofences(effectiveToken)
  const { alerts } = useAlerts(effectiveToken, 4000)

  const isLive = Boolean(deviceStatus?.connected)
  const device = deviceStatus?.device ?? null
  const latestPoint = deviceStatus?.latest_point ?? null
  const trackerPos = useMemo(() => latestDevicePosition(deviceStatus), [deviceStatus])

  const latitude = trackerPos?.latitude ?? null
  const longitude = trackerPos?.longitude ?? null

  // Evaluate which zones the child is currently inside
  const zoneDistances = useMemo(() => {
    if (latitude === null || longitude === null) return []
    return zones.map((zone) => {
      const distance = haversineMeters(latitude, longitude, zone.latitude, zone.longitude)
      const isInside = distance <= zone.radius_m
      return {
        ...zone,
        distanceM: Math.round(distance),
        isInside,
      }
    })
  }, [zones, latitude, longitude])

  const activeZone = zoneDistances.find((z) => z.isInside)
  const recentSosAlert = alerts.find((a) => a.type.toLowerCase() === 'sos')

  const autoCenterTarget: [number, number] | null = useMemo(() => {
    if (latitude !== null && longitude !== null) return [latitude, longitude]
    if (zones.length > 0) return [zones[0].latitude, zones[0].longitude]
    return null
  }, [latitude, longitude, zones])

  const centerCoords: [number, number] = autoCenterTarget ?? [18.5204, 73.8567]

  return (
    <main className="mx-auto max-w-5xl space-y-5 p-4 sm:p-6" aria-label="Child Safe-Trip Companion">
      {/* --- Header -------------------------------------------------------- */}
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-edge pb-4">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl border border-accent/20 bg-primary-fixed text-accent">
            <Compass size={22} />
          </span>
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-ink">
              Child Safe-Trip Companion
            </h1>
            <p className="text-xs text-muted">
              Live location, safe zone awareness, and emergency SOS guide
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span
            className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${
              isLive
                ? 'border border-live/30 bg-live/10 text-live'
                : 'border border-edge bg-surface-2 text-muted'
            }`}
          >
            {isLive ? <Wifi size={14} /> : <WifiOff size={14} />}
            {isLive ? 'Tracker Live' : 'Tracker Offline'}
          </span>

          {onBackToDashboard ? (
            <button
              type="button"
              onClick={onBackToDashboard}
              className="rounded-lg border border-edge bg-surface px-3 py-1.5 text-xs font-medium text-body transition hover:bg-surface-2"
            >
              Dashboard
            </button>
          ) : null}
        </div>
      </header>

      {/* --- Status Hero Banner ------------------------------------------- */}
      <section
        className={`rounded-2xl border p-4 sm:p-5 transition ${
          activeZone
            ? 'border-live/30 bg-live/10'
            : isLive
              ? 'border-accent/30 bg-accent/5'
              : 'border-edge bg-surface-2/60'
        }`}
        aria-label="Safety status banner"
      >
        <div className="flex items-start gap-3.5">
          <span className="mt-0.5 shrink-0">
            {activeZone ? (
              <ShieldCheck size={26} className="text-live" />
            ) : isLive ? (
              <Navigation size={26} className="text-accent" />
            ) : (
              <WifiOff size={26} className="text-muted" />
            )}
          </span>
          <div className="min-w-0 flex-1">
            <h2
              className={`text-base font-semibold sm:text-lg ${
                activeZone ? 'text-live' : isLive ? 'text-ink' : 'text-body'
              }`}
            >
              {activeZone
                ? `Safe Zone: Inside ${activeZone.name}`
                : isLive
                  ? 'On the Move · Outside Safe Zones'
                  : 'Tracker Waiting for Signal'}
            </h2>
            <p className="mt-1 text-xs leading-relaxed text-muted sm:text-sm">
              {activeZone
                ? `You are safely within the ${activeZone.name} perimeter (${activeZone.radius_m} m radius). Parents receive arrival notifications.`
                : isLive
                  ? 'Your live GPS coordinates are being streamed securely to your family.'
                  : `Last contact ${
                      device?.last_seen_at ? formatRelative(device.last_seen_at) : 'unknown'
                    }. The position shown is the last known location.`}
            </p>
          </div>
        </div>

        {/* Live Metrics Grid */}
        <div className="mt-4 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
          <StatTile
            label="Tracker Device"
            value={device?.device_id ?? CONFIGURED_DEVICE_ID}
            hint={
              device?.firmware_version
                ? `v${device.firmware_version}`
                : isLive
                  ? 'reporting'
                  : 'waiting'
            }
            icon={<Cpu size={12} />}
            tone={isLive ? 'live' : 'muted'}
          />
          <StatTile
            label="GPS Fix"
            value={
              isLive && latestPoint
                ? 'FIX ACQUIRED'
                : latestPoint || device?.last_latitude
                  ? 'LAST KNOWN'
                  : 'SEARCHING'
            }
            hint={
              latestPoint?.satellites !== undefined && latestPoint?.satellites !== null
                ? `${latestPoint.satellites} satellites lock`
                : 'satellites —'
            }
            icon={<Satellite size={12} />}
            tone={isLive && latestPoint ? 'live' : 'muted'}
          />
          <StatTile
            label="Current Speed"
            value={formatSpeed(latestPoint?.speed_kmh)}
            hint={
              latestPoint?.altitude !== null && latestPoint?.altitude !== undefined
                ? `Alt: ${Math.round(latestPoint.altitude)} m`
                : 'speed estimate'
            }
            icon={<Activity size={12} />}
            mono
          />
          <StatTile
            label="Safe Zone"
            value={activeZone ? activeZone.name : 'EN ROUTE'}
            hint={
              activeZone
                ? `${activeZone.radius_m} m boundary`
                : `${zoneDistances.length} zones monitored`
            }
            icon={<Shield size={12} />}
            tone={activeZone ? 'live' : 'default'}
          />
        </div>
      </section>

      {/* --- Map & Safe Zones --------------------------------------------- */}
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        {/* Interactive Companion Map */}
        <section className="rounded-2xl border border-edge bg-surface p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-ink">
              <MapPin size={16} className="text-accent" /> Live Map & Safe Zones
            </h3>
            <span className="text-[11px] text-muted">
              {latitude && longitude
                ? `${formatCoordinate(latitude, 4)}, ${formatCoordinate(longitude, 4)}`
                : 'Awaiting fix'}
            </span>
          </div>

          <div className="h-72 overflow-hidden rounded-xl border border-edge-soft sm:h-96">
            <MapContainer center={centerCoords} zoom={14} className="h-full w-full">
              <TileLayer
                attribution="&copy; OpenStreetMap"
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <MapAutoCenter target={autoCenterTarget} />

              {/* Render parent-defined safe zones */}
              {zones.map((zone) => (
                <Circle
                  key={zone.id}
                  center={[zone.latitude, zone.longitude]}
                  radius={zone.radius_m}
                  pathOptions={{
                    color: '#10b981',
                    fillColor: '#10b981',
                    fillOpacity: 0.18,
                    weight: 2,
                  }}
                />
              ))}

              {/* Current child position */}
              {latitude !== null && longitude !== null ? (
                <Marker position={[latitude, longitude]} />
              ) : null}
            </MapContainer>
          </div>
          <p className="mt-2 text-[11px] text-muted">
            Green circles mark family safe zones. The blue pin shows your real-time GPS fix.
          </p>
        </section>

        {/* Safe Zones List & Proximity */}
        <section className="space-y-4">
          <div className="rounded-2xl border border-edge bg-surface p-4">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-ink">
              <Shield size={16} className="text-accent" /> Monitored Safe Zones
            </h3>
            <p className="mt-1 text-xs text-muted">
              Automatic alert triggers managed by your parents.
            </p>

            <div className="mt-3 space-y-2">
              {zoneDistances.length === 0 ? (
                <div className="rounded-xl border border-edge-soft bg-surface-2/40 p-3 text-xs text-muted">
                  No safe zones configured yet. Ask parents to add Home or School in the Parent
                  portal.
                </div>
              ) : (
                zoneDistances.map((zone) => (
                  <div
                    key={zone.id}
                    className={`flex items-center justify-between rounded-xl border p-3 text-xs transition ${
                      zone.isInside
                        ? 'border-live/40 bg-live/10 text-ink'
                        : 'border-edge-soft bg-surface-2/40 text-body'
                    }`}
                  >
                    <div>
                      <div className="flex items-center gap-1.5 font-semibold">
                        {zone.isInside ? (
                          <CheckCircle2 size={14} className="text-live" />
                        ) : (
                          <MapPin size={14} className="text-muted" />
                        )}
                        <span>{zone.name}</span>
                      </div>
                      <p className="mt-0.5 text-[11px] text-muted">
                        Radius: {zone.radius_m} m
                        {zone.distanceM !== undefined ? ` · ${zone.distanceM} m away` : ''}
                      </p>
                    </div>

                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                        zone.isInside
                          ? 'border border-live/30 bg-live/20 text-live'
                          : 'border border-edge bg-surface text-muted'
                      }`}
                    >
                      {zone.isInside ? 'Inside' : 'Outside'}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Emergency SOS Hardware Guide */}
          <div className="rounded-2xl border border-danger/30 bg-danger/5 p-4">
            <div className="flex items-center gap-2">
              <span className="grid h-7 w-7 place-items-center rounded-lg bg-danger/20 text-danger">
                <AlertTriangle size={16} />
              </span>
              <h3 className="text-sm font-semibold text-ink">Hardware Emergency SOS</h3>
            </div>

            <p className="mt-2 text-xs leading-relaxed text-body">
              In an emergency, <strong>press and hold the physical button</strong> on your ESP32-C3
              tracker for <strong>2 seconds</strong>.
            </p>

            <div className="mt-3 rounded-xl border border-danger/20 bg-surface p-3 text-xs">
              <div className="flex items-center justify-between font-semibold">
                <span className="flex items-center gap-1.5 text-danger">
                  <Radio size={14} className="animate-pulse" /> Emergency Protocol
                </span>
                <span className="text-[10px] font-medium text-muted">GPIO Button</span>
              </div>
              <ul className="mt-2 list-disc space-y-1 pl-4 text-[11px] text-muted">
                <li>Immediate SOS flag sent with your live GPS coordinates.</li>
                <li>Instant Telegram alert pushed to all registered parents.</li>
                <li>Queued and retried automatically if Wi-Fi drops.</li>
              </ul>
            </div>

            {recentSosAlert ? (
              <div className="mt-3 flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/10 px-2.5 py-1.5 text-xs text-danger">
                <ShieldAlert size={14} />
                <span>
                  Recent SOS alert recorded ({formatRelative(recentSosAlert.occurred_at)})
                </span>
              </div>
            ) : (
              <div className="mt-3 flex items-center gap-2 text-[11px] text-muted">
                <CheckCircle2 size={13} className="text-live" />
                <span>SOS button active and ready on hardware pin.</span>
              </div>
            )}
          </div>
        </section>
      </div>

      {/* --- Technical Boundaries & Capabilities Disclosure ---------------- */}
      <section
        className="rounded-2xl border border-edge bg-surface p-4 sm:p-5"
        aria-label="Technical capabilities and backend boundaries"
      >
        <div className="flex items-center gap-2">
          <HelpCircle size={18} className="text-accent" />
          <h3 className="text-sm font-semibold text-ink">
            How Child Safe-Trip Works & Technical Boundaries
          </h3>
        </div>

        <div className="mt-3 grid gap-3 text-xs text-muted sm:grid-cols-2 md:grid-cols-4">
          <div className="rounded-xl border border-edge-soft bg-surface-2/30 p-3">
            <h4 className="font-semibold text-ink">Hardware-First Tracker</h4>
            <p className="mt-1 leading-relaxed">
              Autonomous ESP32-C3 and NEO-6M module streaming NMEA GPS fixes directly over Wi-Fi
              (HTTP JSON).
            </p>
          </div>

          <div className="rounded-xl border border-edge-soft bg-surface-2/30 p-3">
            <h4 className="font-semibold text-ink">No Child Web Login</h4>
            <p className="mt-1 leading-relaxed">
              No account, email, or password required for the child. The tracker is identified
              directly by device credentials.
            </p>
          </div>

          <div className="rounded-xl border border-edge-soft bg-surface-2/30 p-3">
            <h4 className="font-semibold text-ink">Automated 1-Way Alerts</h4>
            <p className="mt-1 leading-relaxed">
              Geofence and SOS alerts are pushed automatically to parents via Telegram. In-app
              two-way chat is not supported.
            </p>
          </div>

          <div className="rounded-xl border border-edge-soft bg-surface-2/30 p-3">
            <h4 className="font-semibold text-ink">Physical Button SOS</h4>
            <p className="mt-1 leading-relaxed">
              SOS is debounced and triggered via physical hardware button. Web-triggered SOS without
              device key is not supported.
            </p>
          </div>
        </div>
      </section>
    </main>
  )
}
