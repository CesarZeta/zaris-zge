import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

import type { ReclamoListado } from '../../reclamos/types/reclamo'
import type { EstadoReclamo } from '../../reclamos/types/reclamo'

// Workaround icono default de Leaflet bajo bundler (Vite). Sin esto el marker
// no aparece porque Leaflet busca los PNG en rutas relativas que el build rompe.
// Documentado en CLAUDE.md §4.
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

// Vicente Lopez (centro aproximado) — mismo default que MapaPicker de Reclamos.
const DEFAULT_CENTER: [number, number] = [-34.5305, -58.4779]
const DEFAULT_ZOOM = 13

// Color del marker por estado del reclamo.
const ESTADO_COLOR: Record<string, string> = {
  'Sin asignar':  '#c62828', // rojo
  'En gestión':   '#ef6c00', // naranja
  'En espera':    '#f57f17', // amarillo
  'En auditoría': '#6a1b9a', // violeta
}

function colorEstado(estado: EstadoReclamo | string | null): string {
  return ESTADO_COLOR[estado ?? ''] ?? '#455a64'
}

// Marker custom como divIcon (circulo de color sin sombra).
function makeMarkerIcon(estado: EstadoReclamo | string | null) {
  const color = colorEstado(estado)
  return L.divIcon({
    className: 'dashboard-marker',
    html: `<div style="
      width: 18px; height: 18px;
      background: ${color};
      border: 2px solid white;
      border-radius: 50%;
      box-shadow: 0 1px 4px rgba(0,0,0,0.4);
    "></div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  })
}

interface Props {
  reclamos: ReclamoListado[]
  onMarkerClick?: (r: ReclamoListado) => void
}

export function DashboardMap({ reclamos, onMarkerClick }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const markersLayerRef = useRef<L.LayerGroup | null>(null)
  const onClickRef = useRef(onMarkerClick)

  useEffect(() => { onClickRef.current = onMarkerClick }, [onMarkerClick])

  // Init mapa una sola vez.
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return
    const map = L.map(containerRef.current, {
      center: DEFAULT_CENTER,
      zoom: DEFAULT_ZOOM,
      scrollWheelZoom: true,
      zoomControl: true,
    })
    // Tile gris claro (CartoDB Positron, gratis sin API key). Pensado para
    // dashboards: minimal, no compite visualmente con los markers de estado.
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> © <a href="https://carto.com/attributions">CARTO</a>',
      subdomains: 'abcd',
      maxZoom: 20,
    }).addTo(map)
    markersLayerRef.current = L.layerGroup().addTo(map)
    mapRef.current = map

    return () => {
      map.off()
      map.remove()
      mapRef.current = null
      markersLayerRef.current = null
    }
  }, [])

  // Sincronizar markers con el dataset.
  useEffect(() => {
    if (!mapRef.current || !markersLayerRef.current) return
    markersLayerRef.current.clearLayers()
    const bounds: L.LatLngTuple[] = []
    for (const r of reclamos) {
      if (r.latitud == null || r.longitud == null) continue
      const m = L.marker([r.latitud, r.longitud], { icon: makeMarkerIcon(r.estado) })
        .bindPopup(`
          <div style="font-family: var(--font-display, sans-serif); min-width: 200px;">
            <div style="font-weight: 600; margin-bottom: 4px;">${escapeHtml(r.nro_reclamo ?? '—')}</div>
            <div style="font-size: 0.78rem; color: #666; margin-bottom: 6px;">${escapeHtml(r.tipo_nombre ?? '')}</div>
            <div style="font-size: 0.78rem; margin-bottom: 4px;"><strong>Estado:</strong> ${escapeHtml(r.estado)}</div>
            <div style="font-size: 0.78rem; margin-bottom: 4px;"><strong>Prioridad:</strong> ${escapeHtml(r.prioridad ?? '—')}</div>
            <div style="font-size: 0.75rem; color: #444; margin-top: 6px;">${escapeHtml(r.descripcion?.slice(0, 120) ?? '')}${(r.descripcion?.length ?? 0) > 120 ? '…' : ''}</div>
          </div>
        `)
      m.on('click', () => onClickRef.current?.(r))
      m.addTo(markersLayerRef.current!)
      bounds.push([r.latitud, r.longitud])
    }
    if (bounds.length >= 2) {
      mapRef.current.fitBounds(L.latLngBounds(bounds), { padding: [60, 60], maxZoom: 15 })
    } else if (bounds.length === 1) {
      mapRef.current.setView(bounds[0], 15)
    }
  }, [reclamos])

  return (
    <div ref={containerRef} style={{ position: 'absolute', inset: 0 }} />
  )
}

function escapeHtml(s: string | null | undefined): string {
  const str = String(s ?? '')
  return str.replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c] ?? c))
}
