import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const hoisted = vi.hoisted(() => ({
  listParentAlerts: vi.fn(),
  ackAlert: vi.fn(),
}))

vi.mock('../services/api', () => ({
  api: {
    listParentAlerts: hoisted.listParentAlerts,
    ackAlert: hoisted.ackAlert,
  },
}))

import { useAlerts } from './useAlerts'

describe('useAlerts', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useRealTimers()
  })

  it('loads alerts when a token is provided', async () => {
    const mockAlerts = [
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
    ]
    hoisted.listParentAlerts.mockResolvedValue(mockAlerts)

    const { result } = renderHook(() => useAlerts('test-token'))

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.alerts).toEqual(mockAlerts)
    expect(result.current.error).toBeNull()
    expect(hoisted.listParentAlerts).toHaveBeenCalledWith('test-token')
  })

  it('resets alerts and stays idle when token is null', async () => {
    const { result } = renderHook(() => useAlerts(null))

    expect(result.current.alerts).toEqual([])
    expect(result.current.loading).toBe(false)
    expect(result.current.error).toBeNull()
    expect(hoisted.listParentAlerts).not.toHaveBeenCalled()
  })

  it('handles error when listing alerts fails', async () => {
    hoisted.listParentAlerts.mockRejectedValue(new Error('Alert load error'))

    const { result } = renderHook(() => useAlerts('test-token'))

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.error).toBe('Alert load error')
    expect(result.current.alerts).toEqual([])
  })

  it('acknowledges an alert and refreshes', async () => {
    hoisted.listParentAlerts.mockResolvedValue([])
    hoisted.ackAlert.mockResolvedValue(undefined)

    const { result } = renderHook(() => useAlerts('test-token'))
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => {
      await result.current.ackAlert(42)
    })

    expect(hoisted.ackAlert).toHaveBeenCalledWith('test-token', 42)
    expect(hoisted.listParentAlerts).toHaveBeenCalledTimes(2)
  })

  it('throws an error if ackAlert is called without a token', async () => {
    const { result } = renderHook(() => useAlerts(null))

    await expect(result.current.ackAlert(1)).rejects.toThrow('Not authenticated')
  })

  it('polls periodically when intervalMs is provided', async () => {
    vi.useFakeTimers()
    hoisted.listParentAlerts.mockResolvedValue([])

    const { unmount } = renderHook(() => useAlerts('test-token', 3000))

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(hoisted.listParentAlerts).toHaveBeenCalledTimes(1)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000)
    })
    expect(hoisted.listParentAlerts).toHaveBeenCalledTimes(2)

    unmount()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000)
    })
    expect(hoisted.listParentAlerts).toHaveBeenCalledTimes(2)
  })
})
