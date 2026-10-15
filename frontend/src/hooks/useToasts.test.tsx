import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useToasts } from './useToasts'

describe('useToasts', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('adds a toast for each notification', () => {
    const { result } = renderHook(() => useToasts())
    act(() => {
      result.current.notify('success', 'Saved')
    })
    expect(result.current.toasts).toHaveLength(1)
    expect(result.current.toasts[0]).toMatchObject({ kind: 'success', message: 'Saved' })
  })

  it('caps the queue at four, dropping the oldest', () => {
    const { result } = renderHook(() => useToasts())
    act(() => {
      for (let index = 0; index < 6; index += 1) {
        result.current.notify('info', `msg ${index}`)
      }
    })
    expect(result.current.toasts).toHaveLength(4)
    expect(result.current.toasts[0].message).toBe('msg 2')
    expect(result.current.toasts[3].message).toBe('msg 5')
  })

  it('dismisses a toast by id', () => {
    const { result } = renderHook(() => useToasts())
    let id = 0
    act(() => {
      id = result.current.notify('info', 'transient')
    })
    act(() => {
      result.current.dismiss(id)
    })
    expect(result.current.toasts).toHaveLength(0)
  })

  it('auto-dismisses an info toast after 4 s', () => {
    const { result } = renderHook(() => useToasts())
    act(() => {
      result.current.notify('info', 'fades')
    })
    act(() => {
      vi.advanceTimersByTime(4000)
    })
    expect(result.current.toasts).toHaveLength(0)
  })

  it('keeps an error toast visible for 9 s', () => {
    const { result } = renderHook(() => useToasts())
    act(() => {
      result.current.notify('error', 'sticky')
    })
    act(() => {
      vi.advanceTimersByTime(4000)
    })
    expect(result.current.toasts).toHaveLength(1)
    act(() => {
      vi.advanceTimersByTime(5000)
    })
    expect(result.current.toasts).toHaveLength(0)
  })
})
