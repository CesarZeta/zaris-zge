import { useMemo, useState } from 'react'
import { useCalendarioSemana } from '../hooks/useAgenda'
import { useAgendaStore, filtroUIaBackend } from '../store/agendaStore'
import { AgendaFilters } from '../components/AgendaFilters'
import { Skeleton } from '../../../ui'
import { fromIsoDate, sumarDias, toIsoDate, timeToMinutes } from '../../../lib/dates'
import type { CalendarioSemanaDia, EventoEnCalendario, Ocupacion } from '../types/agenda'
import { EventoModal } from '../modals/EventoModal'
import { OcupacionModal } from '../modals/OcupacionModal'

const HOUR_START = 7
const HOUR_END = 20
const DAY_WIDTH_PX = 110
const HEADER_HEIGHT = 36
const ROW_HEIGHT = 56
const RES_COL_WIDTH = 200

export function WeeklyView() {
  const fecha = useAgendaStore((s) => s.fechaActiva)
  const idMun = useAgendaStore((s) => s.idMunicipio)
  const filtroRec = useAgendaStore((s) => s.filtroRecurso)
  const filtroSubarea = useAgendaStore((s) => s.filtroSubarea)
  const { tipo_recurso, atendido, scopeSubareaPropia } = filtroUIaBackend(filtroRec)

  // Empezamos la semana en el lunes de la semana de la fecha activa.
  const desde = useMemo(() => {
    const d = fromIsoDate(fecha)
    const jsDay = d.getDay()             // 0=Dom..6=Sab
    const restar = jsDay === 0 ? 6 : jsDay - 1
    return toIsoDate(sumarDias(d, -restar))
  }, [fecha])

  const sem = useCalendarioSemana(desde, 7, idMun, tipo_recurso, filtroSubarea, atendido, scopeSubareaPropia)
  const [eventoOpen, setEventoOpen] = useState<{ id: number | null } | null>(null)
  const [ocupOpen,   setOcupOpen]   = useState<{ ocupacion: Ocupacion | null } | null>(null)

  if (sem.isLoading) return <><AgendaFilters /><Skeleton height={400} /></>
  if (sem.isError) {
    return (
      <>
        <AgendaFilters />
        <div style={{ padding: 16, color: 'var(--color-error)', fontFamily: 'var(--font-mono)', fontSize: 13 }}>
          Error: {(sem.error as Error).message}
        </div>
      </>
    )
  }
  if (!sem.data) return null

  const data = sem.data
  if (data.recursos.length === 0) {
    return (
      <>
        <AgendaFilters />
        <div style={{ padding: 24, textAlign: 'center', color: 'var(--fg-3)', background: 'var(--surface-100)', borderRadius: 'var(--radius-lg)' }}>
          No hay recursos activos para este filtro y municipio
        </div>
      </>
    )
  }

  const totalWidth = RES_COL_WIDTH + DAY_WIDTH_PX * 7
  const totalMinDia = (HOUR_END - HOUR_START) * 60

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <AgendaFilters />
      <div style={{ overflowX: 'auto', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)', background: 'var(--surface-100)' }}>
        <div style={{ width: totalWidth, position: 'relative' }}>
          {/* Header */}
          <div style={{ display: 'flex', height: HEADER_HEIGHT, background: 'var(--surface-200)', borderBottom: '1px solid var(--border-medium)' }}>
            <div style={{ width: RES_COL_WIDTH, padding: '8px 12px', fontFamily: 'var(--font-display)', fontSize: 11, color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '.04em' }}>
              Recurso
            </div>
            {data.dias.map((d) => {
              const dt = fromIsoDate(d.fecha)
              return (
                <div
                  key={d.fecha}
                  style={{
                    width: DAY_WIDTH_PX, borderLeft: '1px solid var(--border-primary)',
                    padding: '6px 8px', fontFamily: 'var(--font-display)', fontSize: 12,
                    color: 'var(--fg-1)',
                  }}
                >
                  <div style={{ fontWeight: 500 }}>{['Lun','Mar','Mie','Jue','Vie','Sab','Dom'][(dt.getDay() + 6) % 7]}</div>
                  <div style={{ fontSize: 10, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>{d.fecha.slice(5)}</div>
                </div>
              )
            })}
          </div>

          {/* Filas */}
          {data.recursos.map((rec) => (
            <div key={`${rec.tipo}-${rec.id_recurso}`} style={{ display: 'flex', height: ROW_HEIGHT, borderBottom: '1px solid var(--border-primary)' }}>
              <div style={{
                width: RES_COL_WIDTH, padding: '8px 12px', display: 'flex', alignItems: 'center', gap: 8,
                borderRight: '1px solid var(--border-medium)',
              }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{
                    fontFamily: 'var(--font-display)', fontSize: 13, color: 'var(--fg-1)', fontWeight: 500,
                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                  }}>
                    {rec.nombre ?? `${rec.tipo} ${rec.id_recurso}`}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>
                    {rec.tipo === 'espacio' ? (rec.atendido ? 'espacio · atendido' : 'espacio · desatendido') : rec.tipo}
                  </div>
                </div>
              </div>
              {data.dias.map((d) => (
                <WeeklyDayCell
                  key={`${rec.tipo}-${rec.id_recurso}-${d.fecha}`}
                  dia={d}
                  recursoKey={`${rec.tipo}:${rec.id_recurso}`}
                  tipoRecurso={rec.tipo}
                  idRecurso={rec.id_recurso}
                  totalMinDia={totalMinDia}
                  onOcupacionClick={(o) => o.tipo === 'evento' && o.id_evento ? setEventoOpen({ id: o.id_evento }) : setOcupOpen({ ocupacion: o })}
                  onEventoClick={(ev) => setEventoOpen({ id: ev.id_evento })}
                />
              ))}
            </div>
          ))}
        </div>
      </div>

      <EventoModal
        open={eventoOpen != null}
        onClose={() => setEventoOpen(null)}
        idEvento={eventoOpen?.id ?? null}
        defaultDate={fecha}
      />
      <OcupacionModal
        open={ocupOpen != null}
        onClose={() => setOcupOpen(null)}
        ocupacion={ocupOpen?.ocupacion ?? null}
      />
    </div>
  )
}

interface WeeklyDayCellProps {
  dia: CalendarioSemanaDia
  recursoKey: string
  tipoRecurso: string
  idRecurso: number
  totalMinDia: number
  onOcupacionClick: (o: Ocupacion) => void
  onEventoClick: (e: EventoEnCalendario) => void
}

function WeeklyDayCell({ dia, recursoKey, tipoRecurso, idRecurso, totalMinDia, onOcupacionClick, onEventoClick }: WeeklyDayCellProps) {
  const disp = dia.disponibilidad_por_recurso[recursoKey] ?? []
  const tieneDisp = disp.length > 0

  // Filtrar ocupaciones y ausencias para este recurso (vienen por dia, todos los recursos).
  const ocupaciones = dia.ocupaciones.filter((o) => o.tipo_recurso === tipoRecurso && o.id_recurso === idRecurso)
  // Eventos: pintamos si el recurso es encargado, o si es el espacio asociado.
  const eventos = dia.eventos.filter((ev) => {
    if (tipoRecurso === 'espacio' && ev.id_espacio === idRecurso) return true
    return (ev.encargados ?? []).some(([t, i]) => t === tipoRecurso && i === idRecurso)
  })

  function pos(hi: string, hf: string): { left: number; width: number } | null {
    const ini = timeToMinutes(hi.slice(0, 5))
    const fin = timeToMinutes(hf.slice(0, 5))
    if (fin <= HOUR_START * 60 || ini >= HOUR_END * 60) return null
    const iniC = Math.max(ini, HOUR_START * 60)
    const finC = Math.min(fin, HOUR_END * 60)
    const left = ((iniC - HOUR_START * 60) / totalMinDia) * 100
    const width = ((finC - iniC) / totalMinDia) * 100
    return { left, width }
  }

  return (
    <div style={{
      position: 'relative', width: DAY_WIDTH_PX,
      borderLeft: '1px solid var(--border-primary)',
      background: 'repeating-linear-gradient(45deg, rgba(38,37,30,.05) 0 6px, transparent 6px 12px), var(--surface-200)',
      overflow: 'hidden',
    }}>
      {/* Capa disponibilidad */}
      {disp.map((d, i) => {
        const p = pos(d.hora_inicio, d.hora_fin)
        if (!p) return null
        return (
          <div
            key={`disp-${i}`}
            style={{
              position: 'absolute', top: 0, bottom: 0,
              left: `${p.left}%`, width: `${p.width}%`,
              background: 'var(--surface-100)',
              pointerEvents: 'none',
            }}
          />
        )
      })}
      {/* Eventos */}
      {eventos.map((ev) => {
        const p = pos(ev.hora_inicio, ev.hora_fin)
        if (!p) return null
        const cupoAgotado = ev.cupo_libre <= 0 && ev.capacidad_ciudadanos > 0
        return (
          <button
            key={`ev-${ev.id_evento}`}
            type="button"
            onClick={() => onEventoClick(ev)}
            title={`${ev.nombre} · ${ev.hora_inicio.slice(0, 5)}-${ev.hora_fin.slice(0, 5)}`}
            style={{
              position: 'absolute', top: 4, height: ROW_HEIGHT - 12,
              left: `${p.left}%`, width: `${p.width}%`,
              background: 'rgba(106,27,154,.20)', border: '1px solid #6a1b9a',
              borderRadius: 4, padding: '2px 4px',
              fontFamily: 'var(--font-display)', fontSize: 10, color: 'var(--fg-1)',
              overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis',
              cursor: 'pointer', textAlign: 'left',
              textDecoration: cupoAgotado ? 'line-through' : 'none',
            }}
          >
            {ev.nombre}
          </button>
        )
      })}
      {/* Ocupaciones */}
      {ocupaciones.map((o) => {
        const p = pos(o.hora_inicio, o.hora_fin)
        if (!p) return null
        const color = o.tipo === 'ot' ? 'rgba(245,78,0,.30)'
                    : o.tipo === 'evento' ? 'rgba(159,187,224,.40)'
                    : 'rgba(31,138,101,.25)'
        const border = o.tipo === 'ot' ? 'var(--zaris-orange)'
                     : o.tipo === 'evento' ? '#5a8fb8'
                     : 'var(--color-success)'
        return (
          <button
            key={`oc-${o.id_ocupacion}`}
            type="button"
            onClick={() => onOcupacionClick(o)}
            title={`${o.tipo} · ${o.hora_inicio.slice(0, 5)}-${o.hora_fin.slice(0, 5)}`}
            style={{
              position: 'absolute', top: 4, height: ROW_HEIGHT - 12,
              left: `${p.left}%`, width: `${p.width}%`,
              background: color, border: `1px solid ${border}`,
              borderRadius: 4, padding: '2px 4px',
              fontFamily: 'var(--font-display)', fontSize: 10, color: 'var(--fg-1)',
              overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis',
              cursor: 'pointer', textAlign: 'left',
            }}
          >
            {o.descripcion_corta ?? o.tipo}
          </button>
        )
      })}
      {/* Sin disponibilidad: leyenda en el centro */}
      {!tieneDisp && ocupaciones.length === 0 && eventos.length === 0 && (
        <div style={{
          position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 9, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', pointerEvents: 'none',
        }}>
          (sin horario)
        </div>
      )}
    </div>
  )
}
