import { Circle, MapContainer, Marker, Polyline, TileLayer } from 'react-leaflet'
import { useLiveView } from '../hooks/useLiveView'
import 'leaflet/dist/leaflet.css'

export default function LivePage({ token }: { token: string }) {
  const { data, expired, error } = useLiveView(token)
  if (expired) return <main className="grid min-h-screen place-items-center bg-slate-950 p-6 text-white"><p>This link has expired or was revoked.</p></main>
  if (!data) return <main className="grid min-h-screen place-items-center bg-slate-950 p-6 text-white"><p>{error ?? 'Loading shared location…'}</p></main>
  const point = data.position
  const center: [number, number] = point ? [point.latitude, point.longitude] : data.zones.length ? [data.zones[0].latitude, data.zones[0].longitude] : [0, 0]
  return <main className="min-h-screen bg-slate-950 text-white">
    <header className="flex items-center justify-between p-4"><div><h1 className="text-lg font-semibold">{data.label}</h1><p className="text-sm text-slate-300">GPS estimate, ~2.5 m accuracy</p></div><span className="rounded-full bg-slate-800 px-3 py-1">{data.status === 'online' ? 'Online' : data.status === 'stale' ? 'Stale' : 'Offline'}</span></header>
    <div className="h-[75vh]"><MapContainer center={center} zoom={15} className="h-full w-full"><TileLayer attribution="&copy; OpenStreetMap" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      {data.trail.map((p,i) => i > 0 && (new Date(p.timestamp).getTime()-new Date(data.trail[i-1].timestamp).getTime()>180000 ? null : <Polyline key={i} positions={[[data.trail[i-1].latitude,data.trail[i-1].longitude],[p.latitude,p.longitude]]} color="#38bdf8" />))}
      {point ? <Marker position={[point.latitude,point.longitude]} /> : null}
      {data.zones.map((z,i) => <Circle key={i} center={[z.latitude,z.longitude]} radius={z.radius_m} pathOptions={{color:'#22c55e'}} />)}
    </MapContainer></div>
    <footer className="p-4 text-sm text-slate-300">Last seen: {data.last_seen ? new Date(data.last_seen).toLocaleString() : 'No GPS fix received'} · This is a location sharing aid, not a safety guarantee.</footer>
  </main>
}

