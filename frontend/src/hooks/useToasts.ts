import { useCallback, useEffect, useRef, useState } from 'react'

export type ToastKind = 'info' | 'success' | 'error'

export interface Toast {
  id: number
  kind: ToastKind
  message: string
  detail?: string
}

const MAX_TOASTS = 4

/**
 * Minimal toast queue. Errors are never auto-dismissed silently: they stay long
 * enough to be read (and can be dismissed manually), which matters when a
 * demo goes wrong in front of an audience.
 */
export function useToasts() {
  const [toasts, setToasts] = useState<Toast[]>([])
  const counter = useRef(0)
  const timers = useRef<number[]>([])

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  const notify = useCallback(
    (kind: ToastKind, message: string, detail?: string) => {
      counter.current += 1
      const id = counter.current
      setToasts((current) => [...current.slice(-(MAX_TOASTS - 1)), { id, kind, message, detail }])
      const timeout = window.setTimeout(() => dismiss(id), kind === 'error' ? 9000 : 4000)
      timers.current.push(timeout)
      return id
    },
    [dismiss],
  )

  useEffect(() => {
    const pending = timers.current
    return () => {
      pending.forEach((timer) => window.clearTimeout(timer))
    }
  }, [])

  return { toasts, notify, dismiss }
}
