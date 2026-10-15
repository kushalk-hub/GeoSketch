import { useCallback, useEffect, useRef, useState } from 'react'

import { ApiError, api } from '../services/api'
import type { GPSPointPayload } from '../types'
import type { ToastKind } from './useToasts'

/** How much faster than real time the replay runs. */
export const REPLAY_SPEED = 60
const TICK_MS = 250

interface Options {
  notify: (kind: ToastKind, message: string, detail?: string) => void
  onJourneyOpened: (journeyId: number) => void
  onProgress: () => void | Promise<void>
}

export interface ReplayProgress {
  sent: number
  total: number
}

/**
 * Replays a bundled sample route into a live journey.
 *
 * The points are timestamped as if they had been recorded at the original time
 * (started `span` seconds ago), so the statistics stay realistic while the route
 * appears on the map in about a minute. The journey is created with
 * `source = "demo"` - simulated data can never end up in a hardware journey.
 */
export function useDemoReplay({ notify, onJourneyOpened, onProgress }: Options) {
  const [progress, setProgress] = useState<ReplayProgress | null>(null)
  const [starting, setStarting] = useState(false)
  const timer = useRef<number | null>(null)
  const cancelled = useRef(false)

  const clearTimer = useCallback(() => {
    if (timer.current !== null) {
      window.clearInterval(timer.current)
      timer.current = null
    }
  }, [])

  useEffect(() => () => {
    cancelled.current = true
    clearTimer()
  }, [clearTimer])

  const stopReplay = useCallback(() => {
    clearTimer()
    setProgress(null)
  }, [clearTimer])

  const start = useCallback(
    async (routeId: string) => {
      if (progress !== null || starting) {
        return
      }
      setStarting(true)
      clearTimer()
      try {
        const detail = await api.demoRoute(routeId)
        const points = detail.points
        if (points.length === 0) {
          notify('error', 'Sample route is empty')
          return
        }

        const span = points[points.length - 1].t
        const startedAt = new Date(Date.now() - span * 1000)
        const journey = await api.createJourney({
          title: `${detail.name} — live replay`,
          source: 'demo',
          started_at: startedAt.toISOString(),
          notes: `DEMO MODE live replay of the bundled sample route "${detail.id}". Simulated data.`,
        })
        onJourneyOpened(journey.id)
        cancelled.current = false

        let index = 0
        let sent = 0
        const realStart = Date.now()
        setProgress({ sent: 0, total: points.length })
        notify('info', 'DEMO MODE replay started', `${points.length} simulated points`)

        const tick = async () => {
          if (cancelled.current) {
            return
          }
          const virtualElapsed = ((Date.now() - realStart) / 1000) * REPLAY_SPEED
          const batch: GPSPointPayload[] = []

          while (index < points.length && points[index].t <= virtualElapsed) {
            const point = points[index]
            batch.push({
              latitude: point.latitude,
              longitude: point.longitude,
              altitude: point.altitude,
              speed_kmh: point.speed_kmh,
              satellites: point.satellites ?? 9,
              timestamp: new Date(startedAt.getTime() + point.t * 1000).toISOString(),
              client_point_id: `${routeId}:replay:${index}`,
            })
            index += 1
          }

          if (batch.length > 0) {
            try {
              await api.addPoints(journey.id, batch, 'demo')
            } catch (cause) {
              clearTimer()
              setProgress(null)
              notify(
                'error',
                'Demo replay failed',
                cause instanceof ApiError ? cause.message : String(cause),
              )
              return
            }
            sent += batch.length
            setProgress({ sent, total: points.length })
            await onProgress()
          }

          if (index >= points.length) {
            clearTimer()
            try {
              await api.stopRecording(journey.id)
              notify(
                'success',
                'DEMO MODE replay finished',
                'Recording stopped automatically — press Save to keep the journey',
              )
            } catch {
              /* the journey stays open; the user can stop it manually */
            }
            setProgress(null)
            await onProgress()
          }
        }

        await tick()
        timer.current = window.setInterval(() => void tick(), TICK_MS)
      } catch (cause) {
        notify(
          'error',
          'Could not start the demo replay',
          cause instanceof ApiError ? cause.message : String(cause),
        )
      } finally {
        setStarting(false)
      }
    },
    [clearTimer, notify, onJourneyOpened, onProgress, progress, starting],
  )

  return { progress, starting, start, stopReplay, replaying: progress !== null }
}
