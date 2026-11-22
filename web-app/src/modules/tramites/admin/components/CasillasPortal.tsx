import type { IniciadorTipo } from '../../types'

/**
 * Casillas del tipo que gobiernan el portal del vecino (mig 139).
 * Solo se muestran si el tipo admite iniciador ciudadano: el backend rechaza
 * «se ofrece al vecino» en un tipo sin ciudadano (422).
 */
export function CasillasPortal({
  iniciadores, ofrecer, onOfrecer, exige, onExige,
}: {
  iniciadores: IniciadorTipo[]
  ofrecer: boolean
  onOfrecer: (v: boolean) => void
  exige: boolean
  onExige: (v: boolean) => void
}) {
  if (!iniciadores.includes('ciudadano')) return null
  return (
    <>
      <label style={casilla}>
        <input type="checkbox" checked={ofrecer} onChange={(e) => onOfrecer(e.target.checked)} style={{ marginTop: 3 }} />
        Se ofrece al vecino en el portal
      </label>
      <p style={hint}>Aparece en la app del vecino para iniciarlo desde ahí.</p>

      <label style={casilla}>
        <input type="checkbox" checked={exige} onChange={(e) => onExige(e.target.checked)} style={{ marginTop: 3 }} />
        Exige identidad validada en el municipio
      </label>
      <p style={hint}>El vecino tiene que haber validado su identidad en una ventanilla.</p>
    </>
  )
}

const casilla: React.CSSProperties = {
  display: 'flex', alignItems: 'flex-start', gap: 6, fontSize: 14, cursor: 'pointer', marginBottom: 4,
}
const hint: React.CSSProperties = { fontSize: 11, color: 'var(--fg-3)', margin: '0 0 12px 24px' }
