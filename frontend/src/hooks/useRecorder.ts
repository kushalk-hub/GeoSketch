import { useCallback, useState } from 'react'

import { ApiError, api } from '../services/api'
import type { Journey, JourneyDetail } from '../types'
import type { ToastKind } from './useToasts'

type Notify = (kind: ToastKind, message: string, detail?: string) => void

interface Options {
  deviceId: string
  activeJourney: JourneyDetail | Journey | null
  setActiveJourneyId: (id: number | null) => void
  refresh: () => void | Promise<void>
  notify: Notify
}

function toMessage(cause: unknown): string {
  if (cause instanceof ApiError) {
    return cause.message
  }
  return String(cause)
}

/**
 * Implements the recording controls.
 *
 * The UI disables invalid buttons, and the backend *also* refuses invalid
 * transitions with HTTP 409 - this hook surfaces that refusal instead of hiding
 * it, so the state machine can never be silently violated.
 */
export function useRecorder({
  deviceId,
  activeJourney,
  setActiveJourneyId,
  refresh,
  notify,
}: Options) {
  const [busy, setBusy] = useState(false)

  const run = useCallback(
    async (action: () => Promise<Journey>, successMessage: string) => {
      setBusy(true)
      try {
        const journey = await action()
        setActiveJourneyId(journey.id)
        notify('success', successMessage, `journey #${journey.id} · ${journey.status}`)
        await refresh()
        return journey
      } catch (cause) {
        notify('error', 'Command refused', toMessage(cause))
        return null
      } finally {
        setBusy(false)
      }
    },
    [notify, refresh, setActiveJourneyId],
  )

  /**
   * Start recording.
   *
   * If the ESP32-C3 already opened a journey on its own (it does that as soon as
   * it posts its first fix), that journey is adopted rather than creating a
   * second one - otherwise points would be split across two records.
   */
  const start = useCallback(async () => {
    setBusy(true)
    try {
      const existing = await api.listJourneys({ status: 'recording', source: 'hardware', limit: 5 })
      const alreadyRecording = existing[0]
      if (alreadyRecording) {
        setActiveJourneyId(alreadyRecording.id)
        notify(
          'info',
          'Recording already active',
          `Adopted journey #${alreadyRecording.id} created by the device`,
        )
        await refresh()
        return alreadyRecording
      }
      const paused = await api.listJourneys({ status: 'paused', source: 'hardware', limit: 5 })
      if (paused[0]) {
        return run(() => api.resumeRecording(paused[0].id), 'Recording resumed')
      }
      const journey = await api.createJourney({
        device_id: deviceId,
        source: 'hardware',
        start_immediately: true,
      })
      setActiveJourneyId(journey.id)
      notify('success', 'Recording started', `journey #${journey.id}`)
      await refresh()
      return journey
    } catch (cause) {
      notify('error', 'Could not start recording', toMessage(cause))
      return null
    } finally {
      setBusy(false)
    }
  }, [deviceId, notify, refresh, run, setActiveJourneyId])

  const requireJourney = useCallback((): number | null => {
    if (!activeJourney) {
      notify('info', 'No journey selected', 'Start recording or open a journey first.')
      return null
    }
    return activeJourney.id
  }, [activeJourney, notify])

  const pause = useCallback(() => {
    const id = requireJourney()
    return id === null ? null : run(() => api.pauseRecording(id), 'Recording paused')
  }, [requireJourney, run])

  const resume = useCallback(() => {
    const id = requireJourney()
    return id === null ? null : run(() => api.resumeRecording(id), 'Recording resumed')
  }, [requireJourney, run])

  const stop = useCallback(() => {
    const id = requireJourney()
    return id === null ? null : run(() => api.stopRecording(id), 'Recording finished')
  }, [requireJourney, run])

  const save = useCallback(() => {
    const id = requireJourney()
    return id === null ? null : run(() => api.saveJourney(id), 'Journey saved')
  }, [requireJourney, run])

  const clear = useCallback(async () => {
    const id = requireJourney()
    if (id === null) return null
    setBusy(true)
    try {
      await api.deleteJourney(id)
      setActiveJourneyId(null)
      notify('success', 'Unsaved journey cleared', `journey #${id} removed`)
      await refresh()
      return true
    } catch (cause) {
      notify('error', 'Could not clear the journey', toMessage(cause))
      return null
    } finally {
      setBusy(false)
    }
  }, [notify, refresh, requireJourney, setActiveJourneyId])

  const rename = useCallback(
    (id: number, title: string) =>
      run(() => api.updateJourney(id, { title }), 'Journey renamed'),
    [run],
  )

  return { busy, start, pause, resume, stop, save, clear, rename }
}
