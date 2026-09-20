import { useEffect, useState } from 'react'
import { Plus, Search } from 'lucide-react'
import { useAgendaStore } from '../store/agendaStore'
import { useAuthStore } from '../../../stores/auth'
import { RecursoTogglePills } from '../components/RecursoTogglePills'
import { VistaToggle } from '../components/VistaToggle'
import { AgendaFilters } from '../components/AgendaFilters'
import { TimelineView } from './TimelineView'
import { WeeklyView } from './WeeklyView'
import { MonthlyView } from './MonthlyView'
import { EventoModal } from '../modals/EventoModal'
import { EventoEncargadosModal } from '../modals/EventoEncargadosModal'
import { OcupacionModal } from '../modals/OcupacionModal'
import { OcupacionOTModal } from '../modals/OcupacionOTModal'
import { Button } from '../../../ui'
import { AvisoBuscar } from '../../../ui/busqueda'

export function VistasView() {
  const vistaGrilla = useAgendaStore((s) => s.vistaGrilla)
  const fecha = useAgendaStore((s) => s.fechaActiva)
  const pillInicialAplicada = useAgendaStore((s) => s.pillInicialAplicada)
  const marcarPillInicial = useAgendaStore((s) => s.marcarPillInicial)
  const setFiltroRecurso = useAgendaStore((s) => s.setFiltroRecurso)
  // Búsqueda diferida (§23): las grillas (y con ellas las queries de
  // calendario, conflictos y OTs pendientes) se montan recién tras el primer
  // "Ver agenda". Después, navegar fechas, cambiar de pill o de vista re-pide
  // como siempre (acción explícita del usuario).
  const agendaBuscada = useAgendaStore((s) => s.agendaBuscada)
  const marcarAgendaBuscada = useAgendaStore((s) => s.marcarAgendaBuscada)
  const nivel = useAuthStore((s) => s.user?.nivel_acceso)

  // Pill inicial por rol (una vez por carga): el supervisor (nivel 2) vive
  // asignando OT, asi que aterriza en "Equipos · OT". Admin y operadores
  // mantienen el default "Agentes". Despues manda lo que el usuario clickee.
  useEffect(() => {
    if (pillInicialAplicada || nivel == null) return
    marcarPillInicial()
    if (nivel === 2) setFiltroRecurso('equipos')
  }, [pillInicialAplicada, nivel, marcarPillInicial, setFiltroRecurso])

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
          <Button type="button" variant="default" icon={<Plus size={14} strokeWidth={1.5} />} onClick={() => setEventoOpen(true)}>
            Nuevo evento
          </Button>
          <Button type="button" variant="default" icon={<Plus size={14} strokeWidth={1.5} />} onClick={() => setOcupOpen(true)}>
            Nueva ocupacion
          </Button>
          <Button type="button" variant="accent" icon={<Plus size={14} strokeWidth={1.5} />} onClick={() => setOcupOTOpen(true)}>
            Planificar OT
          </Button>
        </div>
      </div>
      <RecursoTogglePills />

      {!agendaBuscada && (
        <>
          {/* Barra de fecha + subárea: acá SOLO en el estado "sin buscar".
              Después la renderiza cada grilla (Día y Semana la traen adentro;
              Mes tiene su propio encabezado), así no aparece dos veces. */}
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <AgendaFilters />
            </div>
            <Button
              type="button"
              variant="accent"
              icon={<Search size={14} strokeWidth={1.5} />}
              onClick={marcarAgendaBuscada}
              title="Traer la agenda de la fecha y el tipo de recurso elegidos"
            >
              Ver agenda
            </Button>
          </div>
          <AvisoBuscar texto="Elegí Día, Semana o Mes, el tipo de recurso y la fecha, y presioná Ver agenda." />
        </>
      )}

      {agendaBuscada && vistaGrilla === 'dia'    && <TimelineView />}
      {agendaBuscada && vistaGrilla === 'semana' && <WeeklyView />}
      {agendaBuscada && vistaGrilla === 'mes'    && <MonthlyView />}

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
