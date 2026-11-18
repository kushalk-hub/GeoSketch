import { useCallback, useEffect, useState } from 'react'

import { api } from '../services/api'
import type { ParentAlert } from '../types'

export function useAlerts(token: string | null, intervalMs?: number) {
  const [alerts, setAlerts] = useState<ParentAlert[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    if (!token) {
      setAlerts([])
      setLoading(false)
      setError(null)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await api.listParentAlerts(token)
      setAlerts(data)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    void refresh()
    if (!intervalMs || intervalMs <= 0 || !token) return

    let stopped = false
    let timer: number | undefined

    const poll = async () => {
      if (document.visibilityState === 'hidden') {
        timer = window.setTimeout(poll, 1000)
        return
      }
      try {
        const next = await api.listParentAlerts(token)
        if (!stopped) {
          setAlerts(next)
          setError(null)
        }
      } catch (cause) {
        if (!stopped) {
          setError(cause instanceof Error ? cause.message : String(cause))
        }
      }
      if (!stopped) {
        timer = window.setTimeout(poll, intervalMs)
      }
    }

    timer = window.setTimeout(poll, intervalMs)

    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        if (timer) window.clearTimeout(timer)
        void poll()
      }
    }
    document.addEventListener('visibilitychange', onVisibility)

    return () => {
      stopped = true
      if (timer) window.clearTimeout(timer)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [token, intervalMs, refresh])

  const ackAlert = useCallback(
    async (id: number) => {
      if (!token) {
        throw new Error('Not authenticated')
      }
      setError(null)
      await api.ackAlert(token, id)
      await refresh()
    },
    [token, refresh],
  )

  return {
    alerts,
    loading,
    error,
    refresh,
    ackAlert,
    acknowledgeAlert: ackAlert,
  }
}
