import { useCallback, useEffect, useRef, useState } from 'react'

import { ApiError, api } from '../services/api'
import type { JourneyDetail, JourneyStatistics } from '../types'

/**
 * Polls one journey: its recorded points and its freshly computed statistics.
 *
 * Statistics are always recomputed by the backend from the stored points, so the
 * numbers on screen never come from a client-side guess.
 */
export function useJourney(journeyId: number | null, intervalMs = 2000) {
  const [journey, setJourney] = useState<JourneyDetail | null>(null)
  const [statistics, setStatistics] = useState<JourneyStatistics | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(false)
  const mounted = useRef(true)

  const load = useCallback(async () => {
    if (journeyId === null) {
      setJourney(null)
      setStatistics(null)
      return
    }
    try {
      const [detail, stats] = await Promise.all([
        api.getJourney(journeyId),
        api.statistics(journeyId),
      ])
      if (!mounted.current) return
      setJourney(detail)
      setStatistics(stats)
      setError(null)
    } catch (cause) {
      if (!mounted.current) return
      setError(
        cause instanceof ApiError ? cause : new ApiError(0, 'unknown_error', String(cause)),
      )
    } finally {
      if (mounted.current) setLoading(false)
    }
  }, [journeyId])

  useEffect(() => {
    mounted.current = true
    if (journeyId === null) {
      setJourney(null)
      setStatistics(null)
      return
    }
    setLoading(true)
    void load()
    const timer = window.setInterval(() => void load(), intervalMs)
    return () => {
      mounted.current = false
      window.clearInterval(timer)
    }
  }, [journeyId, intervalMs, load])

  return { journey, statistics, error, loading, refresh: load }
}
