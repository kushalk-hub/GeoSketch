import { useCallback, useEffect, useRef, useState } from 'react'

import AppShell, { type TabId } from './components/AppShell'
import Toaster from './components/Toaster'
import DashboardPage from './pages/DashboardPage'
import JourneysPage from './pages/JourneysPage'
import StudioPage from './pages/StudioPage'
import { useDemoReplay } from './hooks/useDemoReplay'
import { useDeviceStatus } from './hooks/useDeviceStatus'
import { useJourney } from './hooks/useJourney'
import { useRecorder } from './hooks/useRecorder'
import { useToasts } from './hooks/useToasts'
import { ApiError, CONFIGURED_DEVICE_ID, api } from './services/api'
import type { ArtworkStyleInfo, Journey, SampleRouteSummary } from './types'

function messageOf(cause: unknown): string {
  return cause instanceof ApiError ? cause.message : String(cause)
}

const TAB_IDS: TabId[] = ['dashboard', 'journeys', 'studio']

function initialTab(): TabId {
  const requested = new URLSearchParams(window.location.search).get('tab')
  return TAB_IDS.includes(requested as TabId) ? (requested as TabId) : 'dashboard'
}

function initialJourneyId(): number | null {
  const raw = new URLSearchParams(window.location.search).get('journey')
  const parsed = raw === null ? Number.NaN : Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

export default function App() {
  const { toasts, notify, dismiss } = useToasts()

  // `?tab=studio&journey=12` deep links: a view can be bookmarked or projected
  // directly during a presentation.
  const [tab, setTab] = useState<TabId>(initialTab)
  /** null = follow the live device journey; a number = a journey the user opened. */
  const [pinnedJourneyId, setPinnedJourneyId] = useState<number | null>(initialJourneyId)
  const [journeys, setJourneys] = useState<Journey[]>([])
  const [journeysLoading, setJourneysLoading] = useState(true)
  const [styles, setStyles] = useState<ArtworkStyleInfo[]>([])
  const [backendOnline, setBackendOnline] = useState(true)
  const [demoRoutes, setDemoRoutes] = useState<SampleRouteSummary[]>([])
  const [selectedDemoRouteId, setSelectedDemoRouteId] = useState<string | null>(null)
  const [demoError, setDemoError] = useState<string | null>(null)
  const [importing, setImporting] = useState(false)
  const warnedOffline = useRef(false)

  const {
    status,
    error: statusError,
    refresh: refreshStatus,
  } = useDeviceStatus(CONFIGURED_DEVICE_ID, 3000)

  const viewingJourneyId = pinnedJourneyId ?? status?.active_journey_id ?? null
  const {
    journey,
    statistics,
    error: journeyError,
    refresh: refreshJourney,
  } = useJourney(viewingJourneyId, 2000)

  // --- data loading -------------------------------------------------------
  const refreshJourneys = useCallback(async () => {
    try {
      const list = await api.listJourneys({ limit: 200 })
      setJourneys(list)
      setBackendOnline(true)
      warnedOffline.current = false
    } catch (cause) {
      setBackendOnline(false)
      if (!warnedOffline.current) {
        warnedOffline.current = true
        notify('error', 'Backend unreachable', messageOf(cause))
      }
    } finally {
      setJourneysLoading(false)
    }
  }, [notify])

  const refreshAll = useCallback(async () => {
    await Promise.all([refreshJourney(), refreshJourneys(), refreshStatus()])
  }, [refreshJourney, refreshJourneys, refreshStatus])

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const [styleList, routes] = await Promise.all([api.artworkStyles(), api.demoRoutes()])
        if (cancelled) return
        setStyles(styleList)
        setDemoRoutes(routes)
        setSelectedDemoRouteId((current) => current ?? routes[0]?.id ?? null)
        setDemoError(null)
      } catch (cause) {
        if (!cancelled) {
          setDemoError(messageOf(cause))
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    void refreshJourneys()
    // A slow heartbeat keeps the backend status pill honest even while idle.
    const timer = window.setInterval(() => void refreshJourneys(), 15000)
    return () => window.clearInterval(timer)
  }, [refreshJourneys])

  // Keep the URL in step with the view (shareable/deep-linkable state).
  useEffect(() => {
    const search = new URLSearchParams()
    if (tab !== 'dashboard') {
      search.set('tab', tab)
    }
    if (pinnedJourneyId !== null) {
      search.set('journey', String(pinnedJourneyId))
    }
    const query = search.toString()
    window.history.replaceState(
      null,
      '',
      query ? `${window.location.pathname}?${query}` : window.location.pathname,
    )
  }, [pinnedJourneyId, tab])

  // --- recording controls -------------------------------------------------
  const recorder = useRecorder({
    deviceId: CONFIGURED_DEVICE_ID,
    activeJourney: journey,
    setActiveJourneyId: setPinnedJourneyId,
    refresh: refreshAll,
    notify,
  })

  // --- DEMO MODE ----------------------------------------------------------
  const replay = useDemoReplay({
    notify,
    onJourneyOpened: (journeyId) => {
      setPinnedJourneyId(journeyId)
      setTab('dashboard')
    },
    onProgress: refreshJourney,
  })

  const wasReplaying = useRef(false)
  useEffect(() => {
    if (wasReplaying.current && !replay.replaying) {
      void refreshAll()
    }
    wasReplaying.current = replay.replaying
  }, [replay.replaying, refreshAll])

  const handleImportDemo = useCallback(async () => {
    if (!selectedDemoRouteId) {
      notify('info', 'Pick a sample route first')
      return
    }
    setImporting(true)
    try {
      const demoJourney = await api.importDemoRoute(selectedDemoRouteId, { duration_scale: 1 })
      setPinnedJourneyId(demoJourney.id)
      setTab('dashboard')
      notify(
        'success',
        'DEMO route imported',
        `${demoJourney.point_count} simulated points stored as journey #${demoJourney.id} (source: demo)`,
      )
      await refreshAll()
    } catch (cause) {
      notify('error', 'Demo import failed', messageOf(cause))
    } finally {
      setImporting(false)
    }
  }, [notify, refreshAll, selectedDemoRouteId])

  const openJourney = useCallback((target: Journey) => {
    setPinnedJourneyId(target.id)
    setTab('dashboard')
  }, [])

  const openStudio = useCallback((target: Journey) => {
    setPinnedJourneyId(target.id)
    setTab('studio')
  }, [])

  const handleRename = useCallback(
    (title: string) => {
      if (journey) {
        void recorder.rename(journey.id, title)
      }
    },
    [journey, recorder],
  )

  return (
    <>
      <AppShell
        tab={tab}
        onTabChange={setTab}
        status={status}
        demoActive={journey?.source === 'demo' || replay.replaying}
        backendOnline={backendOnline}
      >
        {tab === 'dashboard' ? (
          <DashboardPage
            status={status}
            statusError={statusError ? statusError.message : null}
            journey={journey}
            statistics={statistics}
            journeyError={journeyError ? journeyError.message : null}
            pinned={pinnedJourneyId !== null}
            onReturnToLive={() => setPinnedJourneyId(null)}
            onRefresh={() => void refreshAll()}
            onRename={handleRename}
            recorder={{
              busy: recorder.busy,
              onStart: () => void recorder.start(),
              onPause: () => void recorder.pause(),
              onResume: () => void recorder.resume(),
              onStop: () => void recorder.stop(),
              onSave: () => void recorder.save(),
              onClear: () => void recorder.clear(),
            }}
            demo={{
              routes: demoRoutes,
              selectedRouteId: selectedDemoRouteId,
              onSelect: setSelectedDemoRouteId,
              onImport: () => void handleImportDemo(),
              onReplay: () => {
                if (selectedDemoRouteId) {
                  void replay.start(selectedDemoRouteId)
                }
              },
              onStopReplay: replay.stopReplay,
              importing,
              replaying: replay.replaying,
              progress: replay.progress,
              loadError: demoError,
            }}
          />
        ) : null}

        {tab === 'journeys' ? (
          <JourneysPage
            journeys={journeys}
            activeJourneyId={viewingJourneyId}
            loading={journeysLoading}
            onOpen={openJourney}
            onOpenStudio={openStudio}
            onRefresh={() => void refreshJourneys()}
          />
        ) : null}

        {tab === 'studio' ? (
          <StudioPage
            journey={journey}
            journeys={journeys}
            styles={styles}
            onSelectJourney={(target) => setPinnedJourneyId(target.id)}
            notify={notify}
          />
        ) : null}
      </AppShell>

      <Toaster toasts={toasts} onDismiss={dismiss} />
    </>
  )
}
