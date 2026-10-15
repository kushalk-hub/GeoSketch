import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react'

import type { Toast } from '../hooks/useToasts'

interface Props {
  toasts: Toast[]
  onDismiss: (id: number) => void
}

const STYLES = {
  info: { border: 'border-accent/40', bg: 'bg-accent/10', text: 'text-accent', icon: Info },
  success: {
    border: 'border-live/40',
    bg: 'bg-live/10',
    text: 'text-live',
    icon: CheckCircle2,
  },
  error: { border: 'border-danger/45', bg: 'bg-danger/10', text: 'text-danger', icon: AlertTriangle },
} as const

export default function Toaster({ toasts, onDismiss }: Props) {
  if (toasts.length === 0) {
    return null
  }

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[2000] flex w-[min(92vw,360px)] flex-col gap-2">
      {toasts.map((toast) => {
        const style = STYLES[toast.kind]
        const Icon = style.icon
        return (
          <div
            key={toast.id}
            className={`animate-in pointer-events-auto flex items-start gap-2.5 rounded-xl border px-3.5 py-2.5 backdrop-blur ${style.border} ${style.bg}`}
          >
            <Icon size={16} className={`mt-0.5 shrink-0 ${style.text}`} />
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-semibold text-slate-100">{toast.message}</p>
              {toast.detail ? (
                <p className="mt-0.5 break-words text-[11px] leading-snug text-muted">
                  {toast.detail}
                </p>
              ) : null}
            </div>
            <button
              type="button"
              onClick={() => onDismiss(toast.id)}
              className="rounded p-0.5 text-muted transition hover:text-slate-200"
              aria-label="Dismiss notification"
            >
              <X size={14} />
            </button>
          </div>
        )
      })}
    </div>
  )
}
