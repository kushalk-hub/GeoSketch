import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const hoisted = vi.hoisted(() => ({
  listGeofences: vi.fn(),
  createGeofence: vi.fn(),
  deleteGeofence: vi.fn(),
}))

vi.mock('../services/api', () => ({
  api: {
    listGeofences: hoisted.listGeofences,
    createGeofence: hoisted.createGeofence,
    deleteGeofence: hoisted.deleteGeofence,
  },
}))

import { useGeofences } from './useGeofences'

describe('useGeofences', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads geofences when a token is provided', async () => {
    const mockZones = [
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
    ]
    hoisted.listGeofences.mockResolvedValue(mockZones)

    const { result } = renderHook(() => useGeofences('test-token'))

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.zones).toEqual(mockZones)
    expect(result.current.geofences).toEqual(mockZones)
    expect(result.current.error).toBeNull()
    expect(hoisted.listGeofences).toHaveBeenCalledWith('test-token')
  })

  it('resets zones and stays idle when token is null', async () => {
    const { result } = renderHook(() => useGeofences(null))

    expect(result.current.zones).toEqual([])
    expect(result.current.loading).toBe(false)
    expect(result.current.error).toBeNull()
    expect(hoisted.listGeofences).not.toHaveBeenCalled()
  })

  it('handles error when listing geofences fails', async () => {
    hoisted.listGeofences.mockRejectedValue(new Error('Fetch failed'))

    const { result } = renderHook(() => useGeofences('test-token'))

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.error).toBe('Fetch failed')
    expect(result.current.zones).toEqual([])
  })

  it('creates a geofence and refreshes', async () => {
    hoisted.listGeofences.mockResolvedValue([])
    hoisted.createGeofence.mockResolvedValue({
      id: 2,
      device_id: 'geosketch-01',
      name: 'School',
      latitude: 18.53,
      longitude: 73.86,
      radius_m: 200,
      active: true,
      created_at: '2026-11-13T10:00:00Z',
    })

    const { result } = renderHook(() => useGeofences('test-token'))
    await waitFor(() => expect(result.current.loading).toBe(false))

    let created
    await act(async () => {
      created = await result.current.createGeofence({
        device_id: 'geosketch-01',
        name: 'School',
        latitude: 18.53,
        longitude: 73.86,
        radius_m: 200,
      })
    })

    expect(created).toMatchObject({ id: 2, name: 'School' })
    expect(hoisted.createGeofence).toHaveBeenCalledWith('test-token', {
      device_id: 'geosketch-01',
      name: 'School',
      latitude: 18.53,
      longitude: 73.86,
      radius_m: 200,
    })
    expect(hoisted.listGeofences).toHaveBeenCalledTimes(2)
  })

  it('deletes a geofence and refreshes', async () => {
    hoisted.listGeofences.mockResolvedValue([])
    hoisted.deleteGeofence.mockResolvedValue(undefined)

    const { result } = renderHook(() => useGeofences('test-token'))
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => {
      await result.current.deleteGeofence(1)
    })

    expect(hoisted.deleteGeofence).toHaveBeenCalledWith('test-token', 1)
    expect(hoisted.listGeofences).toHaveBeenCalledTimes(2)
  })

  it('throws an error if create or delete is called without a token', async () => {
    const { result } = renderHook(() => useGeofences(null))

    await expect(
      result.current.createGeofence({
        device_id: 'd',
        name: 'z',
        latitude: 0,
        longitude: 0,
        radius_m: 100,
      }),
    ).rejects.toThrow('Not authenticated')

    await expect(result.current.deleteGeofence(1)).rejects.toThrow('Not authenticated')
  })
})
