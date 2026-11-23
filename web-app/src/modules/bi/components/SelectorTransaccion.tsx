import type { CSSProperties } from 'react'
import type { ClaseTransaccion } from '../lib/types'

/** Etiqueta para el resumen del panel contraído (vacío = reclamos, lo de siempre). */
export function labelTransaccion(clase?: ClaseTransaccion): string | undefined {
  return clase === 'relevamientos' ? 'Relevamientos' : undefined
}

/**
 * Tipo de transacción (mig 141): reclamos o relevamientos. No es el canal: el canal es la
 * interfaz por la que se registró (call center, app del vecino, portal, app de agentes).
 * Datos los cuenta APARTE (decisión de César 2026-11-22): nunca se mezclan.
 */
export function SelectorTransaccion({
  value, onChange, labelStyle, inputStyle,
}: {
  value?: ClaseTransaccion
  onChange: (v: ClaseTransaccion | undefined) => void
  labelStyle: CSSProperties
  inputStyle: CSSProperties
}) {
  return (
    <div>
      <label style={labelStyle}>Transacción</label>
      <select
        value={value ?? 'reclamos'}
        onChange={(e) => onChange(e.target.value === 'relevamientos' ? 'relevamientos' : undefined)}
        style={inputStyle}
        title="Los relevamientos los inicia un agente municipal y se cuentan aparte de los reclamos del vecino"
      >
        <option value="reclamos">Reclamos</option>
        <option value="relevamientos">Relevamientos</option>
      </select>
    </div>
  )
}
