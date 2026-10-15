import { useEffect, useMemo, useRef, useState } from 'react'
import {
  CircleMarker,
  MapContainer,
  Marker,
  Polyline,
  TileLayer,
  Tooltip,
  ZoomControl,
  useMap,
} from 'react-leaflet'
import L from 'leaflet'
import { Compass, Crosshair } from 'lucide-react'

import type { GPSPoint, RouteSegment } from '../types'
import { buildDirectionArrows, buildRouteSegments, routeBounds } from '../utils/geo'
import { formatCoordinate, formatRelative, formatTime } from '../utils/format'

const TILE_URL = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
const TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'

const ROUTE_COLOR = '#38bdf8'
const ROUTE_GLOW = '#0ea5e9'

interface Props {
  points: GPSPoint[]
  latestPoint: GPSPoint | null
  /** True only when the device reported a point recently. */
  isLive: boolean
  lastSeenAt: string | null
  heightClass?: string
  showRejected?: boolean
}

/**
 * Fit the view once when data first arrives, and again whenever the user presses
 * "Fit route" (the signal counter changes). New fixes do not steal the view while
 * recording, which would fight the user's own zoom and pan.
 */
function FitRoute({
  bounds,
  signal,
}: {
  bounds: [[number, number], [number, number]] | null
  signal: number
}) {
  const map = useMap()
  const hasFitted = useRef(false)
  const lastSignal = useRef(signal)

  useEffect(() => {
    if (!bounds) {
      return
    }
    const signalChanged = signal !== lastSignal.current
    lastSignal.current = signal
    if (hasFitted.current && !signalChanged) {
      return
    }
    hasFitted.current = true
    map.fitBounds(L.latLngBounds(bounds), { padding: [46, 46], maxZoom: 17, animate: true })
  }, [bounds, signal, map])

  return null
}

function arrowIcon(bearing: number): L.DivIcon {
  return L.divIcon({
    className: 'route-arrow',
    iconSize: [16, 16],
    iconAnchor: [8, 8],
    html: `<svg width="16" height="16" viewBox="0 0 16 16" style="transform: rotate(${bearing.toFixed(1)}deg)">
             <path d="M8 1 L13 14 L8 11 L3 14 Z" fill="#e0f2fe" opacity="0.9"
                   stroke="#0b1120" stroke-width="0.7" stroke-linejoin="round"/>
           </svg>`,
  })
}

function latestIcon(isLive: boolean): L.DivIcon {
  return L.divIcon({
    className: 'live-marker',
    iconSize: [16, 16],
    iconAnchor: [8, 8],
    html: `<div style="position:relative">
             ${isLive ? '<span class="pulse"></span>' : ''}
             <div class="dot ${isLive ? '' : 'stale'}"></div>
           </div>`,
  })
}

export default function RouteMap({
  points,
  latestPoint,
  isLive,
  lastSeenAt,
  heightClass = 'h-[420px] lg:h-full',
  showRejected = false,
}: Props) {
  const segments: RouteSegment[] = useMemo(() => buildRouteSegments(points), [points])
  const bounds = useMemo(() => routeBounds(points), [points])
  const arrows = useMemo(() => buildDirectionArrows(segments), [segments])
  const rejected = useMemo(
    () => points.filter((point) => point.is_plausible === false),
    [points],
  )
  const drawable = useMemo(() => points.filter((point) => point.is_plausible !== false), [points])
  const firstPoint = drawable.length ? drawable[0] : null
  const endPoint = drawable.length ? drawable[drawable.length - 1] : null

  const [fitSignal, setFitSignal] = useState(0)

  const center: [number, number] = latestPoint
    ? [latestPoint.latitude, latestPoint.longitude]
    : bounds
      ? [(bounds[0][0] + bounds[1][0]) / 2, (bounds[0][1] + bounds[1][1]) / 2]
      : [18.5204, 73.8567]

  return (
    <div
      className={`relative overflow-hidden rounded-2xl border border-edge bg-surface ${heightClass}`}
    >
      <MapContainer
        center={center}
        zoom={14}
        zoomControl={false}
        preferCanvas
        className="h-full w-full"
      >
        <TileLayer url={TILE_URL} attribution={TILE_ATTRIBUTION} subdomains="abcd" maxZoom={19} />
        <ZoomControl position="bottomright" />
        <FitRoute bounds={bounds} signal={fitSignal} />

        {/* Soft glow under the track so it reads clearly on dark tiles. */}
        {segments.map((segment, index) => (
          <Polyline
            key={`glow-${index}`}
            positions={segment.positions}
            pathOptions={{ color: ROUTE_GLOW, weight: 11, opacity: 0.18, lineCap: 'round' }}
          />
        ))}
        {segments.map((segment, index) => (
          <Polyline
            key={`route-${index}`}
            positions={segment.positions}
            pathOptions={{ color: ROUTE_COLOR, weight: 4, opacity: 0.95, lineCap: 'round' }}
          />
        ))}

        {arrows.map((arrow) => (
          <Marker
            key={arrow.key}
            position={arrow.position}
            icon={arrowIcon(arrow.bearing)}
            interactive={false}
          />
        ))}

        {firstPoint && (
          <CircleMarker
            center={[firstPoint.latitude, firstPoint.longitude]}
            radius={8}
            pathOptions={{ color: '#ffffff', weight: 2, fillColor: '#22c55e', fillOpacity: 1 }}
          >
            <Tooltip direction="top">
              Start · {formatTime(firstPoint.gps_timestamp ?? firstPoint.server_timestamp)}
            </Tooltip>
          </CircleMarker>
        )}

        {endPoint && endPoint.id !== firstPoint?.id && (
          <CircleMarker
            center={[endPoint.latitude, endPoint.longitude]}
            radius={8}
            pathOptions={{ color: '#ffffff', weight: 2, fillColor: '#ef4444', fillOpacity: 1 }}
          >
            <Tooltip direction="top">
              End · {formatTime(endPoint.gps_timestamp ?? endPoint.server_timestamp)}
            </Tooltip>
          </CircleMarker>
        )}

        {showRejected &&
          rejected.map((point) => (
            <CircleMarker
              key={`rejected-${point.id}`}
              center={[point.latitude, point.longitude]}
              radius={5}
              pathOptions={{
                color: '#f59e0b',
                weight: 2,
                fillColor: '#0b1120',
                fillOpacity: 0.9,
                dashArray: '2 2',
              }}
            >
              <Tooltip direction="top">
                Rejected fix ({point.rejected_reason ?? 'filtered'}) · never drawn
              </Tooltip>
            </CircleMarker>
          ))}

        {latestPoint && (
          <Marker
            position={[latestPoint.latitude, latestPoint.longitude]}
            icon={latestIcon(isLive)}
            zIndexOffset={1000}
          >
            <Tooltip direction="top" offset={[0, -10]}>
              <span className="font-semibold">
                {isLive ? 'Live position' : 'Last known position'}
              </span>
              <br />
              {formatCoordinate(latestPoint.latitude)}, {formatCoordinate(latestPoint.longitude)}
              <br />
              {isLive ? 'updated ' : 'received '}
              {formatRelative(latestPoint.server_timestamp)}
            </Tooltip>
          </Marker>
        )}
      </MapContainer>

      {/* Legend and fit control kept as plain HTML so they never fight Leaflet. */}
      <div className="pointer-events-none absolute left-3 top-3 z-[500] flex flex-col gap-2">
        <div className="pointer-events-auto rounded-xl border border-edge bg-surface/85 px-3 py-2 backdrop-blur">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-muted">
            <Compass size={13} className="text-accent" /> Route legend
          </div>
          <ul className="mt-1.5 space-y-1 text-[11px] text-slate-300">
            <li className="flex items-center gap-2">
              <span className="h-1.5 w-6 rounded-full bg-accent" /> recorded track
            </li>
            <li className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full border border-white bg-live" /> start
            </li>
            <li className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full border border-white bg-danger" /> end
            </li>
            <li className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full border border-white bg-slate-500" /> last known
            </li>
          </ul>
          <p className="mt-1.5 max-w-[190px] text-[10px] leading-tight text-muted">
            {segments.length > 1
              ? `${segments.length} segments — gaps and rejected jumps are never joined.`
              : 'Single continuous segment.'}
          </p>
        </div>

        <button
          type="button"
          onClick={() => setFitSignal((value) => value + 1)}
          className="pointer-events-auto flex items-center gap-1.5 rounded-lg border border-edge bg-surface/85 px-2.5 py-1.5 text-[11px] font-medium text-slate-200 backdrop-blur transition hover:border-accent/60 hover:text-white"
        >
          <Crosshair size={13} /> Fit route
        </button>
      </div>

      {points.length === 0 && (
        <div className="pointer-events-none absolute inset-0 z-[400] flex items-center justify-center">
          <div className="rounded-xl border border-edge bg-surface/80 px-4 py-3 text-center backdrop-blur">
            <p className="text-sm font-medium text-slate-200">No GPS points yet</p>
            <p className="mt-1 max-w-xs text-xs text-muted">
              Start recording and carry the ESP32-C3 outdoors, or load a DEMO MODE sample route.
            </p>
          </div>
        </div>
      )}

      <div className="pointer-events-none absolute bottom-3 left-3 z-[500] rounded-lg border border-edge bg-surface/85 px-2.5 py-1 text-[10px] text-muted backdrop-blur">
        {isLive ? (
          <span className="text-live">● live</span>
        ) : (
          <span>◦ last update {formatRelative(lastSeenAt)}</span>
        )}
      </div>
    </div>
  )
}
