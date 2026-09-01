import { useEffect, useRef, useState } from 'react'
import { FiltrosGlobales } from '../components/FiltrosGlobales'
import { useCatalogoAreas, useMiArea } from '../hooks/useBi'
import { ResumenSection } from '../sections/ResumenSection'
import { RespuestaSection } from '../sections/RespuestaSection'
import { PendientesSection } from '../sections/PendientesSection'
import { SubreclamosSection } from '../sections/SubreclamosSection'
import type { BiFiltros } from '../lib/types'
import { periodoEjecutivoDefault } from '../lib/periodo'
import { useAuthStore } from '../../../stores/auth'

// Página ÚNICA del Operativo (2026-08-30, reemplaza los 4 tabs). Decisiones de César:
//  - una sola hoja que se recorre verticalmente: Resumen → Respuesta → Pendientes
//    (+ Subreclamos al pie), con índice fijo arriba;
//  - filtros GLOBALES que gobiernan todas las visualizaciones y las exportaciones;
//  - el ÁREA DE SERVICIO es el selector principal, con una por defecto: para un
//    Supervisor la de su agente (regla §3); el Administrador arranca en "Todas
//    las áreas" (César 2026-09-01, mismo default que el Ejecutivo);
//  - preseleccionado de período (César 2026-09-01, igual al Ejecutivo): año en
//    curso + mes anterior tildado; "Limpiar" vuelve a ese default completo;
//  - sin tablas de detalle: cada sección exporta los tickets filtrados;
//  - al saltar desde el índice la sección queda debajo de la barra y la barra
//    muestra SIEMPRE en qué sección se está (scroll-spy por posición);
//  - el panel de filtros se puede contraer.
const SECCIONES = [
  { id: 'resumen', label: 'Resumen', desc: 'Volumen y composición de los reclamos del período' },
  { id: 'respuesta', label: 'Respuesta', desc: 'Reclamos cerrados y tiempos de respuesta' },
  { id: 'pendientes', label: 'Pendientes', desc: 'Reclamos abiertos, demora y ubicación' },
  { id: 'subreclamos', label: 'Subreclamos', desc: 'Intervenciones derivadas de un reclamo padre' },
] as const
type SeccionId = (typeof SECCIONES)[number]['id']

const AREA_KEY = 'zaris_bi_area'
const FILTROS_KEY = 'zaris_bi_filtros_colapsados'

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
  // Barra fija: alto real (para el scroll-margin de las secciones) + sección activa.
  const stickyRef = useRef<HTMLDivElement>(null)
  const [stickyH, setStickyH] = useState(200)
  const [activa, setActiva] = useState<SeccionId>('resumen')
  const lockHastaRef = useRef(0) // ms: mientras dura el scroll suave del índice, el spy no pisa la elección
  const calcularRef = useRef<() => void>(() => {})
  const [colapsado, setColapsado] = useState<boolean>(() => {
    try { return localStorage.getItem(FILTROS_KEY) === '1' } catch { return false }
  })

  // Defaults del tablero (César 2026-09-01, mismo tratamiento que el Ejecutivo):
  // SIEMPRE arranca con el año en curso + mes anterior tildado, y el admin con
  // "Todas las áreas" (el área guardada en localStorage NO se restaura al boot).
  // El supervisor (sin "Todas" permitida) arranca con la de su agente; se
  // descarta cualquier candidata fuera del catálogo de áreas activas.
  useEffect(() => {
    if (filtros !== null || miArea.isLoading || areas.isLoading) return
    const catalogo = areas.data ?? []
    const valida = (id?: number | null) => (id != null && catalogo.some((a) => a.id_area === id) ? id : undefined)
    const inicial = esAdmin
      ? undefined // Todas las áreas
      : (valida(miArea.data?.id_area) ?? valida(leerAreaGuardada()) ?? catalogo[0]?.id_area)
    setAreaInicial(inicial)
    setFiltros({ id_area: inicial, ...periodoEjecutivoDefault() })
  }, [filtros, miArea.isLoading, areas.isLoading, miArea.data, areas.data, esAdmin])
  const areaDefault = areaInicial

  useEffect(() => {
    if (!filtros) return
    try {
      if (filtros.id_area) localStorage.setItem(AREA_KEY, String(filtros.id_area))
      else localStorage.removeItem(AREA_KEY)
    } catch { /* sin persistencia: no pasa nada */ }
  }, [filtros])

  useEffect(() => {
    try { localStorage.setItem(FILTROS_KEY, colapsado ? '1' : '0') } catch { /* nada */ }
  }, [colapsado])

  // Alto real de la barra fija → CSS var que usan las secciones como scroll-margin.
  useEffect(() => {
    const el = stickyRef.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(() => setStickyH(el.offsetHeight))
    ro.observe(el)
    setStickyH(el.offsetHeight)
    return () => ro.disconnect()
  }, [filtros, colapsado])

  // Scroll-spy por POSICIÓN: la sección activa es la ÚLTIMA cuyo encabezado ya
  // pasó por debajo de la barra fija (IntersectionObserver marcaba la anterior
  // porque las secciones son más altas que el viewport). Escucha en captura:
  // el contenedor que scrollea es el documento del iframe en prod o <main> en dev.
  useEffect(() => {
    if (!filtros) return
    let raf = 0
    let timer: number | undefined
    const calcular = () => {
      raf = 0
      if (Date.now() < lockHastaRef.current) return
      // Borde inferior REAL de la barra en coordenadas del viewport (en dev la
      // barra arranca debajo del topbar del AppShell; en prod, en 0). Las secciones
      // aterrizan a scroll-margin = alto + 10 de ese borde, así que el umbral va
      // un poco más abajo (+24) para que la recién saltada cuente como activa.
      const rect = stickyRef.current?.getBoundingClientRect()
      const limite = (rect ? rect.bottom : stickyH) + 24
      let actual: SeccionId = SECCIONES[0].id
      for (const s of SECCIONES) {
        const el = document.getElementById(s.id)
        if (el && el.getBoundingClientRect().top <= limite) actual = s.id
      }
      setActiva((prev) => (prev === actual ? prev : actual))
    }
    calcularRef.current = calcular
    // rAF coalesce + trailing debounce: el último evento de un scroll suave puede
    // caer mientras hay un rAF pendiente (se descartaría) → el timer garantiza
    // una evaluación con la posición FINAL.
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(calcular)
      window.clearTimeout(timer)
      timer = window.setTimeout(calcular, 120)
    }
    window.addEventListener('scroll', onScroll, true)
    window.addEventListener('resize', onScroll)
    calcular()
    return () => {
      window.removeEventListener('scroll', onScroll, true)
      window.removeEventListener('resize', onScroll)
      if (raf) cancelAnimationFrame(raf)
      window.clearTimeout(timer)
    }
  }, [filtros, stickyH])

  const irA = (id: SeccionId) => {
    setActiva(id)
    lockHastaRef.current = Date.now() + 900 // el scroll suave tarda < 1s
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    // Al vencer el lock, re-evaluar con la posición final (no depende de que
    // llegue otro evento de scroll).
    window.setTimeout(() => calcularRef.current(), 1000)
  }

  // Compat con las rutas viejas por tab (/bi/operativo/pendientes → ancla).
  useEffect(() => {
    if (!seccion || !filtros) return
    const t = setTimeout(() => irA(seccion as SeccionId), 300)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seccion, filtros === null])

  const nombreArea = filtros?.id_area
    ? (areas.data ?? []).find((a) => a.id_area === filtros.id_area)?.nombre
    : 'Todas las áreas'

  if (!filtros) {
    return <div style={{ color: 'var(--fg-3)', fontSize: '0.86rem', padding: 24, textAlign: 'center' }}>Cargando tablero…</div>
  }

  const secActiva = SECCIONES.find((s) => s.id === activa) ?? SECCIONES[0]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 48, ['--bi-sticky' as string]: `${stickyH}px` } as React.CSSProperties}>
      {/* Barra fija: índice de secciones + filtros globales + sección activa.
          z-index por encima de los panes/controles de Leaflet (400/1000) para
          que el mapa de Pendientes no la tape al scrollear. */}
      <div ref={stickyRef} style={stickyStyle}>
        {/* El scroller embebido (main.embeddedContent) tiene padding-top: la barra
            sticky se pega al borde del CONTENIDO y en esa franja superior se ve
            pasar la página (César 2026-09-01). Este cover la tapa; el overflow
            del main lo recorta en el borde del scrollport, así que no pisa nada. */}
        <div aria-hidden="true" style={coverStyle} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 8 }}>
          <nav aria-label="Secciones del tablero" style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {SECCIONES.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => irA(s.id)}
                aria-current={activa === s.id ? 'true' : undefined}
                style={indiceBtnStyle(activa === s.id)}
              >
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
          colapsado={colapsado}
          onColapsar={setColapsado}
        />
        {/* Título de la sección que se está viendo (pedido de César) */}
        <div style={seccionActivaStyle} aria-live="polite">
          <span style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--fg-3)', fontWeight: 600 }}>Sección</span>
          <span style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--fg-1)' }}>{secActiva.label}</span>
          <span style={{ fontSize: '0.8rem', color: 'var(--fg-3)' }}>— {secActiva.desc}</span>
        </div>
      </div>

      <ResumenSection filtros={filtros} />
      <RespuestaSection filtros={filtros} />
      <PendientesSection filtros={filtros} />
      <SubreclamosSection filtros={filtros} />
    </div>
  )
}

const stickyStyle: React.CSSProperties = {
  position: 'sticky', top: 0, zIndex: 1100,
  background: 'var(--zaris-cream)',
  padding: '8px 0 0',
  borderBottom: '1px solid var(--border-primary)',
}
// Tapa el padding-top del scroll container por encima de la barra pegada (hasta 24px).
const coverStyle: React.CSSProperties = {
  position: 'absolute', top: -24, left: 0, right: 0, height: 24,
  background: 'var(--zaris-cream)',
}
const seccionActivaStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap',
  fontFamily: 'var(--font-display)', padding: '8px 2px 8px',
}
function indiceBtnStyle(active: boolean): React.CSSProperties {
  return {
    fontFamily: 'var(--font-display)', fontSize: '0.84rem', fontWeight: 600,
    padding: '6px 12px', borderRadius: 8,
    border: `1px solid ${active ? 'var(--zaris-orange)' : 'transparent'}`,
    background: active ? 'var(--zaris-orange)' : 'transparent',
    color: active ? '#fff' : 'var(--zaris-orange)', cursor: 'pointer',
  }
}
