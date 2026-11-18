import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockSession = vi.hoisted(() => ({
  token: null as string | null,
  parent: null,
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
}))

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
      last_satellites: 8,
      last_fix_at: '2026-11-13T10:00:00Z',
      points_received: 120,
      is_live: true,
      seconds_since_last_seen: 2,
    },
    connected: true,
    active_journey_id: 1,
    latest_point: {
      id: 1,
      journey_id: 1,
      device_id: 'geosketch-01',
      sequence: 45,
      latitude: 18.5204,
      longitude: 73.8567,
      altitude: 550,
      speed_kmh: 4.5,
      satellites: 8,
      gps_timestamp: '2026-11-13T10:00:00Z',
      server_timestamp: '2026-11-13T10:00:00Z',
      source: 'hardware',
      is_plausible: true,
      rejected_reason: null,
    },
    offline_after_seconds: 30,
    server_time: '2026-11-13T10:00:02Z',
  },
  error: null,
  loading: false,
  refresh: vi.fn(),
}))

const mockShareLinks = vi.hoisted(() => ({
  links: [
    {
      id: 1,
      device_id: 'geosketch-01',
      label: 'Walk to school',
      expires_at: '2026-11-14T10:00:00Z',
      revoked_at: null,
      created_at: '2026-11-13T10:00:00Z',
    },
  ],
  loading: false,
  error: null,
  createShareLink: vi.fn(),
  revokeShareLink: vi.fn(),
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
      message: 'SOS button pressed',
      occurred_at: '2026-11-13T10:00:00Z',
      delivered_at: null,
      delivery_error: null,
    },
  ],
  loading: false,
  error: null,
  ackAlert: vi.fn(),
  refresh: vi.fn(),
}))

vi.mock('../hooks/useParentSession', () => ({
  useParentSession: () => mockSession,
}))

vi.mock('../hooks/useDeviceStatus', () => ({
  useDeviceStatus: () => mockDeviceStatus,
}))

vi.mock('../hooks/useShareLinks', () => ({
  useShareLinks: () => mockShareLinks,
}))

vi.mock('../hooks/useGeofences', () => ({
  useGeofences: () => mockGeofences,
}))

vi.mock('../hooks/useAlerts', () => ({
  useAlerts: () => mockAlerts,
}))

vi.mock('../services/api', () => ({
  CONFIGURED_DEVICE_ID: 'geosketch-01',
  ApiError: class extends Error {},
  api: {
    parentMe: vi.fn().mockResolvedValue({ id: 1, email: 'parent@example.test', telegram_chat_id: '12345' }),
    updateParentMe: vi.fn().mockResolvedValue({ id: 1, email: 'parent@example.test', telegram_chat_id: '12345' }),
  },
}))

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => <div data-testid="map-container">{children}</div>,
  TileLayer: () => <div data-testid="tile-layer" />,
  Circle: ({ children }: { children?: React.ReactNode }) => <div data-testid="map-circle">{children}</div>,
  Marker: ({ children }: { children?: React.ReactNode }) => <div data-testid="map-marker">{children}</div>,
  Tooltip: ({ children }: { children?: React.ReactNode }) => <div data-testid="map-tooltip">{children}</div>,
  useMapEvents: () => null,
  useMap: () => ({ setView: vi.fn(), getZoom: () => 13 }),
}))

import ParentPage from './ParentPage'

describe('ParentPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSession.token = null
  })

  it('opens the feature page directly without blocking with a login screen', () => {
    render(<ParentPage />)

    // Feature page header is visible immediately
    expect(screen.getByText(/Family Safe-Trip · Parent Portal/i)).toBeInTheDocument()

    // Device status card is displayed
    const statusSection = screen.getByLabelText('Device status')
    expect(statusSection).toBeInTheDocument()
    expect(screen.getByText('Online · Live')).toBeInTheDocument()
    expect(screen.getByText('FIX ACQUIRED')).toBeInTheDocument()
    expect(screen.getAllByText(/geosketch-01/i).length).toBeGreaterThanOrEqual(1)

    // Safe zones, share links, alerts sections exist
    expect(screen.getByText('Share live location')).toBeInTheDocument()
    expect(screen.getByText('Safe zones')).toBeInTheDocument()
    expect(screen.getByText('Alerts')).toBeInTheDocument()
    expect(screen.getByText('Telegram notifications')).toBeInTheDocument()

    // Login screen is NOT displayed by default
    expect(screen.queryByPlaceholderText('Email')).not.toBeInTheDocument()
  })

  it('allows toggling the optional account settings panel', () => {
    render(<ParentPage />)
    const accountBtn = screen.getByRole('button', { name: /Account/i })
    fireEvent.click(accountBtn)

    // Account inputs are now accessible
    expect(screen.getByPlaceholderText('Email')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Password (8 characters minimum)')).toBeInTheDocument()
  })

  it('renders authenticated dashboard with alerts and device info', () => {
    mockSession.token = 'valid-token'
    render(<ParentPage />)

    expect(screen.getByText(/Family Safe-Trip · Parent Portal/i)).toBeInTheDocument()
    expect(screen.getByText(/SOS button pressed/i)).toBeInTheDocument()
    expect(screen.getAllByText(/Home/i).length).toBeGreaterThanOrEqual(1)
  })
})
