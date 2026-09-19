import type { ReactNode } from 'react'

// Helpers compartidos por las secciones del tablero de ATENCIÓN (F6, 2026-09-19):
// formateo de porcentajes / minutos / variaciones, el triangulito de variación
// vs período anterior (mismo criterio que la matriz del Ejecutivo) y la tabla
// sin scroll horizontal del módulo (regla de César 2026-09-01).

export const pct = (v: number | null | undefined) => (v == null ? '—' : `${v}%`)
export const minutos = (v: number | null | undefined) => (v == null ? '—' : `${v} min`)
export const num = (v: number | null | undefined) => (v == null ? '—' : v.toLocaleString('es-AR'))

export function varTxt(v: number | null | undefined): string {
  if (v == null) return '—'
  return `${v > 0 ? '+' : ''}${v}%`
}

// Variación de VOLUMEN (turnos otorgados, derivaciones, reservas): más no es ni
// bueno ni malo, es demanda atendida → color neutro. Para indicadores con
// valoración (ausentismo, espera) se usa Tri.
export const VAR_NEUTRO = 'var(--fg-1)'

// Triangulito de variación vs período anterior: dirección real (▲ subió / ▼
// bajó), color por VALORACIÓN (verde mejora, rojo empeora; `invertir` para
// "menos es mejor": ausentismo, espera, cancelación). ■ gris sin variación o sin
// dato previo. Copiado del Ejecutivo (ResumenEjSection) para no cruzar imports
// entre tableros.
export function Tri({ actual, anterior, invertir }: {
  actual: number | null | undefined
  anterior: number | null | undefined
  invertir?: boolean
}) {
  const base: React.CSSProperties = { marginLeft: 5, fontSize: '0.6rem', verticalAlign: 'middle' }
  if (actual == null || anterior == null) {
    return <span aria-hidden="true" style={{ ...base, color: 'var(--fg-3)', opacity: 0.55 }} title="Sin dato del período anterior">■</span>
  }
  const delta = actual - anterior
  if (Math.abs(delta) < 0.05) {
    return <span aria-hidden="true" style={{ ...base, color: 'var(--fg-3)' }} title={`Sin variación (anterior: ${anterior})`}>■</span>
  }
  const mejora = invertir ? delta < 0 : delta > 0
  return (
    <span aria-hidden="true" style={{ ...base, color: mejora ? '#1f8a65' : '#cf2d56' }} title={`Período anterior: ${anterior}`}>
      {delta > 0 ? '▲' : '▼'}
    </span>
  )
}

// ── Tabla sin scroll horizontal ───────────────────────────────────────────────
// Las columnas numéricas van a su ancho mínimo (width 1%, nowrap en el td) y las
// columnas de TEXTO (`texto: true`) absorben el resto envolviendo con
// overflowWrap 'anywhere' (el único valor que reduce el min-content). Los th NO
// llevan nowrap: en cards angostas se parten en dos líneas.
export interface ColumnaAt<T> {
  header: string
  render: (fila: T) => ReactNode
  /** Columna de nombres: alineada a la izquierda y envuelve. */
  texto?: boolean
  color?: string
}

export function TablaAt<T>({ columnas, filas, keyOf, total, maxAlto }: {
  columnas: ColumnaAt<T>[]
  filas: T[]
  keyOf: (fila: T) => string | number
  /** Fila de totales (opcional), se pinta al pie con fondo. */
  total?: T
  /** Alto máximo con scroll VERTICAL (nunca horizontal). */
  maxAlto?: number
}) {
  const tabla = (
    <table style={tableStyle}>
      <thead>
        <tr>
          {columnas.map((c) => (
            <th key={c.header} style={c.texto ? thTextoStyle : thStyle}>{c.header}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {filas.map((f) => (
          <tr key={keyOf(f)}>
            {columnas.map((c) => (
              <td key={c.header} style={{ ...(c.texto ? tdTextoStyle : tdStyle), color: c.color }}>{c.render(f)}</td>
            ))}
          </tr>
        ))}
        {total && (
          <tr style={{ background: 'var(--surface-400)' }}>
            {columnas.map((c) => (
              <td key={c.header} style={{ ...(c.texto ? tdTextoStyle : tdStyle), fontWeight: 700 }}>{c.render(total)}</td>
            ))}
          </tr>
        )}
      </tbody>
    </table>
  )
  if (maxAlto) {
    return <div style={{ maxHeight: maxAlto, overflowY: 'auto', overflowX: 'hidden', paddingRight: 10 }}>{tabla}</div>
  }
  return tabla
}

export const cardStyle: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 12, padding: '14px 16px', minWidth: 0,
}
export const h3Style: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.92rem', fontWeight: 600,
  color: 'var(--fg-1)', margin: '0 0 4px',
}
export const notaStyle: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.72rem', color: 'var(--fg-3)',
  margin: '0 0 10px',
}

const tableStyle: React.CSSProperties = {
  width: '100%', borderCollapse: 'collapse',
  fontFamily: 'var(--font-display)', fontSize: '0.8rem', color: 'var(--fg-1)',
}
const thStyle: React.CSSProperties = {
  textAlign: 'right', padding: '6px 6px', fontSize: '0.68rem', textTransform: 'uppercase',
  letterSpacing: '0.05em', color: 'var(--fg-3)', fontWeight: 700,
  borderBottom: '2px solid var(--zaris-orange)', width: '1%',
  position: 'sticky', top: 0, background: 'var(--surface-100)',
}
const thTextoStyle: React.CSSProperties = { ...thStyle, textAlign: 'left', width: 'auto' }
const tdStyle: React.CSSProperties = {
  textAlign: 'right', padding: '6px 6px', whiteSpace: 'nowrap',
  borderBottom: '1px solid var(--border-primary)',
}
const tdTextoStyle: React.CSSProperties = {
  ...tdStyle, textAlign: 'left', whiteSpace: 'normal', overflowWrap: 'anywhere',
}
