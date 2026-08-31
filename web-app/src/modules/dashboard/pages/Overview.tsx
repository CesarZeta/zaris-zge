import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Building2, CalendarCheck, FileText, FolderOpen, Siren, Ticket,
} from 'lucide-react'
import { useDashboardResumen, useIdentidadMunicipio } from '../hooks/useDashboardData'
import { CAPA_COLOR, DashboardMap, type CapasVisibles } from '../components/DashboardMap'

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

  const tarjetas = resumenQ.data?.tarjetas
  const geo = resumenQ.data?.geo
  const cargando = resumenQ.isLoading

  function toggleCapa(k: keyof CapasVisibles) {
    setCapas((c) => ({ ...c, [k]: !c[k] }))
  }

  return (
    <div style={pageStyle}>
      {/* Mapa de fondo ocupa todo. */}
      <DashboardMap
        emergencias={geo?.emergencias ?? []}
        reclamos={geo?.reclamos ?? []}
        espacios={geo?.espacios ?? []}
        tramites={geo?.tramites ?? []}
        visibles={capas}
        onEmergenciaClick={(e) => navigate(`/emergencias/evento/${e.id_emergencia_evento}`)}
        onReclamoClick={(r) => navigate(`/reclamos/${r.id_reclamo}`)}
        onTramiteClick={(t) => navigate(`/tramites/${t.numero_expediente}`)}
      />

      {/* Panel flotante arriba-izquierda. */}
      <div style={statsLayerStyle}>
        {/* Columna izquierda (titulo compacto + azulejos debajo) y leyenda de
            capas al costado derecho del titulo (pedido 2026-07-02). */}
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, flex: '0 0 auto' }}>
          <div style={headerStyle}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              {identidadQ.data?.municipio_logo_url ? (
                <img
                  src={resolverLogoUrl(identidadQ.data.municipio_logo_url)}
                  alt=""
                  onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
                  style={{ height: 32, width: 'auto', maxWidth: 72, objectFit: 'contain' }}
                />
              ) : null}
              <h1 style={titleStyle}>{identidadQ.data?.municipio_nombre ?? ''}</h1>
            </div>
            <p style={subtitleStyle}>Resumen de actividad municipal</p>
          </div>

          <div style={cardsGridStyle}>
            <StatCard
              icon={Siren}
              color={TARJETA_COLOR.emergencias}
              label="Emergencias activas"
              value={tarjetas?.emergencias_activas ?? 0}
              sublabel={cargando ? 'cargando…' : 'sin cerrar en el COM'}
              onClick={() => navigate('/emergencias')}
            />
            <StatCard
              icon={FileText}
              color={TARJETA_COLOR.reclamos}
              label="Reclamos activos"
              value={tarjetas?.reclamos_activos ?? 0}
              sublabel={cargando ? 'cargando…' : `${geo?.reclamos.length ?? 0} con geo`}
              onClick={() => navigate('/reclamos')}
            />
            <StatCard
              icon={Building2}
              color={TARJETA_COLOR.espacios}
              label="Espacios de atención"
              value={tarjetas?.espacios_disponibles ?? 0}
              sublabel={cargando ? 'cargando…' : 'disponibles'}
              onClick={() => navigate('/agenda')}
            />
            <StatCard
              icon={CalendarCheck}
              color={TARJETA_COLOR.turnos}
              label="Turnos otorgados"
              value={tarjetas?.turnos_otorgados ?? 0}
              sublabel={cargando ? 'cargando…' : 'de hoy en adelante'}
              onClick={() => navigate('/turnos')}
            />
            <StatCard
              icon={Ticket}
              color={TARJETA_COLOR.entradas}
              label="Entradas emitidas"
              value={tarjetas?.entradas_emitidas ?? 0}
              sublabel={cargando ? 'cargando…' : 'eventos vigentes'}
              onClick={() => navigate('/entradas')}
            />
            <StatCard
              icon={FolderOpen}
              color={TARJETA_COLOR.tramites}
              label="Trámites abiertos"
              value={tarjetas?.tramites_abiertos ?? 0}
              sublabel={cargando ? 'cargando…' : 'en circuito'}
              onClick={() => navigate('/tramites')}
            />
          </div>
          </div>

          {/* Leyenda con toggle por capa. */}
          <div style={{ ...legendStyle, flex: '1 1 240px', minWidth: 240 }}>
            <div style={legendTitle}>Capas del mapa</div>
            <div style={legendRowStyle}>
              <LayerToggle
                activo={capas.emergencias}
                onClick={() => toggleCapa('emergencias')}
                label="Emergencias"
                shape={<IconBadge color={CAPA_COLOR.emergencia} icon={Siren} />}
              />
              <LayerToggle
                activo={capas.reclamos}
                onClick={() => toggleCapa('reclamos')}
                label="Reclamos"
                shape={<IconBadge color="#1f8a65" icon={FileText} />}
              />
              <LayerToggle
                activo={capas.espacios}
                onClick={() => toggleCapa('espacios')}
                label="Espacios"
                shape={<IconBadge color={CAPA_COLOR.espacio} icon={Building2} />}
              />
              <LayerToggle
                activo={capas.tramites}
                onClick={() => toggleCapa('tramites')}
                label="Trámites"
                shape={<IconBadge color={CAPA_COLOR.tramite} icon={FolderOpen} />}
              />
            </div>
            {capas.reclamos && (
              <>
                <div style={{ ...legendTitle, marginTop: 8 }}>Estados de reclamos</div>
                <div style={legendRowStyle}>
                  <LegendDot color="#c62828" label="Sin asignar" />
                  <LegendDot color="#1f8a65" label="En gestión" />
                  <LegendDot color="#f57f17" label="En espera" />
                  <LegendDot color="#6a1b9a" label="En auditoría" />
                </div>
              </>
            )}
          </div>
        </div>
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
  reclamos:    '#1f8a65', // verde --color-success (reclamos "En gestión")
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

// Mini version del marker del mapa: badge circular de color con el mismo
// icono Lucide de la tarjeta correspondiente.
function IconBadge({ color, icon: Icon }: {
  color: string
  icon: React.ComponentType<{ size?: number; strokeWidth?: number; color?: string }>
}) {
  return (
    <span style={{
      width: 18, height: 18, borderRadius: '50%',
      background: color, border: '2px solid white',
      boxShadow: '0 1px 3px rgba(0,0,0,0.25)',
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      flexShrink: 0,
    }}>
      <Icon size={10} strokeWidth={2} color="white" />
    </span>
  )
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{
        width: 12, height: 12, borderRadius: '50%',
        background: color, border: '2px solid white',
        boxShadow: '0 1px 3px rgba(0,0,0,0.25)',
        display: 'inline-block',
      }} />
      <span style={{ fontSize: '0.74rem', color: 'var(--fg-2)' }}>{label}</span>
    </div>
  )
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
