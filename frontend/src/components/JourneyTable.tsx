import { FlaskConical, Image as ImageIcon, MapPin, Route } from 'lucide-react'

import type { Journey } from '../types'
import { formatDateTime, formatDistance, formatDuration, formatSpeed, statusLabel } from '../utils/format'

interface Props {
  journeys: Journey[]
  activeJourneyId: number | null
  onOpen: (journey: Journey) => void
  onOpenStudio: (journey: Journey) => void
}

function statusTone(status: string): string {
  switch (status) {
    case 'recording':
      return 'border-danger/40 bg-danger/10 text-danger'
    case 'paused':
      return 'border-warn/40 bg-warn/10 text-warn'
    case 'saved':
      return 'border-live/40 bg-live/10 text-live'
    default:
      return 'border-edge bg-surface-2 text-slate-300'
  }
}

export default function JourneyTable({ journeys, activeJourneyId, onOpen, onOpenStudio }: Props) {
  if (journeys.length === 0) {
    return (
      <div className="rounded-2xl border border-edge bg-surface p-6 text-center">
        <Route size={22} className="mx-auto text-muted" />
        <p className="mt-2 text-sm font-medium text-slate-200">No journeys yet</p>
        <p className="mt-1 text-xs text-muted">
          Start a recording on the dashboard, or import a DEMO MODE sample route.
        </p>
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-edge bg-surface">
      <table className="w-full border-collapse text-left text-[12px]">
        <thead>
          <tr className="border-b border-edge text-[10px] uppercase tracking-wider text-muted">
            <th className="px-3 py-2.5 font-semibold">Journey</th>
            <th className="hidden px-3 py-2.5 font-semibold sm:table-cell">Source</th>
            <th className="px-3 py-2.5 font-semibold">Distance</th>
            <th className="hidden px-3 py-2.5 font-semibold md:table-cell">Duration</th>
            <th className="hidden px-3 py-2.5 font-semibold md:table-cell">Avg speed</th>
            <th className="hidden px-3 py-2.5 font-semibold lg:table-cell">Points</th>
            <th className="hidden px-3 py-2.5 font-semibold lg:table-cell">Recorded</th>
            <th className="px-3 py-2.5 font-semibold">Actions</th>
          </tr>
        </thead>
        <tbody>
          {journeys.map((journey) => {
            const averageSpeed =
              journey.moving_seconds > 5 && journey.total_distance_m > 0
                ? (journey.total_distance_m / journey.moving_seconds) * 3.6
                : null
            const isActive = journey.id === activeJourneyId
            return (
              <tr
                key={journey.id}
                className={`border-b border-edge-soft last:border-0 transition ${
                  isActive ? 'bg-accent/8' : 'hover:bg-surface-2/50'
                }`}
              >
                <td className="px-3 py-2.5">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-slate-100">{journey.title}</span>
                    {isActive ? (
                      <span className="rounded border border-accent/40 bg-accent/12 px-1.5 py-0.5 text-[9px] text-accent">
                        OPEN
                      </span>
                    ) : null}
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-1.5">
                    <span
                      className={`rounded-full border px-1.5 py-0.5 text-[9px] font-semibold tracking-wide ${statusTone(
                        journey.status,
                      )}`}
                    >
                      {statusLabel(journey.status)}
                    </span>
                    <span className="text-[10px] text-muted tabular">#{journey.id}</span>
                    {journey.artwork_count > 0 ? (
                      <span className="flex items-center gap-1 text-[10px] text-muted">
                        <ImageIcon size={10} /> {journey.artwork_count}
                      </span>
                    ) : null}
                    {journey.device_id ? (
                      <span className="flex items-center gap-1 text-[10px] text-muted">
                        <MapPin size={10} /> {journey.device_id}
                      </span>
                    ) : null}
                  </div>
                </td>
                <td className="hidden px-3 py-2.5 sm:table-cell">
                  {journey.source === 'demo' ? (
                    <span className="flex items-center gap-1 text-[10px] font-medium text-demo">
                      <FlaskConical size={11} /> DEMO
                    </span>
                  ) : (
                    <span className="text-[10px] text-live">ESP32-C3</span>
                  )}
                </td>
                <td className="px-3 py-2.5 text-slate-200 tabular">
                  {formatDistance(journey.total_distance_m)}
                </td>
                <td className="hidden px-3 py-2.5 text-slate-200 tabular md:table-cell">
                  {formatDuration(journey.duration_seconds)}
                </td>
                <td className="hidden px-3 py-2.5 text-slate-200 tabular md:table-cell">
                  {averageSpeed === null ? formatSpeed(null) : formatSpeed(averageSpeed)}
                </td>
                <td className="hidden px-3 py-2.5 text-slate-200 tabular lg:table-cell">
                  {journey.point_count}
                </td>
                <td className="hidden px-3 py-2.5 text-[11px] text-muted lg:table-cell">
                  {formatDateTime(journey.started_at)}
                </td>
                <td className="px-3 py-2.5">
                  <div className="flex gap-1.5">
                    <button
                      type="button"
                      onClick={() => onOpen(journey)}
                      className="rounded-md border border-edge px-2 py-1 text-[11px] text-slate-200 transition hover:border-accent/50 hover:text-white"
                    >
                      Open
                    </button>
                    <button
                      type="button"
                      onClick={() => onOpenStudio(journey)}
                      disabled={journey.point_count === 0}
                      className="rounded-md border border-edge px-2 py-1 text-[11px] text-slate-200 transition hover:border-accent/50 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      Studio
                    </button>
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
