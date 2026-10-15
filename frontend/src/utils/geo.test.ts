import { describe, expect, it } from 'vitest'

import type { GPSPoint } from '../types'
import {
  bearingDegrees,
  buildDirectionArrows,
  buildRouteSegments,
  haversineMeters,
  isDrawable,
  routeBounds,
  routeDistance,
  shiftTimestamps,
} from './geo'

const BASE_MS = Date.parse('2026-10-15T10:00:00Z')

function point(
  sequence: number,
  latitude: number,
  longitude: number,
  offsetSeconds: number,
  overrides: Partial<GPSPoint> = {},
): GPSPoint {
  return {
    id: sequence,
    journey_id: 1,
    device_id: 'geosketch-01',
    sequence,
    latitude,
    longitude,
    altitude: null,
    speed_kmh: null,
    satellites: 8,
    gps_timestamp: new Date(BASE_MS + offsetSeconds * 1000).toISOString(),
    server_timestamp: new Date(BASE_MS + offsetSeconds * 1000).toISOString(),
    source: 'hardware',
    is_plausible: true,
    rejected_reason: null,
    ...overrides,
  }
}

describe('haversineMeters', () => {
  it('returns 0 for the same coordinate', () => {
    expect(haversineMeters(18.52, 73.85, 18.52, 73.85)).toBe(0)
  })

  it('approximates one degree of latitude as ~111 km', () => {
    expect(haversineMeters(0, 0, 1, 0)).toBeCloseTo(111194.9, 0)
  })

  it('is symmetric', () => {
    const a = haversineMeters(18.5204, 73.8567, 18.5304, 73.8667)
    const b = haversineMeters(18.5304, 73.8667, 18.5204, 73.8567)
    expect(a).toBeCloseTo(b, 6)
  })
})

describe('isDrawable', () => {
  it('accepts a normal fix', () => {
    expect(isDrawable(point(1, 18.52, 73.85, 0))).toBe(true)
  })

  it('rejects rejected, zero, out-of-range and NaN fixes', () => {
    expect(isDrawable(point(1, 18.52, 73.85, 0, { is_plausible: false }))).toBe(false)
    expect(isDrawable(point(1, 0, 0, 0))).toBe(false)
    expect(isDrawable(point(1, 91, 73.85, 0))).toBe(false)
    expect(isDrawable(point(1, Number.NaN, 73.85, 0))).toBe(false)
  })
})

describe('buildRouteSegments', () => {
  it('orders points by sequence and keeps a continuous run together', () => {
    const segments = buildRouteSegments([
      point(2, 18.5201, 73.85, 10),
      point(1, 18.52, 73.85, 0),
      point(3, 18.5202, 73.851, 20),
    ])
    expect(segments).toHaveLength(1)
    expect(segments[0].positions).toHaveLength(3)
    expect(segments[0].afterBreak).toBe(false)
  })

  it('cuts the route at a recording gap', () => {
    const segments = buildRouteSegments([
      point(1, 18.52, 73.85, 0),
      point(2, 18.5201, 73.85, 10),
      point(3, 18.5300, 73.86, 1000), // > 180 s later
      point(4, 18.5301, 73.8601, 1010),
    ])
    expect(segments).toHaveLength(2)
    expect(segments[1].afterBreak).toBe(true)
  })

  it('cuts the route at an implausible jump', () => {
    const segments = buildRouteSegments([
      point(1, 18.52, 73.85, 0),
      point(2, 18.5201, 73.85, 1),
      point(3, 18.9002, 73.85, 2), // ~42 km in 1 s → impossible
      point(4, 18.9003, 73.85, 3),
    ])
    expect(segments).toHaveLength(2)
    expect(segments[1].afterBreak).toBe(true)
  })

  it('drops a lone point that cannot form a segment', () => {
    expect(buildRouteSegments([point(1, 18.52, 73.85, 0)])).toHaveLength(0)
  })
})

describe('routeDistance', () => {
  it('sums consecutive distances of drawable points', () => {
    const total = routeDistance([
      point(1, 18, 73, 0),
      point(2, 19, 73, 10),
      point(3, 20, 73, 20),
    ])
    expect(total).toBeCloseTo(222389.8, 0)
  })

  it('ignores non-drawable points', () => {
    expect(routeDistance([point(1, 18, 73, 0), point(2, 19, 73, 1, { is_plausible: false })])).toBe(0)
  })
})

describe('bearingDegrees', () => {
  it('reports due north as 0 and due east as ~90', () => {
    expect(bearingDegrees(0, 0, 1, 0)).toBeCloseTo(0, 4)
    expect(bearingDegrees(0, 0, 0, 1)).toBeCloseTo(90, 4)
  })
})

describe('routeBounds', () => {
  it('returns null when nothing is drawable', () => {
    expect(routeBounds([])).toBeNull()
  })

  it('returns south-west and north-east corners', () => {
    expect(
      routeBounds([point(1, 18.52, 73.85, 0), point(2, 18.53, 73.87, 10)]),
    ).toEqual([
      [18.52, 73.85],
      [18.53, 73.87],
    ])
  })
})

describe('buildDirectionArrows', () => {
  it('places arrows along a long segment and respects the cap', () => {
    const points = Array.from({ length: 50 }, (_, index) =>
      point(index + 1, 18.52 + index * 0.002, 73.85, index * 10),
    )
    const segments = buildRouteSegments(points)
    const arrows = buildDirectionArrows(segments, 100, 5)
    expect(arrows.length).toBeGreaterThan(0)
    expect(arrows.length).toBeLessThanOrEqual(5)
    expect(arrows[0].key).toMatch(/^arrow-/)
  })

  it('returns nothing for a too-short route', () => {
    const segments = buildRouteSegments([point(1, 18.52, 73.85, 0), point(2, 18.52001, 73.85, 5)])
    expect(buildDirectionArrows(segments, 1000)).toHaveLength(0)
  })
})

describe('shiftTimestamps', () => {
  it('adds an offset to a base instant', () => {
    const base = new Date('2026-10-15T10:00:00Z')
    expect(shiftTimestamps(base, 90)).toBe('2026-10-15T10:01:30.000Z')
  })
})
