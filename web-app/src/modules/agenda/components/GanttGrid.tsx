import { useEffect, useMemo, useState } from 'react'
import type { CalendarioDia, EventoEnCalendario, Ocupacion, TipoRecurso } from '../types/agenda'
import { GanttResourceRow } from './GanttResourceRow'
import { mismaFecha, fromIsoDate, horaActualHHMM, timeToMinutes } from '../../../lib/dates'
import { HOUR_START, HOUR_END, PX_PER_HOUR, ROW_HEIGHT, COL_LEFT_WIDTH } from '../dnd/gridConstants'

interface Props {
  data: CalendarioDia
  conflictoOcupIds: Set<number>
  onOcupacionClick: (o: Ocupacion) => void
  onSlotVacioClick: (args: { tipo_recurso: TipoRecurso; id_recurso: number; nombre: string | null; hora_inicio: string; hora_fin: string }) => void
  onEventoClick?: (e: EventoEnCalendario) => void
}

export function GanttGrid({ data, conflictoOcupIds, onOcupacionClick, onSlotVacioClick, onEventoClick }: Props) {
  // Indexar eventos por (tipo_recurso, id_recurso) y por id_espacio para que
  // cada fila reciba solo los que le tocan segun el tipo de recurso filtrado.
  const eventosPorRecurso = useMemo(() => {
    const out = new Map<string, EventoEnCalendario[]>()
    const push = (key: string, ev: EventoEnCalendario) => {
      const arr = out.get(key) ?? []
      arr.push(ev)
      out.set(key, arr)
    }
    for (const ev of data.eventos ?? []) {
      // Por encargados (agentes y equipos).
      for (const [tipo, idr] of ev.encargados ?? []) {
        push(`${tipo}-${idr}`, ev)
      }
      // Por espacio (cuando el filtro es espacio el encargado podria ser otro).
      if (ev.id_espacio != null) {
        push(`espacio-${ev.id_espacio}`, ev)
      }
    }
    return out
  }, [data.eventos])
  const horas = useMemo(() => {
    const out: number[] = []
    for (let h = HOUR_START; h <= HOUR_END; h++) out.push(h)
    return out
  }, [])

  // Linea hora actual si la fecha visible == hoy
  const [nowMin, setNowMin] = useState<number | null>(null)
  useEffect(() => {
    const fechaVisible = fromIsoDate(data.fecha)
    if (!mismaFecha(fechaVisible, new Date())) { setNowMin(null); return }
    const actualizar = () => setNowMin(timeToMinutes(horaActualHHMM()))
    actualizar()
    const t = setInterval(actualizar, 60_000)
    return () => clearInterval(t)
  }, [data.fecha])

  const gridWidth = (HOUR_END - HOUR_START) * PX_PER_HOUR

  const nowOffset = nowMin != null ? ((nowMin - HOUR_START * 60) / 60) * PX_PER_HOUR : null

  return (
    <div style={{ display: 'flex', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)', overflow: 'hidden', background: 'var(--surface-100)' }}>
      {/* Columna izq: recursos */}
      <div style={{ width: COL_LEFT_WIDTH, flex: '0 0 auto', borderRight: '1px solid var(--border-medium)' }}>
        {/* Header sticky vacio que coincide con header de horas */}
        <div style={{ height: 36, borderBottom: '1px solid var(--border-medium)', background: 'var(--surface-200)' }} />
        {data.recursos.map((rec) => {
          const bgIcon = rec.tipo === 'agente'  ? 'rgba(159,187,224,.35)'
                       : rec.tipo === 'equipo'  ? 'rgba(245,78,0,.20)'
                       : 'rgba(106,27,154,.20)'
          const subtitulo = rec.tipo === 'espacio'
            ? (rec.atendido ? 'espacio · atendido' : 'espacio · desatendido')
            : rec.tipo
          return (
            <div
              key={`${rec.tipo}-${rec.id_recurso}`}
              style={{
                height: ROW_HEIGHT, borderBottom: '1px solid var(--border-primary)',
                padding: '8px 12px', display: 'flex', alignItems: 'center', gap: 10,
                background: 'var(--surface-100)',
              }}
            >
              <div style={{
                width: 30, height: 30, borderRadius: 'var(--radius-pill)',
                background: bgIcon,
                color: 'var(--fg-1)', display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: 'var(--font-display)', fontSize: 12, fontWeight: 600,
              }}>
                {(rec.nombre ?? '?').slice(0, 1).toUpperCase()}
              </div>
              <div style={{ minWidth: 0 }}>
                <div style={{
                  fontFamily: 'var(--font-display)', fontSize: 13, color: 'var(--fg-1)', fontWeight: 500,
                  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                }}>
                  {rec.nombre ?? `${rec.tipo} ${rec.id_recurso}`}
                </div>
                <div style={{ fontSize: 10, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>
                  {subtitulo}
                </div>
              </div>
            </div>
          )
        })}
      </div>
      {/* Grilla scrolleable horizontal */}
      <div style={{ flex: 1, overflowX: 'auto', position: 'relative' }}>
        <div style={{ width: gridWidth, position: 'relative' }}>
          {/* Header de horas */}
          <div style={{
            height: 36, display: 'flex', position: 'sticky', top: 0, zIndex: 5,
            background: 'var(--surface-200)', borderBottom: '1px solid var(--border-medium)',
          }}>
            {horas.map((h, i) => (
              <div
                key={h}
                style={{
                  width: PX_PER_HOUR, borderRight: i === horas.length - 1 ? 'none' : '1px solid var(--border-primary)',
                  padding: '8px 6px', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-3)',
                }}
              >
                {String(h).padStart(2, '0')}:00
              </div>
            ))}
          </div>

          {/* Linea hora actual */}
          {nowOffset != null && (
            <div
              style={{
                position: 'absolute', top: 0, bottom: 0, left: nowOffset, width: 2,
                background: 'var(--color-error)', zIndex: 10, pointerEvents: 'none',
              }}
            >
              <div style={{
                position: 'absolute', top: 18, left: -22, fontSize: 10,
                background: 'var(--color-error)', color: 'var(--zaris-cream)',
                padding: '1px 5px', borderRadius: 'var(--radius-sm)', fontFamily: 'var(--font-mono)',
              }}>
                ahora
              </div>
            </div>
          )}

          {/* Rows */}
          {data.recursos.map((rec) => (
            <GanttResourceRow
              key={`${rec.tipo}-${rec.id_recurso}`}
              recurso={rec}
              hourStart={HOUR_START * 60}
              hourEnd={HOUR_END * 60}
              pxPerHour={PX_PER_HOUR}
              rowHeight={ROW_HEIGHT}
              conflictoOcupIds={conflictoOcupIds}
              eventos={eventosPorRecurso.get(`${rec.tipo}-${rec.id_recurso}`) ?? []}
              onBlockClick={onOcupacionClick}
              onEventoClick={onEventoClick}
              onEmptySlotClick={(hi, hf) => onSlotVacioClick({
                tipo_recurso: rec.tipo, id_recurso: rec.id_recurso, nombre: rec.nombre, hora_inicio: hi, hora_fin: hf,
              })}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
