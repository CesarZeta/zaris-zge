import { useMemo, useState } from 'react'
import { Plus, Users } from 'lucide-react'
import { useCalendarioDia } from '../hooks/useAgenda'
import { useConflictos } from '../hooks/useConflictos'
import { useAgendaStore } from '../store/agendaStore'
import { AgendaFilters } from '../components/AgendaFilters'
import { GanttGrid } from '../components/GanttGrid'
import { EventoModal } from '../modals/EventoModal'
import { OcupacionModal } from '../modals/OcupacionModal'
import { ReservaModal } from '../modals/ReservaModal'
import { EventoEncargadosModal } from '../modals/EventoEncargadosModal'
import { Button, Skeleton } from '../../../ui'
import type { Ocupacion, OcupacionCreatePayload } from '../types/agenda'

export function TimelineView() {
  const fecha = useAgendaStore((s) => s.fechaActiva)
  const idMun = useAgendaStore((s) => s.idMunicipio)
  const filtroRec = useAgendaStore((s) => s.filtroRecurso)
  const cal = useCalendarioDia(fecha, idMun, filtroRec)
  const conf = useConflictos(false)

  // Set de ocupaciones con conflicto pendiente (origen o conflicto)
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

  // Modals
  const [eventoOpen,   setEventoOpen]   = useState<{ id: number | null } | null>(null)
  const [reservaOpen,  setReservaOpen]  = useState<number | null>(null)
  const [encargOpen,   setEncargOpen]   = useState<number | null>(null)
  const [ocupOpen,     setOcupOpen]     = useState<{ ocupacion: Ocupacion | null; defaults?: Partial<OcupacionCreatePayload> } | null>(null)

  return (
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
          onSlotVacioClick={({ tipo_recurso, id_recurso, hora_inicio, hora_fin }) => {
            setOcupOpen({
              ocupacion: null,
              defaults: { fecha, tipo_recurso, id_recurso, hora_inicio, hora_fin, tipo: 'turno' },
            })
          }}
        />
      )}

      {/* Modales */}
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

      <div style={{ display: 'flex', gap: 8, fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>
        <Legend color="rgba(245,78,0,.16)" border="var(--zaris-orange)" label="ot" />
        <Legend color="rgba(159,187,224,.30)" border="#5a8fb8" label="evento" />
        <Legend color="rgba(31,138,101,.16)" border="var(--color-success)" label="turno" />
        <Legend color="rgba(192,133,50,.18)" border="var(--zaris-gold)" label="licencia" />
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: 'var(--fg-3)' }}>
        <Users size={12} strokeWidth={1.5} />
        {'click en bloque → ver/editar · click en celda vacia → crear ocupacion en ese slot'}
      </div>
    </div>
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
