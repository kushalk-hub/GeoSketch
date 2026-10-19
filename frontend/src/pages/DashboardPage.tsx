import { useState } from 'react'
import { Check, Pencil, RefreshCw, X } from 'lucide-react'

import DemoModePanel from '../components/DemoModePanel'
import RecordingControls from '../components/RecordingControls'
import RouteMap from '../components/RouteMap'
import StatusPanel from '../components/StatusPanel'
import type {
  DeviceStatus,
  JourneyDetail,
  JourneyStatistics,
  SampleRouteSummary,
} from '../types'
import { formatDateTime, formatDistance, formatRelative } from '../utils/format'

interface DemoProps {
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

interface Props {
  status: DeviceStatus | null
  statusError: string | null
  journey: JourneyDetail | null
  statistics: JourneyStatistics | null
  journeyError: string | null
  pinned: boolean
  onReturnToLive: () => void
  onRefresh: () => void
  onRename: (title: string) => void
  recorder: {
    busy: boolean
    onStart: () => void
    onPause: () => void
    onResume: () => void
    onStop: () => void
    onSave: () => void
    onClear: () => void
  }
  demo: DemoProps
}

export default function DashboardPage({
  status,
  statusError,
  journey,
  statistics,
  journeyError,
  pinned,
  onReturnToLive,
  onRefresh,
  onRename,
  recorder,
  demo,
}: Props) {
  const [showRejected, setShowRejected] = useState(false)
  const [editingTitle, setEditingTitle] = useState(false)
  const [titleDraft, setTitleDraft] = useState('')

  const isLive = Boolean(status?.connected)
  const points = journey?.points ?? []
  const latestPoint = status?.latest_point ?? null
  const isDemoJourney = journey?.source === 'demo'

  const startEditing = () => {
    setTitleDraft(journey?.title ?? '')
    setEditingTitle(true)
  }

  return (
    <div className="space-y-4">
      {(statusError || journeyError) && (
        <div className="rounded-xl border border-danger/40 bg-danger/10 px-3.5 py-2.5 text-[12px] text-danger">
          {statusError ?? journeyError}
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_400px]">
        <div className="space-y-4">
          {/* --- journey header ------------------------------------------- */}
          <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-edge bg-surface px-4 py-3">
            {editingTitle ? (
              <div className="flex w-full items-center gap-2">
                <input
                  type="text"
                  value={titleDraft}
                  onChange={(event) => setTitleDraft(event.target.value)}
                  maxLength={160}
                  autoFocus
                  className="min-w-0 flex-1 rounded-lg border border-edge bg-surface-2/70 px-2.5 py-1.5 text-sm text-ink outline-none focus:border-accent/60"
                />
                <button
                  type="button"
                  onClick={() => {
                    onRename(titleDraft.trim() || 'Untitled journey')
                    setEditingTitle(false)
                  }}
                  className="rounded-lg border border-live/40 bg-live/10 p-1.5 text-live"
                  aria-label="Save title"
                >
                  <Check size={15} />
                </button>
                <button
                  type="button"
                  onClick={() => setEditingTitle(false)}
                  className="rounded-lg border border-edge p-1.5 text-muted"
                  aria-label="Cancel"
                >
                  <X size={15} />
                </button>
              </div>
            ) : (
              <>
                <div className="min-w-0">
                  <h2 className="truncate text-[15px] font-semibold text-ink">
                    {journey ? journey.title : 'No journey open'}
                  </h2>
                  <p className="text-[11px] text-muted">
                    {journey ? (
                      <>
                        journey #{journey.id} · started {formatDateTime(journey.started_at)} ·{' '}
                        {formatDistance(statistics?.distance_m ?? journey.total_distance_m)} ·{' '}
                        {points.length} points
                      </>
                    ) : (
                      <>Waiting for a recording. The ESP32-C3 creates a journey automatically.</>
                    )}
                  </p>
                </div>

                <div className="ml-auto flex flex-wrap items-center gap-1.5">
                  {isDemoJourney ? (
                    <span className="rounded-full border border-demo/40 bg-demo/10 px-2.5 py-1 text-[10px] font-semibold text-demo">
                      DEMO DATA
                    </span>
                  ) : journey ? (
                    <span className="rounded-full border border-live/30 bg-live/10 px-2.5 py-1 text-[10px] font-semibold text-live">
                      ESP32-C3
                    </span>
                  ) : null}

                  {pinned ? (
                    <button
                      type="button"
                      onClick={onReturnToLive}
                      className="rounded-lg border border-accent/40 bg-accent/10 px-2.5 py-1.5 text-[11px] font-medium text-accent transition hover:bg-accent/20"
                    >
                      Return to live
                    </button>
                  ) : null}

                  {journey && journey.status !== 'saved' ? (
                    <button
                      type="button"
                      onClick={startEditing}
                      className="flex items-center gap-1.5 rounded-lg border border-edge bg-surface-2/70 px-2.5 py-1.5 text-[11px] text-body transition hover:border-accent/50"
                    >
                      <Pencil size={12} /> Rename
                    </button>
                  ) : null}

                  <button
                    type="button"
                    onClick={onRefresh}
                    className="flex items-center gap-1.5 rounded-lg border border-edge bg-surface-2/70 px-2.5 py-1.5 text-[11px] text-body transition hover:border-accent/50"
                  >
                    <RefreshCw size={12} /> Refresh
                  </button>
                </div>
              </>
            )}
          </div>

          {/* --- map ------------------------------------------------------- */}
          <div className="relative">
            <RouteMap
              points={points}
              latestPoint={latestPoint}
              isLive={isLive}
              lastSeenAt={status?.device?.last_seen_at ?? null}
              heightClass="h-[440px] xl:h-[560px]"
              showRejected={showRejected}
            />
            <label className="absolute right-3 top-3 z-[500] flex items-center gap-1.5 rounded-lg border border-edge bg-surface/85 px-2.5 py-1.5 text-[11px] text-body backdrop-blur">
              <input
                type="checkbox"
                checked={showRejected}
                onChange={(event) => setShowRejected(event.target.checked)}
                className="accent-[#f59e0b]"
              />
              show rejected fixes
            </label>
          </div>

          <RecordingControls
            journey={journey}
            busy={recorder.busy}
            isDemoJourney={isDemoJourney}
            onStart={recorder.onStart}
            onPause={recorder.onPause}
            onResume={recorder.onResume}
            onStop={recorder.onStop}
            onSave={recorder.onSave}
            onClear={recorder.onClear}
          />
        </div>

        {/* --- right column ------------------------------------------------ */}
        <div className="space-y-4">
          <StatusPanel status={status} journey={journey} statistics={statistics} />

          <div className="rounded-2xl border border-edge bg-surface p-4">
            <h3 className="text-sm font-semibold text-ink">Point stream</h3>
            <ul className="mt-2 max-h-[220px] space-y-1.5 overflow-y-auto pr-1">
              {points.length === 0 ? (
                <li className="text-[11px] text-muted">
                  No points yet. Points appear here in the order the backend stored them.
                </li>
              ) : (
                [...points]
                  .slice(-12)
                  .reverse()
                  .map((point) => (
                    <li
                      key={point.id}
                      className="flex items-center justify-between gap-2 rounded-lg border border-edge-soft bg-surface-2/40 px-2.5 py-1.5 text-[11px]"
                    >
                      <span className="tabular text-body">
                        #{point.sequence} {point.latitude.toFixed(5)}, {point.longitude.toFixed(5)}
                      </span>
                      <span className="shrink-0 text-[10px] text-muted">
                        {point.satellites ?? '—'} sat ·{' '}
                        {formatRelative(point.gps_timestamp ?? point.server_timestamp)}
                        {point.is_plausible === false ? (
                          <span className="ml-1 text-warn">rejected</span>
                        ) : null}
                      </span>
                    </li>
                  ))
              )}
            </ul>
          </div>

          <DemoModePanel {...demo} />
        </div>
      </div>
    </div>
  )
}
