import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Journey, SampleRouteDetail } from '../types'

const hoisted = vi.hoisted(() => ({
  demoRoute: vi.fn(),
  createJourney: vi.fn(),
  addPoints: vi.fn(),
  stopRecording: vi.fn(),
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
  return { ApiError, api: hoisted }
})

import { useDemoReplay } from './useDemoReplay'

const route: SampleRouteDetail = {
  id: 'city_grid_walk',
  name: 'City Grid Walk',
  description: 'demo',
  source: 'demo',
  point_count: 2,
  distance_m: 100,
  duration_seconds: 1,
  is_demo: true,
  points: [
    { t: 0, latitude: 18.52, longitude: 73.85, altitude: 12, speed_kmh: 4, satellites: 9 },
    { t: 1, latitude: 18.5201, longitude: 73.8501, altitude: 12, speed_kmh: 4, satellites: 9 },
  ],
}

const journey = { id: 42, status: 'recording', title: 'replay' } as unknown as Journey

function setup() {
  const notify = vi.fn()
  const onJourneyOpened = vi.fn()
  const onProgress = vi.fn().mockResolvedValue(undefined)
  const { result } = renderHook(() =>
    useDemoReplay({ notify, onJourneyOpened, onProgress }),
  )
  return { result, notify, onJourneyOpened, onProgress }
}

describe('useDemoReplay', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('replays a route, streams its points and stops the journey at the end', async () => {
    hoisted.demoRoute.mockResolvedValue(route)
    hoisted.createJourney.mockResolvedValue(journey)
    hoisted.addPoints.mockResolvedValue({ received: 1, stored: 1, duplicates: 0, rejected: 0, journey_id: 42 })
    hoisted.stopRecording.mockResolvedValue({ ...journey, status: 'stopped' } as Journey)
    const { result, notify, onJourneyOpened } = setup()

    await act(async () => {
      await result.current.start('city_grid_walk')
    })

    expect(hoisted.demoRoute).toHaveBeenCalledWith('city_grid_walk')
    expect(hoisted.createJourney).toHaveBeenCalledWith(
      expect.objectContaining({ source: 'demo' }),
    )
    expect(onJourneyOpened).toHaveBeenCalledWith(42)
    expect(hoisted.addPoints).toHaveBeenCalledTimes(1)

    // Advance past the tick interval so the rest of the route is streamed.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(250)
    })

    expect(hoisted.addPoints).toHaveBeenCalledTimes(2)
    expect(hoisted.stopRecording).toHaveBeenCalledWith(42)
    expect(result.current.progress).toBeNull()
    expect(notify).toHaveBeenCalledWith('success', 'DEMO MODE replay finished', expect.any(String))
  })

  it('refuses an empty sample route', async () => {
    hoisted.demoRoute.mockResolvedValue({ ...route, points: [] })
    const { result, notify } = setup()

    await act(async () => {
      await result.current.start('city_grid_walk')
    })

    expect(notify).toHaveBeenCalledWith('error', 'Sample route is empty')
    expect(hoisted.createJourney).not.toHaveBeenCalled()
  })

  it('reports a failure while streaming points', async () => {
    hoisted.demoRoute.mockResolvedValue(route)
    hoisted.createJourney.mockResolvedValue(journey)
    hoisted.addPoints.mockRejectedValue(new Error('backend gone'))
    const { result, notify } = setup()

    await act(async () => {
      await result.current.start('city_grid_walk')
    })

    expect(notify).toHaveBeenCalledWith('error', 'Demo replay failed', 'Error: backend gone')
    expect(result.current.progress).toBeNull()
  })

  it('ignores a second start while a replay is running', async () => {
    hoisted.demoRoute.mockResolvedValue(route)
    hoisted.createJourney.mockResolvedValue(journey)
    hoisted.addPoints.mockResolvedValue({ received: 1, stored: 1, duplicates: 0, rejected: 0, journey_id: 42 })
    const { result } = setup()

    await act(async () => {
      await result.current.start('city_grid_walk')
    })
    await act(async () => {
      await result.current.start('city_grid_walk')
    })

    expect(hoisted.demoRoute).toHaveBeenCalledTimes(1)

    // Leave no pending timer behind.
    await act(async () => {
      result.current.stopReplay()
    })
  })
})
