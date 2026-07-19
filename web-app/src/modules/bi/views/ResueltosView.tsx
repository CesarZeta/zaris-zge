import { useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { FiltrosBar } from '../components/FiltrosBar'
import { SegLabel, SegLabelH, TotalLabel, TotalLabelH } from '../components/barLabels'
import { ChartCard, CenterMsg, KpiCard } from '../components/ui'
import { exportarCsv, hoyISO } from '../components/exportCsv'
import { biApi } from '../lib/api'
import {
  useEvolucionDias,
  useResueltosDetalle,
  useSlaResumen,
  useTiemposMensual,
  useTiemposPorTipo,
} from '../hooks/useBi'
import type { BiFiltros } from '../lib/types'
import { COLOR_TRAMO_0_3, COLOR_TRAMO_4_7, COLOR_TRAMO_MAS7, labelMes } from '../lib/theme'

const AXIS = { fontFamily: 'var(--font-display)', fontSize: 11, fill: 'var(--fg-3)' as const }
const tooltipStyle: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.8rem', background: 'var(--surface-100)',
  border: '1px solid var(--border-medium)', borderRadius: 8, color: 'var(--fg-1)',
}
const legendStyle: React.CSSProperties = { fontFamily: 'var(--font-display)', fontSize: '0.78rem' }

export function ResueltosView() {
  const [filtros, setFiltros] = useState<BiFiltros>({})

  const sla = useSlaResumen(filtros)
  const tMes = useTiemposMensual(filtros)
  const tTipo = useTiemposPorTipo(filtros, 10)
  const evol = useEvolucionDias(filtros)
  const detalle = useResueltosDetalle(filtros, 50, 0)
  const [exportando, setExportando] = useState(false)

  const s = sla.data
  const difPos = (s?.dif_pct ?? 0) >= 0

  // Exporta TODO el detalle del filtro actual (no solo la página visible).
  async function handleExport() {
    setExportando(true)
    try {
      const { data } = await biApi.resueltosDetalle(filtros, 5000, 0)
      exportarCsv(
        `reclamos_resueltos_${hoyISO()}.csv`,
        [
          { header: 'N° Reclamo', value: (r) => r.nro_reclamo },
          { header: 'Fecha cierre', value: (r) => (r.fecha_cierre ? r.fecha_cierre.slice(0, 10) : '') },
          { header: 'Tipo', value: (r) => r.tipo },
          { header: 'Prioridad', value: (r) => r.prioridad },
          { header: 'Días de cierre', value: (r) => r.dias },
          { header: 'Canal', value: (r) => r.canal },
          { header: 'Área', value: (r) => r.area },
        ],
        data,
      )
    } finally {
      setExportando(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <FiltrosBar filtros={filtros} onChange={setFiltros} />

      {/* KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 12 }}>
        <KpiCard label="Resueltos último mes" value={fmt(s?.resueltos_mes_actual)} accent={COLOR_TRAMO_0_3} />
        <KpiCard
          label="Variación mensual"
          value={s ? `${difPos ? '+' : ''}${s.dif_pct}%` : '—'}
          accent={difPos ? COLOR_TRAMO_0_3 : COLOR_TRAMO_MAS7}
          sub="vs. mes anterior"
        />
        <KpiCard
          label="Tiempo cierre promedio"
          value={s?.dias_cierre_promedio != null ? `${s.dias_cierre_promedio} d` : '—'}
          accent="var(--zaris-orange)"
        />
        <KpiCard
          label="% Dentro de SLA"
          value={s?.pct_dentro_sla != null ? `${s.pct_dentro_sla}%` : '—'}
          accent={COLOR_TRAMO_0_3}
          sub="cierre ≤ SLA del tipo"
        />
        <KpiCard label="Total resueltos" value={fmt(s?.total_resueltos)} sub="con fecha de cierre" />
      </div>

      {/* Tiempos de respuesta por mes (apiladas por tramo) */}
      <ChartCard title="Tiempos de respuesta por mes" height={300}>
        {tMes.isLoading ? (
          <CenterMsg>Cargando…</CenterMsg>
        ) : !tMes.data?.length ? (
          <CenterMsg>Sin reclamos resueltos con fecha de cierre en el período.</CenterMsg>
        ) : (
          <ResponsiveContainer>
            <BarChart data={tMes.data.map((m) => ({ ...m, label: labelMes(m.mes) }))} margin={{ top: 24, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" vertical={false} />
              <XAxis dataKey="label" tick={AXIS} />
              <YAxis tick={AXIS} allowDecimals={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={legendStyle} />
              <Bar dataKey="t0_3" name="0 a 3 días" stackId="a" fill={COLOR_TRAMO_0_3}>
                <LabelList dataKey="t0_3" position="center" content={SegLabel} />
              </Bar>
              <Bar dataKey="t4_7" name="4 a 7 días" stackId="a" fill={COLOR_TRAMO_4_7}>
                <LabelList dataKey="t4_7" position="center" content={SegLabel} />
              </Bar>
              <Bar dataKey="tmas7" name="Más de 7 días" stackId="a" fill={COLOR_TRAMO_MAS7} radius={[4, 4, 0, 0]}>
                <LabelList dataKey="tmas7" position="center" content={SegLabel} />
                <LabelList dataKey="total" position="top" content={TotalLabel} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </ChartCard>

      {/* Fila: tiempos por tipo (horizontal) + evolución días (línea) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 16 }}>
        <ChartCard
          title="Tiempos por tipo de reclamo"
          height={Math.max(240, (tTipo.data?.length ?? 1) * 42 + 60)}
        >
          {tTipo.isLoading ? (
            <CenterMsg>Cargando…</CenterMsg>
          ) : !tTipo.data?.length ? (
            <CenterMsg>Sin datos.</CenterMsg>
          ) : (
            <ResponsiveContainer>
              <BarChart data={tTipo.data} layout="vertical" margin={{ left: 12, right: 28 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" horizontal={false} />
                <XAxis type="number" tick={AXIS} allowDecimals={false} />
                <YAxis type="category" dataKey="tipo" tick={AXIS} width={160} />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={legendStyle} />
                <Bar dataKey="t0_3" name="0 a 3 días" stackId="a" fill={COLOR_TRAMO_0_3}>
                  <LabelList dataKey="t0_3" content={SegLabelH} />
                </Bar>
                <Bar dataKey="t4_7" name="4 a 7 días" stackId="a" fill={COLOR_TRAMO_4_7}>
                  <LabelList dataKey="t4_7" content={SegLabelH} />
                </Bar>
                <Bar dataKey="tmas7" name="Más de 7 días" stackId="a" fill={COLOR_TRAMO_MAS7} radius={[0, 4, 4, 0]}>
                  <LabelList dataKey="tmas7" content={SegLabelH} />
                  <LabelList dataKey="total" position="right" content={TotalLabelH} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard title="Evolución del tiempo de cierre (días promedio)" height={300}>
          {evol.isLoading ? (
            <CenterMsg>Cargando…</CenterMsg>
          ) : !evol.data?.length ? (
            <CenterMsg>Sin datos.</CenterMsg>
          ) : (
            <ResponsiveContainer>
              <LineChart data={evol.data.map((m) => ({ ...m, label: labelMes(m.mes) }))} margin={{ top: 24, right: 24, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" vertical={false} />
                <XAxis dataKey="label" tick={AXIS} />
                <YAxis tick={AXIS} allowDecimals={false} />
                <Tooltip contentStyle={tooltipStyle} />
                <Line
                  type="monotone"
                  dataKey="dias_prom"
                  name="Días promedio"
                  stroke="var(--zaris-orange)"
                  strokeWidth={2.5}
                  dot={{ r: 4, fill: 'var(--zaris-orange)' }}
                >
                  <LabelList dataKey="dias_prom" position="top" content={LineLabel} />
                </Line>
              </LineChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      </div>

      {/* Tabla detalle */}
      <ChartCard
        title="Detalle de reclamos resueltos"
        height={undefined}
        action={
          <button
            onClick={handleExport}
            disabled={exportando || !detalle.data?.data?.length}
            style={exportBtnStyle(exportando || !detalle.data?.data?.length)}
          >
            {exportando ? 'Exportando…' : '↓ Exportar CSV'}
          </button>
        }
      >
        {detalle.isLoading ? (
          <CenterMsg>Cargando…</CenterMsg>
        ) : !detalle.data?.data?.length ? (
          <CenterMsg>Sin reclamos resueltos con fecha de cierre.</CenterMsg>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={tableStyle}>
              <thead>
                <tr>
                  {['N° Reclamo', 'Cierre', 'Tipo', 'Prioridad', 'Días', 'Área'].map((h) => (
                    <th key={h} style={thStyle}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {detalle.data.data.map((r, i) => (
                  <tr key={i} style={{ borderTop: '1px solid var(--border-primary)' }}>
                    <td style={tdStyle}>{r.nro_reclamo ?? '—'}</td>
                    <td style={tdStyle}>{r.fecha_cierre ? r.fecha_cierre.slice(0, 10) : '—'}</td>
                    <td style={tdStyle}>{r.tipo}</td>
                    <td style={tdStyle}>{r.prioridad}</td>
                    <td style={{ ...tdStyle, fontWeight: 700, color: diasColor(r.dias) }}>{r.dias}</td>
                    <td style={tdStyle}>{r.area}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </ChartCard>
    </div>
  )
}

function fmt(n: number | undefined): string {
  return n == null ? '—' : n.toLocaleString('es-AR')
}

function diasColor(d: number): string {
  if (d <= 3) return COLOR_TRAMO_0_3
  if (d <= 7) return '#b58900'
  return COLOR_TRAMO_MAS7
}

// Label de punto de línea con pastilla.
function LineLabel(p: { x?: string | number; y?: string | number; value?: string | number }) {
  const x = Number(p.x ?? 0), y = Number(p.y ?? 0), value = p.value
  if (value == null) return null
  const txt = String(value)
  const w = txt.length * 7 + 10
  return (
    <g>
      {/* Pastilla de contraste invertible: fg-1/surface-100 se dan vuelta en dark (§13) */}
      <rect x={x - w / 2} y={y - 22} width={w} height={16} rx={5} fill="var(--fg-1)" fillOpacity={0.82} />
      <text x={x} y={y - 14} textAnchor="middle" dominantBaseline="central"
        fontFamily="var(--font-display)" fontSize={11} fontWeight={700} fill="var(--surface-100)">
        {txt}
      </text>
    </g>
  )
}

const tableStyle: React.CSSProperties = {
  width: '100%', borderCollapse: 'collapse', fontFamily: 'var(--font-display)', fontSize: '0.82rem',
}
const thStyle: React.CSSProperties = {
  textAlign: 'left', padding: '8px 10px', color: 'var(--fg-3)', fontWeight: 600,
  textTransform: 'uppercase', fontSize: '0.7rem', letterSpacing: '0.03em', borderBottom: '1px solid var(--border-medium)',
}
const tdStyle: React.CSSProperties = { padding: '8px 10px', color: 'var(--fg-1)' }

function exportBtnStyle(disabled: boolean): React.CSSProperties {
  return {
    fontFamily: 'var(--font-display)', fontSize: '0.78rem', fontWeight: 600,
    padding: '5px 12px', borderRadius: 8,
    border: `1px solid ${disabled ? 'var(--border-medium)' : 'var(--zaris-orange)'}`,
    background: 'transparent',
    color: disabled ? 'var(--fg-3)' : 'var(--zaris-orange)',
    cursor: disabled ? 'default' : 'pointer',
  }
}
