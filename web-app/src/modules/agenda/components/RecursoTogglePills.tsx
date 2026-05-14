import { Users, UsersRound, Building2, DoorClosed } from 'lucide-react'
import { useAgendaStore } from '../store/agendaStore'
import { useRecursosConteos } from '../hooks/useAgenda'
import type { FiltroRecursoUI } from '../types/agenda'

type Pill = {
  value: FiltroRecursoUI
  label: string
  icon: typeof Users
  conteoKey: 'agentes' | 'equipos' | 'espacios_atendidos' | 'espacios_desatendidos'
}

const PILLS: Pill[] = [
  { value: 'agentes',               label: 'Agentes',              icon: Users,       conteoKey: 'agentes' },
  { value: 'equipos',               label: 'Equipos',              icon: UsersRound,  conteoKey: 'equipos' },
  { value: 'espacios_atendidos',    label: 'Esp. atendidos',       icon: Building2,   conteoKey: 'espacios_atendidos' },
  { value: 'espacios_desatendidos', label: 'Esp. desatendidos',    icon: DoorClosed,  conteoKey: 'espacios_desatendidos' },
]

export function RecursoTogglePills() {
  const filtro = useAgendaStore((s) => s.filtroRecurso)
  const setFiltro = useAgendaStore((s) => s.setFiltroRecurso)
  const idMun = useAgendaStore((s) => s.idMunicipio)
  const conteos = useRecursosConteos(idMun)

  return (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
      {PILLS.map((p) => {
        const Icon = p.icon
        const active = filtro === p.value
        const n = conteos.data?.[p.conteoKey]
        return (
          <button
            key={p.value}
            type="button"
            onClick={() => setFiltro(p.value)}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '6px 12px', borderRadius: 999,
              fontFamily: 'var(--font-display)', fontSize: 'var(--size-btn)',
              border: active ? '1px solid var(--zaris-orange)' : '1px solid var(--border-primary)',
              background: active ? 'var(--zaris-orange)' : 'var(--surface-100)',
              color: active ? '#fff' : 'var(--fg-1)',
              cursor: 'pointer',
              transition: 'all 120ms ease',
            }}
          >
            <Icon size={14} strokeWidth={1.5} />
            {p.label}
            {typeof n === 'number' && (
              <span style={{
                fontSize: 11, opacity: 0.85,
                padding: '0 6px', borderRadius: 999,
                background: active ? 'rgba(255,255,255,.2)' : 'var(--surface-300)',
              }}>
                {n}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
