import { useCallback, useEffect, useState } from 'react'
import { MapContainer, TileLayer, useMapEvents } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'

import { ApiError, CONFIGURED_DEVICE_ID, api } from '../services/api'
import { useParentSession } from '../hooks/useParentSession'
import type { ParentAlert, SafeZone, ShareLink } from '../types'

function CentrePicker({ onPick }: { onPick: (latitude: number, longitude: number) => void }) {
  useMapEvents({ click: (event) => onPick(event.latlng.lat, event.latlng.lng) })
  return null
}

export default function ParentPage() {
  const session = useParentSession()
  const logout = session.logout
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [register, setRegister] = useState(false)
  const [error, setError] = useState('')
  const [links, setLinks] = useState<ShareLink[]>([])
  const [zones, setZones] = useState<SafeZone[]>([])
  const [alerts, setAlerts] = useState<ParentAlert[]>([])
  const [label, setLabel] = useState('Child')
  const [ttl, setTtl] = useState(24)
  const [url, setUrl] = useState('')
  const [name, setName] = useState('Home')
  const [lat, setLat] = useState('')
  const [lon, setLon] = useState('')
  const [radius, setRadius] = useState(150)
  const [chat, setChat] = useState('')

  const refresh = useCallback(async (token: string) => {
    try {
      const [nextLinks, nextZones, nextAlerts, me] = await Promise.all([
        api.listShareLinks(token), api.listGeofences(token),
        api.listParentAlerts(token), api.parentMe(token),
      ])
      setLinks(nextLinks); setZones(nextZones); setAlerts(nextAlerts)
      setChat(me.telegram_chat_id ?? '')
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) logout()
      else setError(cause instanceof Error ? cause.message : String(cause))
    }
  }, [logout])

  useEffect(() => { if (session.token) void refresh(session.token) }, [session.token, refresh])

  const authenticate = async () => {
    setError('')
    try {
      await (register ? session.register(email, password) : session.login(email, password))
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
  }

  if (!session.token) return <main className="mx-auto max-w-md p-6">
    <h1 className="mb-4 text-xl font-semibold">GeoSketch Parent</h1>
    <div className="space-y-3 rounded-xl border border-edge bg-surface p-5">
      <input className="w-full rounded border p-2" type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
      <input className="w-full rounded border p-2" type="password" placeholder="Password (8 characters minimum)" value={password} onChange={(e) => setPassword(e.target.value)} />
      {error && <p role="alert">{error}</p>}
      <button className="rounded bg-accent px-4 py-2 text-white" onClick={() => void authenticate()}>{register ? 'Create account' : 'Sign in'}</button>
      <button className="ml-3 underline" onClick={() => setRegister(!register)}>{register ? 'Sign in instead' : 'Register'}</button>
    </div>
  </main>

  return <main className="mx-auto max-w-4xl space-y-5 p-4">
    <header className="flex justify-between"><h1 className="text-xl font-semibold">Family Safe-Trip</h1><button onClick={logout}>Sign out</button></header>
    {error && <p role="alert">{error}</p>}
    <section className="rounded-xl border border-edge bg-surface p-4">
      <h2 className="font-semibold">Share live location</h2>
      <div className="mt-3 flex flex-wrap gap-2">
        <input className="rounded border p-2" value={label} onChange={(e) => setLabel(e.target.value)} aria-label="Child label" />
        <select className="rounded border p-2" value={ttl} onChange={(e) => setTtl(Number(e.target.value))}><option value={24}>24 hours</option><option value={72}>3 days</option><option value={168}>7 days</option></select>
        <button className="rounded bg-accent px-3 py-2 text-white" onClick={async () => {
          try { const result = await api.createShareLink(session.token!, { device_id: CONFIGURED_DEVICE_ID, label, ttl_hours: ttl }); setUrl(result.url); await refresh(session.token!) }
          catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
        }}>Create link</button>
      </div>
      {url && <p className="mt-2 break-all"><a href={url}>{url}</a><button className="ml-2 underline" onClick={() => void navigator.clipboard.writeText(url)}>Copy</button></p>}
      {links.map((item) => <p key={item.id} className="mt-2">{item.label} · expires {new Date(item.expires_at).toLocaleString()} <button className="ml-2 underline" onClick={async () => { await api.revokeShareLink(session.token!, item.id); await refresh(session.token!) }}>Revoke</button></p>)}
    </section>
    <section className="rounded-xl border border-edge bg-surface p-4">
      <h2 className="font-semibold">Safe zones</h2>
      <p className="mt-1 text-sm text-muted">Click the map to choose a zone centre.</p>
      <div className="my-3 h-56 overflow-hidden rounded-lg"><MapContainer center={[18.5204, 73.8567]} zoom={12} className="h-full w-full"><TileLayer attribution="&copy; OpenStreetMap" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" /><CentrePicker onPick={(a, b) => { setLat(String(a)); setLon(String(b)) }} /></MapContainer></div>
      <div className="flex flex-wrap items-center gap-2">
        <input className="rounded border p-2" value={name} onChange={(e) => setName(e.target.value)} aria-label="Zone name" />
        <input className="w-28 rounded border p-2" type="number" placeholder="Latitude" value={lat} onChange={(e) => setLat(e.target.value)} />
        <input className="w-28 rounded border p-2" type="number" placeholder="Longitude" value={lon} onChange={(e) => setLon(e.target.value)} />
        <label>Radius {radius} m<input type="range" min="50" max="1000" step="10" value={radius} onChange={(e) => setRadius(Number(e.target.value))} /></label>
        <button className="rounded bg-accent px-3 py-2 text-white" onClick={async () => { await api.createGeofence(session.token!, { device_id: CONFIGURED_DEVICE_ID, name, latitude: Number(lat), longitude: Number(lon), radius_m: radius }); await refresh(session.token!) }}>Add zone</button>
      </div>
      {zones.map((item) => <p key={item.id} className="mt-2">{item.name} · {item.radius_m} m <button className="ml-2 underline" onClick={async () => { await api.deleteGeofence(session.token!, item.id); await refresh(session.token!) }}>Delete</button></p>)}
    </section>
    <section className="rounded-xl border border-edge bg-surface p-4"><h2 className="font-semibold">Alerts</h2>{alerts.map((item) => <p key={item.id} className="mt-2">{item.type} · {item.message} · {new Date(item.occurred_at).toLocaleString()}</p>)}</section>
    <section className="rounded-xl border border-edge bg-surface p-4">
      <h2 className="font-semibold">Telegram notifications</h2>
      <div className="mt-2 flex gap-2"><input className="rounded border p-2" placeholder="Chat ID" value={chat} onChange={(e) => setChat(e.target.value)} /><button className="rounded bg-accent px-3 py-2 text-white" onClick={async () => { await api.updateParentMe(session.token!, chat || null) }}>Save</button></div>
      <p className="mt-2 text-sm">Create a bot with BotFather, send it a message, then obtain your chat ID from Telegram's getUpdates endpoint.</p>
    </section>
  </main>
}

