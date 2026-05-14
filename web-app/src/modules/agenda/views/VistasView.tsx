import { useAgendaStore } from '../store/agendaStore'
import { RecursoTogglePills } from '../components/RecursoTogglePills'
import { VistaToggle } from '../components/VistaToggle'
import { TimelineView } from './TimelineView'
import { WeeklyView } from './WeeklyView'
import { MonthlyView } from './MonthlyView'

export function VistasView() {
  const vistaGrilla = useAgendaStore((s) => s.vistaGrilla)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <VistaToggle />
        <RecursoTogglePills />
      </div>
      {vistaGrilla === 'dia'    && <TimelineView />}
      {vistaGrilla === 'semana' && <WeeklyView />}
      {vistaGrilla === 'mes'    && <MonthlyView />}
    </div>
  )
}
