import type { ReactNode } from 'react'
import { KpiCard } from './ui'
import type { Comparativo } from '../lib/types'
import { COLOR_TRAMO_0_3, COLOR_TRAMO_MAS7 } from '../lib/theme'

// Encabezado de cada sección de la página única del Operativo (2026-08-30):
// ancla para el índice fijo, título, subtítulo y el botón "Exportar tickets"
// que reemplaza a las tablas de detalle (decisión de César: la tabla de Power BI
// se resume en exportar los tickets filtrados).
export function Seccion({
  id,
  titulo,
  subtitulo,
  periodo,
  onExport,
  exportando,
  exportDisabled,
  exportLabel = 'Exportar tickets filtrados',
  children,
}: {
  id: string
  titulo: string
  subtitulo?: string
  /** Período analizado EN LETRAS al costado del título (Ejecutivo, César
   *  2026-08-30); reemplaza al subtítulo descriptivo. */
  periodo?: string
  onExport?: () => void
  exportando?: boolean
  exportDisabled?: boolean
  exportLabel?: string
  children: ReactNode
}) {
  const disabled = !!exportando || !!exportDisabled
  return (
    // scroll-margin = alto real de la barra fija (var que setea OperativoPage) para
    // que, al saltar desde el índice, el título de la sección quede visible debajo.
    // gap 32 = el doble entre visualizaciones (César); la fila de KPIs mantiene su gap interno.
    <section id={id} data-seccion style={{ scrollMarginTop: 'calc(var(--bi-sticky, 200px) + 10px)', display: 'flex', flexDirection: 'column', gap: 32 }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', borderBottom: '2px solid var(--zaris-orange)', paddingBottom: 6 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
            <h2 style={{ fontFamily: 'var(--font-display)', fontSize: '1.15rem', fontWeight: 600, letterSpacing: '-0.3px', color: 'var(--fg-1)', margin: 0 }}>
              {titulo}
            </h2>
            {periodo && (
              <span style={{ fontFamily: 'var(--font-display)', fontSize: '0.88rem', color: 'var(--fg-2)' }}>
                — período analizado: <strong style={{ color: 'var(--fg-1)' }}>{periodo}</strong>
              </span>
            )}
          </div>
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

export function totalDe(xs: ReadonlyArray<{ total: number }>): number {
  return xs.reduce((a, x) => a + (x.total ?? 0), 0)
}

export function fmt(n: number | undefined): string {
  return n == null ? '—' : n.toLocaleString('es-AR')
}

// Los dos KPIs comparativos que llevan TODAS las secciones (César 2026-08-30):
// promedio mensual del último año y el mismo valor del período del año anterior.
export function KpisComparativos({ c, etiqueta }: { c?: Comparativo; etiqueta: string }) {
  const var_ = c?.var_pct ?? 0
  const pos = var_ >= 0
  return (
    <>
      <KpiCard
        label={`Prom. mensual últ. año`}
        value={c ? c.prom_mensual_12m.toLocaleString('es-AR') : '—'}
        sub={c ? `${etiqueta}/mes · ${c.total_12m.toLocaleString('es-AR')} en 12 meses` : undefined}
      />
      <KpiCard
        label="Mismo período año anterior"
        value={c ? c.anio_anterior.toLocaleString('es-AR') : '—'}
        accent={c ? (pos ? COLOR_TRAMO_0_3 : COLOR_TRAMO_MAS7) : 'var(--fg-1)'}
        sub={c ? `${pos ? '+' : ''}${var_}% vs. ${c.periodo_anterior}` : undefined}
      />
    </>
  )
}

// Total (en cantidad, no %) en el centro de cada dona (César 2026-08-30). Se usa
// como <Label content={DonaCentro} position="center" /> dentro del <Pie>; recharts
// pasa el viewBox {cx, cy} del centro. El valor viene por `value`.
// (viewBox tipado laxo: recharts pasa CartesianViewBox | PolarViewBox; acá solo importa el polar.)
export function DonaCentro(props: { viewBox?: unknown; value?: unknown }) {
  const { cx = 0, cy = 0 } = (props.viewBox ?? {}) as { cx?: number; cy?: number }
  const v = props.value as number | string | undefined
  if (v == null) return null
  const txt = typeof v === 'number' ? v.toLocaleString('es-AR') : String(v)
  return (
    <g>
      <text x={cx} y={cy - 6} textAnchor="middle" dominantBaseline="central"
        fontFamily="var(--font-display)" fontSize={26} fontWeight={700} fill="var(--fg-1)">
        {txt}
      </text>
      <text x={cx} y={cy + 16} textAnchor="middle" dominantBaseline="central"
        fontFamily="var(--font-display)" fontSize={11} fontWeight={600} fill="var(--fg-3)" letterSpacing="0.06em">
        TOTAL
      </text>
    </g>
  )
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
