import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockDeviceStatus = vi.hoisted(() => ({
  status: {
    device: {
      device_id: 'geosketch-01',
      name: 'GeoSketch Tracker',
      connection_status: 'online',
      firmware_version: '1.2.0',
      last_seen_at: '2026-11-13T10:00:00Z',
      last_latitude: 18.5204,
      last_longitude: 73.8567,
      last_satellites: 9,
      last_fix_at: '2026-11-13T10:00:00Z',
      points_received: 150,
      is_live: true,
      seconds_since_last_seen: 3,
    },
    connected: true,
    active_journey_id: 1,
    latest_point: {
      id: 1,
      journey_id: 1,
      device_id: 'geosketch-01',
      sequence: 55,
      latitude: 18.5204,
      longitude: 73.8567,
      altitude: 540,
      speed_kmh: 5.2,
      satellites: 9,
      gps_timestamp: '2026-11-13T10:00:00Z',
      server_timestamp: '2026-11-13T10:00:00Z',
      source: 'hardware',
      is_plausible: true,
      rejected_reason: null,
    },
    offline_after_seconds: 30,
    server_time: '2026-11-13T10:00:03Z',
  },
  error: null,
  loading: false,
  refresh: vi.fn(),
}))

const mockGeofences = vi.hoisted(() => ({
  zones: [
    {
      id: 1,
      device_id: 'geosketch-01',
      name: 'Home',
      latitude: 18.5204,
      longitude: 73.8567,
      radius_m: 150,
      active: true,
      created_at: '2026-11-13T10:00:00Z',
    },
    {
      id: 2,
      device_id: 'geosketch-01',
      name: 'School',
      latitude: 18.535,
      longitude: 73.87,
      radius_m: 200,
      active: true,
      created_at: '2026-11-13T10:00:00Z',
    },
  ],
  loading: false,
  error: null,
  createGeofence: vi.fn(),
  deleteGeofence: vi.fn(),
  refresh: vi.fn(),
}))

const mockAlerts = vi.hoisted(() => ({
  alerts: [
    {
      id: 1,
      device_id: 'geosketch-01',
      type: 'sos',
      geofence_id: null,
      message: 'Emergency SOS triggered by tracker',
      occurred_at: '2026-11-13T10:00:00Z',
      delivered_at: '2026-11-13T10:00:01Z',
      delivery_error: null,
    },
  ],
  loading: false,
  error: null,
  ackAlert: vi.fn(),
  refresh: vi.fn(),
}))

vi.mock('../hooks/useDeviceStatus', () => ({
  useDeviceStatus: () => mockDeviceStatus,
}))

vi.mock('../hooks/useGeofences', () => ({
  useGeofences: () => mockGeofences,
}))

vi.mock('../hooks/useAlerts', () => ({
  useAlerts: () => mockAlerts,
}))

vi.mock('../hooks/useParentSession', () => ({
  useParentSession: () => ({ token: 'mock-token', parent: null, logout: vi.fn(), login: vi.fn(), register: vi.fn() }),
}))

vi.mock('../services/api', () => ({
  CONFIGURED_DEVICE_ID: 'geosketch-01',
  api: {},
}))

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => <div data-testid="map-container">{children}</div>,
  TileLayer: () => <div data-testid="tile-layer" />,
  Circle: () => <div data-testid="leaflet-circle" />,
  Marker: () => <div data-testid="leaflet-marker" />,
  Polyline: () => <div data-testid="leaflet-polyline" />,
  useMap: () => ({ setView: vi.fn(), getZoom: () => 14 }),
}))

import ChildPage from './ChildPage'

describe('ChildPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders child companion view with live tracking metrics', () => {
    render(<ChildPage />)

    expect(screen.getByText('Child Safe-Trip Companion')).toBeInTheDocument()
    expect(screen.getByText('Tracker Live')).toBeInTheDocument()

    // Status banner shows inside Home zone
    expect(screen.getByText(/Safe Zone: Inside Home/i)).toBeInTheDocument()

    // Metrics tiles
    expect(screen.getByText('FIX ACQUIRED')).toBeInTheDocument()
    expect(screen.getByText(/geosketch-01/i)).toBeInTheDocument()
    expect(screen.getByText('5.2 km/h')).toBeInTheDocument()
  })

  it('lists monitored safe zones and their proximity status', () => {
    render(<ChildPage />)

    expect(screen.getByText('Monitored Safe Zones')).toBeInTheDocument()
    expect(screen.getAllByText('Home').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('School')).toBeInTheDocument()
    expect(screen.getByText('Inside')).toBeInTheDocument()
    expect(screen.getByText('Outside')).toBeInTheDocument()
  })

  it('displays the hardware emergency SOS instructions and alert notice', () => {
    render(<ChildPage />)

    expect(screen.getByText('Hardware Emergency SOS')).toBeInTheDocument()
    expect(screen.getByText(/press and hold the physical button/i)).toBeInTheDocument()
    expect(screen.getByText(/Recent SOS alert recorded/i)).toBeInTheDocument()
  })

  it('explains technical boundaries and unsupported capabilities', () => {
    render(<ChildPage />)

    expect(screen.getByText(/How Child Safe-Trip Works & Technical Boundaries/i)).toBeInTheDocument()
    expect(screen.getByText('Hardware-First Tracker')).toBeInTheDocument()
    expect(screen.getByText('No Child Web Login')).toBeInTheDocument()
    expect(screen.getByText('Automated 1-Way Alerts')).toBeInTheDocument()
    expect(screen.getByText('Physical Button SOS')).toBeInTheDocument()
  })
})
