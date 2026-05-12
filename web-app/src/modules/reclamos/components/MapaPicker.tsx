import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

// Workaround icono default de Leaflet bajo bundler (Vite). Sin esto el marker
// no aparece porque Leaflet busca los PNG en rutas relativas que el build rompe.
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'

const DefaultIcon = L.icon({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
})
L.Marker.prototype.options.icon = DefaultIcon

interface Props {
  lat: number | null
  lon: number | null
  onChange: (lat: number, lon: number, fuente: 'pin_manual') => void
  height?: number
  defaultCenter?: { lat: number; lon: number }
}

// Vicente Lopez (centro aproximado) como default — coincide con el dataset de activos.
const DEFAULT_CENTER = { lat: -34.5305, lon: -58.4779 }
const DEFAULT_ZOOM_NOPIN = 13
const DEFAULT_ZOOM_PIN = 16

export function MapaPicker({ lat, lon, onChange, height = 320, defaultCenter }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const markerRef = useRef<L.Marker | null>(null)
  const onChangeRef = useRef(onChange)

  // Mantener onChange estable sin re-inicializar el mapa.
  useEffect(() => { onChangeRef.current = onChange }, [onChange])

  // Init una sola vez.
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return
    const center = lat != null && lon != null
      ? [lat, lon] as [number, number]
      : [defaultCenter?.lat ?? DEFAULT_CENTER.lat, defaultCenter?.lon ?? DEFAULT_CENTER.lon] as [number, number]
    const zoom = (lat != null && lon != null) ? DEFAULT_ZOOM_PIN : DEFAULT_ZOOM_NOPIN

    const map = L.map(containerRef.current, {
      center,
      zoom,
      scrollWheelZoom: true,
    })
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 19,
    }).addTo(map)

    map.on('click', (e: L.LeafletMouseEvent) => {
      const { lat: la, lng: lo } = e.latlng
      setOrMoveMarker(la, lo)
      onChangeRef.current(la, lo, 'pin_manual')
    })

    mapRef.current = map

    if (lat != null && lon != null) setOrMoveMarker(lat, lon)

    // Cleanup
    return () => {
      map.off()
      map.remove()
      mapRef.current = null
      markerRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Sincronizar marker desde props (cuando el usuario picked desde la lista de busqueda).
  useEffect(() => {
    if (!mapRef.current) return
    if (lat == null || lon == null) {
      if (markerRef.current) {
        markerRef.current.remove()
        markerRef.current = null
      }
      return
    }
    setOrMoveMarker(lat, lon)
    mapRef.current.setView([lat, lon], Math.max(mapRef.current.getZoom(), DEFAULT_ZOOM_PIN))
  }, [lat, lon])

  function setOrMoveMarker(la: number, lo: number) {
    if (!mapRef.current) return
    if (markerRef.current) {
      markerRef.current.setLatLng([la, lo])
    } else {
      markerRef.current = L.marker([la, lo], { draggable: true }).addTo(mapRef.current)
      markerRef.current.on('dragend', (ev) => {
        const m = ev.target as L.Marker
        const ll = m.getLatLng()
        onChangeRef.current(ll.lat, ll.lng, 'pin_manual')
      })
    }
  }

  return (
    <div
      ref={containerRef}
      style={{
        width: '100%',
        height,
        borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--border-primary)',
        overflow: 'hidden',
      }}
    />
  )
}
