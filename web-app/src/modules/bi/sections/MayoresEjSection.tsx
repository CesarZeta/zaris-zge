import { Cell, Label, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { ChartCard, CenterMsg } from '../components/ui'
import { DonaCentro, Seccion, fmt, legendStyle, pieLabel, tooltipStyle } from '../components/SeccionHeader'
import { useEjTopTipos } from '../hooks/useBi'
import { periodoEnLetras } from '../lib/periodo'
import type { BiFiltros, EjTopTipo } from '../lib/types'
import { PALETA_CATEGORICA } from '../lib/theme'

// Sección MAYORES del tablero Ejecutivo (VL "Mayores incidentes por cantidad y
// tiempo de demora"): top 10 de tipos por volumen y por promedio de días de
// cierre, cada uno con su participación por subárea.

const pct = (v: number | null | undefined) => (v == null ? '—' : `${v}%`)

function varColor(v: number | null | undefined): string {
  if (v == null) return 'var(--fg-3)'
  return v <= 0 ? '#1f8a65' : '#cf2d56'
}
function varTxt(v: number | null | undefined): string {
  if (v == null) return '—'
  return `${v > 0 ? '+' : ''}${v}%`
}

function agruparPorSubarea(rows: EjTopTipo[], metrica: (r: EjTopTipo) => number) {
  const acc = new Map<string, number>()
  for (const r of rows) acc.set(r.subarea, (acc.get(r.subarea) ?? 0) + metrica(r))
  return [...acc.entries()].map(([subarea, total]) => ({ subarea, total })).sort((a, b) => b.total - a.total)
}

function TablaTop({ rows, demora }: { rows: EjTopTipo[]; demora?: boolean }) {
  return (
    <div>
      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={{ ...thStyle, textAlign: 'left', width: 'auto' }}>Tipo de incidente</th>
            <th style={{ ...thStyle, textAlign: 'left', width: 'auto' }}>Subárea</th>
            <th style={thStyle}>Total</th>
            <th style={thStyle}>% Var</th>
            <th style={thStyle}>% Cierre</th>
            <th style={thStyle}>{demora ? 'Cierre prom. días' : 'Prom. días'}</th>
            <th style={thStyle}>% Sat</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id_tipo ?? r.tipo}>
              <td style={{ ...tdStyle, textAlign: 'left', whiteSpace: 'normal', overflowWrap: 'anywhere' }}>{r.tipo}</td>
              <td style={{ ...tdStyle, textAlign: 'left', whiteSpace: 'normal', overflowWrap: 'anywhere', color: 'var(--fg-2)' }}>{r.subarea}</td>
              <td style={{ ...tdStyle, fontWeight: 600 }}>{fmt(r.total)}</td>
              <td style={{ ...tdStyle, color: varColor(r.var_pct) }}>{varTxt(r.var_pct)}</td>
              <td style={{ ...tdStyle, color: '#2f7fd1' }}>{pct(r.pct_cierre)}</td>
              <td style={{ ...tdStyle, fontWeight: demora ? 700 : 500 }}>{r.prom_dias ?? '—'}</td>
              <td style={{ ...tdStyle, color: '#6a1b9a' }}>{pct(r.pct_sat)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function DonaSubareas({ data }: { data: Array<{ subarea: string; total: number }> }) {
  return (
    <ResponsiveContainer>
      <PieChart>
        <Pie data={data} dataKey="total" nameKey="subarea" innerRadius="50%" outerRadius="78%" paddingAngle={2} label={pieLabel} labelLine={false}>
          <Label content={DonaCentro} position="center" value={data.reduce((a, x) => a + x.total, 0)} />
          {data.map((_, i) => <Cell key={i} fill={PALETA_CATEGORICA[i % PALETA_CATEGORICA.length]} />)}
        </Pie>
        <Tooltip contentStyle={tooltipStyle} />
        <Legend wrapperStyle={legendStyle} />
      </PieChart>
    </ResponsiveContainer>
  )
}

export function MayoresEjSection({ filtros }: { filtros: BiFiltros }) {
  const porCantidad = useEjTopTipos(filtros, 'cantidad', 10)
  const porDemora = useEjTopTipos(filtros, 'demora', 10)

  return (
    <Seccion
      id="mayores"
      titulo="Mayores incidentes"
      periodo={periodoEnLetras(filtros).actual}
    >
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 3fr) minmax(300px, 2fr)', gap: 16 }}>
        <ChartCard title="Mayores incidentes por cantidad" height={430}>
          {porCantidad.isLoading ? (
            <CenterMsg>Cargando…</CenterMsg>
          ) : !porCantidad.data?.length ? (
            <CenterMsg>Sin datos.</CenterMsg>
          ) : (
            <div style={{ height: '100%', overflowY: 'auto', overflowX: 'hidden', paddingRight: 10 }}>
              <TablaTop rows={porCantidad.data} />
            </div>
          )}
        </ChartCard>
        <ChartCard title="Participación por subárea (top 10)" height={430}>
          {porCantidad.isLoading ? (
            <CenterMsg>Cargando…</CenterMsg>
          ) : !porCantidad.data?.length ? (
            <CenterMsg>Sin datos.</CenterMsg>
          ) : (
            <DonaSubareas data={agruparPorSubarea(porCantidad.data, (r) => r.total)} />
          )}
        </ChartCard>

        <ChartCard title="Mayores tiempos de respuesta" height={430}>
          {porDemora.isLoading ? (
            <CenterMsg>Cargando…</CenterMsg>
          ) : !porDemora.data?.length ? (
            <CenterMsg>Sin cierres en el período (el promedio de días requiere reclamos resueltos).</CenterMsg>
          ) : (
            <div style={{ height: '100%', overflowY: 'auto', overflowX: 'hidden', paddingRight: 10 }}>
              <TablaTop rows={porDemora.data} demora />
            </div>
          )}
        </ChartCard>
        <ChartCard title="Demora acumulada por subárea (top 10)" height={430}>
          {porDemora.isLoading ? (
            <CenterMsg>Cargando…</CenterMsg>
          ) : !porDemora.data?.length ? (
            <CenterMsg>Sin datos.</CenterMsg>
          ) : (
            <DonaSubareas data={agruparPorSubarea(porDemora.data, (r) => r.prom_dias ?? 0)} />
          )}
        </ChartCard>
      </div>
    </Seccion>
  )
}

const tableStyle: React.CSSProperties = {
  width: '100%', borderCollapse: 'collapse',
  fontFamily: 'var(--font-display)', fontSize: '0.8rem', color: 'var(--fg-1)',
}
// Sin scroll horizontal (César 2026-09-01): numéricas a ancho mínimo (width 1%);
// las columnas de nombres (Tipo/Subárea) absorben el resto y envuelven. Los
// encabezados NO llevan nowrap: en cards angostas ("Cierre prom. días") se parten
// en dos líneas en vez de imponer un mínimo que desborda.
const thStyle: React.CSSProperties = {
  textAlign: 'right', padding: '6px 6px', fontSize: '0.68rem', textTransform: 'uppercase',
  letterSpacing: '0.05em', color: 'var(--fg-3)', fontWeight: 700,
  borderBottom: '2px solid var(--zaris-orange)', width: '1%',
  position: 'sticky', top: 0, background: 'var(--surface-100)',
}
const tdStyle: React.CSSProperties = {
  textAlign: 'right', padding: '6px 6px', whiteSpace: 'nowrap',
  borderBottom: '1px solid var(--border-primary)',
}
