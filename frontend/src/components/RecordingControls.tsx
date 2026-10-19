import type { ReactNode } from 'react'
import { CircleDot, Loader2, Pause, Play, RotateCcw, Save, Square, Trash2 } from 'lucide-react'

import type { JourneyDetail } from '../types'
import { statusLabel } from '../utils/format'

interface Props {
  journey: JourneyDetail | null
  busy: boolean
  isDemoJourney: boolean
  onStart: () => void
  onPause: () => void
  onResume: () => void
  onStop: () => void
  onSave: () => void
  onClear: () => void
}

const FLOW = ['recording', 'paused', 'stopped', 'saved'] as const

function Button({
  onClick,
  disabled,
  busy,
  tone = 'default',
  icon,
  children,
  title,
}: {
  onClick: () => void
  disabled?: boolean
  busy?: boolean
  tone?: 'default' | 'primary' | 'danger' | 'success'
  icon: ReactNode
  children: ReactNode
  title?: string
}) {
  const tones = {
    default:
      'border-edge bg-surface text-body hover:border-accent/50 hover:bg-surface-2 hover:text-ink',
    primary:
      'border-accent bg-accent text-white shadow-sm hover:bg-accent/90',
    danger: 'border-danger/25 bg-danger/10 text-danger hover:bg-danger/20',
    success: 'border-live/25 bg-live/10 text-live hover:bg-live/20',
  } as const

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || busy}
      title={title}
      className={`flex items-center justify-center gap-2 rounded-xl border px-3.5 py-2.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-40 ${tones[tone]}`}
    >
      {busy ? <Loader2 size={15} className="animate-spin" /> : icon}
      {children}
    </button>
  )
}

/**
 * Start / Pause / Resume / Stop / Save / Clear.
 *
 * Buttons are disabled based on the *current* journey status, and the backend
 * independently refuses invalid transitions with HTTP 409 — so a finished
 * journey can never be resumed from here or from anywhere else.
 */
export default function RecordingControls({
  journey,
  busy,
  isDemoJourney,
  onStart,
  onPause,
  onResume,
  onStop,
  onSave,
  onClear,
}: Props) {
  const status = journey?.status ?? null
  const hasPoints = (journey?.point_count ?? 0) > 0

  return (
    <div className="rounded-2xl border border-edge bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-ink">
          <CircleDot size={15} className={status === 'recording' ? 'text-danger' : 'text-muted'} />
          Journey recording
        </h3>
        <span
          className={`rounded-full border px-2.5 py-0.5 text-[11px] font-semibold tracking-wide ${
            status === 'recording'
              ? 'border-danger/40 bg-danger/10 text-danger'
              : status === 'paused'
                ? 'border-warn/40 bg-warn/10 text-warn'
                : status === 'saved'
                  ? 'border-live/40 bg-live/10 text-live'
                  : status
                    ? 'border-edge bg-surface-2 text-body'
                    : 'border-edge bg-surface-2 text-muted'
          }`}
        >
          {status ? statusLabel(status) : 'IDLE'}
        </span>
      </div>

      {isDemoJourney ? (
        <p className="mt-2 rounded-lg border border-demo/30 bg-demo/10 px-2.5 py-1.5 text-[11px] text-demo">
          DEMO MODE — this journey contains simulated sample data, not ESP32-C3 readings.
        </p>
      ) : null}

      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
        {/* Start is always available: it adopts a journey the device already
            opened, resumes a paused one, or creates a new one. A finished
            journey is never resumed - a new journey is begun instead. */}
        <Button
          onClick={onStart}
          busy={busy && !journey}
          tone="primary"
          icon={<Play size={15} />}
          title="Start (or join) the journey the ESP32-C3 is posting into"
        >
          Start
        </Button>
        <Button
          onClick={onPause}
          disabled={status !== 'recording'}
          icon={<Pause size={15} />}
          title="Pause: points received now are accepted by the API and dropped"
        >
          Pause
        </Button>
        <Button
          onClick={onResume}
          disabled={status !== 'paused'}
          icon={<RotateCcw size={15} />}
          title="Continue the same journey after a break"
        >
          Resume
        </Button>
        <Button
          onClick={onStop}
          disabled={status !== 'recording' && status !== 'paused'}
          tone="danger"
          icon={<Square size={15} />}
          title="Finish recording and compute the final statistics"
        >
          Stop
        </Button>
        <Button
          onClick={onSave}
          disabled={status !== 'stopped' || !hasPoints}
          tone="success"
          icon={<Save size={15} />}
          title={
            status === 'stopped' && !hasPoints
              ? 'An empty journey cannot be saved'
              : 'Persist the journey so it stays in the list'
          }
        >
          Save
        </Button>
        <Button
          onClick={onClear}
          disabled={!journey || status === 'saved'}
          tone="danger"
          icon={<Trash2 size={15} />}
          title={
            status === 'saved'
              ? 'Saved journeys cannot be cleared'
              : 'Delete this unsaved journey and its points'
          }
        >
          Clear
        </Button>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted">
        {FLOW.map((step, index) => (
          <span key={step} className="flex items-center gap-1.5">
            <span
              className={`rounded px-1.5 py-0.5 ${
                status === step ? 'bg-accent/20 text-accent' : 'bg-surface-2 text-muted'
              }`}
            >
              {step}
            </span>
            {index < FLOW.length - 1 ? <span className="text-edge">→</span> : null}
          </span>
        ))}
      </div>
      <p className="mt-2 text-[11px] leading-snug text-muted">
        The ESP32-C3 keeps posting while a journey is paused; the API answers with
        <code className="mx-1 rounded bg-surface-2 px-1">stored: false</code>
        so those points create a real recording gap instead of a straight line.
      </p>
    </div>
  )
}
