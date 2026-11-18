import { useEffect, useMemo, useState } from 'react'
import { Circle, MapContainer, Marker, TileLayer, Tooltip, useMapEvents } from 'react-leaflet'
import { Activity, Cpu, MapPin, Satellite, User, Wifi, WifiOff } from 'lucide-react'
import 'leaflet/dist/leaflet.css'

import { ApiError, CONFIGURED_DEVICE_ID, api } from '../services/api'
import { useParentSession } from '../hooks/useParentSession'
import { useShareLinks } from '../hooks/useShareLinks'
import { useGeofences } from '../hooks/useGeofences'
import { useAlerts } from '../hooks/useAlerts'
import { useDeviceStatus } from '../hooks/useDeviceStatus'
import MapAutoCenter from '../components/MapAutoCenter'
import StatTile from '../components/StatTile'
import { formatCoordinate, formatDateTime, formatRelative } from '../utils/format'
import { latestDevicePosition } from '../utils/geo'

function CentrePicker({ onPick }: { onPick: (latitude: number, longitude: number) => void }) {
  useMapEvents({ click: (event) => onPick(event.latlng.lat, event.latlng.lng) })
  return null
}

interface Props {
  onBackToDashboard?: () => void
}

export default function ParentPage({ onBackToDashboard }: Props) {
  const session = useParentSession()
  const logout = session.logout
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [register, setRegister] = useState(false)
  const [authError, setAuthError] = useState('')
  const [actionError, setActionError] = useState('')
  const [showAccountBox, setShowAccountBox] = useState(false)

  // Use active session token or default local parent session token
  const effectiveToken = session.token || 'parent-session'

  const {
    links,
    error: linksError,
    createShareLink,
    revokeShareLink,
  } = useShareLinks(effectiveToken)

  const {
    zones,
    error: zonesError,
    createGeofence,
    deleteGeofence,
  } = useGeofences(effectiveToken)

  const {
    alerts,
    error: alertsError,
  } = useAlerts(effectiveToken, 5000)

  const {
    status: deviceStatus,
  } = useDeviceStatus(CONFIGURED_DEVICE_ID)

  const [label, setLabel] = useState('Child')
  const [ttl, setTtl] = useState(24)
  const [url, setUrl] = useState('')
  const [name, setName] = useState('Home')
  const [lat, setLat] = useState('')
  const [lon, setLon] = useState('')
  const [radius, setRadius] = useState(150)
  const [chat, setChat] = useState('')
  const [zoneSaving, setZoneSaving] = useState(false)
  const [zoneFeedback, setZoneFeedback] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [chatSaving, setChatSaving] = useState(false)
  const [chatFeedback, setChatFeedback] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [testingTelegram, setTestingTelegram] = useState(false)
  const [testFeedback, setTestFeedback] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const parsedLat = lat.trim() !== '' && !isNaN(Number(lat)) ? Number(lat) : null
  const parsedLon = lon.trim() !== '' && !isNaN(Number(lon)) ? Number(lon) : null

  const trackerPos = useMemo(() => latestDevicePosition(deviceStatus), [deviceStatus])

  const autoCenterTarget = useMemo<[number, number] | null>(() => {
    if (zones[0]) return [zones[0].latitude, zones[0].longitude]
    if (trackerPos) return [trackerPos.latitude, trackerPos.longitude]
    return null
  }, [zones, trackerPos])

  const mapCenter: [number, number] =
    parsedLat !== null && parsedLon !== null
      ? [parsedLat, parsedLon]
      : autoCenterTarget ?? [18.5204, 73.8567]

  useEffect(() => {
    let active = true
    api.parentMe(effectiveToken)
      .then((me) => {
        if (active && me.telegram_chat_id) {
          setChat(me.telegram_chat_id)
        }
      })
      .catch((cause) => {
        if (cause instanceof ApiError && cause.status === 401 && session.token) {
          logout()
        }
      })
    return () => {
      active = false
    }
  }, [effectiveToken, session.token, logout])

  const authenticate = async () => {
    setAuthError('')
    try {
      await (register ? session.register(email, password) : session.login(email, password))
      setShowAccountBox(false)
    } catch (cause) {
      setAuthError(cause instanceof Error ? cause.message : String(cause))
    }
  }

  const displayedError = actionError || linksError || zonesError || alertsError
  const device = deviceStatus?.device ?? null
  const isOnline = Boolean(deviceStatus?.connected)
  const latestPoint = deviceStatus?.latest_point ?? null

  return (
    <main className="mx-auto max-w-4xl space-y-5 p-4 sm:p-6" aria-label="Parent Portal">
      {/* --- Header ---------------------------------------------------- */}
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-edge pb-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-ink">Family Safe-Trip · Parent Portal</h1>
          <p className="text-xs text-muted">
            Manage device safety, live share links, safe zones, and emergency alerts
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {onBackToDashboard ? (
            <button
              type="button"
              onClick={onBackToDashboard}
              className="rounded-lg border border-edge bg-surface px-3 py-1.5 text-xs font-medium text-body transition hover:bg-surface-2"
            >
              Dashboard
            </button>
          ) : null}

          <button
            type="button"
            onClick={() => setShowAccountBox(!showAccountBox)}
            className="flex items-center gap-1.5 rounded-lg border border-edge bg-surface px-3 py-1.5 text-xs font-medium text-body transition hover:border-accent/40"
          >
            <User size={13} />
            {session.parent?.email ? session.parent.email : 'Account'}
          </button>

          {session.token ? (
            <button
              type="button"
              onClick={logout}
              className="rounded-lg border border-edge bg-surface px-3 py-1.5 text-xs font-medium text-muted transition hover:text-ink"
            >
              Sign out
            </button>
          ) : null}
        </div>
      </header>

      {/* --- Optional Account Modal / Panel (Never a blocking screen) ---- */}
      {showAccountBox && (
        <section className="rounded-xl border border-accent/30 bg-surface p-4 shadow-sm" aria-label="Account management">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-ink">
              {session.token ? 'Parent Account Connected' : 'Connect Parent Cloud Account'}
            </h2>
            <button
              type="button"
              onClick={() => setShowAccountBox(false)}
              className="text-xs text-muted hover:text-ink"
            >
              Close
            </button>
          </div>
          <p className="mt-1 text-xs text-muted">
            {session.token
              ? `Signed in as ${session.parent?.email ?? 'Parent'}. Your links and zones are synced with the server.`
              : 'Sign in or register below to sync safe zones and share links with the backend database.'}
          </p>

          {!session.token ? (
            <div className="mt-3 space-y-2">
              <input
                className="w-full rounded border border-edge bg-surface-2/60 p-2 text-xs"
                type="email"
                placeholder="Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
              <input
                className="w-full rounded border border-edge bg-surface-2/60 p-2 text-xs"
                type="password"
                placeholder="Password (8 characters minimum)"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              {authError && <p role="alert" className="text-xs text-danger">{authError}</p>}
              <div className="flex items-center gap-2 pt-1">
                <button
                  type="button"
                  className="rounded bg-accent px-3 py-1.5 text-xs font-medium text-white transition hover:bg-accent/90"
                  onClick={() => void authenticate()}
                >
                  {register ? 'Create account' : 'Sign in'}
                </button>
                <button
                  type="button"
                  className="text-xs underline text-muted hover:text-ink"
                  onClick={() => setRegister(!register)}
                >
                  {register ? 'Sign in instead' : 'Create new account'}
                </button>
              </div>
            </div>
          ) : null}
        </section>
      )}

      {displayedError && <p role="alert" className="rounded-lg border border-danger/30 bg-danger/10 p-2.5 text-xs text-danger">{displayedError}</p>}

      {/* --- Device status card ----------------------------------------- */}
      <section className="rounded-xl border border-edge bg-surface p-4" aria-label="Device status">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {isOnline ? (
              <Wifi size={18} className="text-live" />
            ) : (
              <WifiOff size={18} className="text-muted" />
            )}
            <h2 className="font-semibold text-ink">Device status</h2>
          </div>
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
              isOnline
                ? 'border border-live/30 bg-live/10 text-live'
                : 'border border-edge bg-surface-2 text-muted'
            }`}
          >
            {isOnline ? 'Online · Live' : 'Offline'}
          </span>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
          <StatTile
            label="Device"
            value={device?.device_id ?? CONFIGURED_DEVICE_ID}
            hint={device?.firmware_version ? `firmware ${device.firmware_version}` : 'tracker'}
            icon={<Cpu size={12} />}
            tone={isOnline ? 'live' : 'muted'}
          />
          <StatTile
            label="GPS fix"
            value={isOnline && trackerPos ? 'FIX ACQUIRED' : trackerPos ? 'LAST KNOWN' : 'WAITING'}
            hint={
              trackerPos
                ? `${trackerPos.satellites ?? '—'} satellites`
                : 'no position fix'
            }
            icon={<Satellite size={12} />}
            tone={isOnline && trackerPos ? 'live' : trackerPos ? 'muted' : 'warn'}
          />
          <StatTile
            label="Coordinates"
            value={
              trackerPos
                ? `${formatCoordinate(trackerPos.latitude, 4)}, ${formatCoordinate(trackerPos.longitude, 4)}`
                : '—'
            }
            hint="latitude, longitude (WGS84)"
            icon={<MapPin size={12} />}
            mono
          />
          <StatTile
            label="Latest GPS update"
            value={formatRelative(trackerPos?.timestamp ?? latestPoint?.server_timestamp ?? device?.last_seen_at)}
            hint={
              trackerPos?.timestamp ?? latestPoint?.server_timestamp ?? device?.last_seen_at
                ? formatDateTime(trackerPos?.timestamp ?? latestPoint?.server_timestamp ?? device?.last_seen_at)
                : 'no updates yet'
            }
            icon={<Activity size={12} />}
          />
        </div>
      </section>

      {/* --- Share live location ----------------------------------------- */}
      <section className="rounded-xl border border-edge bg-surface p-4">
        <h2 className="font-semibold text-ink">Share live location</h2>
        <p className="mt-1 text-xs text-muted">Generate secure, time-limited live links for family members or caregivers.</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <input
            className="rounded border border-edge bg-surface-2/60 p-2 text-xs"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            aria-label="Child label"
          />
          <select
            className="rounded border border-edge bg-surface-2/60 p-2 text-xs"
            value={ttl}
            onChange={(e) => setTtl(Number(e.target.value))}
          >
            <option value={24}>24 hours</option>
            <option value={72}>3 days</option>
            <option value={168}>7 days</option>
          </select>
          <button
            className="rounded bg-accent px-3 py-2 text-xs font-medium text-white transition hover:bg-accent/90"
            onClick={async () => {
              setActionError('')
              try {
                const result = await createShareLink({
                  device_id: CONFIGURED_DEVICE_ID,
                  label,
                  ttl_hours: ttl,
                })
                setUrl(result.url)
              } catch (cause) {
                setActionError(cause instanceof Error ? cause.message : String(cause))
              }
            }}
          >
            Create link
          </button>
        </div>
        {url && (
          <p className="mt-2 break-all text-xs">
            <a href={url} className="text-accent underline">{url}</a>
            <button
              className="ml-2 underline text-muted hover:text-ink"
              onClick={() => void navigator.clipboard.writeText(url)}
            >
              Copy
            </button>
          </p>
        )}
        {links.map((item) => (
          <p key={item.id} className="mt-2 text-xs">
            {item.label} · expires {new Date(item.expires_at).toLocaleString()}{' '}
            <button
              className="ml-2 underline text-muted hover:text-danger"
              onClick={async () => {
                setActionError('')
                try {
                  await revokeShareLink(item.id)
                } catch (cause) {
                  setActionError(cause instanceof Error ? cause.message : String(cause))
                }
              }}
            >
              Revoke
            </button>
          </p>
        ))}
      </section>

      {/* --- Safe zones -------------------------------------------------- */}
      <section className="rounded-xl border border-edge bg-surface p-4">
        <h2 className="font-semibold text-ink">Safe zones</h2>
        <p className="mt-1 text-sm text-muted">Click the map to choose a zone centre.</p>
        <div className="my-3 h-56 overflow-hidden rounded-lg border border-edge-soft sm:h-72">
          <MapContainer center={mapCenter} zoom={13} className="h-full w-full">
            <TileLayer
              attribution="&copy; OpenStreetMap"
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <MapAutoCenter target={autoCenterTarget} />
            <CentrePicker
              onPick={(a, b) => {
                setLat(a.toFixed(6))
                setLon(b.toFixed(6))
              }}
            />

            {/* Highlight all existing saved safe zones */}
            {zones.map((item) => (
              <Circle
                key={item.id}
                center={[item.latitude, item.longitude]}
                radius={item.radius_m}
                pathOptions={{
                  color: item.active ? '#10b981' : '#94a3b8',
                  fillColor: item.active ? '#10b981' : '#94a3b8',
                  fillOpacity: 0.22,
                  weight: 2,
                }}
              >
                <Tooltip permanent direction="top" opacity={0.9} className="font-semibold text-xs">
                  {item.name} ({item.radius_m}m)
                </Tooltip>
              </Circle>
            ))}

            {/* Highlight live preview circle for the zone being picked or created */}
            {parsedLat !== null && parsedLon !== null ? (
              <>
                <Circle
                  center={[parsedLat, parsedLon]}
                  radius={radius}
                  pathOptions={{
                    color: '#3b82f6',
                    fillColor: '#3b82f6',
                    fillOpacity: 0.25,
                    dashArray: '4, 6',
                    weight: 2,
                  }}
                >
                  <Tooltip permanent direction="bottom" opacity={0.9} className="font-semibold text-xs">
                    Preview: {name || 'New Zone'} ({radius}m)
                  </Tooltip>
                </Circle>
                <Marker position={[parsedLat, parsedLon]} />
              </>
            ) : null}

            {/* Child tracker current location marker if available */}
            {trackerPos ? (
              <Marker position={[trackerPos.latitude, trackerPos.longitude]}>
                <Tooltip direction="right" opacity={0.9} className="text-xs">
                  Tracker: {device?.device_id ?? CONFIGURED_DEVICE_ID}
                </Tooltip>
              </Marker>
            ) : null}
          </MapContainer>
        </div>
        <div className="mb-3 flex flex-wrap items-center gap-4 text-[11px] text-muted">
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-live" />
            Active Safe Zone
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full border border-dashed border-accent bg-accent/30" />
            Creating / Preview Zone
          </span>
          {trackerPos ? (
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-blue-600" />
              Tracker Fix ({device?.device_id ?? CONFIGURED_DEVICE_ID})
            </span>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            className="rounded border border-edge bg-surface-2/60 p-2 text-xs"
            value={name}
            onChange={(e) => setName(e.target.value)}
            aria-label="Zone name"
          />
          <input
            className="w-28 rounded border border-edge bg-surface-2/60 p-2 text-xs"
            type="number"
            placeholder="Latitude"
            value={lat}
            onChange={(e) => setLat(e.target.value)}
          />
          <input
            className="w-28 rounded border border-edge bg-surface-2/60 p-2 text-xs"
            type="number"
            placeholder="Longitude"
            value={lon}
            onChange={(e) => setLon(e.target.value)}
          />
          <label className="text-xs text-muted">
            Radius {radius} m
            <input
              type="range"
              min="50"
              max="1000"
              step="10"
              value={radius}
              onChange={(e) => setRadius(Number(e.target.value))}
              className="ml-2 accent-accent align-middle"
            />
          </label>
          <button
            disabled={zoneSaving}
            className="rounded bg-accent px-4 py-2 text-xs font-medium text-white transition hover:bg-accent/90 disabled:opacity-50"
            onClick={async () => {
              setZoneFeedback(null)
              setActionError('')
              if (parsedLat === null || parsedLon === null) {
                setZoneFeedback({
                  type: 'error',
                  text: 'Please click the map above to choose a zone centre, or enter Latitude and Longitude.',
                })
                return
              }
              const zoneName = name.trim() || 'Safe Zone'
              setZoneSaving(true)
              try {
                await createGeofence({
                  device_id: CONFIGURED_DEVICE_ID,
                  name: zoneName,
                  latitude: parsedLat,
                  longitude: parsedLon,
                  radius_m: radius,
                })
                setZoneFeedback({
                  type: 'success',
                  text: `✓ Safe zone "${zoneName}" (${radius}m) saved successfully!`,
                })
                setLat('')
                setLon('')
              } catch (cause) {
                const msg = cause instanceof Error ? cause.message : String(cause)
                setZoneFeedback({ type: 'error', text: msg })
                setActionError(msg)
              } finally {
                setZoneSaving(false)
              }
            }}
          >
            {zoneSaving ? 'Adding...' : 'Add zone'}
          </button>
        </div>

        {/* Immediate Safe Zone Inline Feedback */}
        {zoneFeedback && (
          <div
            className={`mt-2.5 rounded-lg p-2.5 text-xs font-medium ${
              zoneFeedback.type === 'success'
                ? 'border border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
                : 'border border-danger/30 bg-danger/10 text-danger'
            }`}
          >
            {zoneFeedback.text}
          </div>
        )}

        {/* List of Active Safe Zones */}
        <div className="mt-3 divide-y divide-edge-soft">
          {zones.map((item) => (
            <div key={item.id} className="flex items-center justify-between py-2 text-xs">
              <div>
                <span className="font-semibold text-ink">{item.name}</span>
                <span className="ml-2 text-muted">
                  · Radius {item.radius_m}m · ({item.latitude.toFixed(5)}, {item.longitude.toFixed(5)})
                </span>
              </div>
              <button
                className="rounded px-2 py-1 text-xs text-muted hover:bg-danger/10 hover:text-danger transition"
                onClick={async () => {
                  setActionError('')
                  try {
                    await deleteGeofence(item.id)
                  } catch (cause) {
                    setActionError(cause instanceof Error ? cause.message : String(cause))
                  }
                }}
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* --- Alerts ------------------------------------------------------ */}
      <section className="rounded-xl border border-edge bg-surface p-4">
        <h2 className="font-semibold text-ink">Alerts</h2>
        <p className="mt-1 text-xs text-muted">Arrivals, departures, and emergency SOS alerts.</p>
        <div className="mt-2 space-y-1.5">
          {alerts.length === 0 ? (
            <p className="text-xs text-muted">No alert events recorded.</p>
          ) : (
            alerts.map((item) => (
              <p key={item.id} className="text-xs">
                {item.type} · {item.message} · {new Date(item.occurred_at).toLocaleString()}
              </p>
            ))
          )}
        </div>
      </section>

      {/* --- Telegram notifications -------------------------------------- */}
      <section className="rounded-xl border border-edge bg-surface p-4">
        <h2 className="font-semibold text-ink">Telegram notifications</h2>
        <p className="mt-1 text-xs text-muted">
          Receive instant push alerts on Telegram when your child enters or leaves safe zones, or presses the SOS button.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <input
            className="w-48 rounded border border-edge bg-surface-2/60 p-2 text-xs font-mono"
            placeholder="e.g. 5831286566"
            value={chat}
            onChange={(e) => {
              setChat(e.target.value)
              setChatFeedback(null)
            }}
          />
          <button
            disabled={chatSaving}
            className="rounded bg-accent px-4 py-2 text-xs font-medium text-white transition hover:bg-accent/90 disabled:opacity-50"
            onClick={async () => {
              setChatSaving(true)
              setChatFeedback(null)
              setTestFeedback(null)
              setActionError('')
              try {
                await api.updateParentMe(effectiveToken, chat.trim() || null)
                setChatFeedback({
                  type: 'success',
                  text: chat.trim() ? `✓ Telegram Chat ID "${chat.trim()}" saved!` : '✓ Telegram Chat ID cleared.',
                })
              } catch (cause) {
                const msg = cause instanceof Error ? cause.message : String(cause)
                setChatFeedback({ type: 'error', text: msg })
                setActionError(msg)
              } finally {
                setChatSaving(false)
              }
            }}
          >
            {chatSaving ? 'Saving...' : 'Save'}
          </button>

          <button
            disabled={testingTelegram}
            type="button"
            className="rounded border border-edge bg-surface-2 px-3 py-2 text-xs font-medium text-ink transition hover:bg-surface-3 disabled:opacity-50"
            onClick={async () => {
              setTestingTelegram(true)
              setTestFeedback(null)
              try {
                const res = await api.testTelegram(effectiveToken, chat.trim() || undefined)
                setTestFeedback({ type: 'success', text: `✓ ${res.message}` })
              } catch (cause) {
                const msg = cause instanceof Error ? cause.message : String(cause)
                setTestFeedback({ type: 'error', text: msg })
              } finally {
                setTestingTelegram(false)
              }
            }}
          >
            {testingTelegram ? 'Sending test...' : 'Send test alert'}
          </button>
        </div>

        {/* Feedback alerts */}
        {chatFeedback && (
          <div
            className={`mt-2.5 rounded-lg p-2.5 text-xs font-medium ${
              chatFeedback.type === 'success'
                ? 'border border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
                : 'border border-danger/30 bg-danger/10 text-danger'
            }`}
          >
            {chatFeedback.text}
          </div>
        )}

        {testFeedback && (
          <div
            className={`mt-2 rounded-lg p-2.5 text-xs font-medium ${
              testFeedback.type === 'success'
                ? 'border border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
                : 'border border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300'
            }`}
          >
            {testFeedback.text}
          </div>
        )}

        <div className="mt-4 rounded-lg border border-edge-soft bg-surface-2/40 p-3 text-xs text-muted space-y-1">
          <p className="font-semibold text-ink">How to connect Telegram:</p>
          <ol className="list-decimal pl-4 space-y-1">
            <li>Open Telegram and search for <strong className="text-ink">@BotFather</strong>.</li>
            <li>Send <code className="rounded bg-surface-3 px-1 py-0.5 font-mono text-[11px]">/newbot</code> and follow instructions to get your bot token.</li>
            <li>Add the token in <code className="rounded bg-surface-3 px-1 py-0.5 font-mono text-[11px]">backend/.env</code> as <code className="font-mono text-[11px]">GEOSKETCH_TELEGRAM_BOT_TOKEN=...</code></li>
            <li>Open your newly created bot in Telegram and click <strong className="text-ink">START</strong> (or send /start).</li>
            <li>Get your personal Chat ID by messaging <strong className="text-ink">@userinfobot</strong> on Telegram.</li>
            <li>Enter your Chat ID above and click <strong className="text-ink">Save</strong>!</li>
          </ol>
        </div>
      </section>
    </main>
  )
}
