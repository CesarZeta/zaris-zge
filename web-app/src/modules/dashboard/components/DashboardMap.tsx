import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

import type {
  GeoEmergencia, GeoEspacio, GeoReclamo, GeoTramite, LimiteMunicipio,
} from '../hooks/useDashboardData'

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

// Marker del mapa (César 2026-10-19): punto de 13 px — la mitad del badge de
// 26 px con icono que habia antes, ilegible a ese tamaño. Dos colores:
//   * CONTORNO = tipo (reclamo / emergencia / espacio / tramite) — CAPA_COLOR.
//   * CENTRO   = estado (mismo significado en reclamos y emergencias) —
//     ESTADO_COLOR. Las capas sin estado (espacios, tramites) van macizas.
// Ninguno es naranja: el naranja del brand es el sombreado del municipio (§4).

// Estados (centro). Celeste y amarillo por decision de César (2026-10-19).
export const ESTADO_COLOR: Record<string, string> = {
  'Sin asignar':  '#c62828', // rojo (urgencia)
  'En gestión':   '#29b6f6', // celeste (en curso)
  'En espera':    '#fbc02d', // amarillo (bloqueado)
  'En auditoría': '#6a1b9a', // violeta: resuelto, pendiente del auditor (mig 112; 'Auditado' no va al mapa)
}
export const ESTADOS_LEYENDA = Object.keys(ESTADO_COLOR)
const ESTADO_SIN_COLOR = '#90a4ae'

// Tipos (contorno), lejos del naranja del brand y de los colores de estado.
export const CAPA_COLOR = {
  reclamo:    '#37474f', // pizarra: la capa masiva, neutra
  emergencia: '#cf2d56', // --color-error: lo mas urgente del tablero
  espacio:    '#1565c0', // azul: infraestructura municipal
  tramite:    '#8d6e63', // marron: expedientes
} as const

// Las emergencias tienen su propio FSM (§44); para el mapa se agrupan en los
// mismos estados que los reclamos, asi el centro del punto significa lo mismo.
const ESTADO_EMERGENCIA: Record<string, string> = {
  PENDIENTE:      'Sin asignar',
  EN_PREPARACION: 'En gestión',
  EN_CAMINO:      'En gestión',
  EN_SITIO:       'En gestión',
  DERIVADO:       'En espera',
}
export function estadoMapaEmergencia(codigo: string | null | undefined): string {
  return ESTADO_EMERGENCIA[codigo ?? ''] ?? 'En gestión'
}

function colorEstado(estado: string | null): string {
  return ESTADO_COLOR[estado ?? ''] ?? ESTADO_SIN_COLOR
}

const MARKER_PX = 13
const MARKER_ANILLO_PX = 3
function iconEstado(contorno: string, centro: string) {
  return L.divIcon({
    className: 'dashboard-marker',
    // Halo blanco fino (box-shadow) para que el contorno se lea sobre el tile
    // gris claro, el oscuro y el sombreado naranja del municipio.
    html: `<div style="
      width: ${MARKER_PX}px; height: ${MARKER_PX}px; box-sizing: border-box;
      background: ${centro};
      border: ${MARKER_ANILLO_PX}px solid ${contorno};
      border-radius: 50%;
      box-shadow: 0 0 0 1.5px rgba(255,255,255,0.95), 0 1px 3px rgba(0,0,0,0.4);
    "></div>`,
    iconSize: [MARKER_PX, MARKER_PX],
    iconAnchor: [MARKER_PX / 2, MARKER_PX / 2],
  })
}

// Contorno del municipio (mig 111): se sombrea TODO LO DE AFUERA con el naranja
// ZARIS translucido y el municipio queda limpio (César 2026-10-19). Es un
// poligono-mascara: anillo exterior = el mundo, hueco = el municipio. Literal
// (no var()) porque Leaflet lo pinta como atributo SVG; es el valor de
// --zaris-orange, que no cambia entre temas.
const LIMITE_ESTILO: L.PathOptions = {
  color: '#f54e00',
  weight: 2,
  opacity: 0.9,
  fillColor: '#f54e00',
  fillOpacity: 0.18,
  interactive: false,
}
const MUNDO: L.LatLngTuple[] = [[-89, -179.9], [-89, 179.9], [89, 179.9], [89, -179.9]]

function mascaraExterior(limite: LimiteMunicipio): L.Polygon {
  const hueco = limite.coordinates[0].map(([lon, lat]) => [lat, lon] as L.LatLngTuple)
  return L.polygon([MUNDO, hueco], LIMITE_ESTILO)
}

// Marker mínimo tipo scatter para los mapas analíticos del BI Ejecutivo
// (César 2026-08-31: "los puntos deben tener el tamaño de un píxel"). Un 1px
// literal es invisible en pantallas retina; este es el punto mínimo legible.
const PUNTO_PX = 5
function iconPunto(color: string) {
  return L.divIcon({
    className: 'dashboard-marker',
    html: `<div style="width:${PUNTO_PX}px;height:${PUNTO_PX}px;background:${color};border-radius:50%;"></div>`,
    iconSize: [PUNTO_PX, PUNTO_PX],
    iconAnchor: [PUNTO_PX / 2, PUNTO_PX / 2],
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
  /** Reclamos como puntos mínimos de color (scatter) en lugar del badge de
   *  26px. Lo usan los mapas de Satisfacción del BI Ejecutivo (2026-08-31). */
  marcadorPunto?: boolean
  /** Contorno del municipio (mig 111). Si viene, se dibuja sombreado y el
   *  encuadre inicial es el municipio entero en lugar de la nube de puntos. */
  limite?: LimiteMunicipio | null
  /** Zonas libres del mapa donde puede ir el municipio, como márgenes (px)
   *  respecto del contenedor: cada una es una alternativa (p. ej. "a la
   *  derecha del panel" o "debajo de la leyenda") y se usa la que deja el
   *  municipio más grande. Se re-evalúa en cada re-encuadre. */
  encuadresLibres?: () => Encuadre[]
  /** Cambiar este número pide re-encuadrar el municipio (p. ej. porque un
   *  panel flotante cambió de tamaño), salvo que el usuario haya movido el mapa. */
  reencuadre?: number
}

export interface Encuadre {
  topLeft: [number, number]
  bottomRight: [number, number]
}

// Margen por defecto: esquina inferior derecha con lugar para los botones
// (zoom + "ver municipio completo").
const ENCUADRE_DEFAULT: Encuadre = { topLeft: [24, 24], bottomRight: [56, 24] }

// Boton Leaflet "ver el municipio completo" (icono Lucide Maximize, inline:
// Leaflet arma el control con HTML crudo).
function controlVerMunicipio(onClick: () => void): L.Control {
  const Ctl = L.Control.extend({
    onAdd() {
      const div = L.DomUtil.create('div', 'leaflet-bar leaflet-control')
      const a = L.DomUtil.create('a', '', div)
      a.href = '#'
      a.title = 'Ver el municipio completo'
      a.setAttribute('role', 'button')
      a.setAttribute('aria-label', 'Ver el municipio completo')
      a.style.display = 'flex'
      a.style.alignItems = 'center'
      a.style.justifyContent = 'center'
      a.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/><path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/></svg>'
      L.DomEvent.disableClickPropagation(div)
      L.DomEvent.on(a, 'click', (ev) => { L.DomEvent.preventDefault(ev); onClick() })
      return div
    },
  })
  return new Ctl({ position: 'bottomright' })
}

// Rectángulo (coordenadas de ventana) donde el elemento es realmente visible:
// la ventana intersectada con cada ancestro que recorta su contenido.
function areaVisible(el: HTMLElement): { top: number; left: number; bottom: number; right: number } {
  const a = { top: 0, left: 0, bottom: window.innerHeight, right: window.innerWidth }
  for (let p = el.parentElement; p && p !== document.documentElement; p = p.parentElement) {
    const cs = getComputedStyle(p)
    if (cs.overflowX === 'visible' && cs.overflowY === 'visible') continue
    const pr = p.getBoundingClientRect()
    a.top = Math.max(a.top, pr.top)
    a.left = Math.max(a.left, pr.left)
    a.bottom = Math.min(a.bottom, pr.bottom)
    a.right = Math.min(a.right, pr.right)
  }
  return a
}

export function DashboardMap({
  reclamos, emergencias, espacios, tramites, visibles,
  onReclamoClick, onEmergenciaClick, onTramiteClick, colorReclamo, marcadorPunto,
  limite, encuadresLibres, reencuadre,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const markersLayerRef = useRef<L.LayerGroup | null>(null)
  const limiteLayerRef = useRef<L.Polygon | null>(null)
  // Bounds del municipio (no de la mascara, que abarca el mundo) para el encuadre.
  const limiteBoundsRef = useRef<L.LatLngBounds | null>(null)
  const encuadresRef = useRef(encuadresLibres)
  encuadresRef.current = encuadresLibres
  // El municipio se re-encuadra solo (resize de ventana, panel que crece)
  // mientras el usuario no haya movido el mapa a mano; el boton "ver municipio
  // completo" vuelve a ese modo. fittingRef distingue nuestro fit del gesto.
  const usuarioMovioRef = useRef(false)
  const fittingRef = useRef(false)
  const verMunicipioCtlRef = useRef<L.Control | null>(null)
  // Vértices del municipio (anillo exterior).
  const limitePuntosRef = useRef<L.LatLng[]>([])

  // Encuadra el municipio ENTERO y lo más grande posible dentro de la zona
  // libre del mapa (César 2026-10-19: "siempre tiene que estar a la vista al
  // 100%", sin quedar bajo las tarjetas; el norte SIEMPRE arriba, sin rotar).
  // Prueba cada zona libre y se queda con la que da el mayor zoom. Zoom
  // fraccionario (0.1) para no perder hasta un nivel entero por redondeo.
  const encuadrarLimite = useRef(() => {})
  encuadrarLimite.current = () => {
    const map = mapRef.current
    const cont = containerRef.current
    const lls = limitePuntosRef.current
    if (!map || !cont || lls.length < 3) return
    map.invalidateSize()
    map.options.zoomSnap = 0.1
    // Parte del contenedor que no se ve (fuera de la ventana o recortada por
    // un ancestro con scroll/overflow, como el main del shell): se suma al
    // margen para que el municipio caiga en lo visible.
    const r = cont.getBoundingClientRect()
    const vis = areaVisible(cont)
    const oculto = {
      top: Math.max(0, vis.top - r.top),
      left: Math.max(0, vis.left - r.left),
      bottom: Math.max(0, r.bottom - vis.bottom),
      right: Math.max(0, r.right - vis.right),
    }
    const aZona = (c: Encuadre) => ({
      x0: c.topLeft[0] + oculto.left,
      y0: c.topLeft[1] + oculto.top,
      x1: r.width - c.bottomRight[0] - oculto.right,
      y1: r.height - c.bottomRight[1] - oculto.bottom,
    })
    let zonas = (encuadresRef.current?.() ?? []).map(aZona)
      // Zona libre demasiado chica (pantalla angosta): no es candidata.
      .filter((z) => z.x1 - z.x0 >= 120 && z.y1 - z.y0 >= 120)
    if (zonas.length === 0) zonas = [aZona(ENCUADRE_DEFAULT)]

    const z0 = map.getZoom()
    const pts = lls.map((ll) => map.project(ll, z0))
    const x0 = Math.min(...pts.map((p) => p.x)), x1 = Math.max(...pts.map((p) => p.x))
    const y0 = Math.min(...pts.map((p) => p.y)), y1 = Math.max(...pts.map((p) => p.y))
    let elegida: { zona: (typeof zonas)[number]; zoom: number } | null = null
    for (const zona of zonas) {
      const escala = Math.min((zona.x1 - zona.x0) / (x1 - x0), (zona.y1 - zona.y0) / (y1 - y0))
      const z = z0 + Math.log2(escala)
      if (!elegida || z > elegida.zoom) elegida = { zona, zoom: z }
    }
    if (!elegida) return
    const zoom = Math.max(map.getMinZoom(), Math.min(map.getMaxZoom(), Math.floor(elegida.zoom * 10) / 10))

    fittingRef.current = true
    try {
      // Centro de la caja del municipio en el centro de la zona libre elegida.
      const centro = map.unproject(L.point((x0 + x1) / 2, (y0 + y1) / 2), z0)
      map.setView(centro, zoom, { animate: false })
      const cCont = map.getSize().divideBy(2)
      const cZona = L.point((elegida.zona.x0 + elegida.zona.x1) / 2, (elegida.zona.y0 + elegida.zona.y1) / 2)
      map.setView(map.containerPointToLatLng(cCont.multiplyBy(2).subtract(cZona)), zoom, { animate: false })
    } finally {
      fittingRef.current = false
    }
  }

  const clicksRef = useRef({ onReclamoClick, onEmergenciaClick, onTramiteClick })
  // Ref (no dep del effect de markers): una lambda nueva por render no debe redibujar.
  const colorReclamoRef = useRef(colorReclamo)
  const fittedRef = useRef(false)
  const reclamosPrevRef = useRef<GeoReclamo[] | null>(null)

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
    // Mapa NUEVO ⇒ necesita su propio fit inicial. Sin este reset, el doble
    // montaje de StrictMode (dev) dejaba fittedRef=true del primer mapa y el
    // segundo quedaba clavado en el center/zoom default, recortando puntos
    // (cazado 2026-08-31 con el tablero Ejecutivo).
    fittedRef.current = false
    usuarioMovioRef.current = false
    // Hook de QA por navegador (§41): permite leer bounds/zoom reales del mapa
    // desde browser_eval sin exponer nada en la UI.
    ;(containerRef.current as unknown as { _mapDebug?: L.Map })._mapDebug = map

    // El contenedor puede cambiar de tamaño después del init (layout flex que
    // asienta, filtros que se colapsan): sin invalidateSize, Leaflet renderiza
    // con el viewport viejo y el encuadre recorta puntos (César 2026-08-31).
    // Con municipio: además re-encuadrar (debounce) si el usuario no movió el
    // mapa — el resize de la ventana no debe dejarlo recortado ni chico.
    let timer: number | undefined
    const alCambiarTamano = () => {
      map.invalidateSize()
      if (!limiteBoundsRef.current || usuarioMovioRef.current) return
      window.clearTimeout(timer)
      timer = window.setTimeout(() => {
        if (mapRef.current === map) encuadrarLimite.current()
      }, 120)
    }
    let ro: ResizeObserver | undefined
    if (typeof ResizeObserver !== 'undefined' && containerRef.current) {
      ro = new ResizeObserver(alCambiarTamano)
      ro.observe(containerRef.current)
    }
    // El contenedor puede no cambiar de tamaño y aun así quedar parcialmente
    // fuera de la ventana (scroll del iframe): también escuchar la ventana.
    window.addEventListener('resize', alCambiarTamano)
    map.on('dragstart zoomstart', () => {
      if (!fittingRef.current) usuarioMovioRef.current = true
    })

    return () => {
      window.clearTimeout(timer)
      window.removeEventListener('resize', alCambiarTamano)
      ro?.disconnect()
      map.off()
      map.remove()
      mapRef.current = null
      markersLayerRef.current = null
      limiteLayerRef.current = null
      limiteBoundsRef.current = null
      limitePuntosRef.current = []
      // Controles del mapa destruido (doble montaje de StrictMode): no
      // removerlos de nuevo desde el efecto del contorno.
      verMunicipioCtlRef.current = null
    }
  }, [])

  // Contorno del municipio (capa debajo de los markers: overlayPane < markerPane).
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    limiteLayerRef.current?.remove()
    limiteLayerRef.current = limite ? mascaraExterior(limite).addTo(map) : null
    limitePuntosRef.current = limite
      ? limite.coordinates[0].map(([lon, lat]) => L.latLng(lat, lon))
      : []
    limiteBoundsRef.current = limite ? L.latLngBounds(limitePuntosRef.current) : null
    verMunicipioCtlRef.current?.remove()
    verMunicipioCtlRef.current = limite
      ? controlVerMunicipio(() => {
          usuarioMovioRef.current = false
          encuadrarLimite.current()
        }).addTo(map)
      : null
  }, [limite])

  // Un panel flotante cambió de tamaño: re-encuadrar si el usuario no movió el mapa.
  useEffect(() => {
    if (reencuadre === undefined || !fittedRef.current || usuarioMovioRef.current) return
    encuadrarLimite.current()
  }, [reencuadre])

  // Sincronizar markers con datasets + toggles de capa.
  useEffect(() => {
    if (!mapRef.current || !markersLayerRef.current) return
    const layer = markersLayerRef.current
    layer.clearLayers()
    const bounds: L.LatLngTuple[] = []

    if (visibles.emergencias) {
      for (const e of emergencias) {
        if (e.latitud == null || e.longitud == null) continue
        const m = L.marker([e.latitud, e.longitud], { icon: iconEstado(CAPA_COLOR.emergencia, colorEstado(estadoMapaEmergencia(e.estado_codigo))) })
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
        const color = colorReclamoRef.current ? colorReclamoRef.current(r) : colorEstado(r.estado)
        const icon = marcadorPunto ? iconPunto(color) : iconEstado(CAPA_COLOR.reclamo, color)
        const m = L.marker([r.latitud, r.longitud], { icon })
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
        const m = L.marker([s.latitud, s.longitud], { icon: iconEstado(CAPA_COLOR.espacio, CAPA_COLOR.espacio) })
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
        const m = L.marker([t.latitud, t.longitud], { icon: iconEstado(CAPA_COLOR.tramite, CAPA_COLOR.tramite) })
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
    // mientras el usuario esta navegando). En modo punto (mapas analíticos del
    // BI, sin toggles) se re-encuadra también cuando CAMBIA el dataset (nuevo
    // filtro ⇒ nueva nube de puntos, César 2026-08-31). invalidateSize antes
    // del fit + re-fit diferido: si el layout todavía no asentó, el primer fit
    // calcula con un viewport errado y deja puntos fuera de cuadro.
    const datosCambiaron = reclamosPrevRef.current !== reclamos
    reclamosPrevRef.current = reclamos
    const debeFit = !fittedRef.current || (marcadorPunto && datosCambiaron)
    // Con contorno, el encuadre inicial es el municipio entero (no la nube de
    // puntos, que deja afuera zonas sin actividad).
    const limiteBounds = limiteBoundsRef.current
    if (debeFit && (bounds.length > 0 || limiteBounds?.isValid())) {
      fittedRef.current = true
      const map = mapRef.current
      const fit = () => {
        if (limiteBounds?.isValid()) {
          if (!usuarioMovioRef.current) encuadrarLimite.current()
        } else if (bounds.length >= 2) {
          map.fitBounds(L.latLngBounds(bounds), { padding: [60, 60], maxZoom: 15 })
        } else {
          map.setView(bounds[0], 15)
        }
      }
      map.invalidateSize()
      fit()
      window.setTimeout(() => {
        if (mapRef.current !== map) return // ya desmontado
        map.invalidateSize()
        fit()
      }, 300)
    }
  }, [reclamos, emergencias, espacios, tramites, visibles, marcadorPunto, limite])

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
