import { useState } from 'react'
import { Plus } from 'lucide-react'
import { useAgendaStore } from '../store/agendaStore'
import { RecursoTogglePills } from '../components/RecursoTogglePills'
import { VistaToggle } from '../components/VistaToggle'
import { TimelineView } from './TimelineView'
import { WeeklyView } from './WeeklyView'
import { MonthlyView } from './MonthlyView'
import { EventoModal } from '../modals/EventoModal'
import { EventoEncargadosModal } from '../modals/EventoEncargadosModal'
import { OcupacionModal } from '../modals/OcupacionModal'
import { OcupacionOTModal } from '../modals/OcupacionOTModal'
import { Button } from '../../../ui'

export function VistasView() {
  const vistaGrilla = useAgendaStore((s) => s.vistaGrilla)
  const fecha = useAgendaStore((s) => s.fechaActiva)

  // Modales de alta "global" — disponibles desde cualquier vista (dia/semana/mes).
  // El alta contextual desde la grilla (click en slot, drag de OT) la maneja
  // cada vista con sus propios modales.
  const [eventoOpen, setEventoOpen] = useState(false)
  const [encargOpen, setEncargOpen] = useState<number | null>(null)
  const [ocupOpen, setOcupOpen] = useState(false)
  const [ocupOTOpen, setOcupOTOpen] = useState(false)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <VistaToggle />
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <Button variant="default" icon={<Plus size={14} strokeWidth={1.5} />} onClick={() => setEventoOpen(true)}>
            Nuevo evento
          </Button>
          <Button variant="default" icon={<Plus size={14} strokeWidth={1.5} />} onClick={() => setOcupOpen(true)}>
            Nueva ocupacion
          </Button>
          <Button variant="accent" icon={<Plus size={14} strokeWidth={1.5} />} onClick={() => setOcupOTOpen(true)}>
            Planificar OT
          </Button>
        </div>
      </div>
      <RecursoTogglePills />

      {vistaGrilla === 'dia'    && <TimelineView />}
      {vistaGrilla === 'semana' && <WeeklyView />}
      {vistaGrilla === 'mes'    && <MonthlyView />}

      <EventoModal
        open={eventoOpen}
        onClose={() => setEventoOpen(false)}
        idEvento={null}
        defaultDate={fecha}
        onCreated={(id) => setEncargOpen(id)}
      />
      <EventoEncargadosModal
        open={encargOpen != null}
        onClose={() => setEncargOpen(null)}
        idEvento={encargOpen}
      />
      <OcupacionModal
        open={ocupOpen}
        onClose={() => setOcupOpen(false)}
        defaults={{ fecha }}
      />
      <OcupacionOTModal
        open={ocupOTOpen}
        onClose={() => setOcupOTOpen(false)}
        defaults={{ fecha }}
      />
    </div>
  )
}
