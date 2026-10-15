import {
  Activity,
  Cpu,
  Gauge,
  MapPin,
  RadioTower,
  Route,
  Satellite,
  Timer,
  Wifi,
  WifiOff,
} from 'lucide-react'

import StatTile from './StatTile'
import type { DeviceStatus, JourneyDetail, JourneyStatistics } from '../types'
import {
  formatCoordinate,
  formatCount,
  formatDateTime,
  formatDistance,
  formatDuration,
  formatRelative,
  formatSpeed,
  statusLabel,
} from '../utils/format'

interface Props {
  status: DeviceStatus | null
  journey: JourneyDetail | null
  statistics: JourneyStatistics | null
}

export default function StatusPanel({ status, journey, statistics }: Props) {
  const device = status?.device ?? null
  const isLive = Boolean(status?.connected)
  const latest = status?.latest_point ?? null
  const point = journey?.points.length ? journey.points[journey.points.length - 1] : latest

  const isDemo = journey?.source === 'demo'

  return (
    <div className="space-y-4">
      {/* --- connection banner: live vs last known ------------------------- */}
      <div
        className={`flex items-start gap-3 rounded-xl border px-3.5 py-3 ${
          isLive
            ? 'border-live/40 bg-live/10'
            : 'border-edge bg-surface-2/60'
        }`}
      >
        <span className="mt-0.5">
          {isLive ? <Wifi size={18} className="text-live" /> : <WifiOff size={18} className="text-muted" />}
        </span>
        <div className="min-w-0">
          <p className={`text-sm font-semibold ${isLive ? 'text-live' : 'text-slate-200'}`}>
            {isLive ? 'ESP32-C3 connected — live GPS data' : 'Tracker not reporting'}
          </p>
          <p className="mt-0.5 text-[11px] leading-snug text-muted">
            {isLive
              ? `Last point ${formatRelative(device?.last_seen_at)} · device ${device?.device_id}`
              : `Last successful update ${
                  device?.last_seen_at ? formatDateTime(device.last_seen_at) : 'never'
                }${device?.last_seen_at ? ` (${formatRelative(device.last_seen_at)})` : ''}. ${
                  point ? 'The position shown below is the last known one.' : ''
                }`}
          </p>
        </div>
      </div>

      {/* --- device + GPS -------------------------------------------------- */}
      <div className="grid grid-cols-2 gap-2.5">
        <StatTile
          label="Device"
          value={device?.device_id ?? '—'}
          hint={device?.firmware_version ? `firmware ${device.firmware_version}` : 'no firmware reported'}
          icon={<Cpu size={12} />}
          tone={isLive ? 'live' : 'muted'}
        />
        <StatTile
          label="GPS fix"
          value={isDemo ? 'SIMULATED' : point ? 'FIX ACQUIRED' : 'WAITING'}
          hint={
            isDemo
              ? 'demo data — no hardware involved'
              : point
                ? `last point ${point.sequence} · ${point.satellites ?? '—'} satellites`
                : 'no valid fix received yet'
          }
          icon={<Satellite size={12} />}
          tone={isDemo ? 'demo' : point ? 'live' : 'warn'}
        />
        <StatTile
          label="Latitude"
          value={formatCoordinate(point?.latitude)}
          hint="decimal degrees (WGS84)"
          icon={<MapPin size={12} />}
          mono
        />
        <StatTile
          label="Longitude"
          value={formatCoordinate(point?.longitude)}
          hint={
            point?.altitude !== null && point?.altitude !== undefined
              ? `altitude ${point.altitude.toFixed(0)} m`
              : 'altitude unavailable'
          }
          icon={<MapPin size={12} />}
          mono
        />
        <StatTile
          label="Latest GPS update"
          value={formatRelative(point?.server_timestamp)}
          hint={point ? formatDateTime(point.server_timestamp) : 'no updates yet'}
          icon={<Activity size={12} />}
        />
        <StatTile
          label="Recording"
          value={journey ? statusLabel(journey.status) : 'IDLE'}
          hint={journey ? `journey #${journey.id}` : 'press Start recording'}
          icon={<RadioTower size={12} />}
          tone={journey?.status === 'recording' ? 'live' : 'default'}
        />
      </div>

      {/* --- journey statistics ------------------------------------------- */}
      <div className="rounded-xl border border-edge bg-surface-2/50 p-3">
        <div className="flex items-center justify-between">
          <h3 className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-muted">
            <Route size={12} /> Journey statistics
          </h3>
          {statistics?.is_estimate ? (
            <span className="rounded-full border border-edge px-2 py-0.5 text-[10px] text-muted">
              GPS estimate
            </span>
          ) : null}
        </div>

        <div className="mt-2.5 grid grid-cols-2 gap-2.5">
          <StatTile
            label="Total distance"
            value={formatDistance(statistics?.distance_m ?? journey?.total_distance_m)}
            icon={<Route size={12} />}
          />
          <StatTile
            label="Duration"
            value={formatDuration(statistics?.duration_seconds ?? journey?.duration_seconds)}
            hint={
              statistics?.moving_seconds
                ? `${formatDuration(statistics.moving_seconds)} moving`
                : 'waiting for movement'
            }
            icon={<Timer size={12} />}
          />
          <StatTile
            label="Average speed"
            value={formatSpeed(statistics?.average_speed_kmh)}
            hint="over moving time only"
            icon={<Gauge size={12} />}
          />
          <StatTile
            label="GPS points"
            value={formatCount(statistics?.total_points ?? journey?.point_count ?? 0)}
            hint={
              statistics
                ? `${statistics.used_points} used · ${statistics.filtered_points} filtered · ${
                    statistics.gap_count
                  } gap(s)`
                : 'no points recorded'
            }
            icon={<Activity size={12} />}
          />
        </div>

        <p className="mt-2.5 text-[10px] leading-snug text-muted">
          Distance is computed with the haversine formula over accepted fixes. It is an estimate
          and differs from the true walked distance because of satellite noise, filtering and
          recording gaps.
        </p>
      </div>
    </div>
  )
}
