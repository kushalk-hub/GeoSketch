import { describe, expect, it } from 'vitest'

import {
  formatCoordinate,
  formatCount,
  formatDate,
  formatDateTime,
  formatDistance,
  formatDuration,
  formatRelative,
  formatSpeed,
  statusLabel,
} from './format'

describe('formatDistance', () => {
  it('renders an em dash for missing or NaN values', () => {
    expect(formatDistance(null)).toBe('—')
    expect(formatDistance(undefined)).toBe('—')
    expect(formatDistance(Number.NaN)).toBe('—')
  })

  it('keeps one decimal below 10 m and rounds above', () => {
    expect(formatDistance(6.24)).toBe('6.2 m')
    expect(formatDistance(42.6)).toBe('43 m')
    expect(formatDistance(999)).toBe('999 m')
  })

  it('switches to kilometres at 1000 m', () => {
    expect(formatDistance(1000)).toBe('1.00 km')
    expect(formatDistance(2734)).toBe('2.73 km')
  })
})

describe('formatDuration', () => {
  it('returns an em dash for non-positive values', () => {
    expect(formatDuration(0)).toBe('—')
    expect(formatDuration(-5)).toBe('—')
    expect(formatDuration(null)).toBe('—')
  })

  it('formats seconds, minutes and hours', () => {
    expect(formatDuration(45)).toBe('45s')
    expect(formatDuration(75)).toBe('1m 15s')
    expect(formatDuration(3661)).toBe('1h 01m')
  })
})

describe('formatSpeed', () => {
  it('labels an unknown speed as "not meaningful"', () => {
    expect(formatSpeed(null)).toBe('not meaningful')
    expect(formatSpeed(Number.NaN)).toBe('not meaningful')
  })

  it('formats a numeric speed with one decimal', () => {
    expect(formatSpeed(4.53)).toBe('4.5 km/h')
  })
})

describe('formatCoordinate', () => {
  it('returns an em dash for missing values', () => {
    expect(formatCoordinate(null)).toBe('—')
  })

  it('uses 5 decimals by default', () => {
    expect(formatCoordinate(18.5204)).toBe('18.52040')
    expect(formatCoordinate(73.8567, 2)).toBe('73.86')
  })
})

describe('formatCount', () => {
  it('returns an em dash for null/undefined', () => {
    expect(formatCount(null)).toBe('—')
    expect(formatCount(undefined)).toBe('—')
  })

  it('renders a locale string', () => {
    expect(formatCount(1234)).toBe((1234).toLocaleString())
  })
})

describe('formatDateTime / formatDate', () => {
  it('returns an em dash for missing or invalid input', () => {
    expect(formatDateTime(null)).toBe('—')
    expect(formatDateTime('not-a-date')).toBe('—')
    expect(formatDate(undefined)).toBe('—')
  })

  it('formats a valid ISO timestamp', () => {
    expect(formatDateTime('2026-10-15T10:30:00Z')).not.toBe('—')
    expect(formatDate('2026-10-15T10:30:00Z')).not.toBe('—')
  })
})

describe('formatRelative', () => {
  const now = Date.parse('2026-10-15T10:00:00Z')

  it('handles missing and invalid input', () => {
    expect(formatRelative(null, now)).toBe('never')
    expect(formatRelative('nonsense', now)).toBe('unknown')
  })

  it('describes recent, minute and hour ranges', () => {
    expect(formatRelative('2026-10-15T09:59:58Z', now)).toBe('just now')
    expect(formatRelative('2026-10-15T09:59:30Z', now)).toBe('30 s ago')
    expect(formatRelative('2026-10-15T09:55:00Z', now)).toBe('5 min ago')
    expect(formatRelative('2026-10-15T08:56:00Z', now)).toBe('1 h 4 min ago')
    expect(formatRelative('2026-10-15T08:00:00Z', now)).toBe('2 h ago')
  })
})

describe('statusLabel', () => {
  it('maps known statuses to uppercase labels', () => {
    expect(statusLabel('recording')).toBe('RECORDING')
    expect(statusLabel('paused')).toBe('PAUSED')
    expect(statusLabel('stopped')).toBe('STOPPED (unsaved)')
    expect(statusLabel('saved')).toBe('SAVED')
  })

  it('falls back to an uppercased value', () => {
    expect(statusLabel('mystery')).toBe('MYSTERY')
  })
})
