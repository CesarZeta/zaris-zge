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
import { TotalLabelH } from '../components/barLabels'
import { ChartCard, CenterMsg, KpiCard } from '../components/ui'
import { exportarCsv, hoyISO } from '../components/exportCsv'
import { biApi } from '../lib/api'
import {
  usePendientesDetalle,
  usePendientesGeo,
  usePendientesPorTipo,
  usePendientesResumen,
} from '../hooks/useBi'
import { DashboardMap } from '../../dashboard/components/DashboardMap'
import type { GeoReclamo } from '../../dashboard/hooks/useDashboardData'
import type { BiFiltros } from '../lib/types'
import {
  COLOR_TRAMO_0_3,
  COLOR_TRAMO_4_7,
  COLOR_TRAMO_MAS7,
  colorEstado,
} from '../lib/theme'

const AXIS = { fontFamily: 'var(--font-display)', fontSize: 11, fill: 'var(--fg-3)' as const }
const tooltipStyle: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.8rem', background: 'var(--surface-100)',
  border: '1px solid var(--border-medium)', borderRadius: 8, color: 'var(--fg-1)',
}
const legendStyle: React.CSSProperties = { fontFamily: 'var(--font-display)', fontSize: '0.78rem' }

export function PendientesView() {
  const [filtros, setFiltros] = useState<BiFiltros>({})
  const [exportando, setExportando] = useState(false)

  const resumen = usePendientesResumen(filtros)
  const porTipo = usePendientesPorTipo(filtros, 10)
  const detalle = usePendientesDetalle(filtros, 50, 0)
  const geo = usePendientesGeo(filtros)

  const r = resumen.data

  const demora = r
    ? [
        { tramo: '0 a 3 días', total: r.t0_3, color: COLOR_TRAMO_0_3 },
        { tramo: '4 a 7 días', total: r.t4_7, color: COLOR_TRAMO_4_7 },
        { tramo: 'Más de 7 días', total: r.tmas7, color: COLOR_TRAMO_MAS7 },
      ].filter((d) => d.total > 0)
    : []

  async function handleExport() {
    setExportando(true)
    try {
      const { data } = await biApi.pendientesDetalle(filtros, 10000, 0)
      exportarCsv(
        `reclamos_pendientes_${hoyISO()}.csv`,
        [
          { header: 'N° Reclamo', value: (d) => d.nro_reclamo },
          { header: 'Fecha alta', value: (d) => (d.fecha_alta ? d.fecha_alta.slice(0, 10) : '') },
          { header: 'Tipo', value: (d) => d.tipo },
          { header: 'Prioridad', value: (d) => d.prioridad },
          { header: 'Estado', value: (d) => d.estado },
          { header: 'Días de demora', value: (d) => d.dias_demora },
          { header: 'Canal', value: (d) => d.canal },
          { header: 'Área', value: (d) => d.area },
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
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
        <KpiCard label="Total pendientes" value={fmt(r?.total)} accent="var(--zaris-orange)" />
        <KpiCard
          label="Demora promedio"
          value={r?.dias_demora_promedio != null ? `${r.dias_demora_promedio} d` : '—'}
          accent={COLOR_TRAMO_4_7}
          sub="desde el ingreso"
        />
        <KpiCard label="Hasta 3 días" value={fmt(r?.t0_3)} accent={COLOR_TRAMO_0_3} />
        <KpiCard label="4 a 7 días" value={fmt(r?.t4_7)} accent={COLOR_TRAMO_4_7} />
        <KpiCard label="Más de 7 días" value={fmt(r?.tmas7)} accent={COLOR_TRAMO_MAS7} />
      </div>

      {/* Pendientes por mes — histograma con toggle Mes/Día + total + drill (estándar) */}
      <HistogramaTemporal
        tituloBase="Pendientes ingresados"
        cacheKey="pendientes"
        filtros={filtros}
        series={[
          { key: 'sin_asignar', name: 'Sin asignar', color: colorEstado('Sin asignar') },
          { key: 'en_gestion', name: 'En gestión', color: colorEstado('En gestión') },
          { key: 'en_espera', name: 'En espera', color: colorEstado('En espera') },
          { key: 'en_auditoria', name: 'En auditoría', color: colorEstado('En auditoría') },
        ]}
        fetchMensual={(f) => biApi.pendientesMensual(f)}
        fetchDiario={(mes, f) => biApi.pendientesDiario(mes, f)}
      />

      {/* Donas: composición por demora + por estado */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
        <ChartCard title="Composición por tiempo de demora">
          {resumen.isLoading ? (
            <CenterMsg>Cargando…</CenterMsg>
          ) : !demora.length ? (
            <CenterMsg>Sin pendientes.</CenterMsg>
          ) : (
            <ResponsiveContainer>
              <PieChart>
                <Pie data={demora} dataKey="total" nameKey="tramo" innerRadius="50%" outerRadius="78%" paddingAngle={2} label={pieLabel} labelLine={false}>
                  {demora.map((d) => (
                    <Cell key={d.tramo} fill={d.color} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={legendStyle} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard title="Composición por estado">
          {resumen.isLoading ? (
            <CenterMsg>Cargando…</CenterMsg>
          ) : !r?.por_estado?.length ? (
            <CenterMsg>Sin pendientes.</CenterMsg>
          ) : (
            <ResponsiveContainer>
              <PieChart>
                <Pie data={r.por_estado} dataKey="total" nameKey="estado" innerRadius="50%" outerRadius="78%" paddingAngle={2} label={pieLabel} labelLine={false}>
                  {r.por_estado.map((e) => (
                    <Cell key={e.estado} fill={colorEstado(e.estado)} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={legendStyle} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      </div>

      {/* Ranking por tipo */}
      <ChartCard title="Ranking de pendientes por tipo" height={Math.max(220, (porTipo.data?.length ?? 1) * 42 + 60)}>
        {porTipo.isLoading ? (
          <CenterMsg>Cargando…</CenterMsg>
        ) : !porTipo.data?.length ? (
          <CenterMsg>Sin datos.</CenterMsg>
        ) : (
          <ResponsiveContainer>
            <BarChart data={porTipo.data} layout="vertical" margin={{ left: 12, right: 32 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" horizontal={false} />
              <XAxis type="number" tick={AXIS} allowDecimals={false} />
              <YAxis type="category" dataKey="tipo" tick={AXIS} width={180} />
              <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(245,78,0,0.06)' }} />
              <Bar dataKey="total" name="Pendientes" fill="var(--zaris-orange)" radius={[0, 4, 4, 0]}>
                <LabelList dataKey="total" position="right" content={TotalLabelH} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </ChartCard>

      {/* Tabla detalle con export */}
      <ChartCard
        title="Detalle de reclamos pendientes"
        height={undefined}
        action={
          <button onClick={handleExport} disabled={exportando || !detalle.data?.data?.length} style={exportBtnStyle(exportando || !detalle.data?.data?.length)}>
            {exportando ? 'Exportando…' : '↓ Exportar CSV'}
          </button>
        }
      >
        {detalle.isLoading ? (
          <CenterMsg>Cargando…</CenterMsg>
        ) : !detalle.data?.data?.length ? (
          <CenterMsg>Sin reclamos pendientes.</CenterMsg>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={tableStyle}>
              <thead>
                <tr>
                  {['N° Reclamo', 'Alta', 'Tipo', 'Prioridad', 'Estado', 'Demora (días)', 'Área'].map((h) => (
                    <th key={h} style={thStyle}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {detalle.data.data.map((d, i) => (
                  <tr key={i} style={{ borderTop: '1px solid var(--border-primary)' }}>
                    <td style={tdStyle}>{d.nro_reclamo ?? '—'}</td>
                    <td style={tdStyle}>{d.fecha_alta ? d.fecha_alta.slice(0, 10) : '—'}</td>
                    <td style={tdStyle}>{d.tipo}</td>
                    <td style={tdStyle}>{d.prioridad}</td>
                    <td style={tdStyle}>
                      <span style={{ color: colorEstado(d.estado), fontWeight: 600 }}>{d.estado}</span>
                    </td>
                    <td style={{ ...tdStyle, fontWeight: 700, color: demoraColor(d.dias_demora) }}>{d.dias_demora}</td>
                    <td style={tdStyle}>{d.area}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </ChartCard>

      {/* Geoposicionamiento de pendientes — card normal al fondo de la página.
          Reusa el DashboardMap (Leaflet vanilla) del index, filtrado a pendientes
          con coordenadas. */}
      <ChartCard title="Geoposicionamiento de pendientes" height={460}>
        {geo.isLoading ? (
          <CenterMsg>Cargando mapa…</CenterMsg>
        ) : !geo.data?.length ? (
          <CenterMsg>No hay reclamos pendientes con ubicación geográfica.</CenterMsg>
        ) : (
          <div style={{ position: 'relative', width: '100%', height: '100%', borderRadius: 8, overflow: 'hidden' }}>
            <DashboardMap
              reclamos={geo.data as unknown as GeoReclamo[]}
              emergencias={[]}
              espacios={[]}
              tramites={[]}
              visibles={{ reclamos: true, emergencias: false, espacios: false, tramites: false }}
            />
          </div>
        )}
      </ChartCard>
    </div>
  )
}

function fmt(n: number | undefined): string {
  return n == null ? '—' : n.toLocaleString('es-AR')
}

function demoraColor(d: number): string {
  if (d <= 3) return COLOR_TRAMO_0_3
  if (d <= 7) return '#b58900'
  return COLOR_TRAMO_MAS7
}

function pieLabel(props: {
  cx?: number; cy?: number; midAngle?: number; outerRadius?: number; percent?: number; value?: number
}) {
  const { cx = 0, cy = 0, midAngle = 0, outerRadius = 0, percent = 0, value } = props
  if (percent < 0.04) return null
  const RAD = Math.PI / 180
  const rr = outerRadius + 22
  const x = cx + rr * Math.cos(-midAngle * RAD)
  const y = cy + rr * Math.sin(-midAngle * RAD)
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

const tableStyle: React.CSSProperties = { width: '100%', borderCollapse: 'collapse', fontFamily: 'var(--font-display)', fontSize: '0.82rem' }
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
    background: 'transparent', color: disabled ? 'var(--fg-3)' : 'var(--zaris-orange)',
    cursor: disabled ? 'default' : 'pointer',
  }
}
