import type { ReactNode } from 'react'

interface ToolbarProps {
  children: ReactNode
  onRefresh: () => void
  refreshing?: boolean
}

export function Toolbar({ children, onRefresh, refreshing }: ToolbarProps) {
  return (
    <div style={{
      background: '#e3f2fd', border: '1px solid #bbdefb',
      borderRadius: 10, padding: '12px 16px', marginBottom: 12,
    }}>
      <div style={{
        fontSize: '0.74rem', fontWeight: 600, textTransform: 'uppercase',
        letterSpacing: '0.06em', color: '#1565c0', marginBottom: 8,
      }}>
        Buscar y filtrar
      </div>
      <div style={{ display: 'flex', gap: 10, alignItems: 'end', flexWrap: 'wrap' }}>
        {children}
        <button
          onClick={onRefresh}
          disabled={refreshing}
          style={{
            fontFamily: 'var(--font-display)', fontSize: '0.84rem', cursor: 'pointer',
            borderRadius: 8, padding: '7px 14px', border: '1px solid var(--border-medium)',
            background: 'var(--surface-100)', color: 'var(--fg-1)',
            opacity: refreshing ? 0.6 : 1,
          }}
        >
          {refreshing ? 'Actualizando…' : 'Refrescar'}
        </button>
      </div>
    </div>
  )
}

export function Field({ label, children, wide }: { label: string; children: ReactNode; wide?: boolean }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label style={{
        fontSize: '0.7rem', color: 'var(--fg-3)',
        textTransform: 'uppercase', letterSpacing: '0.04em',
      }}>{label}</label>
      <div style={{ minWidth: wide ? 260 : 150 }}>
        {children}
      </div>
    </div>
  )
}

export const inputStyle: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.84rem',
  padding: '6px 10px', borderRadius: 7,
  border: '1px solid var(--border-medium)', background: 'var(--surface-100)',
  color: 'var(--fg-1)', width: '100%',
}

export function StatsChips({ counts, empty }: { counts: Record<string, number>; empty?: string }) {
  const entries = Object.entries(counts)
  if (!entries.length) {
    return (
      <div style={{ display: 'flex', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
        <span style={chipStyle}>{empty ?? 'Sin datos'}</span>
      </div>
    )
  }
  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
      {entries.map(([k, v]) => (
        <span key={k} style={chipStyle}>
          <strong style={{ color: 'var(--fg-1)', fontWeight: 600, marginRight: 4 }}>{v}</strong>
          {k}
        </span>
      ))}
    </div>
  )
}

const chipStyle: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 999, padding: '4px 11px', fontSize: '0.76rem', color: 'var(--fg-2)',
}
