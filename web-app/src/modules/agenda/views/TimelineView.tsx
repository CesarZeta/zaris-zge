import { useMemo, useState } from 'react'
import { Users } from 'lucide-react'
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
import { ConfirmModal } from '../components/ConfirmModal'
import { EventoModal } from '../modals/EventoModal'
import { OcupacionModal } from '../modals/OcupacionModal'
import { ReservaModal } from '../modals/ReservaModal'
import { EventoEncargadosModal } from '../modals/EventoEncargadosModal'
import { Skeleton } from '../../../ui'
import { useDragMutations } from '../dnd/useDragMutations'
import type { DragPayload } from '../dnd/types'
import { PX_PER_HOUR, SNAP_MIN, HOUR_START, ROW_HEIGHT } from '../dnd/gridConstants'
import { timeToMinutes } from '../../../lib/dates'
import type { Ocupacion, OcupacionCreatePayload, TipoRecurso } from '../types/agenda'

// Los reclamos no se agendan (César 2026-10-21: «la agenda solo es para
// turnos»): se quitó el panel de OTs pendientes que se arrastraban a la grilla.
// Las ocupaciones de OT que ya existían se siguen viendo y moviendo.
type PendingConfirm = {
  kind: 'reasignar'
  idOcupacion: number
  desde: { tipo_recurso: TipoRecurso; id_recurso: number }
  hacia: { tipo_recurso: TipoRecurso; id_recurso: number; nombre?: string | null }
  nuevasHoras: { hora_inicio: string; hora_fin: string }
}

export function TimelineView() {
  const fecha = useAgendaStore((s) => s.fechaActiva)
  const idMun = useAgendaStore((s) => s.idMunicipio)
  const filtroRec = useAgendaStore((s) => s.filtroRecurso)
  const filtroSubarea = useAgendaStore((s) => s.filtroSubarea)
  const filtroUbicacion = useAgendaStore((s) => s.filtroUbicacion)
  const { tipo_recurso, atendido, scopeSubareaPropia } = filtroUIaBackend(filtroRec)
  // Modo UBICACION (F2b): la grilla muestra el espacio + sus agentes.
  const modoUbicacion = filtroRec === 'ubicacion'
  const idUbicacion = modoUbicacion ? filtroUbicacion?.id ?? null : null
  const cal = useCalendarioDia(fecha, idMun, tipo_recurso, filtroSubarea, atendido, scopeSubareaPropia, idUbicacion)
  const conf = useConflictos(false)
  const { moverOcupacion } = useDragMutations()

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
  }

  function nombreRecurso(tipo: TipoRecurso, id: number): string | null {
    const rec = cal.data?.recursos.find((r) => r.tipo === tipo && r.id_recurso === id)
    return rec?.nombre ?? null
  }

  function confirmAccept() {
    if (!pendingConfirm) return
    moverOcupacion.mutate({
      id: pendingConfirm.idOcupacion,
      payload: {
        tipo_recurso: pendingConfirm.hacia.tipo_recurso,
        id_recurso: pendingConfirm.hacia.id_recurso,
        hora_inicio: pendingConfirm.nuevasHoras.hora_inicio,
        hora_fin: pendingConfirm.nuevasHoras.hora_fin,
      },
    })
    setPendingConfirm(null)
  }

  function confirmCancel() {
    setPendingConfirm(null)
  }

  // Modo ubicación sin ubicación elegida: pedirla antes de mostrar la grilla.
  if (modoUbicacion && !filtroUbicacion) {
    return (
      <div style={{
        background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
        borderRadius: 12, padding: 40, textAlign: 'center',
        color: 'var(--fg-2)', fontFamily: 'var(--font-display)', fontSize: '0.88rem',
      }}>
        Elegí una ubicación en el selector de arriba para ver su agenda
        (el lugar + los agentes que atienden ahí).
      </div>
    )
  }

  return (
    <DndContext
      sensors={sensors}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragCancel={handleDragCancel}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
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
          title="Reasignar ocupacion"
          message={pendingConfirm ? buildConfirmMessage(pendingConfirm) : ''}
          confirmLabel="Reasignar"
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
          {'click en bloque -> ver/editar  ·  arrastrar bloque -> mover/reasignar'}
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

function buildConfirmMessage(c: PendingConfirm): string {
  return `Reasignar la ocupacion al recurso "${c.hacia.nombre ?? c.hacia.tipo_recurso + ' ' + c.hacia.id_recurso}" en el horario ${c.nuevasHoras.hora_inicio.slice(0, 5)}-${c.nuevasHoras.hora_fin.slice(0, 5)}?`
}
