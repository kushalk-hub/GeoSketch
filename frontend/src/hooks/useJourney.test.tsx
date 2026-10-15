import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { JourneyDetail, JourneyStatistics } from '../types'

const hoisted = vi.hoisted(() => ({
  getJourney: vi.fn(),
  statistics: vi.fn(),
}))

vi.mock('../services/api', () => {
  class ApiError extends Error {
    readonly status: number
    readonly code: string
    constructor(status: number, code: string, message: string) {
      super(message)
      this.name = 'ApiError'
      this.status = status
      this.code = code
    }
    get isNetworkError(): boolean {
      return this.status === 0
    }
  }
  return { ApiError, api: { getJourney: hoisted.getJourney, statistics: hoisted.statistics } }
})

import { useJourney } from './useJourney'

const detail = { id: 5, title: 'Walk', points: [], point_count: 0 } as unknown as JourneyDetail
const stats = { journey_id: 5, distance_m: 1000 } as unknown as JourneyStatistics

describe('useJourney', () => {
  beforeEach(() => {
    hoisted.getJourney.mockReset()
    hoisted.statistics.mockReset()
  })

  it('does not fetch when no journey is selected', async () => {
    const { result } = renderHook(() => useJourney(null, 10000))
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.journey).toBeNull()
    expect(result.current.statistics).toBeNull()
    expect(hoisted.getJourney).not.toHaveBeenCalled()
  })

  it('loads the journey detail and its statistics', async () => {
    hoisted.getJourney.mockResolvedValue(detail)
    hoisted.statistics.mockResolvedValue(stats)
    const { result } = renderHook(() => useJourney(5, 10000))

    await waitFor(() => expect(result.current.journey).toEqual(detail))
    expect(result.current.statistics).toEqual(stats)
    expect(result.current.error).toBeNull()
    expect(hoisted.getJourney).toHaveBeenCalledWith(5)
    expect(hoisted.statistics).toHaveBeenCalledWith(5)
  })

  it('reports a failure while polling', async () => {
    hoisted.getJourney.mockRejectedValue(new Error('down'))
    hoisted.statistics.mockResolvedValue(stats)
    const { result } = renderHook(() => useJourney(5, 10000))
    await waitFor(() => expect(result.current.error).not.toBeNull())
    expect(result.current.error?.code).toBe('unknown_error')
  })
})
