import { Activity, Image, LayoutDashboard, Route, Wifi, WifiOff } from 'lucide-react'
import type { ReactNode } from 'react'

import type { DeviceStatus } from '../types'
import { formatRelative } from '../utils/format'

export type TabId = 'dashboard' | 'journeys' | 'studio'

interface Props {
  tab: TabId
  onTabChange: (tab: TabId) => void
  status: DeviceStatus | null
  demoActive: boolean
  backendOnline: boolean
  children: ReactNode
}

const TABS: { id: TabId; label: string; icon: typeof LayoutDashboard }[] = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'journeys', label: 'Journeys', icon: Route },
  { id: 'studio', label: 'Artwork studio', icon: Image },
]

export default function AppShell({
  tab,
  onTabChange,
  status,
  demoActive,
  backendOnline,
  children,
}: Props) {
  const isLive = Boolean(status?.connected)
  const device = status?.device

  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-[1000] border-b border-edge bg-surface/85 shadow-[0_1px_8px_rgba(15,23,42,0.04)] backdrop-blur-md">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-3 px-4 py-3 md:px-8">
          <div className="flex items-center gap-2.5">
            <span className="grid h-9 w-9 place-items-center rounded-xl border border-accent/20 bg-primary-fixed">
              <Activity size={18} className="text-accent" />
            </span>
            <div className="leading-tight">
              <h1 className="text-[15px] font-semibold tracking-tight text-ink">GeoSketch</h1>
              <p className="text-[10px] uppercase tracking-[0.18em] text-muted">
                ESP32-C3 · NEO-6M · GPS route art
              </p>
            </div>
          </div>

          <nav className="order-3 flex w-full gap-1 rounded-full border border-edge bg-surface-2 p-1.5 sm:order-none sm:w-auto">
            {TABS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                onClick={() => onTabChange(id)}
                className={`flex flex-1 items-center justify-center gap-1.5 rounded-full px-3.5 py-1.5 text-[12px] font-medium transition sm:flex-none ${
                  tab === id
                    ? 'bg-surface font-semibold text-accent shadow-sm ring-1 ring-edge'
                    : 'text-muted hover:text-ink'
                }`}
              >
                <Icon size={14} />
                {label}
              </button>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-2">
            {demoActive ? (
              <span className="rounded-full border border-demo/25 bg-demo/10 px-2.5 py-1 text-[10px] font-semibold tracking-wide text-demo">
                DEMO DATA
              </span>
            ) : null}

            <span
              className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium ${
                !backendOnline
                  ? 'border-danger/25 bg-danger/10 text-danger'
                  : isLive
                    ? 'border-live/25 bg-live/10 text-live'
                    : 'border-edge bg-surface-2 text-muted'
              }`}
              title={
                backendOnline
                  ? isLive
                    ? `Live: last point ${formatRelative(device?.last_seen_at)}`
                    : 'No recent GPS point from the tracker'
                  : 'The GeoSketch backend is unreachable'
              }
            >
              {isLive ? <Wifi size={13} /> : <WifiOff size={13} />}
              {!backendOnline
                ? 'backend offline'
                : isLive
                  ? `live · ${device?.device_id ?? 'device'}`
                  : `no signal · ${formatRelative(device?.last_seen_at)}`}
            </span>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-5 md:px-8">{children}</main>

      <footer className="mx-auto w-full max-w-[1600px] px-4 pb-6 pt-2 md:px-8">
        <p className="text-center text-[10px] leading-relaxed text-muted">
          GeoSketch · real GPS hardware (ESP32-C3 + NEO-6M) → Wi-Fi → FastAPI/SQLite → route
          artwork. Distances, speeds and durations are GPS estimates. Demo sample routes are
          simulated and always labelled as such.
        </p>
      </footer>
    </div>
  )
}
