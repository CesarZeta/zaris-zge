import type { CSSProperties } from 'react'
import type { OrigenIncidente } from '../lib/types'

/** Etiqueta del origen para el resumen del panel contraído (vacío = el de siempre). */
export function labelOrigen(origen?: OrigenIncidente): string | undefined {
  return origen === 'relevamientos' ? 'Relevamientos' : undefined
}

/**
 * Origen de los incidentes (mig 141): los reclamos del vecino o los relevamientos que carga un
 * agente municipal. Datos los cuenta APARTE (decisión de César 2026-11-22): nunca se mezclan.
 */
export function SelectorOrigen({
  value, onChange, labelStyle, inputStyle,
}: {
  value?: OrigenIncidente
  onChange: (v: OrigenIncidente | undefined) => void
  labelStyle: CSSProperties
  inputStyle: CSSProperties
}) {
  return (
    <div>
      <label style={labelStyle}>Origen</label>
      <select
        value={value ?? 'reclamos'}
        onChange={(e) => onChange(e.target.value === 'relevamientos' ? 'relevamientos' : undefined)}
        style={inputStyle}
        title="Los relevamientos los carga un agente municipal y se cuentan aparte de los reclamos del vecino"
      >
        <option value="reclamos">Reclamos del vecino</option>
        <option value="relevamientos">Relevamientos</option>
      </select>
    </div>
  )
}
