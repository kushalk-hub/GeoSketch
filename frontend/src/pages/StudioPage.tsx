import ArtworkStudio from '../components/ArtworkStudio'
import type { ArtworkStyleInfo, Journey, JourneyDetail } from '../types'
import type { ToastKind } from '../hooks/useToasts'
import { formatDistance, statusLabel } from '../utils/format'

interface Props {
  journey: JourneyDetail | null
  journeys: Journey[]
  styles: ArtworkStyleInfo[]
  onSelectJourney: (journey: Journey) => void
  notify: (kind: ToastKind, message: string, detail?: string) => void
}

export default function StudioPage({
  journey,
  journeys,
  styles,
  onSelectJourney,
  notify,
}: Props) {
  const withPoints = journeys.filter((item) => item.point_count > 0)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-edge bg-surface px-4 py-3">
        <div className="min-w-0">
          <h2 className="text-[15px] font-semibold text-ink">Artwork studio</h2>
          <p className="text-[11px] text-muted">
            Five styles rendered by the backend from the stored GPS points — vector SVG and raster
            PNG, no machine learning and no paid service.
          </p>
        </div>

        <label className="ml-auto flex items-center gap-2 text-[11px] text-muted">
          Journey
          <select
            value={journey?.id ?? ''}
            onChange={(event) => {
              const selected = journeys.find((item) => item.id === Number(event.target.value))
              if (selected) {
                onSelectJourney(selected)
              }
            }}
            className="max-w-[280px] rounded-lg border border-edge bg-surface-2/70 px-2.5 py-1.5 text-[12px] text-ink outline-none"
          >
            <option value="" disabled>
              {withPoints.length === 0 ? 'No journeys with points yet' : 'Select a journey…'}
            </option>
            {withPoints.map((item) => (
              <option key={item.id} value={item.id}>
                #{item.id} · {item.title} · {item.source === 'demo' ? 'DEMO' : 'hardware'} ·{' '}
                {statusLabel(item.status)} · {formatDistance(item.total_distance_m)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {!journey ? (
        <div className="rounded-2xl border border-edge bg-surface p-6 text-center">
          <p className="text-sm text-body">Select a journey to open the studio</p>
          <p className="mt-1 text-xs text-muted">
            Journeys with at least one GPS point can be turned into artwork. Record one on the
            dashboard, or import a DEMO MODE sample route.
          </p>
        </div>
      ) : (
        <ArtworkStudio journey={journey} styles={styles} notify={notify} />
      )}
    </div>
  )
}
