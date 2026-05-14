import { CalendarDays, CalendarRange, Calendar } from 'lucide-react'
import { useAgendaStore } from '../store/agendaStore'
import type { VistaGrilla } from '../types/agenda'

const OPCIONES: { value: VistaGrilla; label: string; icon: typeof CalendarDays }[] = [
  { value: 'dia',    label: 'Dia',    icon: CalendarDays },
  { value: 'semana', label: 'Semana', icon: CalendarRange },
  { value: 'mes',    label: 'Mes',    icon: Calendar },
]

export function VistaToggle() {
  const vistaGrilla = useAgendaStore((s) => s.vistaGrilla)
  const setVistaGrilla = useAgendaStore((s) => s.setVistaGrilla)

  return (
    <div style={{
      display: 'inline-flex',
      borderRadius: 8,
      background: 'var(--surface-100)',
      border: '1px solid var(--border-primary)',
      padding: 2,
    }}>
      {OPCIONES.map((o) => {
        const Icon = o.icon
        const active = vistaGrilla === o.value
        return (
          <button
            key={o.value}
            type="button"
            onClick={() => setVistaGrilla(o.value)}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '6px 12px', borderRadius: 6,
              fontFamily: 'var(--font-display)', fontSize: 'var(--size-btn)',
              border: 'none',
              background: active ? 'var(--zaris-orange)' : 'transparent',
              color: active ? '#fff' : 'var(--fg-2)',
              cursor: 'pointer',
              transition: 'all 120ms ease',
            }}
          >
            <Icon size={14} strokeWidth={1.5} />
            {o.label}
          </button>
        )
      })}
    </div>
  )
}
