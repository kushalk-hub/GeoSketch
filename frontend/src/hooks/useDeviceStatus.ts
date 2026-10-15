import { useCallback, useEffect, useRef, useState } from 'react'

import { ApiError, api } from '../services/api'
import type { DeviceStatus } from '../types'

/**
 * Polls the tracker status.
 *
 * The backend derives "live" from the last received GPS point, so when the
 * ESP32-C3 goes out of range the dashboard reports a *last known* position
 * instead of pretending the connection is still up.
 */
export function useDeviceStatus(deviceId: string, intervalMs = 3000) {
  const [status, setStatus] = useState<DeviceStatus | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(true)
  const mounted = useRef(true)

  const load = useCallback(async () => {
    try {
      const next = await api.deviceStatus(deviceId)
      if (!mounted.current) return
      setStatus(next)
      setError(null)
    } catch (cause) {
      if (!mounted.current) return
      setError(
        cause instanceof ApiError
          ? cause
          : new ApiError(0, 'unknown_error', String(cause)),
      )
    } finally {
      if (mounted.current) setLoading(false)
    }
  }, [deviceId])

  useEffect(() => {
    mounted.current = true
    void load()
    const timer = window.setInterval(() => void load(), intervalMs)
    return () => {
      mounted.current = false
      window.clearInterval(timer)
    }
  }, [load, intervalMs])

  return { status, error, loading, refresh: load }
}
