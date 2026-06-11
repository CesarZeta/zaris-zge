// Mapa del tablero de emergencias: clon del patron DashboardMap (s4) con tile
// CartoDB Positron (gris claro) y markers coloreados por estado del evento
// (ESTADO_COLOR de lib/ui). Click en un marker abre el evento.
import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

import type { EmergenciaEvento } from '../types'
import { ESTADO_COLOR } from '../lib/ui'

// Workaround icono default de Leaflet bajo bundler (Vite). Sin esto el marker
// no aparece porque Leaflet busca los PNG en rutas relativas que el build rompe.
// Documentado en CLAUDE.md s4.
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

// Vicente Lopez (centro aproximado) — mismo default que DashboardMap/MapaPicker.
const DEFAULT_CENTER: [number, number] = [-34.5305, -58.4779]
const DEFAULT_ZOOM = 13

function makeMarkerIcon(estadoCodigo: string) {
  const color = ESTADO_COLOR[estadoCodigo] ?? '#455a64'
  return L.divIcon({
    className: 'emergencias-marker',
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
  eventos: EmergenciaEvento[]
  onMarkerClick?: (ev: EmergenciaEvento) => void
}

export function EmergenciasMap({ eventos, onMarkerClick }: Props) {
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
      zoomControl: false,
    })
    L.control.zoom({ position: 'bottomright' }).addTo(map)
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

  // Sincronizar markers con el dataset (polling 30s del tablero).
  useEffect(() => {
    if (!mapRef.current || !markersLayerRef.current) return
    markersLayerRef.current.clearLayers()
    const bounds: L.LatLngTuple[] = []
    for (const ev of eventos) {
      if (ev.latitud == null || ev.longitud == null) continue
      const m = L.marker([ev.latitud, ev.longitud], { icon: makeMarkerIcon(ev.estado_codigo) })
        .bindPopup(`
          <div style="font-family: var(--font-display, sans-serif); min-width: 200px;">
            <div style="font-weight: 700; margin-bottom: 4px;">${escapeHtml(ev.numero_operativo)}</div>
            <div style="font-size: 0.78rem; color: #666; margin-bottom: 6px;">${escapeHtml(ev.tipo_nombre ?? '')}${ev.subtipo_nombre ? ' · ' + escapeHtml(ev.subtipo_nombre) : ''}</div>
            <div style="font-size: 0.78rem; margin-bottom: 4px;"><strong>Estado:</strong> ${escapeHtml(ev.estado_nombre ?? ev.estado_codigo)}</div>
            <div style="font-size: 0.78rem; margin-bottom: 4px;"><strong>Prioridad:</strong> ${escapeHtml(ev.prioridad_codigo ?? '—')}</div>
            <div style="font-size: 0.75rem; color: #444; margin-top: 6px;">${escapeHtml(ev.direccion_evento ?? '')}</div>
          </div>
        `)
      m.on('click', () => onClickRef.current?.(ev))
      m.addTo(markersLayerRef.current!)
      bounds.push([ev.latitud, ev.longitud])
    }
    if (bounds.length >= 2) {
      mapRef.current.fitBounds(L.latLngBounds(bounds), { padding: [50, 50], maxZoom: 15 })
    } else if (bounds.length === 1) {
      mapRef.current.setView(bounds[0], 15)
    }
  }, [eventos])

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
