import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Building2, CalendarCheck, ChevronDown, ChevronUp, FileText, FolderOpen, Layers, Siren, Ticket,
} from 'lucide-react'
import { useDashboardResumen, useIdentidadMunicipio } from '../hooks/useDashboardData'
import {
  CAPA_COLOR, DashboardMap, ESTADO_COLOR, ESTADOS_LEYENDA, estadoMapaEmergencia,
  type CapasVisibles, type Encuadre,
} from '../components/DashboardMap'

// Tablero home: "Resumen de actividad municipal". Mapa geoposicionado de fondo
// (emergencias + reclamos + espacios de atencion + tramites) y 6 tarjetas de
// actividad. Titulo con logo y nombre del municipio (Config -> Identidad).

export function Overview() {
  const navigate = useNavigate()
  const resumenQ = useDashboardResumen()
  const identidadQ = useIdentidadMunicipio()

  const [capas, setCapas] = useState<CapasVisibles>({
    emergencias: true, reclamos: true, espacios: true, tramites: true,
  })

  // Filtro por estado (= color del centro del punto). Aplica a reclamos y
  // emergencias, las dos capas con estado (César 2026-10-19).
  const [estadosOcultos, setEstadosOcultos] = useState<Set<string>>(new Set())
  const [verLimite, setVerLimite] = useState(true)

  const tarjetas = resumenQ.data?.tarjetas
  const geo = resumenQ.data?.geo
  const cargando = resumenQ.isLoading

  const reclamosMapa = useMemo(
    () => (geo?.reclamos ?? []).filter((r) => !estadosOcultos.has(r.estado)),
    [geo?.reclamos, estadosOcultos],
  )
  const emergenciasMapa = useMemo(
    () => (geo?.emergencias ?? []).filter((e) => !estadosOcultos.has(estadoMapaEmergencia(e.estado_codigo))),
    [geo?.emergencias, estadosOcultos],
  )
  // Conteo por estado de lo que las capas visibles muestran (sin el filtro de
  // estado, para que un estado oculto siga mostrando cuántos hay).
  const conteoEstados = useMemo(() => {
    const n: Record<string, number> = {}
    if (capas.reclamos) for (const r of geo?.reclamos ?? []) n[r.estado] = (n[r.estado] ?? 0) + 1
    if (capas.emergencias) {
      for (const e of geo?.emergencias ?? []) {
        const k = estadoMapaEmergencia(e.estado_codigo)
        n[k] = (n[k] ?? 0) + 1
      }
    }
    return n
  }, [geo?.reclamos, geo?.emergencias, capas.reclamos, capas.emergencias])

  // Encuadre del municipio (César 2026-10-19: siempre entero y a la vista,
  // sin quedar bajo las tarjetas). Se mide el panel REAL (columna de tarjetas
  // y leyenda, que hace wrap según el ancho) y se ofrecen al mapa las zonas
  // libres; el mapa usa la que deja el municipio más grande.
  const pageRef = useRef<HTMLDivElement>(null)
  const columnaRef = useRef<HTMLDivElement>(null)
  const leyendaRef = useRef<HTMLDivElement>(null)
  const encuadresLibres = useCallback((): Encuadre[] => {
    const page = pageRef.current?.getBoundingClientRect()
    if (!page) return []
    const rel = (el: HTMLElement | null) => {
      const r = el?.getBoundingClientRect()
      return r ? { left: r.left - page.left, top: r.top - page.top, right: r.right - page.left, bottom: r.bottom - page.top } : null
    }
    const cols = rel(columnaRef.current)
    const ley = rel(leyendaRef.current)
    const obst = [cols, ley].filter((o): o is NonNullable<typeof o> => o !== null)
    if (obst.length === 0) return []
    const M = 16
    const br: [number, number] = [56, 24] // abajo-derecha: botones del mapa
    const derecha = Math.max(...obst.map((o) => o.right))
    const abajo = Math.max(...obst.map((o) => o.bottom))
    const zonas: Encuadre[] = [
      { topLeft: [derecha + M, M], bottomRight: br },  // a la derecha de todo el panel
      { topLeft: [M, abajo + M], bottomRight: br },    // debajo de todo el panel
    ]
    // Leyenda al costado de las tarjetas: también sirve la franja a la
    // derecha de las tarjetas y debajo de la leyenda.
    if (cols && ley && ley.left >= cols.right - 1) {
      zonas.push({ topLeft: [cols.right + M, ley.bottom + M], bottomRight: br })
    }
    return zonas
  }, [])
  // El panel cambia de alto/ancho (wrap de la leyenda, fila de estados que
  // aparece o desaparece): pedirle al mapa que re-encuadre.
  // Modo compacto (César 2026-10-19, opción 1): con el mapa angosto el panel
  // completo tapa el municipio. Las 6 tarjetas pasan a una fila de chips
  // (icono + número; el nombre en el tooltip) y la leyenda se pliega detrás de
  // un botón "Capas". El encuadre mide el panel igual que en modo normal.
  const [anchoPagina, setAnchoPagina] = useState(0)
  const compacto = anchoPagina > 0 && anchoPagina < ANCHO_COMPACTO
  const [leyendaAbierta, setLeyendaAbierta] = useState(false)
  const mostrarLeyenda = !compacto || leyendaAbierta
  useEffect(() => {
    const el = pageRef.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(([e]) => setAnchoPagina(e.contentRect.width))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const [reencuadre, setReencuadre] = useState(0)
  useEffect(() => {
    if (typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(() => setReencuadre((n) => n + 1))
    if (columnaRef.current) ro.observe(columnaRef.current)
    if (leyendaRef.current) ro.observe(leyendaRef.current)
    return () => ro.disconnect()
    // Al cambiar de modo o plegar la leyenda cambian los elementos observados.
  }, [compacto, mostrarLeyenda])

  const tarjetasDef: TarjetaDef[] = [
    { icon: Siren, color: TARJETA_COLOR.emergencias, label: 'Emergencias activas',
      value: tarjetas?.emergencias_activas ?? 0, sublabel: 'sin cerrar en el COM', ruta: '/emergencias' },
    { icon: FileText, color: TARJETA_COLOR.reclamos, label: 'Reclamos activos',
      value: tarjetas?.reclamos_activos ?? 0, sublabel: `${geo?.reclamos.length ?? 0} con geo`, ruta: '/reclamos' },
    { icon: Building2, color: TARJETA_COLOR.espacios, label: 'Espacios de atención',
      value: tarjetas?.espacios_disponibles ?? 0, sublabel: 'disponibles', ruta: '/agenda' },
    { icon: CalendarCheck, color: TARJETA_COLOR.turnos, label: 'Turnos otorgados',
      value: tarjetas?.turnos_otorgados ?? 0, sublabel: 'de hoy en adelante', ruta: '/turnos' },
    { icon: Ticket, color: TARJETA_COLOR.entradas, label: 'Entradas emitidas',
      value: tarjetas?.entradas_emitidas ?? 0, sublabel: 'eventos vigentes', ruta: '/entradas' },
    { icon: FolderOpen, color: TARJETA_COLOR.tramites, label: 'Trámites abiertos',
      value: tarjetas?.tramites_abiertos ?? 0, sublabel: 'en circuito', ruta: '/tramites' },
  ]

  function toggleCapa(k: keyof CapasVisibles) {
    setCapas((c) => ({ ...c, [k]: !c[k] }))
  }
  function toggleEstado(estado: string) {
    setEstadosOcultos((prev) => {
      const sig = new Set(prev)
      if (sig.has(estado)) sig.delete(estado)
      else sig.add(estado)
      return sig
    })
  }

  function logo(alto: number) {
    const url = identidadQ.data?.municipio_logo_url
    if (!url) return null
    return (
      <img
        src={resolverLogoUrl(url)}
        alt=""
        onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
        style={{ height: alto, width: 'auto', maxWidth: alto * 2.25, objectFit: 'contain', flexShrink: 0 }}
      />
    )
  }

  // Leyenda: el CONTORNO del punto es el tipo (toggle por capa) y el CENTRO es
  // el estado (toggle = filtro). Pedido 2026-10-19.
  const leyenda = (
    <div ref={leyendaRef} style={compacto ? legendStyle : { ...legendStyle, flex: '1 1 240px', minWidth: 240 }}>
      <div style={legendTitle}>Capas del mapa · contorno del punto</div>
      <div style={legendRowStyle}>
        <LayerToggle
          activo={capas.emergencias}
          onClick={() => toggleCapa('emergencias')}
          label="Emergencias"
          shape={<MarkerSwatch contorno={CAPA_COLOR.emergencia} centro="var(--surface-100)" />}
        />
        <LayerToggle
          activo={capas.reclamos}
          onClick={() => toggleCapa('reclamos')}
          label="Reclamos"
          shape={<MarkerSwatch contorno={CAPA_COLOR.reclamo} centro="var(--surface-100)" />}
        />
        <LayerToggle
          activo={capas.espacios}
          onClick={() => toggleCapa('espacios')}
          label="Espacios"
          shape={<MarkerSwatch contorno={CAPA_COLOR.espacio} centro={CAPA_COLOR.espacio} />}
        />
        <LayerToggle
          activo={capas.tramites}
          onClick={() => toggleCapa('tramites')}
          label="Trámites"
          shape={<MarkerSwatch contorno={CAPA_COLOR.tramite} centro={CAPA_COLOR.tramite} />}
        />
        {geo?.limite ? (
          <LayerToggle
            activo={verLimite}
            onClick={() => setVerLimite((v) => !v)}
            label="Límite del municipio"
            shape={<span style={limiteSwatchStyle} />}
          />
        ) : null}
      </div>
      {(capas.reclamos || capas.emergencias) && (
        <>
          <div style={{ ...legendTitle, marginTop: 8 }}>Estado · centro del punto</div>
          <div style={legendRowStyle}>
            {ESTADOS_LEYENDA.map((estado) => (
              <LayerToggle
                key={estado}
                activo={!estadosOcultos.has(estado)}
                onClick={() => toggleEstado(estado)}
                label={`${estado} (${conteoEstados[estado] ?? 0})`}
                shape={<MarkerSwatch contorno={ESTADO_COLOR[estado]} centro={ESTADO_COLOR[estado]} />}
              />
            ))}
          </div>
        </>
      )}
    </div>
  )

  return (
    <div ref={pageRef} style={pageStyle}>
      {/* Mapa de fondo ocupa todo. */}
      <DashboardMap
        emergencias={emergenciasMapa}
        reclamos={reclamosMapa}
        espacios={geo?.espacios ?? []}
        tramites={geo?.tramites ?? []}
        visibles={capas}
        limite={verLimite ? geo?.limite : null}
        encuadresLibres={encuadresLibres}
        reencuadre={reencuadre}
        onEmergenciaClick={(e) => navigate(`/emergencias/evento/${e.id_emergencia_evento}`)}
        onReclamoClick={(r) => navigate(`/reclamos/${r.id_reclamo}`)}
        onTramiteClick={(t) => navigate(`/tramites/${t.numero_expediente}`)}
      />

      {/* Panel flotante arriba-izquierda (en compacto, franja a lo ancho). */}
      <div style={compacto ? { ...statsLayerStyle, right: 16 } : statsLayerStyle}>
        {compacto ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div ref={columnaRef} style={compactoStyle}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {logo(24)}
                <h1 style={{ ...titleStyle, fontSize: '1rem', flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {identidadQ.data?.municipio_nombre ?? ''}
                </h1>
                <button
                  type="button"
                  onClick={() => setLeyendaAbierta((v) => !v)}
                  aria-expanded={leyendaAbierta}
                  title={leyendaAbierta ? 'Ocultar capas y estados' : 'Ver capas y estados del mapa'}
                  style={capasBtnStyle}
                >
                  <Layers size={14} strokeWidth={1.8} />
                  Capas
                  {leyendaAbierta ? <ChevronUp size={14} strokeWidth={1.8} /> : <ChevronDown size={14} strokeWidth={1.8} />}
                </button>
              </div>
              <div style={chipsRowStyle}>
                {tarjetasDef.map((t) => (
                  <MiniCard key={t.ruta} {...t} cargando={cargando} onClick={() => navigate(t.ruta)} />
                ))}
              </div>
            </div>
            {mostrarLeyenda && leyenda}
          </div>
        ) : (
          /* Columna izquierda (titulo compacto + azulejos debajo) y leyenda de
             capas al costado derecho del titulo (pedido 2026-07-02). */
          <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start', flexWrap: 'wrap' }}>
            <div ref={columnaRef} style={{ display: 'flex', flexDirection: 'column', gap: 12, flex: '0 0 auto' }}>
              <div style={headerStyle}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  {logo(32)}
                  <h1 style={titleStyle}>{identidadQ.data?.municipio_nombre ?? ''}</h1>
                </div>
                <p style={subtitleStyle}>Resumen de actividad municipal</p>
              </div>
              <div style={cardsGridStyle}>
                {tarjetasDef.map((t) => (
                  <StatCard
                    key={t.ruta}
                    icon={t.icon}
                    color={t.color}
                    label={t.label}
                    value={t.value}
                    sublabel={cargando ? 'cargando…' : t.sublabel}
                    onClick={() => navigate(t.ruta)}
                  />
                ))}
              </div>
            </div>
            {leyenda}
          </div>
        )}
      </div>
    </div>
  )
}

// El logo del municipio puede venir absoluto (Supabase, prod) o relativo a la
// raiz del shell ('/design-system/...', valor demo local). El bundle vive bajo
// <root>/web-app/dist/: una ruta que arranca con '/' hay que prefijarla con el
// subpath del deploy (p.ej. '/zaris-zge') o rompe en GH Pages (§32 Q13).
function resolverLogoUrl(url: string): string {
  if (!url.startsWith('/')) return url // absoluta (https://...) — va directo
  const m = window.location.pathname.match(/^(.*)\/web-app\/dist\//)
  return (m ? m[1] : '') + url
}

// Lado de los azulejos: dos filas de tres, cuadrados y CHICOS (pedido
// 2026-07-02; 25% menos que la primera version de 136px, mismas fuentes).
// Declarado ANTES de los estilos que lo usan (headerStyle/cardsGridStyle) —
// un const de modulo usado antes de declararse tira TDZ en runtime.
const TILE = 102

// Color identitario de cada tarjeta (= color del icono y del tinte de fondo).
// Coherentes con CAPA_COLOR del mapa; nunca naranja (brand, §4).
const TARJETA_COLOR = {
  emergencias: '#cf2d56', // rojo --color-error (capa emergencias)
  reclamos:    '#1f8a65', // verde --color-success (identidad de la tarjeta)
  espacios:    '#1565c0', // azul (capa espacios)
  turnos:      '#00838f', // cian oscuro (atención con turno)
  entradas:    '#6a1b9a', // violeta (eventos)
  tramites:    '#8d6e63', // marrón (capa trámites)
} as const

// rgba del hex para el tinte de fondo (los hex de arriba son fijos, 6 dígitos).
function tinte(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

// Ancho del mapa (px) por debajo del cual el panel pasa a modo compacto: con
// menos, la columna de azulejos + la leyenda no dejan lugar al municipio.
const ANCHO_COMPACTO = 900

interface TarjetaDef {
  icon: React.ComponentType<{ size?: number; strokeWidth?: number; color?: string }>
  color: string
  label: string
  value: number
  sublabel: string
  ruta: string
}

// Chip del modo compacto: icono + número, tinte y borde superior del color de
// la tarjeta; el nombre completo va en el tooltip (y en aria-label).
function MiniCard({ icon: Icon, color, label, value, sublabel, cargando, onClick }: TarjetaDef & {
  cargando: boolean
  onClick: () => void
}) {
  const detalle = cargando ? `${label}: cargando…` : `${label}: ${value} (${sublabel})`
  return (
    <button
      type="button"
      onClick={onClick}
      title={detalle}
      aria-label={detalle}
      style={{
        ...miniCardStyle,
        backgroundImage: `linear-gradient(${tinte(color, 0.16)}, ${tinte(color, 0.16)})`,
        borderTop: `3px solid ${color}`,
      }}
    >
      <Icon size={14} strokeWidth={1.8} color={color} />
      <span style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--fg-1)', lineHeight: 1 }}>{value}</span>
    </button>
  )
}

function StatCard({ icon: Icon, color, label, value, sublabel, onClick }: {
  icon: React.ComponentType<{ size?: number; strokeWidth?: number; color?: string }>
  color: string
  label: string
  value: number
  sublabel?: string
  onClick?: () => void
}) {
  return (
    <div
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      style={{
        ...cardStyle,
        // Tinte del color del icono sobre la superficie translucida del panel.
        backgroundImage: `linear-gradient(${tinte(color, 0.16)}, ${tinte(color, 0.16)})`,
        borderTop: `3px solid ${color}`,
        cursor: onClick ? 'pointer' : 'default',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 6 }}>
        <span style={{ fontSize: '0.62rem', color: 'var(--fg-2)', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 600, lineHeight: 1.25 }}>
          {label}
        </span>
        <Icon size={16} strokeWidth={1.8} color={color} />
      </div>
      <div style={{ fontSize: '1.7rem', fontWeight: 600, color: 'var(--fg-1)', lineHeight: 1 }}>
        {value}
      </div>
      {sublabel && (
        <div style={{ fontSize: '0.6rem', color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', lineHeight: 1.3 }}>
          {sublabel}
        </div>
      )}
    </div>
  )
}

function LayerToggle({ activo, onClick, label, shape }: {
  activo: boolean
  onClick: () => void
  label: string
  shape: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={activo ? `Ocultar ${label.toLowerCase()} del mapa` : `Mostrar ${label.toLowerCase()} en el mapa`}
      style={{
        display: 'flex', alignItems: 'center', gap: 6,
        background: 'transparent', border: 'none', padding: 0,
        cursor: 'pointer', opacity: activo ? 1 : 0.35,
      }}
    >
      {shape}
      <span style={{ fontSize: '0.74rem', color: 'var(--fg-2)', fontFamily: 'var(--font-display)', textDecoration: activo ? 'none' : 'line-through' }}>
        {label}
      </span>
    </button>
  )
}

// Mini version del marker del mapa (mismo dibujo: contorno = tipo, centro =
// estado), un poco mas grande que el punto real para que se lea en la leyenda.
function MarkerSwatch({ contorno, centro }: { contorno: string; centro: string }) {
  return (
    <span style={{
      width: 14, height: 14, borderRadius: '50%', boxSizing: 'border-box',
      background: centro, border: `3px solid ${contorno}`,
      boxShadow: '0 0 0 1.5px rgba(255,255,255,0.95), 0 1px 3px rgba(0,0,0,0.3)',
      display: 'inline-block', flexShrink: 0,
    }} />
  )
}

// Muestra de la mascara del mapa: alrededor sombreado (--zaris-orange al 18%,
// como en el mapa) y el municipio limpio con su borde.
const limiteSwatchStyle: React.CSSProperties = {
  width: 18, height: 14, borderRadius: 3, flexShrink: 0,
  background: 'rgba(245, 78, 0, 0.3)',
  boxShadow: 'inset 0 0 0 3px rgba(245, 78, 0, 0.3), inset 0 0 0 5px var(--zaris-orange), inset 0 0 0 9px var(--surface-100)',
  boxSizing: 'border-box',
}

const pageStyle: React.CSSProperties = {
  position: 'relative',
  width: '100%',
  // El AppShell embebido pone el contenido en un main; le damos altura completa
  // restando el sidebar. height: 'calc(100vh - X)' no funciona porque el iframe
  // no tiene chrome propio. Usamos 100vh full y dejamos que overflow corte.
  height: 'calc(100vh - 32px)',
  minHeight: 540,
  overflow: 'hidden',
}

const statsLayerStyle: React.CSSProperties = {
  position: 'absolute',
  top: 16,
  left: 16,
  zIndex: 500,                       // sobre el overlay gris y los markers
  display: 'flex',
  flexDirection: 'column',
  gap: 12,
  // Ancho para que el titulo del municipio y la leyenda de capas convivan en
  // la misma fila (pedido 2026-07-02); en pantallas angostas la fila hace wrap.
  maxWidth: 'min(880px, calc(100% - 32px))',
  maxHeight: 'calc(100% - 32px)',
  overflowY: 'auto',
  // Bug 2026-08-31 (César): arrastrar el mapa arrancando sobre el panel
  // seleccionaba el texto de TODAS las tarjetas (selección nativa del browser)
  // y no paneaba. El panel no captura eventos (los huecos entre tarjetas
  // panean el mapa); cada caja interactiva los re-habilita con
  // pointerEvents: 'auto'. userSelect corta la selección en las cajas mismas.
  pointerEvents: 'none',
  userSelect: 'none',
  WebkitUserSelect: 'none',
}

const headerStyle: React.CSSProperties = {
  background: 'var(--surface-overlay)',  // claro u oscuro segun data-theme
  backdropFilter: 'blur(8px)',
  WebkitBackdropFilter: 'blur(8px)',
  border: '1px solid var(--border-primary)',
  borderRadius: 12,
  padding: '12px 16px',
  boxShadow: '0 4px 20px rgba(38,37,30,0.08)',
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'center',
  // No mas ancho que la grilla de azulejos: si el titulo + logo crecen, el
  // texto envuelve. Sino el header empuja a la leyenda debajo (flexWrap).
  maxWidth: TILE * 3 + 20,
  boxSizing: 'border-box',
  pointerEvents: 'auto', // re-habilita eventos dentro del statsLayer (ver ahi)
}

const titleStyle: React.CSSProperties = {
  fontSize: '1.25rem', fontWeight: 600, letterSpacing: '-0.4px',
  color: 'var(--fg-1)', margin: 0, lineHeight: 1.15,
  fontFamily: 'var(--font-display)',
}

const subtitleStyle: React.CSSProperties = {
  fontSize: '0.8rem', color: 'var(--fg-3)', margin: '4px 0 0',
}

const cardsGridStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: `repeat(3, ${TILE}px)`,
  gap: 10,
}

const cardStyle: React.CSSProperties = {
  background: 'var(--surface-overlay)',
  backdropFilter: 'blur(8px)',
  WebkitBackdropFilter: 'blur(8px)',
  border: '1px solid var(--border-primary)',
  borderRadius: 12,
  padding: '8px 10px',
  boxShadow: '0 4px 20px rgba(38,37,30,0.08)',
  // Azulejo cuadrado: contenido distribuido verticalmente (label / valor / sub).
  width: TILE,
  height: TILE,
  boxSizing: 'border-box',
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'space-between',
  pointerEvents: 'auto', // el azulejo es clickeable (ver statsLayerStyle)
}

const compactoStyle: React.CSSProperties = {
  background: 'var(--surface-overlay)',
  backdropFilter: 'blur(8px)',
  WebkitBackdropFilter: 'blur(8px)',
  border: '1px solid var(--border-primary)',
  borderRadius: 12,
  padding: '8px 10px',
  boxShadow: '0 4px 20px rgba(38,37,30,0.08)',
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
  pointerEvents: 'auto', // ver statsLayerStyle
}

const chipsRowStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(6, minmax(0, 1fr))',
  gap: 6,
}

const miniCardStyle: React.CSSProperties = {
  background: 'var(--surface-overlay)',
  border: '1px solid var(--border-primary)',
  borderRadius: 8,
  padding: '5px 4px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 5,
  minWidth: 0,
  cursor: 'pointer',
  fontFamily: 'var(--font-display)',
}

const capasBtnStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 4,
  flexShrink: 0,
  background: 'var(--surface-100)',
  border: '1px solid var(--border-medium)',
  borderRadius: 999,
  padding: '3px 10px',
  fontSize: '0.74rem',
  fontFamily: 'var(--font-display)',
  color: 'var(--fg-2)',
  cursor: 'pointer',
}

const legendStyle: React.CSSProperties = {
  background: 'var(--surface-overlay)',
  backdropFilter: 'blur(8px)',
  WebkitBackdropFilter: 'blur(8px)',
  border: '1px solid var(--border-primary)',
  borderRadius: 10,
  padding: '8px 12px',
  boxShadow: '0 4px 20px rgba(38,37,30,0.08)',
  pointerEvents: 'auto', // los toggles de capa son clickeables (ver statsLayerStyle)
}

const legendTitle: React.CSSProperties = {
  fontSize: '0.68rem', color: 'var(--fg-3)',
  textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600,
  marginBottom: 6,
}

const legendRowStyle: React.CSSProperties = {
  display: 'flex', gap: 14, flexWrap: 'wrap',
}
