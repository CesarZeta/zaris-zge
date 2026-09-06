import { useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight, RefreshCw, Search } from 'lucide-react'
import { useTurnos } from '../hooks/useTurnos'
import { TurnoDetalleModal } from '../components/TurnoDetalleModal'
import { useTurnoFiltros, TurnoFiltrosBar } from '../lib/turnoFiltros'
import { AvisoBuscar } from '../lib/busqueda'
import {
  toIsoDate, hoy, sumarDias, lunesDeSemana,
  nombreDia, etiquetaFechaCorta, etiquetaFechaLarga, mismaFecha,
  rangoDias, timeToMinutes,
} from '../../../lib/dates'
import { useUbicacionTurnosStore } from '../stores/ubicacionTurnos'
import type { EstadoTurno, Turno } from '../types/turno'

// Agenda de SOLO turnos, embebida en el módulo Turnos. NO reusa la grilla de
// Agenda (que mezcla OTs + eventos + turnos): construye su propia grilla simple
// día/semana sobre GET /turnos, que ya viene scopeado por nivel/subárea en el
// backend (§33). Vista de lectura: los turnos se gestionan desde la tab Turnos.

type Modo = 'dia' | 'semana'

// Ventana horaria visible de la grilla (07:00 a 21:00).
const HORA_INI = 7
const HORA_FIN = 21
const PX_POR_HORA = 56
const ALTO_GRILLA = (HORA_FIN - HORA_INI) * PX_POR_HORA

const ESTADO_COLOR: Record<EstadoTurno, { bg: string; border: string; fg: string }> = {
  reservado: { bg: 'rgba(245,127,23,0.14)', border: '#f57f17', fg: '#8a5800' },
  llamado:   { bg: 'rgba(245,78,0,0.16)', border: '#f54e00', fg: '#a33400' },
  cumplido:  { bg: 'rgba(31,138,101,0.16)', border: '#1f8a65', fg: '#15614a' },
  ausente:   { bg: 'rgba(198,40,40,0.14)', border: '#c62828', fg: '#8f1d1d' },
  cancelado: { bg: 'rgba(38,37,30,0.07)',   border: 'var(--border-medium)', fg: 'var(--fg-3)' },
}

export function AgendaTurnos() {
  const [modo, setModo] = useState<Modo>('dia')
  const [ancla, setAncla] = useState<Date>(hoy())
  const [detalle, setDetalle] = useState<Turno | null>(null)
  // Búsqueda diferida (§23): la grilla no pide nada al entrar. "Ver agenda"
  // habilita la query; después, cambiar de día/semana (acción explícita del
  // usuario) vuelve a pedir el rango nuevo.
  const [verAgenda, setVerAgenda] = useState(false)

  const dias = useMemo<Date[]>(() => {
    if (modo === 'dia') return [ancla]
    return rangoDias(lunesDeSemana(ancla), 7)
  }, [modo, ancla])

  const desde = toIsoDate(dias[0])
  const hasta = toIsoDate(dias[dias.length - 1])

  // Contexto ubicación-primero (F2): la agenda respeta la ubicación elegida.
  const ubicacion = useUbicacionTurnosStore((s) => s.ubicacion)
  const { data, isLoading, isError, error, refetch, isFetching } = useTurnos({
    fecha_desde: desde,
    fecha_hasta: hasta,
    id_espacio_ubicacion: ubicacion?.id_espacio,
  }, { enabled: verAgenda })

  // Excluir cancelados de la grilla (ocupan lugar sin sentido). Se ven en la tab Turnos.
  const turnos = useMemo(
    () => (data ?? []).filter((t) => t.estado !== 'cancelado'),
    [data],
  )

  // Filtros Prestación / Recurso / Ciudadano (opciones derivadas de los turnos
  // del rango visible). Mismo helper que la vista de Turnos.
  const { filtros, setFiltros, opciones, filtrar, hayActivos, limpiar } = useTurnoFiltros(turnos)
  const visibles = useMemo(() => filtrar(turnos), [turnos, filtrar])

  const turnosPorDia = useMemo(() => {
    const m = new Map<string, Turno[]>()
    for (const t of visibles) {
      if (!m.has(t.fecha)) m.set(t.fecha, [])
      m.get(t.fecha)!.push(t)
    }
    return m
  }, [visibles])

  function navegar(dir: -1 | 1) {
    setAncla((a) => sumarDias(a, dir * (modo === 'dia' ? 1 : 7)))
  }

  const horas = useMemo(
    () => Array.from({ length: HORA_FIN - HORA_INI }, (_, i) => HORA_INI + i),
    [],
  )

  const tituloRango = modo === 'dia'
    ? etiquetaFechaLarga(dias[0])
    : `${etiquetaFechaCorta(dias[0])} – ${etiquetaFechaCorta(dias[6])} ${dias[6].getFullYear()}`

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={toolbar}>
        <div style={{ display: 'flex', gap: 4, background: 'var(--surface-300)', borderRadius: 10, padding: 3 }}>
          {(['dia', 'semana'] as Modo[]).map((m) => (
            <button
              key={m}
              onClick={() => setModo(m)}
              style={{
                ...toggleBtn,
                background: modo === m ? 'var(--surface-100)' : 'transparent',
                color: modo === m ? 'var(--fg-1)' : 'var(--fg-3)',
                fontWeight: modo === m ? 600 : 400,
                boxShadow: modo === m ? '0 1px 2px rgba(0,0,0,0.08)' : 'none',
              }}
            >
              {m === 'dia' ? 'Día' : 'Semana'}
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button onClick={() => navegar(-1)} style={navBtn} aria-label="Anterior"><ChevronLeft size={16} /></button>
          <button onClick={() => setAncla(hoy())} style={hoyBtn}>Hoy</button>
          <button onClick={() => navegar(1)} style={navBtn} aria-label="Siguiente"><ChevronRight size={16} /></button>
          <span style={{ fontWeight: 600, color: 'var(--fg-1)', fontSize: '0.92rem', textTransform: 'capitalize', minWidth: 0 }}>
            {tituloRango}
          </span>
        </div>

        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
          {!verAgenda && (
            <button onClick={() => setVerAgenda(true)} style={btnPrimary} title="Traer los turnos del día o la semana elegida">
              <Search size={14} strokeWidth={1.5} /> Ver agenda
            </button>
          )}
          <button onClick={() => refetch()} style={navBtn} title="Refrescar" disabled={!verAgenda}>
            <RefreshCw size={14} strokeWidth={1.5} style={{ animation: isFetching ? 'spin 1s linear infinite' : undefined }} />
          </button>
        </div>
      </div>

      {!verAgenda && (
        <AvisoBuscar texto="Elegí Día o Semana, ubicate en la fecha y presioná Ver agenda." />
      )}

      {turnos.length > 0 && (
        <div style={filtrosBar}>
          <TurnoFiltrosBar opciones={opciones} filtros={filtros} setFiltros={setFiltros} />
          {hayActivos && (
            <button onClick={limpiar} style={{ ...navBtn, alignSelf: 'flex-end' }} title="Limpiar filtros">
              Limpiar
            </button>
          )}
        </div>
      )}

      {isError && <div style={errorBanner}>{(error as Error)?.message ?? 'Error al cargar la agenda'}</div>}

      {/* Leyenda de estados ARRIBA de la grilla (pedido del usuario 2026-06-11:
          abajo quedaba fuera de vista al scrollear). */}
      {verAgenda && <div style={leyendaBar}>
        <Leyenda color={ESTADO_COLOR.reservado.border} label="Reservado" />
        <Leyenda color={ESTADO_COLOR.cumplido.border} label="Cumplido" />
        <span style={{ color: 'var(--fg-3)' }}>
          Los turnos cancelados no se muestran (se gestionan en la pestaña Turnos). Clic en un turno para ver su detalle.
        </span>
      </div>}

      {verAgenda && <div style={card}>
        {isLoading ? (
          <p style={vacio}>Cargando…</p>
        ) : (
          <div style={{ display: 'flex', overflowX: 'auto' }}>
            {/* eje de horas */}
            <div style={{ flexShrink: 0, width: 52, paddingTop: 36 }}>
              {horas.map((h) => (
                <div key={h} style={{ height: PX_POR_HORA, position: 'relative' }}>
                  <span style={horaLabel}>{String(h).padStart(2, '0')}:00</span>
                </div>
              ))}
            </div>

            {/* columnas por día */}
            <div style={{ display: 'flex', flex: 1, minWidth: modo === 'semana' ? 720 : 0 }}>
              {dias.map((d) => {
                const iso = toIsoDate(d)
                const esHoy = mismaFecha(d, hoy())
                const items = (turnosPorDia.get(iso) ?? []).slice().sort(
                  (a, b) => timeToMinutes(a.hora_inicio) - timeToMinutes(b.hora_inicio),
                )
                return (
                  <div key={iso} style={{ flex: 1, minWidth: modo === 'semana' ? 100 : 0, borderLeft: '1px solid var(--border-primary)' }}>
                    <div style={{ ...colHeader, color: esHoy ? 'var(--zaris-orange)' : 'var(--fg-2)' }}>
                      <span style={{ textTransform: 'capitalize' }}>{nombreDia(d)}</span>{' '}
                      <span style={{ fontWeight: 600 }}>{d.getDate()}</span>
                    </div>
                    <div style={{ position: 'relative', height: ALTO_GRILLA, background: esHoy ? 'rgba(245,78,0,0.025)' : undefined }}>
                      {/* líneas de hora */}
                      {horas.map((h, i) => (
                        <div key={h} style={{ position: 'absolute', top: i * PX_POR_HORA, left: 0, right: 0, borderTop: '1px solid var(--border-primary)', opacity: 0.5 }} />
                      ))}
                      {/* bloques de turno */}
                      {items.map((t) => (
                        <BloqueTurno key={t.id_turno} t={t} compacto={modo === 'semana'} onClick={() => setDetalle(t)} />
                      ))}
                      {items.length === 0 && (
                        <div style={sinTurnos}>—</div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>}

      <TurnoDetalleModal turno={detalle} onClose={() => setDetalle(null)} />

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

function BloqueTurno({ t, compacto, onClick }: { t: Turno; compacto: boolean; onClick: () => void }) {
  const ini = timeToMinutes(t.hora_inicio)
  const fin = timeToMinutes(t.hora_fin || t.hora_inicio)
  const topMin = Math.max(0, ini - HORA_INI * 60)
  const top = (topMin / 60) * PX_POR_HORA
  const durMin = Math.max(20, fin - ini)
  const alto = Math.max(22, (durMin / 60) * PX_POR_HORA - 2)
  const c = ESTADO_COLOR[t.estado] ?? ESTADO_COLOR.reservado
  const horaTxt = `${t.hora_inicio?.slice(0, 5)}–${(t.hora_fin || '').slice(0, 5)}`

  return (
    <div
      onClick={onClick}
      title={`${horaTxt} · ${t.prestacion_nombre ?? ''} · ${t.ciudadano_nombre ?? ''}${t.recurso_nombre ? ' · ' + t.recurso_nombre : ''} — clic para ver detalle`}
      style={{
        position: 'absolute', top, left: 3, right: 3, height: alto,
        background: c.bg, borderLeft: `3px solid ${c.border}`, borderRadius: 5,
        padding: compacto ? '2px 4px' : '3px 7px', overflow: 'hidden',
        fontSize: compacto ? '0.68rem' : '0.74rem', lineHeight: 1.2, color: c.fg,
        cursor: 'pointer',
      }}
    >
      <div style={{ fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {compacto ? t.hora_inicio?.slice(0, 5) : horaTxt}
      </div>
      {!compacto && (
        <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: 'var(--fg-1)' }}>
          {t.ciudadano_nombre ?? '—'}
        </div>
      )}
      <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {t.prestacion_nombre ?? '—'}
      </div>
    </div>
  )
}

function Leyenda({ color, label }: { color: string; label: string }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <span style={{ width: 12, height: 12, borderRadius: 3, background: color, display: 'inline-block' }} />
      {label}
    </span>
  )
}

const toolbar: React.CSSProperties = {
  display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center',
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)', borderRadius: 12, padding: 12,
}
const filtrosBar: React.CSSProperties = {
  display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end',
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)', borderRadius: 12, padding: 12,
}
const leyendaBar: React.CSSProperties = {
  display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center',
  fontSize: '0.78rem', color: 'var(--fg-2)',
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 12, padding: '8px 14px',
}
const toggleBtn: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: 13, cursor: 'pointer', border: 'none',
  borderRadius: 8, padding: '6px 14px',
}
const navBtn: React.CSSProperties = {
  fontFamily: 'var(--font-display)', cursor: 'pointer', borderRadius: 8, padding: '6px 8px',
  background: 'transparent', color: 'var(--fg-2)', border: '1px solid var(--border-medium)',
  display: 'inline-flex', alignItems: 'center',
}
const btnPrimary: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.82rem', cursor: 'pointer',
  borderRadius: 8, padding: '7px 12px', fontWeight: 500,
  display: 'inline-flex', alignItems: 'center', gap: 6,
  background: 'var(--zaris-orange)', color: 'white', border: '1px solid var(--zaris-orange)',
}
const hoyBtn: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: 13, cursor: 'pointer', borderRadius: 8, padding: '6px 12px',
  background: 'transparent', color: 'var(--fg-2)', border: '1px solid var(--border-medium)',
}
const card: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)', borderRadius: 12, overflow: 'hidden',
}
const colHeader: React.CSSProperties = {
  height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4,
  fontSize: '0.8rem', borderBottom: '1px solid var(--border-primary)', background: 'var(--surface-300)',
}
const horaLabel: React.CSSProperties = {
  position: 'absolute', top: -7, right: 8, fontSize: '0.68rem', color: 'var(--fg-3)', fontFamily: 'var(--font-mono)',
}
const sinTurnos: React.CSSProperties = {
  position: 'absolute', top: 10, left: 0, right: 0, textAlign: 'center', color: 'var(--fg-3)', fontSize: '0.8rem',
}
const vacio: React.CSSProperties = { color: 'var(--fg-3)', fontSize: 13, textAlign: 'center', padding: 40 }
const errorBanner: React.CSSProperties = {
  background: '#ffebee', border: '1px solid #ffcdd2', borderLeft: '4px solid var(--color-error)',
  borderRadius: 8, padding: '12px 16px', color: '#c62828', fontSize: '0.86rem',
}
