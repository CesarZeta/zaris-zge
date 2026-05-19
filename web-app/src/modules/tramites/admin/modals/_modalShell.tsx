import type { ReactNode } from 'react'

/**
 * Shell mínimo de modal: overlay + caja centrada. Reusable por todos los
 * modales del admin. No usa libs externas para mantener bundle chico.
 */
export function ModalShell({
  titulo, onCerrar, ancho = 520, children,
}: {
  titulo: string
  onCerrar: () => void
  ancho?: number
  children: ReactNode
}) {
  return (
    <div style={overlay} onClick={(e) => { if (e.target === e.currentTarget) onCerrar() }}>
      <div style={{ ...box, maxWidth: ancho }}>
        <div style={header}>
          <h2 style={{ margin: 0, fontSize: '1.05rem', color: 'var(--fg-1)' }}>{titulo}</h2>
          <button onClick={onCerrar} style={cerrarBtn} aria-label="Cerrar">×</button>
        </div>
        <div style={{ padding: 16 }}>{children}</div>
      </div>
    </div>
  )
}

export const label: React.CSSProperties = {
  display: 'block', fontSize: 12, color: 'var(--fg-2)',
  fontFamily: 'var(--font-display)', marginBottom: 4, fontWeight: 600,
}
export const requiredMark: React.CSSProperties = { color: 'var(--color-error)' }
export const errorMsg: React.CSSProperties = {
  color: 'var(--color-error)', fontSize: 13, margin: '8px 0 0',
}
export const formRow: React.CSSProperties = { marginBottom: 12 }

const overlay: React.CSSProperties = {
  position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  zIndex: 1000, padding: 20,
}
const box: React.CSSProperties = {
  background: 'var(--surface-100)', borderRadius: 'var(--radius-lg)',
  width: '100%', boxShadow: '0 10px 40px rgba(0,0,0,0.2)',
  display: 'flex', flexDirection: 'column', maxHeight: '90vh', overflow: 'hidden',
}
const header: React.CSSProperties = {
  padding: '14px 16px', borderBottom: '1px solid var(--border-primary)',
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
}
const cerrarBtn: React.CSSProperties = {
  background: 'transparent', border: 'none', cursor: 'pointer',
  fontSize: 24, lineHeight: 1, color: 'var(--fg-3)', padding: '0 4px',
}
