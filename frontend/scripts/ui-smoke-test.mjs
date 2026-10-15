/**
 * GeoSketch UI smoke test (no browser-driver dependency).
 *
 * Drives the real dashboard in headless Chrome over the DevTools Protocol and
 * asserts the flows a human would perform: recording start/pause/resume/stop/save,
 * DEMO MODE replay + import, the artwork studio preview/generation/download and
 * the journey history.
 *
 * Keep a debug Chrome alive, then run:
 *   chrome --headless=new --remote-debugging-port=9222 --user-data-dir=<tmp-dir>
 *   node scripts/ui-smoke-test.mjs [dashboardUrl] [debugPort]
 *
 * Notes on the assertions:
 *  - Labels are styled `uppercase`, and Chrome's `innerText` applies
 *    `text-transform`, so text matching is done on a lower-cased copy.
 *  - The map uses Leaflet's canvas renderer (`preferCanvas`), so the route lives
 *    on a <canvas>, not in SVG `path` elements.
 */

const DASHBOARD = process.argv[2] ?? 'http://127.0.0.1:5173'
const PORT = process.argv[3] ?? '9222'
const API = process.env.GEOSKETCH_API ?? 'http://127.0.0.1:8000/api/v1'
// Credentials the firmware would use (must match GEOSKETCH_DEVICE_KEYS).
const DEVICE_ID = process.env.GEOSKETCH_DEVICE_ID ?? 'geosketch-01'
const DEVICE_KEY = process.env.GEOSKETCH_DEVICE_KEY ?? 'CHANGE-ME-device-key-please'

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const failures = []

function check(label, ok, detail = '') {
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${label}${detail ? `  [${detail}]` : ''}`)
  if (!ok) failures.push(label)
}

async function api(path, init) {
  const response = await fetch(API + path, init)
  if (!response.ok) {
    throw new Error(`API ${path} -> ${response.status}: ${await response.text()}`)
  }
  return response.json()
}

/** Post a fix exactly the way the ESP32-C3 firmware does. */
function postDevicePoint(journeyId, point) {
  return api('/gps/points', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Device-Id': DEVICE_ID,
      'X-Device-Key': DEVICE_KEY,
    },
    body: JSON.stringify({ ...point, journey_id: journeyId }),
  })
}

async function connect() {
  for (let attempt = 0; attempt < 30; attempt += 1) {
    try {
      const response = await fetch(`http://127.0.0.1:${PORT}/json/list`)
      const targets = await response.json()
      const page = targets.find((target) => target.type === 'page')
      if (page?.webSocketDebuggerUrl) return page.webSocketDebuggerUrl
    } catch {
      /* chrome not ready yet */
    }
    await sleep(500)
  }
  throw new Error('Could not reach Chrome DevTools Protocol')
}

const socket = new WebSocket(await connect())
let nextId = 1
const pending = new Map()

socket.addEventListener('message', (event) => {
  const message = JSON.parse(event.data)
  const resolver = pending.get(message.id)
  if (resolver) {
    pending.delete(message.id)
    resolver(message)
  }
})

await new Promise((resolve, reject) => {
  socket.addEventListener('open', resolve)
  socket.addEventListener('error', reject)
})

function send(method, params = {}) {
  const id = nextId++
  return new Promise((resolve) => {
    pending.set(id, resolve)
    socket.send(JSON.stringify({ id, method, params }))
  })
}

async function evaluate(expression) {
  const message = await send('Runtime.evaluate', {
    expression,
    awaitPromise: true,
    returnByValue: true,
  })
  const failure = message.result?.exceptionDetails
  if (failure) {
    throw new Error(failure.exception?.description ?? 'evaluation failed')
  }
  return message.result?.result?.value
}

const HELPERS = `
  window.__click = (text) => {
    const target = [...document.querySelectorAll('button')]
      .find((button) => (button.textContent || '').trim().toLowerCase().startsWith(text.toLowerCase()));
    if (!target) return 'not-found';
    if (target.disabled) return 'disabled';
    target.click();
    return 'clicked';
  };
  window.__text = () => (document.body.innerText || '').toLowerCase();
  window.__statusPill = () => {
    const pill = [...document.querySelectorAll('span')]
      .map((node) => (node.textContent || '').trim())
      .find((value) => /^(recording|paused|stopped|saved|idle)/i.test(value));
    return pill ? pill.toUpperCase() : 'NONE';
  };
  window.__canvasCount = () => document.querySelectorAll('.leaflet-overlay-pane canvas').length;
  window.__arrowCount = () => document.querySelectorAll('.route-arrow').length;
  window.__tileCount = () => document.querySelectorAll('.leaflet-tile-loaded').length;`

await send('Page.enable')
await send('Runtime.enable')

async function open(path, waitMs = 4000) {
  // A hidden/backgrounded tab throttles timers, which stalls a demo replay and
  // delays React updates, so keep the page in the foreground for every check.
  await send('Page.bringToFront')
  await send('Page.navigate', { url: path })
  await sleep(waitMs)
  await evaluate(HELPERS)
}

/** Poll until an expression is truthy: async UI such as toasts and live replays. */
async function waitFor(expression, timeoutMs = 10000, stepMs = 400) {
  const deadline = Date.now() + timeoutMs
  for (;;) {
    if (await evaluate(expression)) return true
    if (Date.now() >= deadline) return false
    await sleep(stepMs)
  }
}

const text = () => evaluate('window.__text()')
const pill = () => evaluate('window.__statusPill()')

check('helper injection works', (await (async () => {
  await open(`${DASHBOARD}/?tab=dashboard`, 6000)
  return evaluate('1 + 1')
})()) === 2)

console.log('\n[1] Dashboard renders and states the connection honestly')
let body = await text()
check('app title rendered', body.includes('geosketch'))
check(
  'connection state is honest (live or last-known)',
  body.includes('live') || body.includes('not reporting'),
  (body.match(/live|not reporting/) ?? [''])[0],
)
check('recording controls present', body.includes('journey recording'))
check('statistics tiles present', body.includes('total distance') && body.includes('gps points'))
check('statistics disclaimer shown', body.includes('estimate'))
check(
  'leaflet map initialised with OSM tiles',
  (await evaluate('window.__tileCount()')) > 0,
  `${await evaluate('window.__tileCount()')} tiles`,
)
check('DEMO MODE panel is labelled', body.includes('demo mode') && body.includes('simulated data'))
check(
  'rejected-fix toggle present',
  body.includes('show rejected fixes'),
)

console.log('\n[2] Recording state machine through the UI')
check('Start clicked', (await evaluate('window.__click("Start")')) === 'clicked')
await sleep(2500)
check('status pill shows RECORDING', (await pill()) === 'RECORDING', await pill())

const active = await api('/journeys?status=recording&limit=1')
const activeJourney = active[0]
check('a recording journey exists', Boolean(activeJourney), activeJourney ? `#${activeJourney.id}` : '')
check('journey is hardware sourced', activeJourney?.source === 'hardware')

if (activeJourney) {
  const refused = await fetch(`${API}/journeys/${activeJourney.id}/points`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source: 'demo', points: [{ latitude: 18.52, longitude: 73.85 }] }),
  })
  check('simulated points refused in a hardware journey', refused.status === 422, `status=${refused.status}`)

  const now = Date.now()
  const route = [
    [18.5204, 73.8567],
    [18.5209, 73.8571],
    [18.5215, 73.8576],
    [18.5221, 73.8582],
  ]
  for (const [index, [latitude, longitude]] of route.entries()) {
    await postDevicePoint(activeJourney.id, {
      latitude,
      longitude,
      altitude: 560 + index,
      speed_kmh: 4.5,
      satellites: 9,
      timestamp: new Date(now - (route.length - index) * 60000).toISOString(),
      client_point_id: `ui-${index}`,
    })
  }
  await sleep(4500)
  body = await text()
  check('device points appear on the dashboard', body.includes('18.5204'), 'latitude visible via polling')
  check(
    'route drawn on the canvas',
    (await evaluate('window.__canvasCount()')) > 0,
    `${await evaluate('window.__canvasCount()')} canvas layer(s)`,
  )
  check(
    'direction arrows drawn',
    (await evaluate('window.__arrowCount()')) > 0,
    `${await evaluate('window.__arrowCount()')} arrows`,
  )
  const stats = await api(`/journeys/${activeJourney.id}/statistics`)
  check('distance computed from the points', stats.distance_m > 100, `${stats.distance_m.toFixed(0)} m`)

  check('Pause clicked', (await evaluate('window.__click("Pause")')) === 'clicked')
  await sleep(2200)
  check('status pill shows PAUSED', (await pill()) === 'PAUSED', await pill())
  const paused = await api(`/journeys/${activeJourney.id}`)
  check('journey paused server-side', paused.status === 'paused')
  check(
    'points during a pause are dropped, not faked',
    (await (async () => {
      const outcome = await postDevicePoint(activeJourney.id, {
        latitude: 18.53,
        longitude: 73.86,
        satellites: 9,
        timestamp: new Date().toISOString(),
        client_point_id: 'ui-paused',
      })
      return outcome.accepted === false && outcome.stored === false
    })()),
  )

  check('Resume clicked', (await evaluate('window.__click("Resume")')) === 'clicked')
  await sleep(2200)
  check('status pill shows RECORDING again', (await pill()) === 'RECORDING', await pill())
  check('Stop clicked', (await evaluate('window.__click("Stop")')) === 'clicked')
  await sleep(2500)
  check('status pill shows STOPPED', (await pill()).startsWith('STOPPED'), await pill())
  check('Save clicked', (await evaluate('window.__click("Save")')) === 'clicked')
  await sleep(2500)
  check('status pill shows SAVED', (await pill()) === 'SAVED', await pill())
  check(
    'saved journey cannot be cleared or resumed',
    (await evaluate('window.__click("Clear")')) === 'disabled' &&
      (await evaluate('window.__click("Resume")')) === 'disabled',
  )
  const saved = await api(`/journeys/${activeJourney.id}`)
  check('journey persisted as saved', saved.status === 'saved' && saved.point_count === route.length)
}

console.log('\n[3] DEMO MODE: live replay of a bundled sample route')
await open(`${DASHBOARD}/?tab=dashboard`, 5000)
check('Replay clicked', (await evaluate('window.__click("Replay on the map")')) === 'clicked')
await sleep(7000)
let replayJourney = (await api('/journeys?source=demo&limit=1'))[0]
check('replay creates a demo journey', Boolean(replayJourney), replayJourney ? `#${replayJourney.id}` : '')
if (replayJourney) {
  check('demo journey is server-tagged as demo', replayJourney.source === 'demo')
  const firstCount = replayJourney.point_count
  await sleep(5000)
  replayJourney = await api(`/journeys/${replayJourney.id}`)
  check(
    'points stream in progressively',
    firstCount > 0 && replayJourney.point_count > firstCount,
    `${firstCount} -> ${replayJourney.point_count} points`,
  )
  check(
    'replayed route drawn live on the map',
    await waitFor('window.__canvasCount() > 0 && window.__arrowCount() > 0', 12000),
  )
  check('DEMO badge shown for simulated data', (await text()).includes('demo data'))
}
check('Stop replay clicked', (await evaluate('window.__click("Stop replay")')) === 'clicked')
await sleep(1500)

console.log('\n[3b] DEMO MODE: instant import')
await open(`${DASHBOARD}/?tab=dashboard`, 5000)
const beforeImport = (await api('/journeys?limit=200')).length
check('Import clicked', (await evaluate('window.__click("Import instantly")')) === 'clicked')
check('success toast shown', await waitFor("window.__text().includes('demo route imported')", 6000))
await sleep(2500)
body = await text()
const after = await api('/journeys?limit=200')
check('one journey added', after.length === beforeImport + 1, `${beforeImport} -> ${after.length}`)
const imported = after.find((journey) => journey.source === 'demo' && journey.status === 'stopped')
check('imported journey marked source=demo', Boolean(imported), imported ? `#${imported.id}, ${imported.point_count} points` : '')
const importedStats = imported ? await api(`/journeys/${imported.id}/statistics`) : null
check(
  'imported statistics are realistic',
  Boolean(importedStats && importedStats.distance_km > 1 && importedStats.average_speed_kmh),
  importedStats ? `${importedStats.distance_km} km, ${importedStats.average_speed_kmh} km/h` : '',
)

console.log('\n[4] Artwork studio: preview, styles, generation and export')
const studioJourney = imported ?? after[0]
await open(`${DASHBOARD}/?tab=studio&journey=${studioJourney.id}`, 7000)
body = await text()
check(
  'all five styles listed',
  ['minimal route', 'neon trail', 'gradient journey', 'artistic poster', 'custom art'].every((label) =>
    body.includes(label),
  ),
)
check('processing report shown', body.includes('coordinate processing') && body.includes('segments drawn'))
check('raw data preserved note shown', body.includes('raw gps points are stored untouched'))
check('inline SVG preview rendered', (await evaluate('document.querySelectorAll(".artwork-preview svg").length')) > 0)
check(
  'preview contains real geometry',
  (await evaluate(
    'document.querySelectorAll(".artwork-preview svg polyline, .artwork-preview svg circle, .artwork-preview svg rect").length',
  )) > 2,
)
check(
  'preview reports segment count for a route with a gap',
  /segments drawn: [1-9]/.test(body),
  (body.match(/segments drawn: \d+/) ?? [''])[0],
)

check('Neon style selected', (await evaluate('window.__click("Neon Trail")')) === 'clicked')
await sleep(2500)
check(
  'neon preview uses glow filters',
  await evaluate('/blur\\d/.test(document.querySelector(".artwork-preview")?.innerHTML || "")'),
)
check('Poster style selected', (await evaluate('window.__click("Artistic Poster")')) === 'clicked')
await sleep(2500)
check(
  'poster preview includes title and statistics text',
  await evaluate('/geosketch/i.test(document.querySelector(".artwork-preview")?.innerHTML || "")'),
)
check('Generate clicked', (await evaluate('window.__click("Generate & store")')) === 'clicked')
await sleep(6000)
body = await text()
check('artwork listed after generation', /saved artworks \(\d+\)/.test(body), (body.match(/saved artworks \(\d+\)/) ?? [''])[0])

const artworks = await api(`/journeys/${studioJourney.id}/artworks`)
const savedCount = Number((body.match(/saved artworks \((\d+)\)/) ?? [])[1] ?? -1)
check(
  'artwork persisted by the API',
  artworks.length >= 1 && savedCount >= 1,
  `${artworks.length} artwork(s) in the DB, UI lists ${savedCount}`,
)
check(
  'generated artwork keeps the selected style',
  artworks[0]?.style === 'poster',
  artworks[0]?.style ?? 'none',
)
if (artworks.length) {
  const pngResponse = await fetch(`${API}/artworks/${artworks[0].id}/download?format=png`)
  const png = new Uint8Array(await pngResponse.arrayBuffer())
  check('downloaded PNG is valid', png[0] === 0x89 && png[1] === 0x50, `${png.length} bytes`)
  const svgResponse = await fetch(`${API}/artworks/${artworks[0].id}/download?format=svg`)
  const svg = await svgResponse.text()
  check(
    'downloaded SVG is valid and scalable',
    svg.startsWith('<?xml') && svg.includes('viewBox') && svg.includes('</svg>'),
    `${svg.length} chars`,
  )
}

console.log('\n[5] Journey history')
await open(`${DASHBOARD}/?tab=journeys`, 5000)
body = await text()
check('history table rendered', body.includes('journey') && body.includes('distance'))
check('provenance visible (hardware vs demo)', body.includes('hardware') && body.includes('demo'))
check('filters rendered', body.includes('all sources') && body.includes('all statuses'))
check('totals summarised', body.includes('total distance') && body.includes('recorded points'))

console.log(`\n${'='.repeat(64)}`)
console.log(
  failures.length === 0
    ? 'UI SMOKE TEST: ALL CHECKS PASSED'
    : `UI SMOKE TEST: ${failures.length} FAILED -> ${failures.join(', ')}`,
)
console.log('='.repeat(64))

socket.close()
process.exit(failures.length === 0 ? 0 : 1)
