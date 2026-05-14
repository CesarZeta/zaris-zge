import { useMemo, useState } from 'react'
import {
  DndContext, DragOverlay, PointerSensor, KeyboardSensor, useSensor, useSensors,
  useDraggable, useDroppable,
  type DragEndEvent, type DragStartEvent,
} from '@dnd-kit/core'
import { useCalendarioSemana } from '../hooks/useAgenda'
import { useAgendaStore, filtroUIaBackend } from '../store/agendaStore'
import { useDragMutations } from '../dnd/useDragMutations'
import { AgendaFilters } from '../components/AgendaFilters'
import { ConfirmModal } from '../components/ConfirmModal'
import { Skeleton } from '../../../ui'
import { fromIsoDate, sumarDias, toIsoDate, timeToMinutes } from '../../../lib/dates'
import type { CalendarioSemanaDia, EventoEnCalendario, Ocupacion, TipoRecurso } from '../types/agenda'
import { EventoModal } from '../modals/EventoModal'
import { OcupacionModal } from '../modals/OcupacionModal'

const HOUR_START = 7
const HOUR_END = 20
const DAY_WIDTH_PX = 110
const HEADER_HEIGHT = 36
const ROW_HEIGHT = 56
const RES_COL_WIDTH = 200

// Payload del drag de una ocupacion en la vista Semana.
interface WeeklyDragPayload {
  ocupacion: Ocupacion
  fechaOrigen: string
}

// Confirmacion pendiente al soltar una ocupacion en otra celda (otro dia o recurso).
interface PendingMove {
  idOcupacion: number
  descripcion: string
  fechaDestino: string
  tipoDestino: TipoRecurso
  idDestino: number
  nombreDestino: string | null
}

export function WeeklyView() {
  const fecha = useAgendaStore((s) => s.fechaActiva)
  const idMun = useAgendaStore((s) => s.idMunicipio)
  const filtroRec = useAgendaStore((s) => s.filtroRecurso)
  const filtroSubarea = useAgendaStore((s) => s.filtroSubarea)
  const { tipo_recurso, atendido, scopeSubareaPropia } = filtroUIaBackend(filtroRec)
  const { moverOcupacion } = useDragMutations()

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
  const [activeDrag, setActiveDrag] = useState<WeeklyDragPayload | null>(null)
  const [pendingMove, setPendingMove] = useState<PendingMove | null>(null)

  // KeyboardSensor: la vista Semana no tiene snap en pixeles, asi que el drag
  // por teclado mueve celda a celda. dnd-kit resuelve el droppable mas cercano
  // con el coordinateGetter default, suficiente para mover entre celdas.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor),
  )

  function nombreRecurso(tipo: TipoRecurso, id: number): string | null {
    const rec = sem.data?.recursos.find((r) => r.tipo === tipo && r.id_recurso === id)
    return rec?.nombre ?? null
  }

  function handleDragStart(e: DragStartEvent) {
    const data = e.active.data.current as WeeklyDragPayload | undefined
    if (data) setActiveDrag(data)
  }

  function handleDragCancel() {
    setActiveDrag(null)
  }

  function handleDragEnd(e: DragEndEvent) {
    const data = e.active.data.current as WeeklyDragPayload | undefined
    const over = e.over?.data.current as
      | { kind: 'cell'; fecha: string; tipo_recurso: TipoRecurso; id_recurso: number }
      | undefined
    setActiveDrag(null)
    if (!data || !over || over.kind !== 'cell') return

    const o = data.ocupacion
    const mismaCelda =
      over.fecha === data.fechaOrigen &&
      over.tipo_recurso === o.tipo_recurso &&
      over.id_recurso === o.id_recurso
    if (mismaCelda) return

    // La vista Semana no tiene granularidad horaria: el bloque conserva su
    // horario y solo cambia de dia/recurso. Pedimos confirmacion siempre
    // (consistente con la reasignacion del Timeline, ver feedback §29).
    setPendingMove({
      idOcupacion: o.id_ocupacion,
      descripcion: o.descripcion_corta ?? o.tipo,
      fechaDestino: over.fecha,
      tipoDestino: over.tipo_recurso,
      idDestino: over.id_recurso,
      nombreDestino: nombreRecurso(over.tipo_recurso, over.id_recurso),
    })
  }

  function confirmAccept() {
    if (!pendingMove) return
    moverOcupacion.mutate({
      id: pendingMove.idOcupacion,
      payload: {
        fecha: pendingMove.fechaDestino,
        tipo_recurso: pendingMove.tipoDestino,
        id_recurso: pendingMove.idDestino,
      },
    })
    setPendingMove(null)
  }

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
    <DndContext
      sensors={sensors}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragCancel={handleDragCancel}
    >
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

        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: 'var(--fg-3)' }}>
          {'arrastrar un bloque -> mover a otro dia o recurso (conserva el horario)'}
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
        <ConfirmModal
          open={pendingMove != null}
          title="Mover ocupacion"
          message={pendingMove
            ? `Mover "${pendingMove.descripcion}" al ${pendingMove.fechaDestino} sobre "${pendingMove.nombreDestino ?? pendingMove.tipoDestino + ' ' + pendingMove.idDestino}"? El horario se mantiene.`
            : ''}
          confirmLabel="Mover"
          onConfirm={confirmAccept}
          onCancel={() => setPendingMove(null)}
        />
      </div>

      <DragOverlay dropAnimation={null}>
        {activeDrag && (
          <div style={{
            width: DAY_WIDTH_PX - 8, height: ROW_HEIGHT - 12,
            background: 'rgba(245,78,0,.85)', color: 'white',
            borderRadius: 4, padding: '2px 4px',
            fontFamily: 'var(--font-display)', fontSize: 10, opacity: 0.9,
            overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis',
            boxShadow: '0 6px 16px rgba(38,37,30,.25)',
          }}>
            {activeDrag.ocupacion.descripcion_corta ?? activeDrag.ocupacion.tipo}
          </div>
        )}
      </DragOverlay>
    </DndContext>
  )
}

interface WeeklyDayCellProps {
  dia: CalendarioSemanaDia
  recursoKey: string
  tipoRecurso: TipoRecurso
  idRecurso: number
  totalMinDia: number
  onOcupacionClick: (o: Ocupacion) => void
  onEventoClick: (e: EventoEnCalendario) => void
}

function WeeklyDayCell({ dia, recursoKey, tipoRecurso, idRecurso, totalMinDia, onOcupacionClick, onEventoClick }: WeeklyDayCellProps) {
  const disp = dia.disponibilidad_por_recurso[recursoKey] ?? []
  const tieneDisp = disp.length > 0

  const { setNodeRef, isOver, active } = useDroppable({
    id: `cell-${tipoRecurso}-${idRecurso}-${dia.fecha}`,
    data: { kind: 'cell', fecha: dia.fecha, tipo_recurso: tipoRecurso, id_recurso: idRecurso },
  })

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

  const isDropTarget = isOver && active != null

  return (
    <div
      ref={setNodeRef}
      style={{
        position: 'relative', width: DAY_WIDTH_PX,
        borderLeft: '1px solid var(--border-primary)',
        background: 'repeating-linear-gradient(45deg, rgba(38,37,30,.05) 0 6px, transparent 6px 12px), var(--surface-200)',
        overflow: 'hidden',
        outline: isDropTarget ? '2px dashed var(--zaris-orange)' : 'none',
        outlineOffset: -2,
        transition: 'outline-color 120ms',
      }}
    >
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
              zIndex: 2,
            }}
          >
            {ev.nombre}
          </button>
        )
      })}
      {/* Ocupaciones (draggables) */}
      {ocupaciones.map((o) => {
        const p = pos(o.hora_inicio, o.hora_fin)
        if (!p) return null
        return (
          <WeeklyOccupationBlock
            key={`oc-${o.id_ocupacion}`}
            ocupacion={o}
            fechaOrigen={dia.fecha}
            left={p.left}
            width={p.width}
            onClick={() => onOcupacionClick(o)}
          />
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

interface WeeklyOccupationBlockProps {
  ocupacion: Ocupacion
  fechaOrigen: string
  left: number
  width: number
  onClick: () => void
}

function WeeklyOccupationBlock({ ocupacion, fechaOrigen, left, width, onClick }: WeeklyOccupationBlockProps) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `wk-oc-${ocupacion.id_ocupacion}`,
    data: { ocupacion, fechaOrigen } satisfies WeeklyDragPayload,
  })

  const color = ocupacion.tipo === 'ot' ? 'rgba(245,78,0,.30)'
              : ocupacion.tipo === 'evento' ? 'rgba(159,187,224,.40)'
              : 'rgba(31,138,101,.25)'
  const border = ocupacion.tipo === 'ot' ? 'var(--zaris-orange)'
               : ocupacion.tipo === 'evento' ? '#5a8fb8'
               : 'var(--color-success)'

  return (
    <button
      ref={setNodeRef}
      type="button"
      onClick={onClick}
      {...listeners}
      {...attributes}
      title={`${ocupacion.tipo} · ${ocupacion.hora_inicio.slice(0, 5)}-${ocupacion.hora_fin.slice(0, 5)}`}
      style={{
        position: 'absolute', top: 4, height: ROW_HEIGHT - 12,
        left: `${left}%`, width: `${width}%`,
        background: color, border: `1px solid ${border}`,
        borderRadius: 4, padding: '2px 4px',
        fontFamily: 'var(--font-display)', fontSize: 10, color: 'var(--fg-1)',
        overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis',
        cursor: 'grab', textAlign: 'left',
        opacity: isDragging ? 0.35 : 1,
        zIndex: 3,
      }}
    >
      {ocupacion.descripcion_corta ?? ocupacion.tipo}
    </button>
  )
}
