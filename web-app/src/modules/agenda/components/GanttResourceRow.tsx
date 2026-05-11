import React from 'react'
import type { CalendarioRecurso, Ocupacion } from '../types/agenda'
import { GanttOccupationBlock } from './GanttOccupationBlock'
import { timeToMinutes } from '../../../lib/dates'

interface Props {
  recurso: CalendarioRecurso
  hourStart: number
  hourEnd: number
  pxPerHour: number
  rowHeight: number
  conflictoOcupIds: Set<number>
  onBlockClick: (o: Ocupacion) => void
  onEmptySlotClick: (hi: string, hf: string) => void
}

function _GanttResourceRow({
  recurso, hourStart, hourEnd, pxPerHour, rowHeight,
  conflictoOcupIds, onBlockClick, onEmptySlotClick,
}: Props) {
  const totalMin = (hourEnd - hourStart)
  const width = (totalMin / 60) * pxPerHour

  // Bloques de ausencia (todo el dia => bloque que cubre toda la franja con patron rayado)
  const ausencias = recurso.ausencias

  function handleBgClick(e: React.MouseEvent<HTMLDivElement>) {
    const rect = e.currentTarget.getBoundingClientRect()
    const x = e.clientX - rect.left
    const minutosDesdeInicio = (x / pxPerHour) * 60 + hourStart
    // Snap a la hora mas cercana
    const snap = Math.round(minutosDesdeInicio / 30) * 30
    const hi = `${String(Math.floor(snap / 60)).padStart(2, '0')}:${String(snap % 60).padStart(2, '0')}`
    const fin = snap + 60
    const hf = `${String(Math.floor(fin / 60)).padStart(2, '0')}:${String(fin % 60).padStart(2, '0')}`
    onEmptySlotClick(hi, hf)
  }

  return (
    <div
      style={{
        position: 'relative', height: rowHeight, width,
        borderBottom: '1px solid var(--border-primary)',
        background:
          'repeating-linear-gradient(to right, transparent 0, transparent ' + (pxPerHour - 1) + 'px, var(--border-primary) ' + (pxPerHour - 1) + 'px, var(--border-primary) ' + pxPerHour + 'px)',
      }}
      onClick={handleBgClick}
    >
      {/* Ausencias: bloques rayados de fondo (cubren todo el row si es ausencia de dia entero) */}
      {ausencias.map((au) => (
        <div
          key={au.id_ausencia}
          title={`Ausencia: ${au.motivo ?? 'sin motivo'}`}
          style={{
            position: 'absolute', inset: 0,
            background: 'repeating-linear-gradient(45deg, rgba(192,133,50,.18) 0 6px, transparent 6px 12px)',
            pointerEvents: 'none',
          }}
        >
          <span style={{
            position: 'absolute', left: 8, top: 6, fontSize: 11, color: 'var(--zaris-gold)',
            fontFamily: 'var(--font-display)', fontWeight: 500,
          }}>
            licencia {au.motivo ? ` · ${au.motivo}` : ''}
          </span>
        </div>
      ))}
      {/* Ocupaciones */}
      {recurso.ocupaciones.map((o) => {
        const inicio = timeToMinutes(o.hora_inicio.slice(0, 5))
        const fin = timeToMinutes(o.hora_fin.slice(0, 5))
        if (fin <= hourStart || inicio >= hourEnd) return null
        return (
          <div
            key={o.id_ocupacion}
            onClick={(ev) => ev.stopPropagation()}
            style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}
          >
            <div style={{ pointerEvents: 'auto' }}>
              <GanttOccupationBlock
                ocupacion={o}
                hourStart={hourStart}
                pxPerHour={pxPerHour}
                rowHeight={rowHeight}
                enConflicto={conflictoOcupIds.has(o.id_ocupacion)}
                onClick={() => onBlockClick(o)}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}

export const GanttResourceRow = React.memo(_GanttResourceRow)
