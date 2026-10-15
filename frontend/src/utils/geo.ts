/**
 * Geometry helpers for the map.
 *
 * Break detection mirrors the backend's segmentation so the drawn route and the
 * reported statistics always agree:
 *   - keep the recorded chronological order,
 *   - drop rejected (implausible) fixes,
 *   - start a new segment after a recording gap or an impossible jump,
 *   - never draw a straight line across a break.
 */

import type { GPSPoint, RouteSegment } from '../types'

export const EARTH_RADIUS_M = 6371008.8

export interface SegmentOptions {
  /** A time gap longer than this starts a new segment (seconds). */
  maxGapSeconds?: number
  /** An implied speed above this starts a new segment (km/h). */
  maxPlausibleSpeedKmh?: number
}

export function haversineMeters(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number,
): number {
  const toRad = Math.PI / 180
  const phi1 = lat1 * toRad
  const phi2 = lat2 * toRad
  const dPhi = (lat2 - lat1) * toRad
  const dLambda = (lon2 - lon1) * toRad
  const a =
    Math.sin(dPhi / 2) ** 2 + Math.cos(phi1) * Math.cos(phi2) * Math.sin(dLambda / 2) ** 2
  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(Math.max(0, a))))
}

function pointTime(point: GPSPoint): number | null {
  const raw = point.gps_timestamp ?? point.server_timestamp
  if (!raw) {
    return null
  }
  const value = new Date(raw).getTime()
  return Number.isNaN(value) ? null : value
}

export function isDrawable(point: GPSPoint): boolean {
  if (point.is_plausible === false) {
    return false
  }
  const { latitude, longitude } = point
  if (Number.isNaN(latitude) || Number.isNaN(longitude)) {
    return false
  }
  if (Math.abs(latitude) > 90 || Math.abs(longitude) > 180) {
    return false
  }
  // 0,0 means the module had no fix; it must never be drawn.
  return !(Math.abs(latitude) < 1e-7 && Math.abs(longitude) < 1e-7)
}

/** Split recorded points into map segments (chronological, break aware). */
export function buildRouteSegments(
  points: GPSPoint[],
  options: SegmentOptions = {},
): RouteSegment[] {
  const maxGapSeconds = options.maxGapSeconds ?? 180
  const maxSpeed = options.maxPlausibleSpeedKmh ?? 200

  const usable = points
    .filter(isDrawable)
    .slice()
    .sort((a, b) => a.sequence - b.sequence)

  const segments: RouteSegment[] = []
  let current: [number, number][] = []

  usable.forEach((point, index) => {
    const position: [number, number] = [point.latitude, point.longitude]
    if (index === 0) {
      current = [position]
      return
    }

    const previous = usable[index - 1]
    const distance = haversineMeters(
      previous.latitude,
      previous.longitude,
      point.latitude,
      point.longitude,
    )
    const previousTime = pointTime(previous)
    const currentTime = pointTime(point)
    const delta = previousTime !== null && currentTime !== null ? (currentTime - previousTime) / 1000 : null

    let isBreak = false
    if (delta !== null && delta > maxGapSeconds) {
      isBreak = true
    } else if (delta !== null && delta > 0) {
      const impliedSpeed = (distance / delta) * 3.6
      if (impliedSpeed > maxSpeed) {
        isBreak = true
      }
    }

    if (isBreak) {
      if (current.length >= 2) {
        segments.push({ positions: current, afterBreak: segments.length > 0 })
      }
      current = [position]
    } else {
      current.push(position)
    }
  })

  if (current.length >= 2) {
    segments.push({ positions: current, afterBreak: segments.length > 0 })
  }

  return segments
}

/** Total haversine distance of the drawable points, in metres. */
export function routeDistance(points: GPSPoint[]): number {
  const usable = points.filter(isDrawable).sort((a, b) => a.sequence - b.sequence)
  let total = 0
  for (let index = 1; index < usable.length; index += 1) {
    total += haversineMeters(
      usable[index - 1].latitude,
      usable[index - 1].longitude,
      usable[index].latitude,
      usable[index].longitude,
    )
  }
  return total
}

export function bearingDegrees(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number,
): number {
  const toRad = Math.PI / 180
  const phi1 = lat1 * toRad
  const phi2 = lat2 * toRad
  const dLambda = (lon2 - lon1) * toRad
  const x = Math.sin(dLambda) * Math.cos(phi2)
  const y =
    Math.cos(phi1) * Math.sin(phi2) - Math.sin(phi1) * Math.cos(phi2) * Math.cos(dLambda)
  return (Math.atan2(x, y) * 180) / Math.PI
}

export interface DirectionArrow {
  position: [number, number]
  bearing: number
  key: string
}

/**
 * Place direction arrows at a few well spaced points along the route.
 *
 * Arrows are placed every `spacingMeters` of travelled distance instead of on
 * every N-th fix, so they stay evenly spread for both dense and sparse data.
 */
export function buildDirectionArrows(
  segments: RouteSegment[],
  spacingMeters = 220,
  maxArrows = 26,
): DirectionArrow[] {
  const arrows: DirectionArrow[] = []
  segments.forEach((segment, segmentIndex) => {
    let sinceLast = spacingMeters * 0.5 // delay the first arrow a little
    for (let index = 1; index < segment.positions.length; index += 1) {
      const [previousLat, previousLon] = segment.positions[index - 1]
      const [lat, lon] = segment.positions[index]
      sinceLast += haversineMeters(previousLat, previousLon, lat, lon)
      if (sinceLast >= spacingMeters) {
        sinceLast = 0
        arrows.push({
          position: [lat, lon],
          bearing: bearingDegrees(previousLat, previousLon, lat, lon),
          key: `arrow-${segmentIndex}-${index}`,
        })
        if (arrows.length >= maxArrows) {
          return
        }
      }
    }
  })
  return arrows
}

/** Bounding box of the drawable points as [[south, west], [north, east]]. */
export function routeBounds(points: GPSPoint[]): [[number, number], [number, number]] | null {
  const usable = points.filter(isDrawable)
  if (usable.length === 0) {
    return null
  }
  const lats = usable.map((point) => point.latitude)
  const lons = usable.map((point) => point.longitude)
  return [
    [Math.min(...lats), Math.min(...lons)],
    [Math.max(...lats), Math.max(...lons)],
  ]
}

/** Demo replay support: advance a route's points to wall-clock timestamps. */
export function shiftTimestamps(
  startedAt: Date,
  offsetSeconds: number,
): string {
  return new Date(startedAt.getTime() + offsetSeconds * 1000).toISOString()
}
