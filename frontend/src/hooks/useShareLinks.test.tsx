import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const hoisted = vi.hoisted(() => ({
  listShareLinks: vi.fn(),
  createShareLink: vi.fn(),
  revokeShareLink: vi.fn(),
}))

vi.mock('../services/api', () => ({
  api: {
    listShareLinks: hoisted.listShareLinks,
    createShareLink: hoisted.createShareLink,
    revokeShareLink: hoisted.revokeShareLink,
  },
}))

import { useShareLinks } from './useShareLinks'

describe('useShareLinks', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads share links when a token is provided', async () => {
    const mockLinks = [
      {
        id: 1,
        device_id: 'geosketch-01',
        label: 'School Trip',
        expires_at: '2026-11-14T10:00:00Z',
        revoked_at: null,
        created_at: '2026-11-13T10:00:00Z',
      },
    ]
    hoisted.listShareLinks.mockResolvedValue(mockLinks)

    const { result } = renderHook(() => useShareLinks('test-token'))

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.links).toEqual(mockLinks)
    expect(result.current.error).toBeNull()
    expect(hoisted.listShareLinks).toHaveBeenCalledWith('test-token')
  })

  it('resets links and stays idle when token is null', async () => {
    const { result } = renderHook(() => useShareLinks(null))

    expect(result.current.links).toEqual([])
    expect(result.current.loading).toBe(false)
    expect(result.current.error).toBeNull()
    expect(hoisted.listShareLinks).not.toHaveBeenCalled()
  })

  it('handles error when listing fails', async () => {
    hoisted.listShareLinks.mockRejectedValue(new Error('Network error'))

    const { result } = renderHook(() => useShareLinks('test-token'))

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.error).toBe('Network error')
    expect(result.current.links).toEqual([])
  })

  it('creates a share link and refreshes', async () => {
    hoisted.listShareLinks.mockResolvedValue([])
    hoisted.createShareLink.mockResolvedValue({
      id: 2,
      url: 'http://127.0.0.1:5173/live/abc',
      token: 'abc',
      expires_at: '2026-11-14T10:00:00Z',
    })

    const { result } = renderHook(() => useShareLinks('test-token'))
    await waitFor(() => expect(result.current.loading).toBe(false))

    let created
    await act(async () => {
      created = await result.current.createShareLink({
        device_id: 'geosketch-01',
        label: 'Trip',
        ttl_hours: 24,
      })
    })

    expect(created).toMatchObject({ id: 2, token: 'abc' })
    expect(hoisted.createShareLink).toHaveBeenCalledWith('test-token', {
      device_id: 'geosketch-01',
      label: 'Trip',
      ttl_hours: 24,
    })
    expect(hoisted.listShareLinks).toHaveBeenCalledTimes(2)
  })

  it('revokes a share link and refreshes', async () => {
    hoisted.listShareLinks.mockResolvedValue([])
    hoisted.revokeShareLink.mockResolvedValue(undefined)

    const { result } = renderHook(() => useShareLinks('test-token'))
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => {
      await result.current.revokeShareLink(1)
    })

    expect(hoisted.revokeShareLink).toHaveBeenCalledWith('test-token', 1)
    expect(hoisted.listShareLinks).toHaveBeenCalledTimes(2)
  })

  it('throws an error if create or revoke is called without a token', async () => {
    const { result } = renderHook(() => useShareLinks(null))

    await expect(
      result.current.createShareLink({ device_id: 'd', label: 'l', ttl_hours: 24 }),
    ).rejects.toThrow('Not authenticated')

    await expect(result.current.revokeShareLink(1)).rejects.toThrow('Not authenticated')
  })
})
