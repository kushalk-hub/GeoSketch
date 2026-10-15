import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { DeviceStatus } from '../types'

const hoisted = vi.hoisted(() => ({
  deviceStatus: vi.fn(),
}))

vi.mock('../services/api', () => {
  class ApiError extends Error {
    readonly status: number
    readonly code: string
    readonly details?: Record<string, unknown>
    constructor(status: number, code: string, message: string, details?: Record<string, unknown>) {
      super(message)
      this.name = 'ApiError'
      this.status = status
      this.code = code
      this.details = details
    }
    get isNetworkError(): boolean {
      return this.status === 0
    }
  }
  return {
    ApiError,
    api: { deviceStatus: hoisted.deviceStatus },
  }
})

import { useDeviceStatus } from './useDeviceStatus'

const status: DeviceStatus = {
  device: null,
  connected: true,
  active_journey_id: 7,
  latest_point: null,
  offline_after_seconds: 30,
  server_time: '2026-10-15T10:00:00Z',
}

describe('useDeviceStatus', () => {
  beforeEach(() => {
    hoisted.deviceStatus.mockReset()
  })

  it('loads the status and clears the loading flag', async () => {
    hoisted.deviceStatus.mockResolvedValue(status)
    const { result } = renderHook(() => useDeviceStatus('geosketch-01', 10000))

    expect(result.current.loading).toBe(true)
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.status).toEqual(status)
    expect(result.current.error).toBeNull()
    expect(hoisted.deviceStatus).toHaveBeenCalledWith('geosketch-01')
  })

  it('reports an error when the API call fails', async () => {
    hoisted.deviceStatus.mockRejectedValue(new Error('boom'))
    const { result } = renderHook(() => useDeviceStatus('geosketch-01', 10000))

    await waitFor(() => expect(result.current.error).not.toBeNull())
    expect(result.current.error?.code).toBe('unknown_error')
    expect(result.current.loading).toBe(false)
  })
})
