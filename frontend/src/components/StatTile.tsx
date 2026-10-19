import type { ReactNode } from 'react'

interface Props {
  label: string
  value: ReactNode
  hint?: ReactNode
  icon?: ReactNode
  tone?: 'default' | 'live' | 'demo' | 'warn' | 'muted'
  mono?: boolean
}

const TONES: Record<NonNullable<Props['tone']>, string> = {
  default: 'text-ink',
  live: 'text-live',
  demo: 'text-demo',
  warn: 'text-warn',
  muted: 'text-muted',
}

export default function StatTile({
  label,
  value,
  hint,
  icon,
  tone = 'default',
  mono = false,
}: Props) {
  return (
    <div className="rounded-xl border border-edge bg-surface px-3.5 py-3 shadow-[0_1px_2px_rgba(15,23,42,0.04)] transition hover:border-accent/40">
      {/* Labels wrap instead of being ellipsised: a clipped "Total dista…" tile
          is worse than a two line label. */}
      <div className="flex items-start gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted">
        <span className="mt-px shrink-0">{icon}</span>
        <span className="leading-tight">{label}</span>
      </div>
      <div
        className={`mt-1.5 text-lg font-semibold leading-tight ${TONES[tone]} ${
          mono ? 'tabular' : ''
        }`}
      >
        {value}
      </div>
      {hint ? <div className="mt-1 text-[11px] leading-snug text-muted">{hint}</div> : null}
    </div>
  )
}
