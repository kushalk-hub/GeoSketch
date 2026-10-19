import { useMemo, useState } from 'react'
import { FlaskConical, RefreshCw, Route, Search, Smartphone } from 'lucide-react'

import JourneyTable from '../components/JourneyTable'
import type { Journey, JourneyStatus } from '../types'
import { formatDistance } from '../utils/format'

interface Props {
  journeys: Journey[]
  activeJourneyId: number | null
  loading: boolean
  onOpen: (journey: Journey) => void
  onOpenStudio: (journey: Journey) => void
  onRefresh: () => void
}

const STATUS_FILTERS: (JourneyStatus | 'all')[] = ['all', 'recording', 'paused', 'stopped', 'saved']

export default function JourneysPage({
  journeys,
  activeJourneyId,
  loading,
  onOpen,
  onOpenStudio,
  onRefresh,
}: Props) {
  const [search, setSearch] = useState('')
  const [sourceFilter, setSourceFilter] = useState<'all' | 'hardware' | 'demo'>('all')
  const [statusFilter, setStatusFilter] = useState<JourneyStatus | 'all'>('all')

  const filtered = useMemo(
    () =>
      journeys.filter((journey) => {
        if (sourceFilter !== 'all' && journey.source !== sourceFilter) return false
        if (statusFilter !== 'all' && journey.status !== statusFilter) return false
        if (search && !journey.title.toLowerCase().includes(search.toLowerCase())) return false
        return true
      }),
    [journeys, search, sourceFilter, statusFilter],
  )

  const totals = useMemo(() => {
    const hardware = journeys.filter((journey) => journey.source === 'hardware')
    const demo = journeys.filter((journey) => journey.source === 'demo')
    return {
      distance: journeys.reduce((sum, journey) => sum + journey.total_distance_m, 0),
      points: journeys.reduce((sum, journey) => sum + journey.point_count, 0),
      hardware: hardware.length,
      demo: demo.length,
      saved: journeys.filter((journey) => journey.status === 'saved').length,
    }
  }, [journeys])

  return (
    <div className="space-y-4">
      <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-edge bg-surface px-3.5 py-3">
          <p className="text-[10px] uppercase tracking-wider text-muted">Journeys</p>
          <p className="mt-1 text-lg font-semibold text-ink tabular">{journeys.length}</p>
          <p className="text-[10px] text-muted">
            {totals.saved} saved · {totals.hardware} hardware · {totals.demo} demo
          </p>
        </div>
        <div className="rounded-xl border border-edge bg-surface px-3.5 py-3">
          <p className="text-[10px] uppercase tracking-wider text-muted">Total distance</p>
          <p className="mt-1 text-lg font-semibold text-ink tabular">
            {formatDistance(totals.distance)}
          </p>
          <p className="text-[10px] text-muted">GPS estimate across all journeys</p>
        </div>
        <div className="rounded-xl border border-edge bg-surface px-3.5 py-3">
          <p className="text-[10px] uppercase tracking-wider text-muted">Recorded points</p>
          <p className="mt-1 text-lg font-semibold text-ink tabular">{totals.points}</p>
          <p className="text-[10px] text-muted">raw fixes stored (nothing overwritten)</p>
        </div>
        <div className="rounded-xl border border-edge bg-surface px-3.5 py-3">
          <p className="text-[10px] uppercase tracking-wider text-muted">Data provenance</p>
          <div className="mt-1 flex items-center gap-2 text-[11px]">
            <span className="flex items-center gap-1 text-live">
              <Smartphone size={12} /> {totals.hardware} hardware
            </span>
            <span className="flex items-center gap-1 text-demo">
              <FlaskConical size={12} /> {totals.demo} demo
            </span>
          </div>
          <p className="mt-1 text-[10px] text-muted">
            hardware and simulated points are stored separately
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-edge bg-surface px-3.5 py-3">
        <label className="flex items-center gap-1.5 rounded-lg border border-edge bg-surface-2/70 px-2.5 py-1.5">
          <Search size={13} className="text-muted" />
          <input
            type="text"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search titles…"
            className="w-40 bg-transparent text-[12px] text-ink outline-none placeholder:text-muted"
          />
        </label>

        <select
          value={sourceFilter}
          onChange={(event) => setSourceFilter(event.target.value as typeof sourceFilter)}
          className="rounded-lg border border-edge bg-surface-2/70 px-2.5 py-1.5 text-[12px] text-ink outline-none"
        >
          <option value="all">All sources</option>
          <option value="hardware">ESP32-C3 hardware</option>
          <option value="demo">DEMO MODE</option>
        </select>

        <select
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)}
          className="rounded-lg border border-edge bg-surface-2/70 px-2.5 py-1.5 text-[12px] text-ink outline-none"
        >
          {STATUS_FILTERS.map((value) => (
            <option key={value} value={value}>
              {value === 'all' ? 'All statuses' : value}
            </option>
          ))}
        </select>

        <button
          type="button"
          onClick={onRefresh}
          className="ml-auto flex items-center gap-1.5 rounded-lg border border-edge bg-surface-2/70 px-2.5 py-1.5 text-[11px] text-body transition hover:border-accent/50"
        >
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      {filtered.length === 0 && journeys.length > 0 ? (
        <div className="rounded-2xl border border-edge bg-surface p-6 text-center">
          <Route size={20} className="mx-auto text-muted" />
          <p className="mt-2 text-sm text-body">No journey matches these filters</p>
        </div>
      ) : (
        <JourneyTable
          journeys={filtered}
          activeJourneyId={activeJourneyId}
          onOpen={onOpen}
          onOpenStudio={onOpenStudio}
        />
      )}
    </div>
  )
}
