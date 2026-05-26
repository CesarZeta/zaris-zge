import type { ReactNode } from 'react'

// ── KpiCard ───────────────────────────────────────────────────────────────────
// Tarjeta de número grande con etiqueta. `accent` colorea el valor.
export function KpiCard({
  label,
  value,
  accent = 'var(--fg-1)',
  sub,
}: {
  label: string
  value: ReactNode
  accent?: string
  sub?: string
}) {
  return (
    <div
      style={{
        background: 'var(--surface-100)',
        border: '1px solid var(--border-primary)',
        borderRadius: 12,
        padding: '16px 18px',
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
        minWidth: 0,
      }}
    >
      <span
        style={{
          fontFamily: 'var(--font-display)',
          fontSize: '0.72rem',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          color: 'var(--fg-3)',
          fontWeight: 600,
        }}
      >
        {label}
      </span>
      <span style={{ fontFamily: 'var(--font-display)', fontSize: '1.9rem', fontWeight: 700, lineHeight: 1.05, color: accent }}>
        {value}
      </span>
      {sub && <span style={{ fontSize: '0.74rem', color: 'var(--fg-3)' }}>{sub}</span>}
    </div>
  )
}

// ── ChartCard ─────────────────────────────────────────────────────────────────
// Contenedor con título para envolver una visualización.
export function ChartCard({
  title,
  children,
  height,
  action,
}: {
  title: string
  children: ReactNode
  height?: number
  action?: ReactNode
}) {
  return (
    <div
      style={{
        background: 'var(--surface-100)',
        border: '1px solid var(--border-primary)',
        borderRadius: 12,
        padding: '14px 16px 8px',
        display: 'flex',
        flexDirection: 'column',
        minWidth: 0,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, margin: '0 0 10px' }}>
        <h3
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: '0.92rem',
            fontWeight: 600,
            color: 'var(--fg-1)',
            margin: 0,
          }}
        >
          {title}
        </h3>
        {action}
      </div>
      <div style={{ height: height ?? 280, width: '100%' }}>{children}</div>
    </div>
  )
}

// ── Estados de carga / vacío ────────────────────────────────────────────────────
export function CenterMsg({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--fg-3)',
        fontSize: '0.84rem',
        textAlign: 'center',
        padding: 12,
      }}
    >
      {children}
    </div>
  )
}
