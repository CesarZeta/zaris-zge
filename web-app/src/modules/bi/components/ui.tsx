import type { ReactNode } from 'react'

// ── KpiCard ───────────────────────────────────────────────────────────────────
// Tarjeta de número grande con etiqueta. `accent` colorea el valor. Compacta
// (2026-08-30): la fila de KPIs de cada sección debe entrar en UNA línea.
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
        padding: '12px 14px',
        display: 'flex',
        flexDirection: 'column',
        gap: 3,
        minWidth: 0,
      }}
    >
      <span
        style={{
          fontFamily: 'var(--font-display)',
          fontSize: '0.68rem',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          color: 'var(--fg-3)',
          fontWeight: 600,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
        title={label}
      >
        {label}
      </span>
      <span style={{ fontFamily: 'var(--font-display)', fontSize: '1.6rem', fontWeight: 700, lineHeight: 1.05, color: accent, whiteSpace: 'nowrap' }}>
        {value}
      </span>
      {sub && (
        <span style={{ fontSize: '0.7rem', color: 'var(--fg-3)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={sub}>
          {sub}
        </span>
      )}
    </div>
  )
}

// Fila ÚNICA de KPIs (no envuelve): N columnas iguales.
export function KpiRow({ n, children }: { n: number; children: ReactNode }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: `repeat(${n}, minmax(0, 1fr))`, gap: 10 }}>
      {children}
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
  nota,
}: {
  title: string
  children: ReactNode
  height?: number
  action?: ReactNode
  /** Aclaración en minúscula al lado del título (ej. "últimos 12 meses"). */
  nota?: string
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
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, minWidth: 0, flexWrap: 'wrap' }}>
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
          {nota && (
            <span style={{ fontFamily: 'var(--font-display)', fontSize: '0.74rem', color: 'var(--fg-3)', textTransform: 'lowercase' }}>
              {nota}
            </span>
          )}
        </div>
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
