import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('../components/RouteMap', () => ({
  default: () => <div data-testid="route-map" />,
}))

vi.mock('../components/RecordingControls', () => ({
  default: () => <div data-testid="recording-controls" />,
}))

vi.mock('../components/StatusPanel', () => ({
  default: () => <div data-testid="status-panel" />,
}))

vi.mock('../components/DemoModePanel', () => ({
  default: () => <div data-testid="demo-panel" />,
}))

import DashboardPage from './DashboardPage'

describe('DashboardPage - Family Safe-Trip cards', () => {
  const baseProps = {
    status: {
      device: {
        device_id: 'geosketch-01',
        name: 'Tracker',
        connection_status: 'online' as const,
        firmware_version: '1.2.0',
        last_seen_at: '2026-11-13T10:00:00Z',
        last_latitude: 18.5204,
        last_longitude: 73.8567,
        last_satellites: 8,
        last_fix_at: '2026-11-13T10:00:00Z',
        points_received: 10,
        is_live: true,
        seconds_since_last_seen: 2,
      },
      connected: true,
      active_journey_id: 1,
      latest_point: null,
      offline_after_seconds: 30,
      server_time: '2026-11-13T10:00:02Z',
    },
    statusError: null,
    journey: null,
    statistics: null,
    journeyError: null,
    pinned: false,
    onReturnToLive: vi.fn(),
    onRefresh: vi.fn(),
    onRename: vi.fn(),
    recorder: {
      busy: false,
      onStart: vi.fn(),
      onPause: vi.fn(),
      onResume: vi.fn(),
      onStop: vi.fn(),
      onSave: vi.fn(),
      onClear: vi.fn(),
    },
    demo: {
      routes: [],
      selectedRouteId: null,
      onSelect: vi.fn(),
      onImport: vi.fn(),
      onReplay: vi.fn(),
      onStopReplay: vi.fn(),
      importing: false,
      replaying: false,
      progress: null,
      loadError: null,
    },
  }

  it('renders the Parent and Child dashboard cards and triggers navigation', () => {
    const handleOpenParent = vi.fn()
    const handleOpenChild = vi.fn()

    render(
      <DashboardPage
        {...baseProps}
        onOpenParent={handleOpenParent}
        onOpenChild={handleOpenChild}
      />,
    )

    // Family Safe-Trip section
    expect(screen.getByRole('region', { name: /Family Safe-Trip/i })).toBeInTheDocument()

    // Parent Portal card
    expect(screen.getByText('Parent Portal')).toBeInTheDocument()
    const openParentBtn = screen.getByRole('button', { name: 'Open Parent' })
    expect(openParentBtn).toBeInTheDocument()

    // Child Companion card
    expect(screen.getByText('Child Companion')).toBeInTheDocument()
    const openChildBtn = screen.getByRole('button', { name: 'Open Child' })
    expect(openChildBtn).toBeInTheDocument()

    // Clicking buttons triggers callbacks
    fireEvent.click(openParentBtn)
    expect(handleOpenParent).toHaveBeenCalledTimes(1)

    fireEvent.click(openChildBtn)
    expect(handleOpenChild).toHaveBeenCalledTimes(1)
  })
})
