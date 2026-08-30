import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

import type { GeoEmergencia, GeoEspacio, GeoReclamo, GeoTramite } from '../hooks/useDashboardData'

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

// Color del marker de reclamo por estado. Verde de --color-success del DS
// (#1f8a65) para "En gestión". Nunca naranja (choca con el brand, §4).
const ESTADO_COLOR: Record<string, string> = {
  'Sin asignar':  '#c62828', // rojo (urgencia)
  'En gestión':   '#1f8a65', // verde DS --color-success (en curso)
  'En espera':    '#f57f17', // amarillo (bloqueado)
  'En auditoría': '#6a1b9a', // violeta (verificacion)
}

// Colores por capa (lejos del naranja del brand, §4):
export const CAPA_COLOR = {
  emergencia: '#cf2d56', // --color-error: lo mas urgente del tablero
  espacio:    '#1565c0', // azul: infraestructura municipal
  tramite:    '#8d6e63', // marron: expedientes
} as const

function colorEstadoReclamo(estado: string | null): string {
  return ESTADO_COLOR[estado ?? ''] ?? '#455a64'
}

// Paths SVG de Lucide (mismos iconos que las tarjetas: Siren / FileText /
// Building2 / FolderOpen), inline porque Leaflet arma el marker con HTML crudo.
export const CAPA_ICON_SVG = {
  emergencia: '<path d="M7 18v-6a5 5 0 1 1 10 0v6"/><path d="M5 21a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-1a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2z"/><path d="M21 12h1"/><path d="M18.5 4.5 18 5"/><path d="M2 12h1"/><path d="M12 2v1"/><path d="m4.929 4.929.707.707"/><path d="M12 12v6"/>',
  reclamo:    '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>',
  espacio:    '<path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/><path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/><path d="M10 6h4"/><path d="M10 10h4"/><path d="M10 14h4"/>',
  tramite:    '<path d="m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2"/>',
} as const

// Marker = badge circular de color con el icono Lucide de la capa en blanco.
// El color de reclamos varia por estado; el resto usa el color fijo de la capa.
function iconBadge(color: string, svgPaths: string) {
  return L.divIcon({
    className: 'dashboard-marker',
    html: `<div style="
      width: 26px; height: 26px;
      background: ${color};
      border: 2px solid white;
      border-radius: 50%;
      box-shadow: 0 1px 5px rgba(0,0,0,0.45);
      display: flex; align-items: center; justify-content: center;
    "><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${svgPaths}</svg></div>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
  })
}

export interface CapasVisibles {
  reclamos: boolean
  emergencias: boolean
  espacios: boolean
  tramites: boolean
}

interface Props {
  reclamos: GeoReclamo[]
  emergencias: GeoEmergencia[]
  espacios: GeoEspacio[]
  tramites: GeoTramite[]
  visibles: CapasVisibles
  onReclamoClick?: (r: GeoReclamo) => void
  onEmergenciaClick?: (e: GeoEmergencia) => void
  onTramiteClick?: (t: GeoTramite) => void
  /** Color del marker de reclamo. Default: por estado. El BI de pendientes lo
   *  usa para el semáforo de demora (0-3 / 4-7 / +7 días), 2026-08-30. */
  colorReclamo?: (r: GeoReclamo) => string
}

export function DashboardMap({
  reclamos, emergencias, espacios, tramites, visibles,
  onReclamoClick, onEmergenciaClick, onTramiteClick, colorReclamo,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const markersLayerRef = useRef<L.LayerGroup | null>(null)
  const clicksRef = useRef({ onReclamoClick, onEmergenciaClick, onTramiteClick })
  // Ref (no dep del effect de markers): una lambda nueva por render no debe redibujar.
  const colorReclamoRef = useRef(colorReclamo)
  const fittedRef = useRef(false)

  useEffect(() => {
    clicksRef.current = { onReclamoClick, onEmergenciaClick, onTramiteClick }
    colorReclamoRef.current = colorReclamo
  }, [onReclamoClick, onEmergenciaClick, onTramiteClick, colorReclamo])

  // Init mapa una sola vez.
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return
    const map = L.map(containerRef.current, {
      center: DEFAULT_CENTER,
      zoom: DEFAULT_ZOOM,
      scrollWheelZoom: true,
      // El control de zoom default va en top-left, donde vive el panel de stats.
      zoomControl: false,
    })
    L.control.zoom({ position: 'bottomright' }).addTo(map)
    // Tile minimal gris claro/oscuro SIN API key: Esri Gray Canvas. CARTO
    // (Positron/Dark Matter) empezo a servir tiles con marca "API KEY REQUIRED"
    // (cazado en prod 2026-08-30). Esri no tiene tiles nativos mas alla de
    // z16 en la zona -> maxNativeZoom escala en vez de dejar huecos.
    const esDark = document.documentElement.dataset.theme === 'dark'
    L.tileLayer(`https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_${esDark ? 'Dark_Gray' : 'Light_Gray'}_Base/MapServer/tile/{z}/{y}/{x}`, {
      attribution: '© <a href="https://www.esri.com">Esri</a> © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxNativeZoom: 16,
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

  // Sincronizar markers con datasets + toggles de capa.
  useEffect(() => {
    if (!mapRef.current || !markersLayerRef.current) return
    const layer = markersLayerRef.current
    layer.clearLayers()
    const bounds: L.LatLngTuple[] = []

    if (visibles.emergencias) {
      for (const e of emergencias) {
        if (e.latitud == null || e.longitud == null) continue
        const m = L.marker([e.latitud, e.longitud], { icon: iconBadge(CAPA_COLOR.emergencia, CAPA_ICON_SVG.emergencia) })
          .bindPopup(`
            <div style="font-family: var(--font-display, sans-serif); min-width: 200px;">
              <div style="font-weight: 600; margin-bottom: 4px;">Emergencia ${esc(e.numero_operativo ?? '—')}</div>
              <div style="font-size: 0.78rem; color: #666; margin-bottom: 6px;">${esc(e.tipo_nombre ?? '')}</div>
              <div style="font-size: 0.78rem; margin-bottom: 4px;"><strong>Estado:</strong> ${esc(e.estado_nombre)}</div>
              <div style="font-size: 0.78rem;">${esc(e.direccion_evento ?? '')}</div>
            </div>
          `)
        m.on('click', () => clicksRef.current.onEmergenciaClick?.(e))
        m.addTo(layer)
        bounds.push([e.latitud, e.longitud])
      }
    }

    if (visibles.reclamos) {
      for (const r of reclamos) {
        if (r.latitud == null || r.longitud == null) continue
        const color = colorReclamoRef.current ? colorReclamoRef.current(r) : colorEstadoReclamo(r.estado)
        const m = L.marker([r.latitud, r.longitud], { icon: iconBadge(color, CAPA_ICON_SVG.reclamo) })
          .bindPopup(`
            <div style="font-family: var(--font-display, sans-serif); min-width: 200px;">
              <div style="font-weight: 600; margin-bottom: 4px;">${esc(r.nro_reclamo ?? '—')}</div>
              <div style="font-size: 0.78rem; color: #666; margin-bottom: 6px;">${esc(r.tipo_nombre ?? '')}</div>
              <div style="font-size: 0.78rem; margin-bottom: 4px;"><strong>Estado:</strong> ${esc(r.estado)}</div>
              <div style="font-size: 0.78rem; margin-bottom: 4px;"><strong>Prioridad:</strong> ${esc(r.prioridad ?? '—')}</div>
              <div style="font-size: 0.75rem; color: #444; margin-top: 6px;">${esc(r.descripcion ?? '')}</div>
            </div>
          `)
        m.on('click', () => clicksRef.current.onReclamoClick?.(r))
        m.addTo(layer)
        bounds.push([r.latitud, r.longitud])
      }
    }

    if (visibles.espacios) {
      for (const s of espacios) {
        if (s.latitud == null || s.longitud == null) continue
        const m = L.marker([s.latitud, s.longitud], { icon: iconBadge(CAPA_COLOR.espacio, CAPA_ICON_SVG.espacio) })
          .bindPopup(`
            <div style="font-family: var(--font-display, sans-serif); min-width: 200px;">
              <div style="font-weight: 600; margin-bottom: 4px;">${esc(s.nombre)}</div>
              <div style="font-size: 0.78rem; color: #666; margin-bottom: 6px;">${esc(s.direccion ?? '')}</div>
              <div style="font-size: 0.78rem; margin-bottom: 4px;"><strong>Turnos vigentes:</strong> ${s.turnos_vigentes}</div>
              <div style="font-size: 0.78rem;"><strong>Entradas emitidas:</strong> ${s.entradas_vigentes}</div>
            </div>
          `)
        m.addTo(layer)
        bounds.push([s.latitud, s.longitud])
      }
    }

    if (visibles.tramites) {
      for (const t of tramites) {
        if (t.latitud == null || t.longitud == null) continue
        const m = L.marker([t.latitud, t.longitud], { icon: iconBadge(CAPA_COLOR.tramite, CAPA_ICON_SVG.tramite) })
          .bindPopup(`
            <div style="font-family: var(--font-display, sans-serif); min-width: 200px;">
              <div style="font-weight: 600; margin-bottom: 4px;">${esc(t.numero_expediente)}</div>
              <div style="font-size: 0.78rem; color: #666; margin-bottom: 6px;">${esc(t.tipo_nombre ?? '')}</div>
              <div style="font-size: 0.78rem; margin-bottom: 4px;"><strong>Estado:</strong> ${esc(t.estado_etiqueta ?? '—')}</div>
              <div style="font-size: 0.78rem;">${esc(t.direccion ?? '')}</div>
            </div>
          `)
        m.on('click', () => clicksRef.current.onTramiteClick?.(t))
        m.addTo(layer)
        bounds.push([t.latitud, t.longitud])
      }
    }

    // Fit inicial una sola vez (que un toggle de capa no re-encuadre el mapa
    // mientras el usuario esta navegando).
    if (!fittedRef.current && bounds.length > 0) {
      fittedRef.current = true
      if (bounds.length >= 2) {
        mapRef.current.fitBounds(L.latLngBounds(bounds), { padding: [60, 60], maxZoom: 15 })
      } else {
        mapRef.current.setView(bounds[0], 15)
      }
    }
  }, [reclamos, emergencias, espacios, tramites, visibles])

  return (
    <div ref={containerRef} style={{ position: 'absolute', inset: 0 }} />
  )
}

function esc(s: string | null | undefined): string {
  const str = String(s ?? '')
  return str.replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c] ?? c))
}
