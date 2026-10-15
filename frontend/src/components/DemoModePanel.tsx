import { FlaskConical, Import, Loader2, Play, Square } from 'lucide-react'

import type { SampleRouteSummary } from '../types'
import { formatDistance, formatDuration } from '../utils/format'

interface Props {
  routes: SampleRouteSummary[]
  selectedRouteId: string | null
  onSelect: (routeId: string) => void
  onImport: () => void
  onReplay: () => void
  onStopReplay: () => void
  importing: boolean
  replaying: boolean
  progress: { sent: number; total: number } | null
  loadError: string | null
}

const SPEEDS = [1, 10, 60] as const

/**
 * DEMO MODE.
 *
 * Everything produced here is labelled as simulated: the journeys it creates are
 * stored with `source = "demo"` and the dashboard shows a DEMO badge, so sample
 * data is never presented as an ESP32-C3 recording.
 */
export default function DemoModePanel({
  routes,
  selectedRouteId,
  onSelect,
  onImport,
  onReplay,
  onStopReplay,
  importing,
  replaying,
  progress,
  loadError,
}: Props) {
  return (
    <div className="rounded-2xl border border-demo/35 bg-demo/5 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-demo">
          <FlaskConical size={15} /> DEMO MODE
        </h3>
        <span className="rounded-full border border-demo/40 bg-demo/10 px-2.5 py-0.5 text-[10px] font-semibold tracking-wide text-demo">
          SIMULATED DATA
        </span>
      </div>

      <p className="mt-2 text-[11px] leading-snug text-muted">
        Replay a bundled sample route for development and presentations when GPS reception is not
        possible (e.g. indoors). Imported routes are always stored as{' '}
        <code className="rounded bg-surface-2 px-1">source = demo</code> and are never mixed with
        hardware points.
      </p>

      {loadError ? (
        <p className="mt-2 rounded-lg border border-danger/40 bg-danger/10 px-2.5 py-1.5 text-[11px] text-danger">
          {loadError}
        </p>
      ) : null}

      <div className="mt-3 space-y-2">
        {routes.length === 0 && !loadError ? (
          <p className="text-[11px] text-muted">Loading sample routes…</p>
        ) : null}

        {routes.map((route) => {
          const selected = route.id === selectedRouteId
          return (
            <button
              key={route.id}
              type="button"
              onClick={() => onSelect(route.id)}
              className={`w-full rounded-xl border px-3 py-2 text-left transition ${
                selected
                  ? 'border-demo/60 bg-demo/15'
                  : 'border-edge bg-surface-2/50 hover:border-demo/40'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-[12px] font-semibold text-slate-100">{route.name}</span>
                <span className="shrink-0 text-[10px] text-muted tabular">
                  {formatDistance(route.distance_m)} · {formatDuration(route.duration_seconds)}
                </span>
              </div>
              <p className="mt-0.5 text-[10px] leading-snug text-muted">{route.description}</p>
              <p className="mt-1 text-[10px] text-muted tabular">{route.point_count} points</p>
            </button>
          )
        })}
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onImport}
          disabled={!selectedRouteId || importing || replaying}
          className="flex items-center gap-1.5 rounded-lg border border-demo/50 bg-demo/15 px-3 py-2 text-[12px] font-medium text-demo transition hover:bg-demo/25 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {importing ? <Loader2 size={14} className="animate-spin" /> : <Import size={14} />}
          Import instantly
        </button>

        {replaying ? (
          <button
            type="button"
            onClick={onStopReplay}
            className="flex items-center gap-1.5 rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-[12px] font-medium text-danger transition hover:bg-danger/20"
          >
            <Square size={14} /> Stop replay
          </button>
        ) : (
          <button
            type="button"
            onClick={onReplay}
            disabled={!selectedRouteId || importing}
            className="flex items-center gap-1.5 rounded-lg border border-edge bg-surface-2/80 px-3 py-2 text-[12px] font-medium text-slate-200 transition hover:border-accent/50 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Play size={14} /> Replay on the map
          </button>
        )}
      </div>

      {progress ? (
        <div className="mt-3">
          <div className="flex items-center justify-between text-[10px] text-muted">
            <span>Replay progress</span>
            <span className="tabular">
              {progress.sent}/{progress.total} points
            </span>
          </div>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-2">
            <div
              className="h-full rounded-full bg-demo transition-all"
              style={{
                width: `${progress.total ? Math.round((progress.sent / progress.total) * 100) : 0}%`,
              }}
            />
          </div>
        </div>
      ) : null}

      <p className="mt-3 text-[10px] leading-snug text-muted">
        Replay speed is {SPEEDS[2]}× — a 45-minute route appears in about 45 seconds. The points are
        timestamped as if they had been recorded live, so the statistics stay realistic.
      </p>
    </div>
  )
}
