import type { ReactNode } from 'react'

// Encabezado de cada sección de la página única del Operativo (2026-08-30):
// ancla para el índice fijo, título, subtítulo y el botón "Exportar tickets"
// que reemplaza a las tablas de detalle (decisión de César: la tabla de Power BI
// se resume en exportar los tickets filtrados).
export function Seccion({
  id,
  titulo,
  subtitulo,
  onExport,
  exportando,
  exportDisabled,
  exportLabel = 'Exportar tickets filtrados',
  children,
}: {
  id: string
  titulo: string
  subtitulo?: string
  onExport?: () => void
  exportando?: boolean
  exportDisabled?: boolean
  exportLabel?: string
  children: ReactNode
}) {
  const disabled = !!exportando || !!exportDisabled
  return (
    <section id={id} style={{ scrollMarginTop: 150, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', borderBottom: '2px solid var(--zaris-orange)', paddingBottom: 6 }}>
        <div>
          <h2 style={{ fontFamily: 'var(--font-display)', fontSize: '1.15rem', fontWeight: 600, letterSpacing: '-0.3px', color: 'var(--fg-1)', margin: 0 }}>
            {titulo}
          </h2>
          {subtitulo && <p style={{ fontSize: '0.8rem', color: 'var(--fg-3)', margin: '2px 0 0' }}>{subtitulo}</p>}
        </div>
        {onExport && (
          <button onClick={onExport} disabled={disabled} style={exportBtnStyle(disabled)} title="Descarga un CSV con los tickets que responden a los filtros globales">
            {exportando ? 'Exportando…' : `↓ ${exportLabel}`}
          </button>
        )}
      </div>
      {children}
    </section>
  )
}

export function exportBtnStyle(disabled: boolean): React.CSSProperties {
  return {
    fontFamily: 'var(--font-display)', fontSize: '0.78rem', fontWeight: 600,
    padding: '6px 14px', borderRadius: 8,
    border: `1px solid ${disabled ? 'var(--border-medium)' : 'var(--zaris-orange)'}`,
    background: 'transparent',
    color: disabled ? 'var(--fg-3)' : 'var(--zaris-orange)',
    cursor: disabled ? 'default' : 'pointer',
  }
}

// Estilos compartidos por las secciones (tooltip/leyenda/ejes de recharts).
export const AXIS = { fontFamily: 'var(--font-display)', fontSize: 11, fill: 'var(--fg-3)' as const }
export const tooltipStyle: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.8rem', background: 'var(--surface-100)',
  border: '1px solid var(--border-medium)', borderRadius: 8, color: 'var(--fg-1)',
}
export const legendStyle: React.CSSProperties = { fontFamily: 'var(--font-display)', fontSize: '0.78rem' }

export function fmt(n: number | undefined): string {
  return n == null ? '—' : n.toLocaleString('es-AR')
}

// Label de dona (porcentaje + valor) con pastilla de contraste invertible (§13).
export function pieLabel(props: {
  cx?: number; cy?: number; midAngle?: number; outerRadius?: number; percent?: number; value?: number
}) {
  const { cx = 0, cy = 0, midAngle = 0, outerRadius = 0, percent = 0, value } = props
  if (percent < 0.04) return null // ocultar tajadas < 4%
  const RAD = Math.PI / 180
  const r = outerRadius + 22
  const x = cx + r * Math.cos(-midAngle * RAD)
  const y = cy + r * Math.sin(-midAngle * RAD)
  const txt = `${(percent * 100).toFixed(1)}% (${value})`
  const anchorStart = x > cx
  const w = txt.length * 6.2 + 8
  const rx = anchorStart ? x - 4 : x - w + 4
  return (
    <g>
      <rect x={rx} y={y - 9} width={w} height={17} rx={5} fill="var(--fg-1)" fillOpacity={0.82} />
      <text x={x} y={y} textAnchor={anchorStart ? 'start' : 'end'} dominantBaseline="central"
        fontFamily="var(--font-display)" fontSize={11} fontWeight={600} fill="var(--surface-100)">
        {txt}
      </text>
    </g>
  )
}
