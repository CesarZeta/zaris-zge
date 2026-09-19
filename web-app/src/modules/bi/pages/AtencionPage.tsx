import { useEffect, useRef, useState } from 'react'
import { FiltrosAtencion } from '../components/FiltrosAtencion'
import { useAtCatalogoGestiones, useAtCatalogoPrestaciones, useAtCatalogoUbicaciones, useMiArea } from '../hooks/useBi'
import { ResumenAtSection } from '../sections/ResumenAtSection'
import { EvolucionAtSection } from '../sections/EvolucionAtSection'
import { UbicacionesAtSection } from '../sections/UbicacionesAtSection'
import { EsperaAtSection } from '../sections/EsperaAtSection'
import { GuardiaAtSection } from '../sections/GuardiaAtSection'
import { EventosAtSection } from '../sections/EventosAtSection'
import type { BiFiltros } from '../lib/types'
import { periodoEjecutivoDefault } from '../lib/periodo'
import { useAuthStore } from '../../../stores/auth'

// Tablero de ATENCIÓN — "BI de atención por gestión" (proyecto ATENCIÓN F6,
// 2026-09-19). Misma página única del Ejecutivo (índice fijo + scroll-spy +
// filtros arriba); filtros = PERÍODO + GESTIÓN (área) + UBICACIÓN + PRESTACIÓN.
// Seis secciones: turnos del período, evolución, ubicaciones y agentes, espera
// real y llamados (colero F3), Guardia (F4) y eventos con reservas (Cultura).
const SECCIONES = [
  { id: 'resumen', label: 'Resumen', desc: 'Turnos del período, matriz por ubicación y composición' },
  { id: 'evolucion', label: 'Evolución', desc: 'Turnos por mes y día e indicadores mensuales' },
  { id: 'ubicaciones', label: 'Ubicaciones', desc: 'Ocupación por ubicación y atención por agente' },
  { id: 'espera', label: 'Espera', desc: 'Tiempo de espera real y llamados del colero' },
  { id: 'guardia', label: 'Guardia', desc: 'Atenciones derivadas desde Emergencias' },
  { id: 'eventos', label: 'Eventos', desc: 'Reservas y asistencia a eventos' },
] as const
type SeccionId = (typeof SECCIONES)[number]['id']

const AREA_KEY = 'zaris_bi_at_area'
const FILTROS_KEY = 'zaris_bi_at_filtros_colapsados'

function leerAreaGuardada(): number | undefined {
  try {
    const v = localStorage.getItem(AREA_KEY)
    return v ? Number(v) : undefined
  } catch {
    return undefined
  }
}

export function AtencionPage() {
  const nivel = useAuthStore((s) => s.user?.nivel_acceso ?? 99)
  const esAdmin = nivel === 1
  const gestiones = useAtCatalogoGestiones()
  const miArea = useMiArea()
  const [filtros, setFiltros] = useState<BiFiltros | null>(null)
  const ubicaciones = useAtCatalogoUbicaciones(filtros?.id_area)
  const prestaciones = useAtCatalogoPrestaciones(filtros?.id_area, filtros?.id_espacio_ubicacion)
  const [areaInicial, setAreaInicial] = useState<number | undefined>(undefined)
  const stickyRef = useRef<HTMLDivElement>(null)
  const [stickyH, setStickyH] = useState(200)
  const [activa, setActiva] = useState<SeccionId>('resumen')
  const lockHastaRef = useRef(0)
  const calcularRef = useRef<() => void>(() => {})
  const [colapsado, setColapsado] = useState<boolean>(() => {
    try { return localStorage.getItem(FILTROS_KEY) === '1' } catch { return false }
  })

  // Defaults (mismos del Ejecutivo): año en curso + mes anterior tildado; admin
  // arranca en "Todas las gestiones", el supervisor en la gestión de su agente
  // (si es una gestión de atención; si no, la primera del catálogo).
  useEffect(() => {
    if (filtros !== null || miArea.isLoading || gestiones.isLoading) return
    const catalogo = gestiones.data ?? []
    const valida = (id?: number | null) => (id != null && catalogo.some((a) => a.id_area === id) ? id : undefined)
    const inicial = esAdmin
      ? undefined
      : (valida(miArea.data?.id_area) ?? valida(leerAreaGuardada()) ?? catalogo[0]?.id_area)
    setAreaInicial(inicial)
    setFiltros({ id_area: inicial, ...periodoEjecutivoDefault() })
  }, [filtros, miArea.isLoading, gestiones.isLoading, miArea.data, gestiones.data, esAdmin])
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

  // Scroll-spy por POSICIÓN (mismo mecanismo que Operativo / Ejecutivo).
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

  const nombreGestion = filtros?.id_area
    ? (gestiones.data ?? []).find((a) => a.id_area === filtros.id_area)?.nombre
    : 'Todas las gestiones'

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
            Gestión: <strong style={{ color: 'var(--fg-1)' }}>{nombreGestion ?? '—'}</strong>
            {miArea.data?.origen === 'agente' && filtros.id_area === miArea.data.id_area && (
              <span style={{ color: 'var(--fg-3)' }}> · tu gestión</span>
            )}
          </span>
        </div>
        <FiltrosAtencion
          filtros={filtros}
          onChange={setFiltros}
          gestiones={gestiones.data ?? []}
          ubicaciones={ubicaciones.data ?? []}
          prestaciones={prestaciones.data ?? []}
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

      <ResumenAtSection filtros={filtros} />
      <EvolucionAtSection filtros={filtros} />
      <UbicacionesAtSection filtros={filtros} />
      <EsperaAtSection filtros={filtros} />
      <GuardiaAtSection filtros={filtros} />
      <EventosAtSection filtros={filtros} />
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
