import { useCallback, useEffect, useState } from 'react'

import { api } from '../services/api'
import type { SafeZone } from '../types'

export function useGeofences(token: string | null) {
  const [zones, setZones] = useState<SafeZone[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    if (!token) {
      setZones([])
      setLoading(false)
      setError(null)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await api.listGeofences(token)
      setZones(data)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const createGeofence = useCallback(
    async (body: {
      device_id: string
      name: string
      latitude: number
      longitude: number
      radius_m: number
    }) => {
      if (!token) {
        throw new Error('Not authenticated')
      }
      setError(null)
      const result = await api.createGeofence(token, body)
      await refresh()
      return result
    },
    [token, refresh],
  )

  const deleteGeofence = useCallback(
    async (id: number) => {
      if (!token) {
        throw new Error('Not authenticated')
      }
      setError(null)
      await api.deleteGeofence(token, id)
      await refresh()
    },
    [token, refresh],
  )

  return {
    zones,
    geofences: zones,
    loading,
    error,
    refresh,
    createGeofence,
    deleteGeofence,
    createZone: createGeofence,
    deleteZone: deleteGeofence,
  }
}
