import { useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { FiltrosBar } from '../components/FiltrosBar'
import { HistogramaTemporal } from '../components/HistogramaTemporal'
import { SegLabelH, TotalLabelH } from '../components/barLabels'
import { ChartCard, CenterMsg, KpiCard } from '../components/ui'
import { usePorArea, usePorCanal, usePorEstado, useResumen } from '../hooks/useBi'
import { biApi } from '../lib/api'
import type { BiFiltros } from '../lib/types'
import {
  COLOR_CANCELADO,
  COLOR_PENDIENTE,
  COLOR_RESUELTO,
  PALETA_CATEGORICA,
  colorEstado,
  labelCanal,
} from '../lib/theme'

const AXIS = { fontFamily: 'var(--font-display)', fontSize: 11, fill: 'var(--fg-3)' as const }

export function ResumenView() {
  const [filtros, setFiltros] = useState<BiFiltros>({})

  const resumen = useResumen(filtros)
  const porEstado = usePorEstado(filtros)
  const porCanal = usePorCanal(filtros)
  const porArea = usePorArea(filtros)

  const r = resumen.data

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <FiltrosBar filtros={filtros} onChange={setFiltros} />

      {/* KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12 }}>
        <KpiCard label="Reclamos totales" value={fmt(r?.total)} />
        <KpiCard label="Resueltos" value={fmt(r?.resueltos)} accent={COLOR_RESUELTO} />
        <KpiCard label="Pendientes" value={fmt(r?.pendientes)} accent={COLOR_PENDIENTE} />
        <KpiCard label="Cancelados" value={fmt(r?.cancelados)} accent={COLOR_CANCELADO} />
        <KpiCard
          label="% Cumplimiento"
          value={r ? `${r.pct_cumplido}%` : '—'}
          accent="var(--zaris-orange)"
          sub="resueltos / cerrados"
        />
        <KpiCard label="Subreclamos" value={fmt(r?.subreclamos)} />
      </div>

      {/* Fila 1: histograma temporal con toggle Mes/Día + drill-down */}
      <HistogramaTemporal
        tituloBase="Reclamos ingresados"
        cacheKey="resumen"
        filtros={filtros}
        series={[
          { key: 'resueltos', name: 'Resueltos', color: COLOR_RESUELTO },
          { key: 'pendientes', name: 'Pendientes', color: COLOR_PENDIENTE },
          { key: 'cancelados', name: 'Cancelados', color: COLOR_CANCELADO },
        ]}
        fetchMensual={(f) => biApi.mensual(f)}
        fetchDiario={(mes, f) => biApi.diario(mes, f)}
      />

      {/* Fila 2: dona estado + dona canal */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
        <ChartCard title="Composición por estado">
          {porEstado.isLoading ? (
            <CenterMsg>Cargando…</CenterMsg>
          ) : !porEstado.data?.length ? (
            <CenterMsg>Sin datos.</CenterMsg>
          ) : (
            <ResponsiveContainer>
              <PieChart>
                <Pie
                  data={porEstado.data}
                  dataKey="total"
                  nameKey="estado"
                  innerRadius="50%"
                  outerRadius="78%"
                  paddingAngle={2}
                  label={pieLabel}
                  labelLine={false}
                >
                  {porEstado.data.map((e) => (
                    <Cell key={e.estado} fill={colorEstado(e.estado)} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={legendStyle} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard title="Reclamos por canal de origen">
          {porCanal.isLoading ? (
            <CenterMsg>Cargando…</CenterMsg>
          ) : !porCanal.data?.length ? (
            <CenterMsg>Sin datos.</CenterMsg>
          ) : (
            <ResponsiveContainer>
              <PieChart>
                <Pie
                  data={porCanal.data.map((c) => ({ ...c, label: labelCanal(c.canal) }))}
                  dataKey="total"
                  nameKey="label"
                  innerRadius="50%"
                  outerRadius="78%"
                  paddingAngle={2}
                  label={pieLabel}
                  labelLine={false}
                >
                  {porCanal.data.map((_, i) => (
                    <Cell key={i} fill={PALETA_CATEGORICA[i % PALETA_CATEGORICA.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={legendStyle} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      </div>

      {/* Fila 3: barras horizontales por área */}
      <ChartCard title="Reclamos por área y estado" height={Math.max(220, (porArea.data?.length ?? 1) * 48 + 60)}>
        {porArea.isLoading ? (
          <CenterMsg>Cargando…</CenterMsg>
        ) : !porArea.data?.length ? (
          <CenterMsg>Sin datos.</CenterMsg>
        ) : (
          <ResponsiveContainer>
            <BarChart data={porArea.data} layout="vertical" margin={{ left: 12, right: 24 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" horizontal={false} />
              <XAxis type="number" tick={AXIS} allowDecimals={false} />
              <YAxis type="category" dataKey="area" tick={AXIS} width={150} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={legendStyle} />
              <Bar dataKey="resueltos" name="Resueltos" stackId="a" fill={COLOR_RESUELTO}>
                <LabelList dataKey="resueltos" content={SegLabelH} />
              </Bar>
              <Bar dataKey="pendientes" name="Pendientes" stackId="a" fill={COLOR_PENDIENTE}>
                <LabelList dataKey="pendientes" content={SegLabelH} />
              </Bar>
              <Bar dataKey="cancelados" name="Cancelados" stackId="a" fill={COLOR_CANCELADO} radius={[0, 4, 4, 0]}>
                <LabelList dataKey="cancelados" content={SegLabelH} />
                <LabelList dataKey="total" position="right" content={TotalLabelH} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </ChartCard>
    </div>
  )
}

function fmt(n: number | undefined): string {
  return n == null ? '—' : n.toLocaleString('es-AR')
}

// ── Label de dona (porcentaje + valor) ──────────────────────────────────────────
function pieLabel(props: {
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
      {/* Pastilla de contraste invertible: fg-1/surface-100 se dan vuelta en dark (§13) */}
      <rect x={rx} y={y - 9} width={w} height={17} rx={5} fill="var(--fg-1)" fillOpacity={0.82} />
      <text x={x} y={y} textAnchor={anchorStart ? 'start' : 'end'} dominantBaseline="central"
        fontFamily="var(--font-display)" fontSize={11} fontWeight={600} fill="var(--surface-100)">
        {txt}
      </text>
    </g>
  )
}

const tooltipStyle: React.CSSProperties = {
  fontFamily: 'var(--font-display)',
  fontSize: '0.8rem',
  background: 'var(--surface-100)',
  border: '1px solid var(--border-medium)',
  borderRadius: 8,
  color: 'var(--fg-1)',
}
const legendStyle: React.CSSProperties = {
  fontFamily: 'var(--font-display)',
  fontSize: '0.78rem',
}
