import { useMemo, useState } from 'react'
import { Plus, Users } from 'lucide-react'
import {
  DndContext, DragOverlay, PointerSensor, KeyboardSensor, useSensor, useSensors,
  type DragEndEvent, type DragStartEvent,
  type KeyboardCoordinateGetter,
} from '@dnd-kit/core'
import { useCalendarioDia } from '../hooks/useAgenda'
import { useConflictos } from '../hooks/useConflictos'
import { useAgendaStore, filtroUIaBackend } from '../store/agendaStore'
import { AgendaFilters } from '../components/AgendaFilters'
import { GanttGrid } from '../components/GanttGrid'
import { PendingOTsPanel } from '../components/PendingOTsPanel'
import { ConfirmModal } from '../components/ConfirmModal'
import { EventoModal } from '../modals/EventoModal'
import { OcupacionModal } from '../modals/OcupacionModal'
import { ReservaModal } from '../modals/ReservaModal'
import { EventoEncargadosModal } from '../modals/EventoEncargadosModal'
import { Button, Skeleton } from '../../../ui'
import { useDragMutations } from '../dnd/useDragMutations'
import type { DragPayload } from '../dnd/types'
import { PX_PER_HOUR, SNAP_MIN, HOUR_START, ROW_HEIGHT } from '../dnd/gridConstants'
import { timeToMinutes } from '../../../lib/dates'
import type { Ocupacion, OcupacionCreatePayload, TipoRecurso } from '../types/agenda'

type PendingConfirm =
  | {
      kind: 'reasignar'
      idOcupacion: number
      desde: { tipo_recurso: TipoRecurso; id_recurso: number }
      hacia: { tipo_recurso: TipoRecurso; id_recurso: number; nombre?: string | null }
      nuevasHoras: { hora_inicio: string; hora_fin: string }
    }
  | {
      kind: 'crear-desde-ot'
      ot: { id_ot: number; nro_ot: string | null; descripcion: string | null; sla_dias: number | null; tipo_audit: boolean | null }
      destino: { tipo_recurso: TipoRecurso; id_recurso: number; nombre?: string | null }
      horas: { hora_inicio: string; hora_fin: string }
    }

export function TimelineView() {
  const fecha = useAgendaStore((s) => s.fechaActiva)
  const idMun = useAgendaStore((s) => s.idMunicipio)
  const filtroRec = useAgendaStore((s) => s.filtroRecurso)
  const filtroSubarea = useAgendaStore((s) => s.filtroSubarea)
  const { tipo_recurso, atendido } = filtroUIaBackend(filtroRec)
  const cal = useCalendarioDia(fecha, idMun, tipo_recurso, filtroSubarea, atendido)
  const conf = useConflictos(false)
  const { moverOcupacion, crearDesdeOT } = useDragMutations()

  const conflictoOcupIds = useMemo(() => {
    const s = new Set<number>()
    for (const c of conf.data ?? []) {
      if (!c.resuelto) {
        if (c.id_ocupacion_origen)     s.add(c.id_ocupacion_origen)
        if (c.id_ocupacion_conflicto)  s.add(c.id_ocupacion_conflicto)
      }
    }
    return s
  }, [conf.data])

  const [eventoOpen,   setEventoOpen]   = useState<{ id: number | null } | null>(null)
  const [reservaOpen,  setReservaOpen]  = useState<number | null>(null)
  const [encargOpen,   setEncargOpen]   = useState<number | null>(null)
  const [ocupOpen,     setOcupOpen]     = useState<{ ocupacion: Ocupacion | null; defaults?: Partial<OcupacionCreatePayload> } | null>(null)

  const [otPanelOpen, setOtPanelOpen] = useState(true)
  const [activeDrag, setActiveDrag] = useState<DragPayload | null>(null)
  const [pendingConfirm, setPendingConfirm] = useState<PendingConfirm | null>(null)

  // PointerSensor con activationConstraint para que un click corto sea click,
  // no drag. 5px de distancia minima antes de iniciar drag.
  // KeyboardSensor: foco con Tab al bloque, Space/Enter activa drag, flechas mueven
  // en pasos de SNAP_MIN (X) o ROW_HEIGHT (Y), Space/Enter suelta, Esc cancela.
  const pxPerSnapMin = (PX_PER_HOUR * SNAP_MIN) / 60
  const keyboardCoordinateGetter: KeyboardCoordinateGetter = (event, { currentCoordinates }) => {
    switch (event.code) {
      case 'ArrowRight': return { ...currentCoordinates, x: currentCoordinates.x + pxPerSnapMin }
      case 'ArrowLeft':  return { ...currentCoordinates, x: currentCoordinates.x - pxPerSnapMin }
      case 'ArrowDown':  return { ...currentCoordinates, y: currentCoordinates.y + ROW_HEIGHT }
      case 'ArrowUp':    return { ...currentCoordinates, y: currentCoordinates.y - ROW_HEIGHT }
    }
    return undefined
  }
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: keyboardCoordinateGetter }),
  )

  function handleDragStart(e: DragStartEvent) {
    const data = e.active.data.current as DragPayload | undefined
    if (data) setActiveDrag(data)
  }

  function handleDragCancel() {
    setActiveDrag(null)
  }

  function handleDragEnd(e: DragEndEvent) {
    const data = e.active.data.current as DragPayload | undefined
    const overData = e.over?.data.current as { kind: 'row'; tipo_recurso: TipoRecurso; id_recurso: number } | undefined
    setActiveDrag(null)
    if (!data || !overData || overData.kind !== 'row') return

    // === MOVER / REASIGNAR OCUPACION EXISTENTE ===========================
    if (data.kind === 'occupation') {
      const o = data.ocupacion
      const inicioMin = timeToMinutes(o.hora_inicio.slice(0, 5))
      const finMin    = timeToMinutes(o.hora_fin.slice(0, 5))
      const durMin    = finMin - inicioMin

      // delta.x viene en px; convertimos a minutos y snap a 15 min.
      const deltaMin = Math.round(((e.delta.x / PX_PER_HOUR) * 60) / SNAP_MIN) * SNAP_MIN
      let nuevoInicio = inicioMin + deltaMin
      // Clamp dentro de la jornada visible: no antes de HOUR_START, no despues de 20:00 - dur.
      const minMin = HOUR_START * 60
      const maxMin = 20 * 60 - durMin
      if (nuevoInicio < minMin) nuevoInicio = minMin
      if (nuevoInicio > maxMin) nuevoInicio = maxMin
      const nuevoFin = nuevoInicio + durMin
      const hi = toHHMMSS(nuevoInicio)
      const hf = toHHMMSS(nuevoFin)

      const mismoRecurso = overData.tipo_recurso === o.tipo_recurso && overData.id_recurso === o.id_recurso
      const sinMover = mismoRecurso && nuevoInicio === inicioMin

      if (sinMover) return

      if (!mismoRecurso) {
        // Reasignar: pedir confirmacion via ConfirmModal (NO window.confirm, ver feedback §29).
        const nombreDest = nombreRecurso(overData.tipo_recurso, overData.id_recurso)
        setPendingConfirm({
          kind: 'reasignar',
          idOcupacion: o.id_ocupacion,
          desde: { tipo_recurso: o.tipo_recurso, id_recurso: o.id_recurso },
          hacia: { tipo_recurso: overData.tipo_recurso, id_recurso: overData.id_recurso, nombre: nombreDest },
          nuevasHoras: { hora_inicio: hi, hora_fin: hf },
        })
        return
      }

      // Mover en el mismo recurso: persiste directo, sin modal.
      moverOcupacion.mutate({
        id: o.id_ocupacion,
        payload: { hora_inicio: hi, hora_fin: hf },
      })
      return
    }

    // === CREAR OCUPACION DESDE OT PENDIENTE ==============================
    if (data.kind === 'pending-ot') {
      const ot = data.ot
      // Hora exacta del drop: usamos activatorEvent.clientX + delta.x para
      // ubicar el pointer al soltar, y lo mapeamos al rect de la fila destino
      // (data-row-tipo/id estan en el DOM del GanttResourceRow).
      const dur = 60
      let hi = '09:00:00'
      const rowEl = document.querySelector<HTMLDivElement>(
        `[data-row-tipo="${overData.tipo_recurso}"][data-row-id="${overData.id_recurso}"]`,
      )
      const act = e.activatorEvent as PointerEvent | MouseEvent | null
      if (rowEl && act && 'clientX' in act) {
        const dropX = act.clientX + e.delta.x
        const rect = rowEl.getBoundingClientRect()
        const xInRow = dropX - rect.left
        if (xInRow >= 0 && xInRow <= rect.width) {
          const minutosDesdeStart = (xInRow / PX_PER_HOUR) * 60
          const minutosAbs = HOUR_START * 60 + minutosDesdeStart
          const snap = Math.round(minutosAbs / SNAP_MIN) * SNAP_MIN
          const minMin = HOUR_START * 60
          const maxMin = 20 * 60 - dur
          const inicioClamped = Math.max(minMin, Math.min(maxMin, snap))
          hi = toHHMMSS(inicioClamped)
        }
      }
      const inicioFinal = timeToMinutes(hi.slice(0, 5))
      const fin = inicioFinal + dur
      const hf = toHHMMSS(fin)
      const nombreDest = nombreRecurso(overData.tipo_recurso, overData.id_recurso)
      setPendingConfirm({
        kind: 'crear-desde-ot',
        ot: { id_ot: ot.id_ot, nro_ot: ot.nro_ot, descripcion: ot.reclamo_descripcion, sla_dias: ot.sla_dias, tipo_audit: ot.tipo_audit ?? null },
        destino: { tipo_recurso: overData.tipo_recurso, id_recurso: overData.id_recurso, nombre: nombreDest },
        horas: { hora_inicio: hi, hora_fin: hf },
      })
    }
  }

  function nombreRecurso(tipo: TipoRecurso, id: number): string | null {
    const rec = cal.data?.recursos.find((r) => r.tipo === tipo && r.id_recurso === id)
    return rec?.nombre ?? null
  }

  function confirmAccept() {
    if (!pendingConfirm) return
    if (pendingConfirm.kind === 'reasignar') {
      moverOcupacion.mutate({
        id: pendingConfirm.idOcupacion,
        payload: {
          tipo_recurso: pendingConfirm.hacia.tipo_recurso,
          id_recurso: pendingConfirm.hacia.id_recurso,
          hora_inicio: pendingConfirm.nuevasHoras.hora_inicio,
          hora_fin: pendingConfirm.nuevasHoras.hora_fin,
        },
      })
    } else if (pendingConfirm.kind === 'crear-desde-ot') {
      const payload: OcupacionCreatePayload = {
        tipo: 'ot',
        tipo_recurso: pendingConfirm.destino.tipo_recurso,
        id_recurso: pendingConfirm.destino.id_recurso,
        fecha,
        hora_inicio: pendingConfirm.horas.hora_inicio,
        hora_fin: pendingConfirm.horas.hora_fin,
        id_orden_trabajo: pendingConfirm.ot.id_ot,
        duracion_aplicada_min: minutosEntre(pendingConfirm.horas.hora_inicio, pendingConfirm.horas.hora_fin),
        id_municipio: idMun,
      }
      crearDesdeOT.mutate(payload)
    }
    setPendingConfirm(null)
  }

  function confirmCancel() {
    setPendingConfirm(null)
  }

  return (
    <DndContext
      sensors={sensors}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragCancel={handleDragCancel}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 'var(--size-subhead)', fontWeight: 400, letterSpacing: 'var(--track-subhead)', color: 'var(--fg-1)' }}>
            timeline
          </h2>
          <div style={{ display: 'flex', gap: 8 }}>
            <Button variant="default" icon={<Plus size={14} strokeWidth={1.5} />} onClick={() => setEventoOpen({ id: null })}>
              Nuevo evento
            </Button>
            <Button variant="accent" icon={<Plus size={14} strokeWidth={1.5} />} onClick={() => setOcupOpen({ ocupacion: null, defaults: { fecha } })}>
              Nueva ocupacion
            </Button>
          </div>
        </div>

        <AgendaFilters />

        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            {cal.isLoading && <Skeleton height={300} />}
            {cal.isError && (
              <div style={{ padding: 16, color: 'var(--color-error)', fontFamily: 'var(--font-mono)', fontSize: 13 }}>
                Error: {(cal.error as Error).message}
              </div>
            )}
            {cal.data && cal.data.recursos.length === 0 && (
              <div style={{ padding: 24, textAlign: 'center', color: 'var(--fg-3)', background: 'var(--surface-100)', borderRadius: 'var(--radius-lg)' }}>
                No hay recursos activos para este municipio
              </div>
            )}
            {cal.data && cal.data.recursos.length > 0 && (
              <GanttGrid
                data={cal.data}
                conflictoOcupIds={conflictoOcupIds}
                onOcupacionClick={(o) => {
                  if (o.tipo === 'evento' && o.id_evento) {
                    setEventoOpen({ id: o.id_evento })
                  } else {
                    setOcupOpen({ ocupacion: o })
                  }
                }}
                onEventoClick={(ev) => setEventoOpen({ id: ev.id_evento })}
                onSlotVacioClick={({ tipo_recurso, id_recurso, hora_inicio, hora_fin }) => {
                  setOcupOpen({
                    ocupacion: null,
                    defaults: { fecha, tipo_recurso, id_recurso, hora_inicio, hora_fin, tipo: 'turno' },
                  })
                }}
              />
            )}
          </div>
          <PendingOTsPanel open={otPanelOpen} onToggle={() => setOtPanelOpen((v) => !v)} />
        </div>

        <EventoModal
          open={eventoOpen != null}
          onClose={() => setEventoOpen(null)}
          idEvento={eventoOpen?.id ?? null}
          defaultDate={fecha}
          onCreated={(id) => setEncargOpen(id)}
        />
        <EventoEncargadosModal
          open={encargOpen != null}
          onClose={() => setEncargOpen(null)}
          idEvento={encargOpen}
        />
        <ReservaModal
          open={reservaOpen != null}
          onClose={() => setReservaOpen(null)}
          idEvento={reservaOpen}
        />
        <OcupacionModal
          open={ocupOpen != null}
          onClose={() => setOcupOpen(null)}
          defaults={ocupOpen?.defaults}
          ocupacion={ocupOpen?.ocupacion ?? null}
        />

        <ConfirmModal
          open={pendingConfirm != null}
          title={pendingConfirm?.kind === 'reasignar' ? 'Reasignar ocupacion' : 'Planificar OT'}
          message={pendingConfirm ? buildConfirmMessage(pendingConfirm) : ''}
          confirmLabel={pendingConfirm?.kind === 'reasignar' ? 'Reasignar' : 'Crear ocupacion'}
          onConfirm={confirmAccept}
          onCancel={confirmCancel}
        />

        <div style={{ display: 'flex', gap: 8, fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>
          <Legend color="rgba(245,78,0,.16)" border="var(--zaris-orange)" label="ot" />
          <Legend color="rgba(159,187,224,.30)" border="#5a8fb8" label="evento" />
          <Legend color="rgba(31,138,101,.16)" border="var(--color-success)" label="turno" />
          <Legend color="rgba(192,133,50,.18)" border="var(--zaris-gold)" label="licencia" />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: 'var(--fg-3)' }}>
          <Users size={12} strokeWidth={1.5} />
          {'click en bloque -> ver/editar  ·  arrastrar bloque -> mover/reasignar  ·  arrastrar OT del panel -> planificar'}
        </div>
      </div>

      <DragOverlay dropAnimation={null}>
        {activeDrag?.kind === 'occupation' && (
          <div style={{
            width: 160, height: 36, background: 'rgba(245,78,0,.85)', color: 'white',
            borderRadius: 'var(--radius-md)', padding: '6px 10px',
            fontFamily: 'var(--font-display)', fontSize: 11, opacity: 0.85,
            boxShadow: '0 6px 16px rgba(38,37,30,.25)',
          }}>
            {activeDrag.ocupacion.descripcion_corta ?? activeDrag.ocupacion.tipo}
          </div>
        )}
        {activeDrag?.kind === 'pending-ot' && (
          <div style={{
            width: 220, padding: '8px 10px',
            background: 'var(--zaris-orange)', color: 'white',
            borderRadius: 'var(--radius-md)', fontSize: 12, opacity: 0.9,
            fontFamily: 'var(--font-display)',
            boxShadow: '0 6px 16px rgba(38,37,30,.25)',
          }}>
            <div style={{ fontWeight: 600, fontSize: 11 }}>{activeDrag.ot.nro_ot}</div>
            <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {activeDrag.ot.reclamo_descripcion}
            </div>
          </div>
        )}
      </DragOverlay>
    </DndContext>
  )
}

function Legend({ color, border, label }: { color: string; border: string; label: string }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
      <span style={{ width: 12, height: 8, background: color, border: `1px solid ${border}`, borderRadius: 2 }} />
      {label}
    </span>
  )
}

function toHHMMSS(totalMin: number): string {
  const h = Math.floor(totalMin / 60)
  const m = totalMin % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:00`
}

function minutosEntre(hi: string, hf: string): number {
  return timeToMinutes(hf.slice(0, 5)) - timeToMinutes(hi.slice(0, 5))
}

function buildConfirmMessage(c: PendingConfirm): string {
  if (c.kind === 'reasignar') {
    return `Reasignar la ocupacion al recurso "${c.hacia.nombre ?? c.hacia.tipo_recurso + ' ' + c.hacia.id_recurso}" en el horario ${c.nuevasHoras.hora_inicio.slice(0, 5)}-${c.nuevasHoras.hora_fin.slice(0, 5)}?`
  }
  return `Planificar la OT ${c.ot.nro_ot ?? '#' + c.ot.id_ot} sobre "${c.destino.nombre ?? c.destino.tipo_recurso + ' ' + c.destino.id_recurso}" de ${c.horas.hora_inicio.slice(0, 5)} a ${c.horas.hora_fin.slice(0, 5)}? Despues podras ajustar el horario.`
}
