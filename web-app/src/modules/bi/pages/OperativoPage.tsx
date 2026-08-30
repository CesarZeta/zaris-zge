import { useEffect, useState } from 'react'
import { FiltrosGlobales } from '../components/FiltrosGlobales'
import { useCatalogoAreas, useMiArea } from '../hooks/useBi'
import { ResumenSection } from '../sections/ResumenSection'
import { RespuestaSection } from '../sections/RespuestaSection'
import { PendientesSection } from '../sections/PendientesSection'
import { SubreclamosSection } from '../sections/SubreclamosSection'
import type { BiFiltros } from '../lib/types'
import { useAuthStore } from '../../../stores/auth'

// Página ÚNICA del Operativo (2026-08-30, reemplaza los 4 tabs). Decisiones de César:
//  - una sola hoja que se recorre verticalmente: Resumen → Respuesta → Pendientes
//    (+ Subreclamos al pie), con índice fijo arriba;
//  - filtros GLOBALES que gobiernan todas las visualizaciones y las exportaciones;
//  - el ÁREA DE SERVICIO es el selector principal, con una por defecto: para un
//    Supervisor la de su agente (regla §3); para un Administrador la última usada
//    (localStorage) o la sugerida por el backend; "Todas las áreas" solo admin;
//  - sin tablas de detalle: cada sección exporta los tickets filtrados.
const SECCIONES = [
  { id: 'resumen', label: 'Resumen' },
  { id: 'respuesta', label: 'Respuesta' },
  { id: 'pendientes', label: 'Pendientes' },
  { id: 'subreclamos', label: 'Subreclamos' },
] as const

const AREA_KEY = 'zaris_bi_area'

function leerAreaGuardada(): number | undefined {
  try {
    const v = localStorage.getItem(AREA_KEY)
    return v ? Number(v) : undefined
  } catch {
    return undefined
  }
}

export function OperativoPage({ seccion }: { seccion?: string }) {
  const nivel = useAuthStore((s) => s.user?.nivel_acceso ?? 99)
  const esAdmin = nivel === 1
  const areas = useCatalogoAreas()
  const miArea = useMiArea()
  const [filtros, setFiltros] = useState<BiFiltros | null>(null)
  // Área con la que arrancó la visita: es a la que vuelve "Limpiar". Se fija UNA
  // vez (no sigue a la selección: sino "Limpiar" restauraría la última elegida).
  const [areaInicial, setAreaInicial] = useState<number | undefined>(undefined)

  // Área por defecto (una sola vez, cuando catálogo y backend contestaron).
  // Candidatas en orden; se descarta cualquiera que no esté en el catálogo de
  // áreas activas (ej. agente vinculado a un área dada de baja). Si ninguna
  // sirve: el admin cae a "Todas", el supervisor a la primera del catálogo.
  useEffect(() => {
    if (filtros !== null || miArea.isLoading || areas.isLoading) return
    const catalogo = areas.data ?? []
    const valida = (id?: number | null) => (id != null && catalogo.some((a) => a.id_area === id) ? id : undefined)
    const inicial = esAdmin
      ? (valida(leerAreaGuardada()) ?? valida(miArea.data?.id_area) ?? undefined)
      : (valida(miArea.data?.id_area) ?? valida(leerAreaGuardada()) ?? catalogo[0]?.id_area)
    setAreaInicial(inicial)
    setFiltros({ id_area: inicial })
  }, [filtros, miArea.isLoading, areas.isLoading, miArea.data, areas.data, esAdmin])
  const areaDefault = areaInicial

  useEffect(() => {
    if (!filtros) return
    try {
      if (filtros.id_area) localStorage.setItem(AREA_KEY, String(filtros.id_area))
      else localStorage.removeItem(AREA_KEY)
    } catch { /* sin persistencia: no pasa nada */ }
  }, [filtros])

  // Compat con las rutas viejas por tab (/bi/operativo/pendientes → ancla).
  useEffect(() => {
    if (!seccion || !filtros) return
    const t = setTimeout(() => irA(seccion), 250)
    return () => clearTimeout(t)
  }, [seccion, filtros])

  const nombreArea = filtros?.id_area
    ? (areas.data ?? []).find((a) => a.id_area === filtros.id_area)?.nombre
    : 'Todas las áreas'

  if (!filtros) {
    return <div style={{ color: 'var(--fg-3)', fontSize: '0.86rem', padding: 24, textAlign: 'center' }}>Cargando tablero…</div>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 28 }}>
      {/* Barra fija: índice de secciones + filtros globales */}
      <div style={stickyStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 8 }}>
          <nav aria-label="Secciones del tablero" style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {SECCIONES.map((s) => (
              <button key={s.id} type="button" onClick={() => irA(s.id)} style={indiceBtnStyle}>
                {s.label}
              </button>
            ))}
          </nav>
          <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-display)', fontSize: '0.78rem', color: 'var(--fg-2)' }}>
            Área: <strong style={{ color: 'var(--fg-1)' }}>{nombreArea ?? '—'}</strong>
            {miArea.data?.origen === 'agente' && filtros.id_area === miArea.data.id_area && (
              <span style={{ color: 'var(--fg-3)' }}> · tu área</span>
            )}
          </span>
        </div>
        <FiltrosGlobales
          filtros={filtros}
          onChange={setFiltros}
          areas={areas.data ?? []}
          areaDefault={areaDefault}
          permiteTodas={esAdmin}
        />
      </div>

      <ResumenSection filtros={filtros} />
      <RespuestaSection filtros={filtros} />
      <PendientesSection filtros={filtros} />
      <SubreclamosSection filtros={filtros} />
    </div>
  )
}

function irA(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const stickyStyle: React.CSSProperties = {
  position: 'sticky', top: 0, zIndex: 30,
  background: 'var(--zaris-cream)',
  padding: '8px 0 10px',
  borderBottom: '1px solid var(--border-primary)',
}
const indiceBtnStyle: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.84rem', fontWeight: 600,
  padding: '6px 12px', borderRadius: 8, border: '1px solid transparent',
  background: 'transparent', color: 'var(--zaris-orange)', cursor: 'pointer',
}
