import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockApi = vi.hoisted(() => ({ parentMe: vi.fn(), parentLogin: vi.fn(), parentRegister: vi.fn() }))
vi.mock('../services/api', () => {
  class ApiError extends Error { status:number; constructor(status:number){super('error');this.status=status} }
  return { ApiError, api: mockApi }
})
import { useParentSession } from './useParentSession'

describe('useParentSession', () => {
  beforeEach(() => { sessionStorage.clear(); mockApi.parentMe.mockReset(); mockApi.parentMe.mockResolvedValue({id:1,email:"p@example.test",telegram_chat_id:null}); mockApi.parentLogin.mockReset(); mockApi.parentRegister.mockReset() })
  it('stores a login token in sessionStorage and clears it on logout', async () => {
    mockApi.parentLogin.mockResolvedValue({token:'session-secret',parent:{id:1,email:'p@example.test',telegram_chat_id:null}})
    mockApi.parentMe.mockResolvedValue({id:1,email:'p@example.test',telegram_chat_id:null})
    const { result } = renderHook(() => useParentSession())
    await act(async () => { await result.current.login('p@example.test','password123') })
    expect(sessionStorage.getItem('geosketch-parent-session')).toBe('session-secret')
    await waitFor(() => expect(result.current.parent?.id).toBe(1))
    act(() => result.current.logout())
    expect(sessionStorage.getItem('geosketch-parent-session')).toBeNull()
    expect(result.current.token).toBeNull()
  })
  it('registers a new parent', async () => {
    mockApi.parentRegister.mockResolvedValue({token:'new-session',parent:{id:2,email:'n@example.test',telegram_chat_id:null}})
    const { result } = renderHook(() => useParentSession())
    await act(async () => { await result.current.register('n@example.test','password123') })
    expect(sessionStorage.getItem('geosketch-parent-session')).toBe('new-session')
  })
})

