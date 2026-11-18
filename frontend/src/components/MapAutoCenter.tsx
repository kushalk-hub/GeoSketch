import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'

/**
 * Pan the Leaflet map once when async tracker/zone coordinates first arrive so
 * the map does not stay stuck on the initial fallback coordinates.
 */
export default function MapAutoCenter({ target }: { target: [number, number] | null }) {
  const map = useMap()
  const centeredOnce = useRef(false)

  useEffect(() => {
    if (!target || centeredOnce.current) {
      return
    }
    centeredOnce.current = true
    map.setView(target, map.getZoom(), { animate: true })
  }, [target, map])

  return null
}
