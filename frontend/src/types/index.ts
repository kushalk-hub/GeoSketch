/**
 * Types mirroring the GeoSketch backend schemas.
 *
 * Timestamps are ISO-8601 strings in UTC (always ending with `Z`), so they can
 * be fed straight into `new Date(...)` in the browser.
 */

export type JourneyStatus = 'recording' | 'paused' | 'stopped' | 'saved'
export type JourneySource = 'hardware' | 'demo'
export type ArtworkStyleId = 'minimal' | 'neon' | 'gradient' | 'poster' | 'custom'

export interface ApiErrorBody {
  code: string
  message: string
  details?: Record<string, unknown>
}

export interface GPSPoint {
  id: number
  journey_id: number
  device_id: string | null
  sequence: number
  latitude: number
  longitude: number
  altitude: number | null
  speed_kmh: number | null
  satellites: number | null
  gps_timestamp: string | null
  server_timestamp: string
  source: JourneySource
  is_plausible: boolean
  rejected_reason: string | null
}

export interface Journey {
  id: number
  title: string
  device_id: string | null
  source: JourneySource
  status: JourneyStatus
  notes: string | null
  created_at: string
  started_at: string
  paused_at: string | null
  finished_at: string | null
  saved_at: string | null
  total_distance_m: number
  duration_seconds: number
  moving_seconds: number
  point_count: number
  start_latitude: number | null
  start_longitude: number | null
  end_latitude: number | null
  end_longitude: number | null
  artwork_count: number
}

export interface JourneyDetail extends Journey {
  points: GPSPoint[]
}

export interface JourneyStatistics {
  journey_id: number
  source: JourneySource
  status: JourneyStatus
  distance_m: number
  distance_km: number
  duration_seconds: number
  moving_seconds: number
  average_speed_kmh: number | null
  max_speed_kmh: number | null
  total_points: number
  used_points: number
  filtered_points: number
  rejected_points: number
  gap_count: number
  jump_count: number
  start_latitude: number | null
  start_longitude: number | null
  end_latitude: number | null
  end_longitude: number | null
  started_at: string | null
  finished_at: string | null
  is_estimate: boolean
  note: string
}

export interface Device {
  device_id: string
  name: string
  connection_status: 'unknown' | 'online' | 'offline'
  firmware_version: string | null
  last_seen_at: string | null
  last_latitude: number | null
  last_longitude: number | null
  last_satellites: number | null
  last_fix_at: string | null
  points_received: number
  is_live: boolean
  seconds_since_last_seen: number | null
}

export interface DeviceStatus {
  device: Device | null
  connected: boolean
  active_journey_id: number | null
  latest_point: GPSPoint | null
  offline_after_seconds: number
  server_time: string
}

export interface ArtworkCustomization {
  background?: string
  route_color?: string
  accent_color?: string
  line_width?: number
  glow?: boolean
  title?: string
  subtitle?: string
  show_start_marker?: boolean
  show_end_marker?: boolean
  palette?: string | null
}

export interface Artwork {
  id: number
  journey_id: number
  title: string
  style: ArtworkStyleId
  export_format: string
  width: number
  height: number
  point_count: number
  segment_count: number
  distance_m: number
  created_at: string
  customization: ArtworkCustomization
  png_url: string | null
  svg_url: string | null
}

export interface ArtworkProcessing {
  source_points: number
  drawn_points: number
  redundant_removed: number
  excluded_points: number
  gap_cuts: number
  jump_cuts: number
  segments: number
  scale_px_per_m: number
  projection: string
}

export interface ArtworkPreview {
  style: ArtworkStyleId
  title: string
  width: number
  height: number
  svg: string
  point_count: number
  segment_count: number
  distance_m: number
  duration_seconds: number
  processing: ArtworkProcessing
}

export interface ArtworkStyleInfo {
  id: ArtworkStyleId
  label: string
  description: string
  default_width: number
  default_height: number
}

export interface SamplePoint {
  t: number
  latitude: number
  longitude: number
  altitude: number | null
  speed_kmh: number | null
  satellites: number | null
}

export interface SampleRouteSummary {
  id: string
  name: string
  description: string
  source: 'demo'
  point_count: number
  distance_m: number
  duration_seconds: number
  is_demo: boolean
}

export interface SampleRouteDetail extends SampleRouteSummary {
  points: SamplePoint[]
}

export interface HealthResponse {
  status: string
  service: string
  time: string
  database: string
  devices: number
  journeys: number
  device_offline_after_seconds: number
  artwork_styles: ArtworkStyleId[]
}

export interface GPSPointPayload {
  latitude: number
  longitude: number
  altitude?: number | null
  speed_kmh?: number | null
  satellites?: number | null
  timestamp?: string | null
  device_id?: string | null
  client_point_id?: string | null
  journey_id?: number | null
}

/** Route segment used by the map: drawn as one continuous polyline. */
export interface RouteSegment {
  /** [lat, lng] pairs in chronological order. */
  positions: [number, number][]
  /** True when the segment follows a recording gap or a rejected jump. */
  afterBreak: boolean
}
