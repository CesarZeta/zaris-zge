import { useState } from 'react'
import { Building2, CalendarClock } from 'lucide-react'
import { EspaciosConfig } from '../components/config/EspaciosConfig'
import { DisponibilidadConfig } from '../components/config/DisponibilidadConfig'

type Tab = 'espacios' | 'disponibilidad'

export function ConfigView() {
  const [tab, setTab] = useState<Tab>('espacios')
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{
        display: 'inline-flex', alignSelf: 'flex-start',
        borderRadius: 8, background: 'var(--surface-100)',
        border: '1px solid var(--border-primary)', padding: 2,
      }}>
        <TabBtn active={tab === 'espacios'}        onClick={() => setTab('espacios')}        icon={Building2}     label="Espacios" />
        <TabBtn active={tab === 'disponibilidad'}  onClick={() => setTab('disponibilidad')}  icon={CalendarClock} label="Disponibilidad" />
      </div>
      {tab === 'espacios'       && <EspaciosConfig />}
      {tab === 'disponibilidad' && <DisponibilidadConfig />}
    </div>
  )
}

function TabBtn({ active, onClick, icon: Icon, label }: { active: boolean; onClick: () => void; icon: typeof Building2; label: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        padding: '6px 12px', borderRadius: 6,
        border: 'none',
        background: active ? 'var(--zaris-orange)' : 'transparent',
        color: active ? '#fff' : 'var(--fg-2)',
        fontFamily: 'var(--font-display)', fontSize: 'var(--size-btn)',
        cursor: 'pointer',
      }}
    >
      <Icon size={14} strokeWidth={1.5} />
      {label}
    </button>
  )
}
