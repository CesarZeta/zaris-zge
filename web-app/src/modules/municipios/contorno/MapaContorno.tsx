import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { LimiteMunicipio } from '../../dashboard/hooks/useDashboardData'

// Vista del contorno (guardado o a punto de guardarse). Leaflet vanilla montado en useEffect, como
// MapaPicker (CLAUDE.md §4); tile Esri gris claro u oscuro según el tema, como el mapa del inicio.
// Color literal: Leaflet lo pinta como atributo SVG; es el valor de --zaris-orange.
const ESRI = (base: string) =>
  `https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/${base}/MapServer/tile/{z}/{y}/{x}`

export function MapaContorno({ geometria, height = 260 }: { geometria: LimiteMunicipio; height?: number }) {
  const contRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const capaRef = useRef<L.GeoJSON | null>(null)

  useEffect(() => {
    if (!contRef.current || mapRef.current) return
    const oscuro = document.documentElement.dataset.theme === 'dark'
    const map = L.map(contRef.current, { scrollWheelZoom: false, attributionControl: true })
    L.tileLayer(ESRI(oscuro ? 'World_Dark_Gray_Base' : 'World_Light_Gray_Base'), {
      attribution: '© Esri © OpenStreetMap', maxNativeZoom: 16, maxZoom: 20,
    }).addTo(map)
    mapRef.current = map
    return () => { map.remove(); mapRef.current = null; capaRef.current = null }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    capaRef.current?.remove()
    const capa = L.geoJSON(geometria as GeoJSON.GeoJsonObject, {
      style: { color: '#f54e00', weight: 2, fillColor: '#f54e00', fillOpacity: 0.12 },
      interactive: false,
    }).addTo(map)
    capaRef.current = capa
    const b = capa.getBounds()
    if (b.isValid()) map.fitBounds(b, { padding: [12, 12] })
  }, [geometria])

  return (
    <div ref={contRef} data-mapa-contorno
         style={{ height, width: '100%', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-primary)' }} />
  )
}
