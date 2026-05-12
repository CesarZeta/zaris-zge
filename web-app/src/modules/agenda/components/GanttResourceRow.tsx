import React, { useRef, useState } from 'react'
import { useDroppable, useDndMonitor } from '@dnd-kit/core'
import type { CalendarioRecurso, Ocupacion } from '../types/agenda'
import { GanttOccupationBlock } from './GanttOccupationBlock'
import { timeToMinutes } from '../../../lib/dates'
import { HOUR_START, SNAP_MIN } from '../dnd/gridConstants'

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

  const { setNodeRef, isOver, active } = useDroppable({
    id: `row-${recurso.tipo}-${recurso.id_recurso}`,
    data: { kind: 'row', tipo_recurso: recurso.tipo, id_recurso: recurso.id_recurso },
  })

  // Snap visual: linea vertical naranja sobre la posicion donde se soltaria
  // (snap a SNAP_MIN). Solo se muestra si la fila es el droppable activo.
  const rowElRef = useRef<HTMLDivElement | null>(null)
  const [snapPx, setSnapPx] = useState<number | null>(null)

  function setRefs(el: HTMLDivElement | null) {
    rowElRef.current = el
    setNodeRef(el)
  }

  useDndMonitor({
    onDragMove(ev) {
      if (!isOver || !rowElRef.current) return
      const act = ev.activatorEvent as PointerEvent | MouseEvent | null
      if (!act || !('clientX' in act)) return
      const rect = rowElRef.current.getBoundingClientRect()
      const xInRow = act.clientX + ev.delta.x - rect.left
      if (xInRow < 0 || xInRow > rect.width) { setSnapPx(null); return }
      const minutosDesdeStart = (xInRow / pxPerHour) * 60
      const minutosAbs = HOUR_START * 60 + minutosDesdeStart
      const snap = Math.round(minutosAbs / SNAP_MIN) * SNAP_MIN
      const snapPos = ((snap - HOUR_START * 60) / 60) * pxPerHour
      setSnapPx(snapPos)
    },
    onDragEnd() { setSnapPx(null) },
    onDragCancel() { setSnapPx(null) },
  })

  const ausencias = recurso.ausencias

  function handleBgClick(e: React.MouseEvent<HTMLDivElement>) {
    const rect = e.currentTarget.getBoundingClientRect()
    const x = e.clientX - rect.left
    const minutosDesdeInicio = (x / pxPerHour) * 60 + hourStart
    const snap = Math.round(minutosDesdeInicio / 30) * 30
    const hi = `${String(Math.floor(snap / 60)).padStart(2, '0')}:${String(snap % 60).padStart(2, '0')}`
    const fin = snap + 60
    const hf = `${String(Math.floor(fin / 60)).padStart(2, '0')}:${String(fin % 60).padStart(2, '0')}`
    onEmptySlotClick(hi, hf)
  }

  const isDropTarget = isOver && active != null

  return (
    <div
      ref={setRefs}
      style={{
        position: 'relative', height: rowHeight, width,
        borderBottom: '1px solid var(--border-primary)',
        background:
          'repeating-linear-gradient(to right, transparent 0, transparent ' + (pxPerHour - 1) + 'px, var(--border-primary) ' + (pxPerHour - 1) + 'px, var(--border-primary) ' + pxPerHour + 'px)',
        outline: isDropTarget ? '2px dashed var(--zaris-orange)' : 'none',
        outlineOffset: isDropTarget ? -2 : 0,
        transition: 'outline-color 120ms',
      }}
      data-row-tipo={recurso.tipo}
      data-row-id={recurso.id_recurso}
    >
      {/* Layer de fondo clickeable. Va debajo de las ocupaciones (zIndex 0) y
          captura clicks en celdas vacias para abrir el modal de nueva ocupacion.
          Necesario porque el droppable wrapper recibe pointerdown de dnd-kit y
          no siempre dispara click sobre el padre. */}
      <div
        onClick={handleBgClick}
        style={{ position: 'absolute', inset: 0, zIndex: 0, cursor: 'pointer' }}
      />
      {/* Snap visual: linea vertical naranja en la posicion de snap mientras
          esta fila es el droppable activo. */}
      {isDropTarget && snapPx != null && (
        <div
          aria-hidden
          style={{
            position: 'absolute', top: 0, bottom: 0, left: snapPx,
            width: 2, background: 'var(--zaris-orange)',
            boxShadow: '0 0 6px rgba(245,78,0,.5)',
            pointerEvents: 'none', zIndex: 25,
          }}
        />
      )}
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
            licencia {au.motivo ? ` - ${au.motivo}` : ''}
          </span>
        </div>
      ))}
      {/* Las ocupaciones se posicionan en absoluto sobre la fila. El <button>
          dentro de GanttOccupationBlock tiene su propio left/width y captura
          pointer events solo en su area; el resto de la fila queda libre para
          que el layer de fondo dispare el click de "nueva ocupacion". */}
      {recurso.ocupaciones.map((o) => {
        const inicio = timeToMinutes(o.hora_inicio.slice(0, 5))
        const fin = timeToMinutes(o.hora_fin.slice(0, 5))
        if (fin <= hourStart || inicio >= hourEnd) return null
        return (
          <GanttOccupationBlock
            key={o.id_ocupacion}
            ocupacion={o}
            hourStart={hourStart}
            pxPerHour={pxPerHour}
            rowHeight={rowHeight}
            enConflicto={conflictoOcupIds.has(o.id_ocupacion)}
            onClick={() => onBlockClick(o)}
          />
        )
      })}
    </div>
  )
}

export const GanttResourceRow = React.memo(_GanttResourceRow)
