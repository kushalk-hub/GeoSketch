import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Download, Image as ImageIcon, Loader2, Palette, RefreshCw, Sparkles } from 'lucide-react'

import { ApiError, api } from '../services/api'
import type { ToastKind } from '../hooks/useToasts'
import type {
  Artwork,
  ArtworkPreview,
  ArtworkStyleId,
  ArtworkStyleInfo,
  JourneyDetail,
} from '../types'
import { formatDateTime, formatDistance, formatDuration } from '../utils/format'

interface Props {
  journey: JourneyDetail | null
  styles: ArtworkStyleInfo[]
  notify: (kind: ToastKind, message: string, detail?: string) => void
}

const PALETTES: { id: string; label: string; colours: string[] }[] = [
  { id: 'aurora', label: 'Aurora', colours: ['#22d3ee', '#818cf8', '#f472b6'] },
  { id: 'sunset', label: 'Sunset', colours: ['#fbbf24', '#fb7185', '#7c3aed'] },
  { id: 'ocean', label: 'Ocean', colours: ['#0ea5e9', '#22d3ee', '#a7f3d0'] },
  { id: 'forest', label: 'Forest', colours: ['#a3e635', '#22c55e', '#0f766e'] },
  { id: 'magma', label: 'Magma', colours: ['#fde047', '#f97316', '#dc2626'] },
  { id: 'mono', label: 'Mono', colours: ['#e2e8f0', '#94a3b8', '#475569'] },
]

function triggerDownload(url: string): void {
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.rel = 'noopener'
  anchor.target = '_blank'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
}

export default function ArtworkStudio({ journey, styles, notify }: Props) {
  const [style, setStyle] = useState<ArtworkStyleId>('minimal')
  const [palette, setPalette] = useState('aurora')
  const [background, setBackground] = useState('#0b1120')
  const [routeColor, setRouteColor] = useState('#38bdf8')
  const [accentColor, setAccentColor] = useState('#a78bfa')
  const [lineWidth, setLineWidth] = useState(6)
  const [glow, setGlow] = useState(true)
  const [title, setTitle] = useState('')
  const [showStart, setShowStart] = useState(true)
  const [showEnd, setShowEnd] = useState(true)

  const [preview, setPreview] = useState<ArtworkPreview | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [previewing, setPreviewing] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [artworks, setArtworks] = useState<Artwork[]>([])
  const requestId = useRef(0)

  const journeyId = journey?.id ?? null
  const pointCount = journey?.point_count ?? 0

  // Reset the customisation when another journey is opened.
  useEffect(() => {
    setTitle(journey?.title ?? '')
    setArtworks([])
    setPreview(null)
    setPreviewError(null)
  }, [journeyId, journey?.title])

  const loadArtworks = useCallback(async () => {
    if (journeyId === null) {
      setArtworks([])
      return
    }
    try {
      setArtworks(await api.listArtworks(journeyId))
    } catch (cause) {
      notify('error', 'Could not load the artwork history', String(cause))
    }
  }, [journeyId, notify])

  useEffect(() => {
    void loadArtworks()
  }, [loadArtworks])

  const customization = useMemo(
    () => ({
      background,
      route_color: routeColor,
      accent_color: accentColor,
      line_width: lineWidth,
      glow,
      show_start_marker: showStart,
      show_end_marker: showEnd,
      title: title || undefined,
    }),
    [accentColor, background, glow, lineWidth, routeColor, showEnd, showStart, title],
  )

  // --- debounced preview: the backend does the real rendering --------------
  useEffect(() => {
    if (journeyId === null || pointCount === 0) {
      setPreview(null)
      return
    }
    const id = requestId.current + 1
    requestId.current = id
    const timer = window.setTimeout(async () => {
      setPreviewing(true)
      try {
        const next = await api.previewArtwork(journeyId, {
          style,
          title: title || undefined,
          palette,
          customization,
        })
        if (requestId.current !== id) return
        setPreview(next)
        setPreviewError(null)
      } catch (cause) {
        if (requestId.current !== id) return
        setPreviewError(cause instanceof ApiError ? cause.message : String(cause))
      } finally {
        if (requestId.current === id) setPreviewing(false)
      }
    }, 320)

    return () => window.clearTimeout(timer)
  }, [customization, journeyId, palette, pointCount, style, title])

  const generate = useCallback(async () => {
    if (journeyId === null) {
      notify('info', 'No journey selected', 'Record or open a journey first.')
      return
    }
    setGenerating(true)
    try {
      const artwork = await api.generateArtwork(journeyId, {
        style,
        title: title || undefined,
        palette,
        export_format: 'png',
        customization,
      })
      notify(
        'success',
        'Artwork generated',
        `${artwork.width}×${artwork.height} px · PNG + SVG stored`,
      )
      await loadArtworks()
    } catch (cause) {
      notify(
        'error',
        'Artwork generation failed',
        cause instanceof ApiError ? cause.message : String(cause),
      )
    } finally {
      setGenerating(false)
    }
  }, [customization, journeyId, loadArtworks, notify, palette, style, title])

  if (!journey) {
    return (
      <div className="rounded-2xl border border-edge bg-surface p-6 text-center">
        <ImageIcon size={22} className="mx-auto text-muted" />
        <p className="mt-2 text-sm font-medium text-slate-200">No journey selected</p>
        <p className="mt-1 text-xs text-muted">
          Open a journey from the Journeys tab (or record one) to generate route artwork.
        </p>
      </div>
    )
  }

  const activeStyle = styles.find((item) => item.id === style)

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
      {/* --- preview + export ------------------------------------------- */}
      <div className="space-y-3">
        <div className="rounded-2xl border border-edge bg-surface p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="min-w-0">
              <h2 className="truncate text-sm font-semibold text-slate-100">{journey.title}</h2>
              <p className="text-[11px] text-muted">
                journey #{journey.id} ·{' '}
                <span className={journey.source === 'demo' ? 'text-demo' : 'text-muted'}>
                  {journey.source === 'demo' ? 'DEMO DATA' : 'ESP32-C3 hardware'}
                </span>{' '}
                · {formatDistance(journey.total_distance_m)} ·{' '}
                {formatDuration(journey.duration_seconds)} · {pointCount} points
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => void loadArtworks()}
                className="flex items-center gap-1.5 rounded-lg border border-edge bg-surface-2/70 px-2.5 py-1.5 text-[11px] text-slate-200 transition hover:border-accent/50"
              >
                <RefreshCw size={13} /> Refresh
              </button>
              <button
                type="button"
                onClick={() => void generate()}
                disabled={generating || pointCount === 0}
                className="flex items-center gap-1.5 rounded-lg border border-accent/50 bg-accent/15 px-3 py-1.5 text-[12px] font-medium text-accent transition hover:bg-accent/25 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
              >
                {generating ? (
                  <Loader2 size={13} className="animate-spin" />
                ) : (
                  <Sparkles size={13} />
                )}
                Generate & store
              </button>
            </div>
          </div>

          <div className="relative mt-3 overflow-hidden rounded-xl border border-edge bg-abyss">
            {preview ? (
              <div
                className="artwork-preview"
                // The SVG is produced by our own backend renderer (no user HTML).
                dangerouslySetInnerHTML={{ __html: preview.svg }}
              />
            ) : (
              <div className="grid h-[320px] place-items-center">
                <p className="text-xs text-muted">
                  {pointCount === 0
                    ? 'This journey has no GPS points yet — nothing to draw.'
                    : 'Rendering preview…'}
                </p>
              </div>
            )}
            {previewing ? (
              <span className="absolute right-3 top-3 rounded-full border border-edge bg-surface/80 px-2 py-0.5 text-[10px] text-muted backdrop-blur">
                rendering…
              </span>
            ) : null}
          </div>

          {previewError ? (
            <p className="mt-2 rounded-lg border border-danger/40 bg-danger/10 px-2.5 py-1.5 text-[11px] text-danger">
              {previewError}
            </p>
          ) : null}

          {preview ? (
            <div className="mt-3 grid gap-2 text-[11px] sm:grid-cols-2">
              <div className="rounded-lg border border-edge bg-surface-2/50 px-3 py-2">
                <p className="font-semibold text-slate-200">Coordinate processing</p>
                <ul className="mt-1 space-y-0.5 text-muted tabular">
                  <li>source fixes: {preview.processing.source_points}</li>
                  <li>drawn points: {preview.processing.drawn_points}</li>
                  <li>redundant points removed: {preview.processing.redundant_removed}</li>
                  <li>rejected fixes excluded: {preview.processing.excluded_points}</li>
                  <li>gaps split: {preview.processing.gap_cuts}</li>
                  <li>impossible jumps split: {preview.processing.jump_cuts}</li>
                  <li>segments drawn: {preview.processing.segments}</li>
                </ul>
              </div>
              <div className="rounded-lg border border-edge bg-surface-2/50 px-3 py-2">
                <p className="font-semibold text-slate-200">Canvas</p>
                <ul className="mt-1 space-y-0.5 text-muted tabular">
                  <li>
                    {preview.width} × {preview.height} px
                  </li>
                  <li>projection: {preview.processing.projection}</li>
                  <li>scale: {preview.processing.scale_px_per_m} px/m</li>
                  <li>distance drawn: {formatDistance(preview.distance_m)}</li>
                  <li>duration: {formatDuration(preview.duration_seconds)}</li>
                  <li>aspect ratio preserved</li>
                </ul>
              </div>
            </div>
          ) : null}

          <p className="mt-2 text-[10px] leading-snug text-muted">
            The raw GPS points are stored untouched; only this derived canvas representation is
            filtered (sub-pixel points removed, breaks preserved). A recorded walk only looks like a
            recognisable shape if that is the route you actually walked.
          </p>
        </div>

        {/* --- history ------------------------------------------------------ */}
        <div className="rounded-2xl border border-edge bg-surface p-4">
          <h3 className="text-sm font-semibold text-slate-100">
            Saved artworks{' '}
            <span className="text-muted">({artworks.length})</span>
          </h3>
          {artworks.length === 0 ? (
            <p className="mt-1 text-[11px] text-muted">
              Nothing stored yet. Generate an artwork to keep a PNG + SVG pair with its settings.
            </p>
          ) : (
            <ul className="mt-2 space-y-2">
              {artworks.map((artwork) => (
                <li
                  key={artwork.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-edge bg-surface-2/50 px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="truncate text-[12px] font-medium text-slate-100">
                      {artwork.title}{' '}
                      <span className="text-muted">· {artwork.style}</span>
                    </p>
                    <p className="text-[10px] text-muted tabular">
                      {artwork.width}×{artwork.height} · {artwork.point_count} pts ·{' '}
                      {artwork.segment_count} seg · {formatDateTime(artwork.created_at)}
                    </p>
                  </div>
                  <div className="flex gap-1.5">
                    <button
                      type="button"
                      onClick={() => triggerDownload(api.artworkUrl(artwork, 'png'))}
                      className="flex items-center gap-1 rounded-md border border-edge px-2 py-1 text-[11px] text-slate-200 transition hover:border-accent/50 hover:text-white"
                    >
                      <Download size={12} /> PNG
                    </button>
                    <button
                      type="button"
                      onClick={() => triggerDownload(api.artworkUrl(artwork, 'svg'))}
                      className="flex items-center gap-1 rounded-md border border-edge px-2 py-1 text-[11px] text-slate-200 transition hover:border-accent/50 hover:text-white"
                    >
                      <Download size={12} /> SVG
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* --- controls ---------------------------------------------------- */}
      <div className="space-y-3">
        <div className="rounded-2xl border border-edge bg-surface p-4">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-100">
            <Palette size={15} className="text-accent" /> Style
          </h3>
          <div className="mt-2 space-y-2">
            {styles.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setStyle(item.id)}
                className={`w-full rounded-xl border px-3 py-2 text-left transition ${
                  style === item.id
                    ? 'border-accent/60 bg-accent/12'
                    : 'border-edge bg-surface-2/50 hover:border-accent/40'
                }`}
              >
                <p className="text-[12px] font-semibold text-slate-100">{item.label}</p>
                <p className="mt-0.5 text-[10px] leading-snug text-muted">{item.description}</p>
              </button>
            ))}
          </div>
          {activeStyle ? (
            <p className="mt-2 text-[10px] text-muted tabular">
              default canvas {activeStyle.default_width} × {activeStyle.default_height} px
            </p>
          ) : null}
        </div>

        <div className="rounded-2xl border border-edge bg-surface p-4">
          <h3 className="text-sm font-semibold text-slate-100">Customisation</h3>

          <label className="mt-3 block text-[11px] font-medium text-muted">
            Artwork title
            <input
              type="text"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              maxLength={120}
              placeholder={journey.title}
              className="mt-1 w-full rounded-lg border border-edge bg-surface-2/70 px-2.5 py-1.5 text-[12px] text-slate-100 outline-none transition focus:border-accent/60"
            />
          </label>

          <div className="mt-3 grid grid-cols-3 gap-2">
            {[
              { label: 'Background', value: background, set: setBackground },
              { label: 'Route', value: routeColor, set: setRouteColor },
              { label: 'Accent', value: accentColor, set: setAccentColor },
            ].map(({ label, value, set }) => (
              <label key={label} className="text-[11px] font-medium text-muted">
                {label}
                <span className="mt-1 flex items-center gap-1.5 rounded-lg border border-edge bg-surface-2/70 px-1.5 py-1">
                  <input
                    type="color"
                    value={value}
                    onChange={(event) => set(event.target.value)}
                    className="h-5 w-6 cursor-pointer border-0 bg-transparent p-0"
                  />
                  <span className="text-[10px] tabular text-slate-300">{value}</span>
                </span>
              </label>
            ))}
          </div>

          <label className="mt-3 block text-[11px] font-medium text-muted">
            Line width · {lineWidth} px
            <input
              type="range"
              min={1}
              max={20}
              step={0.5}
              value={lineWidth}
              onChange={(event) => setLineWidth(Number(event.target.value))}
              className="mt-1 w-full accent-[#38bdf8]"
            />
          </label>

          <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-slate-300">
            <label className="flex items-center gap-1.5">
              <input
                type="checkbox"
                checked={glow}
                onChange={(event) => setGlow(event.target.checked)}
                className="accent-[#38bdf8]"
              />
              glow
            </label>
            <label className="flex items-center gap-1.5">
              <input
                type="checkbox"
                checked={showStart}
                onChange={(event) => setShowStart(event.target.checked)}
                className="accent-[#38bdf8]"
              />
              start marker
            </label>
            <label className="flex items-center gap-1.5">
              <input
                type="checkbox"
                checked={showEnd}
                onChange={(event) => setShowEnd(event.target.checked)}
                className="accent-[#38bdf8]"
              />
              end marker
            </label>
          </div>

          <div className="mt-3">
            <p className="text-[11px] font-medium text-muted">Colour ramp (gradient style)</p>
            <div className="mt-1.5 grid grid-cols-3 gap-1.5">
              {PALETTES.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setPalette(item.id)}
                  className={`rounded-lg border px-2 py-1.5 text-left transition ${
                    palette === item.id
                      ? 'border-accent/60 bg-accent/12'
                      : 'border-edge bg-surface-2/50 hover:border-accent/40'
                  }`}
                >
                  <span className="flex gap-0.5">
                    {item.colours.map((colour) => (
                      <span
                        key={colour}
                        className="h-2.5 w-2.5 rounded-full"
                        style={{ backgroundColor: colour }}
                      />
                    ))}
                  </span>
                  <span className="mt-1 block text-[10px] text-slate-300">{item.label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
