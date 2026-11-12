import { useEffect, useState } from 'react'
import { ApiError, api } from '../services/api'
import type { LiveView } from '../types'

export function useLiveView(token: string) {
  const [data, setData] = useState<LiveView | null>(null)
  const [expired, setExpired] = useState(false)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let stopped = false
    let timer = 0
    let delay = 5000
    const poll = async () => {
      if (document.visibilityState === 'hidden') {
        timer = window.setTimeout(poll, 1000)
        return
      }
      try {
        const next = await api.liveView(token)
        if (stopped) return
        setData(next); setExpired(false); setError(null); delay = 5000
      } catch (cause) {
        if (stopped) return
        if (cause instanceof ApiError && cause.status === 404) setExpired(true)
        else { setError(cause instanceof Error ? cause.message : String(cause)); delay = Math.min(delay * 2, 60000) }
      }
      if (!stopped) timer = window.setTimeout(poll, delay)
    }
    const visibility = () => {
      if (document.visibilityState === 'visible') { window.clearTimeout(timer); void poll() }
    }
    document.addEventListener('visibilitychange', visibility)
    void poll()
    return () => { stopped = true; window.clearTimeout(timer); document.removeEventListener('visibilitychange', visibility) }
  }, [token])
  return { data, expired, error }
}

