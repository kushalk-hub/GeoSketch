import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { Journey, JourneyDetail } from '../types'

const hoisted = vi.hoisted(() => ({
  listJourneys: vi.fn(),
  createJourney: vi.fn(),
  resumeRecording: vi.fn(),
  pauseRecording: vi.fn(),
  stopRecording: vi.fn(),
  saveJourney: vi.fn(),
  deleteJourney: vi.fn(),
  updateJourney: vi.fn(),
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

import { useRecorder } from './useRecorder'

const journey = (id: number, status = 'recording') =>
  ({ id, status, title: 'Walk' }) as unknown as Journey

interface SetupResult {
  setActiveJourneyId: ReturnType<typeof vi.fn>
  refresh: ReturnType<typeof vi.fn>
  notify: ReturnType<typeof vi.fn>
  result: { current: ReturnType<typeof useRecorder> }
}

function setup(activeJourney: JourneyDetail | Journey | null = null): SetupResult {
  const setActiveJourneyId = vi.fn()
  const refresh = vi.fn().mockResolvedValue(undefined)
  const notify = vi.fn()
  const { result } = renderHook(() =>
    useRecorder({
      deviceId: 'geosketch-01',
      activeJourney,
      setActiveJourneyId,
      refresh,
      notify,
    }),
  )
  return { setActiveJourneyId, refresh, notify, result }
}

describe('useRecorder', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('creates a new hardware journey when nothing is active', async () => {
    hoisted.listJourneys.mockResolvedValue([])
    hoisted.createJourney.mockResolvedValue(journey(9))
    const { result, notify, setActiveJourneyId, refresh } = setup()

    await act(async () => {
      await result.current.start()
    })

    expect(hoisted.createJourney).toHaveBeenCalledWith(
      expect.objectContaining({ source: 'hardware', start_immediately: true }),
    )
    expect(setActiveJourneyId).toHaveBeenCalledWith(9)
    expect(refresh).toHaveBeenCalled()
    expect(notify).toHaveBeenCalledWith('success', 'Recording started', expect.stringContaining('#9'))
  })

  it('adopts a journey the device already opened', async () => {
    hoisted.listJourneys.mockResolvedValueOnce([journey(4, 'recording')])
    const { result, notify, setActiveJourneyId } = setup()

    await act(async () => {
      await result.current.start()
    })

    expect(hoisted.createJourney).not.toHaveBeenCalled()
    expect(setActiveJourneyId).toHaveBeenCalledWith(4)
    expect(notify).toHaveBeenCalledWith('info', 'Recording already active', expect.any(String))
  })

  it('resumes a paused journey instead of starting a new one', async () => {
    hoisted.listJourneys.mockResolvedValueOnce([]).mockResolvedValueOnce([journey(3, 'paused')])
    hoisted.resumeRecording.mockResolvedValue(journey(3))
    const { result } = setup()

    await act(async () => {
      await result.current.start()
    })

    expect(hoisted.resumeRecording).toHaveBeenCalledWith(3)
    expect(hoisted.createJourney).not.toHaveBeenCalled()
  })

  it('surfaces a failed start as an error toast', async () => {
    hoisted.listJourneys.mockRejectedValue(new Error('offline'))
    const { result, notify } = setup()

    await act(async () => {
      await result.current.start()
    })

    expect(notify).toHaveBeenCalledWith('error', 'Could not start recording', 'Error: offline')
  })

  it('warns when a control is used without a journey', async () => {
    const { result, notify } = setup(null)
    await act(async () => {
      result.current.pause()
    })
    expect(notify).toHaveBeenCalledWith('info', 'No journey selected', expect.any(String))
    expect(hoisted.pauseRecording).not.toHaveBeenCalled()
  })

  it('runs pause, resume, stop and save on the active journey', async () => {
    hoisted.pauseRecording.mockResolvedValue(journey(7, 'paused'))
    hoisted.resumeRecording.mockResolvedValue(journey(7, 'recording'))
    hoisted.stopRecording.mockResolvedValue(journey(7, 'stopped'))
    hoisted.saveJourney.mockResolvedValue(journey(7, 'saved'))
    const { result } = setup(journey(7))

    await act(async () => {
      await result.current.pause()
      await result.current.resume()
      await result.current.stop()
      await result.current.save()
    })

    expect(hoisted.pauseRecording).toHaveBeenCalledWith(7)
    expect(hoisted.resumeRecording).toHaveBeenCalledWith(7)
    expect(hoisted.stopRecording).toHaveBeenCalledWith(7)
    expect(hoisted.saveJourney).toHaveBeenCalledWith(7)
  })

  it('surfaces a refused transition (409) as "Command refused"', async () => {
    const { ApiError } = await import('../services/api')
    hoisted.saveJourney.mockRejectedValue(new ApiError(409, 'invalid_transition', 'not allowed'))
    const { result, notify } = setup(journey(7))

    await act(async () => {
      await result.current.save()
    })

    expect(notify).toHaveBeenCalledWith('error', 'Command refused', 'not allowed')
  })

  it('clears an unsaved journey', async () => {
    hoisted.deleteJourney.mockResolvedValue({ message: 'cleared' })
    const { result, setActiveJourneyId, notify } = setup(journey(7, 'stopped'))

    await act(async () => {
      await result.current.clear()
    })

    expect(hoisted.deleteJourney).toHaveBeenCalledWith(7)
    expect(setActiveJourneyId).toHaveBeenCalledWith(null)
    expect(notify).toHaveBeenCalledWith('success', 'Unsaved journey cleared', expect.any(String))
  })

  it('renames a journey', async () => {
    hoisted.updateJourney.mockResolvedValue(journey(7))
    const { result } = setup(journey(7))

    await act(async () => {
      await result.current.rename(7, 'Renamed walk')
    })

    expect(hoisted.updateJourney).toHaveBeenCalledWith(7, { title: 'Renamed walk' })
  })
})
