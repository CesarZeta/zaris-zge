import { useEffect, useRef, useState } from 'react'
import { FiltrosEjecutivo } from '../components/FiltrosEjecutivo'
import { useCatalogoAreas, useEjCatalogoLocalidades, useEjCatalogoSubareas, useMiArea } from '../hooks/useBi'
import { ResumenEjSection } from '../sections/ResumenEjSection'
import { EvolucionEjSection } from '../sections/EvolucionEjSection'
import { HistoricoEjSection } from '../sections/HistoricoEjSection'
import { MayoresEjSection } from '../sections/MayoresEjSection'
import { SatisfaccionEjSection } from '../sections/SatisfaccionEjSection'
import type { BiFiltros } from '../lib/types'
import { periodoEjecutivoDefault } from '../lib/periodo'
import { useAuthStore } from '../../../stores/auth'

// Tablero EJECUTIVO — "Análisis de demanda ciudadana" (2026-08-30). Decisiones
// de César sobre las capturas Power BI de VL:
//  - misma página única del Operativo: índice fijo + scroll-spy + filtros arriba;
//  - filtros = PERÍODO + ÁREA (+ localidad); el desglose es por SUBÁREA
//    (las "áreas de servicio" de VL son nuestras subáreas);
//  - 5 secciones espejando las 5 pantallas de referencia.
const SECCIONES = [
  { id: 'resumen', label: 'Resumen', desc: 'Score del período y matriz por subárea y tipo' },
  { id: 'evolucion', label: 'Evolución', desc: 'Altas vs cierres e indicadores mensuales' },
  { id: 'historico', label: 'Histórico', desc: 'Series por subárea, canal y localidad' },
  { id: 'mayores', label: 'Mayores', desc: 'Top de incidentes por cantidad y demora' },
  { id: 'satisfaccion', label: 'Satisfacción', desc: 'Satisfacción vs cierre y mapas' },
] as const
type SeccionId = (typeof SECCIONES)[number]['id']

const AREA_KEY = 'zaris_bi_ej_area'
const FILTROS_KEY = 'zaris_bi_ej_filtros_colapsados'

function leerAreaGuardada(): number | undefined {
  try {
    const v = localStorage.getItem(AREA_KEY)
    return v ? Number(v) : undefined
  } catch {
    return undefined
  }
}

export function EjecutivoPage() {
  const nivel = useAuthStore((s) => s.user?.nivel_acceso ?? 99)
  const esAdmin = nivel === 1
  const areas = useCatalogoAreas()
  const miArea = useMiArea()
  const localidades = useEjCatalogoLocalidades()
  const [filtros, setFiltros] = useState<BiFiltros | null>(null)
  const subareas = useEjCatalogoSubareas(filtros?.id_area)
  const [areaInicial, setAreaInicial] = useState<number | undefined>(undefined)
  const stickyRef = useRef<HTMLDivElement>(null)
  const [stickyH, setStickyH] = useState(200)
  const [activa, setActiva] = useState<SeccionId>('resumen')
  const lockHastaRef = useRef(0)
  const calcularRef = useRef<() => void>(() => {})
  const [colapsado, setColapsado] = useState<boolean>(() => {
    try { return localStorage.getItem(FILTROS_KEY) === '1' } catch { return false }
  })

  // Defaults del Ejecutivo (César 2026-08-31): SIEMPRE arranca con el año en
  // curso + mes anterior tildado, y con "Todas las áreas" (admin). El área
  // guardada en localStorage NO se restaura al boot (el "siempre" manda); para
  // el supervisor (sin "Todas" permitida) queda la de su agente.
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

  // Alto real de la barra fija → scroll-margin de las secciones.
  useEffect(() => {
    const el = stickyRef.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(() => setStickyH(el.offsetHeight))
    ro.observe(el)
    setStickyH(el.offsetHeight)
    return () => ro.disconnect()
  }, [filtros, colapsado])

  // Scroll-spy por POSICIÓN (mismo mecanismo que OperativoPage: borde real de la
  // barra + rAF + debounce de cola + lock durante el salto del índice).
  useEffect(() => {
    if (!filtros) return
    let raf = 0
    let timer: number | undefined
    const calcular = () => {
      raf = 0
      if (Date.now() < lockHastaRef.current) return
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
    lockHastaRef.current = Date.now() + 900
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    window.setTimeout(() => calcularRef.current(), 1000)
  }

  const nombreArea = filtros?.id_area
    ? (areas.data ?? []).find((a) => a.id_area === filtros.id_area)?.nombre
    : 'Todas las áreas'

  if (!filtros) {
    return <div style={{ color: 'var(--fg-3)', fontSize: '0.86rem', padding: 24, textAlign: 'center' }}>Cargando tablero…</div>
  }

  const secActiva = SECCIONES.find((s) => s.id === activa) ?? SECCIONES[0]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 48, ['--bi-sticky' as string]: `${stickyH}px` } as React.CSSProperties}>
      <div ref={stickyRef} style={stickyStyle}>
        {/* Cover de la franja del padding-top del scroller embebido (ver OperativoPage). */}
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
        <FiltrosEjecutivo
          filtros={filtros}
          onChange={setFiltros}
          areas={areas.data ?? []}
          subareas={subareas.data ?? []}
          localidades={localidades.data ?? []}
          areaDefault={areaDefault}
          permiteTodas={esAdmin}
          colapsado={colapsado}
          onColapsar={setColapsado}
        />
        <div style={seccionActivaStyle} aria-live="polite">
          <span style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--fg-3)', fontWeight: 600 }}>Sección</span>
          <span style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--fg-1)' }}>{secActiva.label}</span>
          <span style={{ fontSize: '0.8rem', color: 'var(--fg-3)' }}>— {secActiva.desc}</span>
        </div>
      </div>

      <ResumenEjSection filtros={filtros} />
      <EvolucionEjSection filtros={filtros} />
      <HistoricoEjSection filtros={filtros} />
      <MayoresEjSection filtros={filtros} />
      <SatisfaccionEjSection filtros={filtros} />
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
