import { afterEach, describe, expect, it, vi } from 'vitest'

import { API_BASE, ApiError, api } from './api'

function stubFetch(impl: (input: string, init?: RequestInit) => Promise<Response>) {
  const spy = vi.fn(impl)
  vi.stubGlobal('fetch', spy)
  return spy
}

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
  } as Response
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('api request layer', () => {
  it('parses a successful JSON response', async () => {
    stubFetch(async () => jsonResponse({ status: 'ok', service: 'GeoSketch API' }))
    const health = await api.health()
    expect(health).toMatchObject({ status: 'ok', service: 'GeoSketch API' })
  })

  it('returns undefined for 204 responses', async () => {
    stubFetch(async () => ({ ok: true, status: 204, text: async () => '' }) as Response)
    await expect(api.saveJourney(1)).resolves.toBeUndefined()
  })

  it('maps a backend error envelope to ApiError', async () => {
    stubFetch(async () =>
      jsonResponse(
        { error: { code: 'invalid_transition', message: 'nope', details: { from: 'saved' } } },
        409,
      ),
    )
    await expect(api.saveJourney(1)).rejects.toMatchObject({
      name: 'ApiError',
      status: 409,
      code: 'invalid_transition',
      message: 'nope',
      details: { from: 'saved' },
    })
  })

  it('falls back to an http_<status> code when the body has no envelope', async () => {
    stubFetch(async () => jsonResponse({ nope: true }, 500))
    await expect(api.health()).rejects.toMatchObject({ status: 500, code: 'http_500' })
  })

  it('wraps a connection failure as a network ApiError', async () => {
    stubFetch(async () => {
      throw new Error('ECONNREFUSED')
    })
    const error = await api.health().catch((cause: unknown) => cause)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(0)
    expect((error as ApiError).isNetworkError).toBe(true)
  })

  it('builds the request URL from the configured base and prefix', async () => {
    const spy = stubFetch(async () => jsonResponse([]))
    await api.listJourneys({ status: 'saved', limit: 5 })
    expect(spy).toHaveBeenCalledTimes(1)
    const url = spy.mock.calls[0][0]
    expect(url.startsWith(`${API_BASE}/api/v1/journeys`)).toBe(true)
    expect(url).toContain('status=saved')
    expect(url).toContain('limit=5')
  })

  it('omits empty query parameters', async () => {
    const spy = stubFetch(async () => jsonResponse([]))
    await api.listJourneys({ status: undefined, limit: undefined })
    expect(spy.mock.calls[0][0]).toBe(`${API_BASE}/api/v1/journeys`)
  })

  it('sends a JSON body with the correct content type', async () => {
    const spy = stubFetch(async () => jsonResponse({ id: 1 }))
    await api.createJourney({ title: 'Walk' })
    const init = spy.mock.calls[0][1] as RequestInit
    expect(init.method).toBe('POST')
    expect((init.headers as Record<string, string>)['Content-Type']).toBe('application/json')
    expect(init.body).toBe(JSON.stringify({ title: 'Walk' }))
  })
})
