/**
 * Thin, typed client for the GeoSketch API.
 *
 * Every failure is normalised into an `ApiError` carrying the backend's
 * `{ error: { code, message, details } }` envelope, so the UI can show a real
 * reason instead of "something went wrong".
 */

import type {
  Artwork,
  ArtworkPreview,
  ArtworkStyleId,
  ArtworkStyleInfo,
  Device,
  DeviceStatus,
  GPSPointPayload,
  HealthResponse,
  Journey,
  JourneyDetail,
  JourneyStatistics,
  SampleRouteDetail,
  SampleRouteSummary,
} from '../types'

const RAW_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'
export const API_BASE = RAW_BASE.replace(/\/+$/, '')
export const API_PREFIX = '/api/v1'
export const CONFIGURED_DEVICE_ID = import.meta.env.VITE_DEVICE_ID ?? 'geosketch-01'

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details?: Record<string, unknown>

  constructor(status: number, code: string, message: string, details?: Record<string, unknown>) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }

  /** True for connection failures (backend down / wrong IP). */
  get isNetworkError(): boolean {
    return this.status === 0
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${API_PREFIX}${path}`
  let response: Response
  try {
    response = await fetch(url, {
      ...init,
      headers: {
        Accept: 'application/json',
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...(init.headers ?? {}),
      },
    })
  } catch (cause) {
    throw new ApiError(
      0,
      'network_error',
      `Cannot reach the GeoSketch API at ${API_BASE}. Is the backend running?`,
      { cause: String(cause) },
    )
  }

  if (response.status === 204) {
    return undefined as T
  }

  const text = await response.text()
  let payload: unknown = null
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = null
    }
  }

  if (!response.ok) {
    const envelope = (payload as { error?: { code?: string; message?: string; details?: Record<string, unknown> } } | null)?.error
    throw new ApiError(
      response.status,
      envelope?.code ?? `http_${response.status}`,
      envelope?.message ?? `Request failed with status ${response.status}`,
      envelope?.details,
    )
  }

  return payload as T
}

function query(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      search.set(key, String(value))
    }
  })
  const text = search.toString()
  return text ? `?${text}` : ''
}

export const api = {
  // --- meta ---------------------------------------------------------------
  health: () => request<HealthResponse>('/health'),
  artworkStyles: () => request<ArtworkStyleInfo[]>('/artwork/styles'),

  // --- devices ------------------------------------------------------------
  listDevices: () => request<Device[]>('/devices'),
  deviceStatus: (deviceId: string) =>
    request<DeviceStatus>(`/devices/${encodeURIComponent(deviceId)}/status`),

  // --- journeys -----------------------------------------------------------
  listJourneys: (params: {
    status?: string
    source?: string
    savedOnly?: boolean
    limit?: number
  } = {}) =>
    request<Journey[]>(
      `/journeys${query({
        status: params.status,
        source: params.source,
        saved_only: params.savedOnly,
        limit: params.limit,
      })}`,
    ),

  getJourney: (journeyId: number) => request<JourneyDetail>(`/journeys/${journeyId}`),

  createJourney: (body: {
    title?: string
    device_id?: string | null
    source?: 'hardware' | 'demo'
    start_immediately?: boolean
    notes?: string
    started_at?: string
  }) => request<Journey>('/journeys', { method: 'POST', body: JSON.stringify(body) }),

  updateJourney: (journeyId: number, body: { title?: string; notes?: string }) =>
    request<Journey>(`/journeys/${journeyId}`, { method: 'PATCH', body: JSON.stringify(body) }),

  deleteJourney: (journeyId: number) =>
    request<{ message: string }>(`/journeys/${journeyId}`, { method: 'DELETE' }),

  startRecording: (journeyId: number) =>
    request<Journey>(`/journeys/${journeyId}/start`, { method: 'POST' }),
  pauseRecording: (journeyId: number) =>
    request<Journey>(`/journeys/${journeyId}/pause`, { method: 'POST' }),
  resumeRecording: (journeyId: number) =>
    request<Journey>(`/journeys/${journeyId}/resume`, { method: 'POST' }),
  stopRecording: (journeyId: number) =>
    request<Journey>(`/journeys/${journeyId}/stop`, { method: 'POST' }),
  saveJourney: (journeyId: number) =>
    request<Journey>(`/journeys/${journeyId}/save`, { method: 'POST' }),

  statistics: (journeyId: number) =>
    request<JourneyStatistics>(`/journeys/${journeyId}/statistics`),

  addPoints: (journeyId: number, points: GPSPointPayload[], source: 'demo' | 'hardware' = 'demo') =>
    request<{ received: number; stored: number; duplicates: number; rejected: number; journey_id: number }>(
      `/journeys/${journeyId}/points`,
      { method: 'POST', body: JSON.stringify({ points, source }) },
    ),

  // --- artwork ------------------------------------------------------------
  previewArtwork: (
    journeyId: number,
    body: {
      style: ArtworkStyleId
      title?: string
      palette?: string | null
      customization?: Record<string, unknown>
    },
  ) => request<ArtworkPreview>(`/journeys/${journeyId}/artwork/preview`, {
    method: 'POST',
    body: JSON.stringify(body),
  }),

  generateArtwork: (
    journeyId: number,
    body: {
      style: ArtworkStyleId
      title?: string
      palette?: string | null
      export_format?: 'png' | 'svg'
      width?: number
      height?: number
      customization?: Record<string, unknown>
    },
  ) => request<Artwork>(`/journeys/${journeyId}/artwork`, {
    method: 'POST',
    body: JSON.stringify(body),
  }),

  listArtworks: (journeyId: number) => request<Artwork[]>(`/journeys/${journeyId}/artworks`),

  artworkUrl: (artwork: Artwork, format: 'png' | 'svg') =>
    `${API_BASE}${artwork[format === 'png' ? 'png_url' : 'svg_url'] ?? `/api/v1/artworks/${artwork.id}/download?format=${format}`}`,

  // --- demo mode ----------------------------------------------------------
  demoRoutes: () => request<SampleRouteSummary[]>('/demo/routes'),
  demoRoute: (routeId: string) =>
    request<SampleRouteDetail>(`/demo/routes/${encodeURIComponent(routeId)}`),
  importDemoRoute: (
    routeId: string,
    body: { title?: string; duration_scale?: number } = {},
  ) =>
    request<Journey>(`/demo/routes/${encodeURIComponent(routeId)}/import`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
}

export type Api = typeof api
