import { useCallback, useEffect, useState } from 'react'
import { ApiError, api } from '../services/api'
import type { ParentAccount } from '../types'

const STORAGE_KEY = 'geosketch-parent-session'
export function useParentSession() {
  const [token, setToken] = useState<string | null>(() => sessionStorage.getItem(STORAGE_KEY))
  const [parent, setParent] = useState<ParentAccount | null>(null)
  const logout = useCallback(() => { sessionStorage.removeItem(STORAGE_KEY); setToken(null); setParent(null) }, [])
  useEffect(() => {
    if (!token) return
    void api.parentMe(token).then(setParent).catch((cause: unknown) => {
      if (cause instanceof ApiError && cause.status === 401) logout()
    })
  }, [token, logout])
  const save = (next: string, account: ParentAccount) => {
    sessionStorage.setItem(STORAGE_KEY, next); setToken(next); setParent(account)
  }
  const login = async (email: string, password: string) => {
    const result = await api.parentLogin(email, password); save(result.token, result.parent)
  }
  const register = async (email: string, password: string) => {
    const result = await api.parentRegister(email, password); save(result.token, result.parent)
  }
  return { token, parent, login, register, logout }
}

