/** Human readable formatting helpers (mirrors the backend's formatting module). */

export function formatDistance(metres: number | null | undefined): string {
  if (metres === null || metres === undefined || Number.isNaN(metres)) {
    return '—'
  }
  if (metres < 1000) {
    return `${metres < 10 ? metres.toFixed(1) : Math.round(metres)} m`
  }
  return `${(metres / 1000).toFixed(2)} km`
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds) || seconds <= 0) {
    return '—'
  }
  const total = Math.round(seconds)
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const secs = total % 60
  if (hours > 0) {
    return `${hours}h ${String(minutes).padStart(2, '0')}m`
  }
  if (minutes > 0) {
    return `${minutes}m ${String(secs).padStart(2, '0')}s`
  }
  return `${secs}s`
}

export function formatSpeed(kmh: number | null | undefined): string {
  if (kmh === null || kmh === undefined || Number.isNaN(kmh)) {
    return 'not meaningful'
  }
  return `${kmh.toFixed(1)} km/h`
}

export function formatCoordinate(value: number | null | undefined, digits = 5): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—'
  }
  return value.toFixed(digits)
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) {
    return '—'
  }
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) {
    return '—'
  }
  return date.toLocaleString(undefined, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) {
    return '—'
  }
  const date = new Date(iso)
  return Number.isNaN(date.getTime())
    ? '—'
    : date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) {
    return '—'
  }
  const date = new Date(iso)
  return Number.isNaN(date.getTime())
    ? '—'
    : date.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' })
}

/** "3 s ago", "2 min ago", "1 h 4 min ago". */
export function formatRelative(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) {
    return 'never'
  }
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) {
    return 'unknown'
  }
  const seconds = Math.max(0, Math.round((now - then) / 1000))
  if (seconds < 5) return 'just now'
  if (seconds < 60) return `${seconds} s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) {
    const rest = minutes % 60
    return rest ? `${hours} h ${rest} min ago` : `${hours} h ago`
  }
  return formatDateTime(iso)
}

export function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return '—'
  }
  return value.toLocaleString()
}

export function statusLabel(status: string): string {
  switch (status) {
    case 'recording':
      return 'RECORDING'
    case 'paused':
      return 'PAUSED'
    case 'stopped':
      return 'STOPPED (unsaved)'
    case 'saved':
      return 'SAVED'
    default:
      return status.toUpperCase()
  }
}
