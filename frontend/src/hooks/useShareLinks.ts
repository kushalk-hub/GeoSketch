import { useCallback, useEffect, useState } from 'react'

import { api } from '../services/api'
import type { ShareLink } from '../types'

export function useShareLinks(token: string | null) {
  const [links, setLinks] = useState<ShareLink[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    if (!token) {
      setLinks([])
      setLoading(false)
      setError(null)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await api.listShareLinks(token)
      setLinks(data)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const createShareLink = useCallback(
    async (body: { device_id: string; label: string; ttl_hours: number }) => {
      if (!token) {
        throw new Error('Not authenticated')
      }
      setError(null)
      const result = await api.createShareLink(token, body)
      await refresh()
      return result
    },
    [token, refresh],
  )

  const revokeShareLink = useCallback(
    async (id: number) => {
      if (!token) {
        throw new Error('Not authenticated')
      }
      setError(null)
      await api.revokeShareLink(token, id)
      await refresh()
    },
    [token, refresh],
  )

  return {
    links,
    loading,
    error,
    refresh,
    createShareLink,
    revokeShareLink,
    createLink: createShareLink,
    revokeLink: revokeShareLink,
  }
}
