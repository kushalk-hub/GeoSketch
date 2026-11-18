import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockLive = vi.hoisted(() => vi.fn())
vi.mock('../services/api', () => {
  class ApiError extends Error { status:number; code:string; constructor(status:number,code:string,message:string){super(message);this.status=status;this.code=code} }
  return { ApiError, api: { liveView: mockLive } }
})
import { ApiError } from '../services/api'
import { useLiveView } from './useLiveView'

describe('useLiveView', () => {
  beforeEach(() => { mockLive.mockReset(); Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' }) })
  it('loads the public view', async () => {
    mockLive.mockResolvedValue({label:'Child',status:'online',trail:[],zones:[],position:null,last_seen:null,expires_at:'later'})
    const { result } = renderHook(() => useLiveView('secret'))
    await waitFor(() => expect(result.current.data?.label).toBe('Child'))
  })
  it('maps a 404 response to the expired or revoked state', async () => {
    mockLive.mockRejectedValue(new ApiError(404,'not_found','missing'))
    const { result } = renderHook(() => useLiveView('secret'))
    await waitFor(() => expect(result.current.expired).toBe(true))
  })
})

