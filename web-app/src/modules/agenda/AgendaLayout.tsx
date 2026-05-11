import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { CalendarDays, CalendarRange, ListChecks, AlertTriangle } from 'lucide-react'

const tabs = [
  { to: '/agenda',             label: 'timeline',   icon: CalendarDays,   end: true  },
  { to: '/agenda/mensual',     label: 'mensual',    icon: CalendarRange,  end: false },
  { to: '/agenda/eventos',     label: 'eventos',    icon: ListChecks,     end: false },
  { to: '/agenda/conflictos',  label: 'conflictos', icon: AlertTriangle,  end: false },
]

export function AgendaLayout({ children }: { children: ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <h1 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 'var(--size-section)', fontWeight: 400, letterSpacing: 'var(--track-section)', color: 'var(--fg-1)' }}>
          agenda
        </h1>
        <p style={{ margin: '6px 0 0', color: 'var(--fg-3)', fontSize: 'var(--size-btn)' }}>
          eventos, ocupaciones y vista timeline del coordinador.
        </p>
      </div>

      <nav style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--border-primary)' }}>
        {tabs.map((t) => {
          const Icon = t.icon
          return (
            <NavLink
              key={t.to}
              to={t.to}
              end={t.end}
              style={({ isActive }) => ({
                display: 'inline-flex', alignItems: 'center', gap: 6,
                padding: '8px 12px', borderRadius: '6px 6px 0 0',
                fontFamily: 'var(--font-display)', fontSize: 'var(--size-btn)',
                color: isActive ? 'var(--fg-1)' : 'var(--fg-3)',
                background: isActive ? 'var(--surface-100)' : 'transparent',
                borderBottom: isActive ? '2px solid var(--zaris-orange)' : '2px solid transparent',
                textDecoration: 'none', marginBottom: -1,
              })}
            >
              <Icon size={14} strokeWidth={1.5} />
              {t.label}
            </NavLink>
          )
        })}
      </nav>

      {children}
    </div>
  )
}
