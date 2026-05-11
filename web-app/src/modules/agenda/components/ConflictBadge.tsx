import { AlertTriangle } from 'lucide-react'

export function ConflictBadge({ small = false }: { small?: boolean }) {
  return (
    <span
      title="Esta ocupacion tiene conflicto de agenda"
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 4,
        background: 'rgba(207,45,86,.18)', color: 'var(--color-error)',
        fontSize: small ? 10 : 11, fontFamily: 'var(--font-display)', fontWeight: 600,
        padding: small ? '1px 5px' : '2px 6px', borderRadius: 'var(--radius-pill)',
        whiteSpace: 'nowrap',
      }}
    >
      <AlertTriangle size={small ? 10 : 11} strokeWidth={1.5} />
      conflicto
    </span>
  )
}
