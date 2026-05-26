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
  useSubreclamosDetalle,
  useSubreclamosPorTipo,
  useSubreclamosResumen,
} from '../hooks/useBi'
import type { BiFiltros } from '../lib/types'
import { colorEstado } from '../lib/theme'

const AXIS = { fontFamily: 'var(--font-display)', fontSize: 11, fill: 'var(--fg-3)' as const }
const tooltipStyle: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.8rem', background: 'var(--surface-100)',
  border: '1px solid var(--border-medium)', borderRadius: 8, color: 'var(--fg-1)',
}
const legendStyle: React.CSSProperties = { fontFamily: 'var(--font-display)', fontSize: '0.78rem' }

export function SubreclamosView() {
  const [filtros, setFiltros] = useState<BiFiltros>({})
  const [exportando, setExportando] = useState(false)

  const resumen = useSubreclamosResumen(filtros)
  const porTipo = useSubreclamosPorTipo(filtros, 10)
  const detalle = useSubreclamosDetalle(filtros, 50, 0)

  const r = resumen.data

  async function handleExport() {
    setExportando(true)
    try {
      const { data } = await biApi.subreclamosDetalle(filtros, 10000, 0)
      exportarCsv(
        `subreclamos_${hoyISO()}.csv`,
        [
          { header: 'N° Subreclamo', value: (d) => d.nro_reclamo },
          { header: 'Fecha alta', value: (d) => (d.fecha_alta ? d.fecha_alta.slice(0, 10) : '') },
          { header: 'Tipo', value: (d) => d.tipo },
          { header: 'Prioridad', value: (d) => d.prioridad },
          { header: 'Estado', value: (d) => d.estado },
          { header: 'Área', value: (d) => d.area },
          { header: 'N° Reclamo padre', value: (d) => d.nro_padre },
          { header: 'Estado padre', value: (d) => d.estado_padre },
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
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
        <KpiCard label="Total subreclamos" value={fmt(r?.total)} accent="var(--zaris-orange)" />
        <KpiCard label="Reclamos padre" value={fmt(r?.padres)} sub="con subreclamos asociados" />
      </div>

      {/* Histograma temporal — toggle Mes/Día + total + drill (estándar) */}
      <HistogramaTemporal
        tituloBase="Subreclamos ingresados"
        cacheKey="subreclamos"
        filtros={filtros}
        series={[
          { key: 'sin_asignar', name: 'Sin asignar', color: colorEstado('Sin asignar') },
          { key: 'en_gestion', name: 'En gestión', color: colorEstado('En gestión') },
          { key: 'en_espera', name: 'En espera', color: colorEstado('En espera') },
          { key: 'en_auditoria', name: 'En auditoría', color: colorEstado('En auditoría') },
          { key: 'resuelto', name: 'Resuelto', color: colorEstado('Resuelto') },
          { key: 'cancelado', name: 'Cancelado', color: colorEstado('Cancelado') },
        ]}
        fetchMensual={(f) => biApi.subreclamosMensual(f)}
        fetchDiario={(mes, f) => biApi.subreclamosDiario(mes, f)}
      />

      {/* Donas: subreclamos por estado + reclamos padre por estado */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
        <ChartCard title="Subreclamos por estado">
          {resumen.isLoading ? (
            <CenterMsg>Cargando…</CenterMsg>
          ) : !r?.por_estado?.length ? (
            <CenterMsg>Sin subreclamos.</CenterMsg>
          ) : (
            <ResponsiveContainer>
              <PieChart>
                <Pie data={r.por_estado} dataKey="total" nameKey="estado" innerRadius="50%" outerRadius="78%" paddingAngle={2} label={pieLabel} labelLine={false}>
                  {r.por_estado.map((e) => <Cell key={e.estado} fill={colorEstado(e.estado)} />)}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={legendStyle} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard title="Reclamos padre por estado">
          {resumen.isLoading ? (
            <CenterMsg>Cargando…</CenterMsg>
          ) : !r?.por_estado_padre?.length ? (
            <CenterMsg>Sin datos.</CenterMsg>
          ) : (
            <ResponsiveContainer>
              <PieChart>
                <Pie data={r.por_estado_padre} dataKey="total" nameKey="estado" innerRadius="50%" outerRadius="78%" paddingAngle={2} label={pieLabel} labelLine={false}>
                  {r.por_estado_padre.map((e) => <Cell key={e.estado} fill={colorEstado(e.estado)} />)}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={legendStyle} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      </div>

      {/* Ranking por tipo */}
      <ChartCard title="Ranking de subreclamos por tipo" height={Math.max(220, (porTipo.data?.length ?? 1) * 42 + 60)}>
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
              <Bar dataKey="total" name="Subreclamos" fill="var(--zaris-orange)" radius={[0, 4, 4, 0]}>
                <LabelList dataKey="total" position="right" content={TotalLabelH} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </ChartCard>

      {/* Tabla detalle con incidente padre + export */}
      <ChartCard
        title="Detalle de subreclamos"
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
          <CenterMsg>No hay subreclamos en el período.</CenterMsg>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={tableStyle}>
              <thead>
                <tr>
                  {['N° Subreclamo', 'Alta', 'Tipo', 'Estado', 'Área', 'Reclamo padre', 'Estado padre'].map((h) => (
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
                    <td style={tdStyle}><span style={{ color: colorEstado(d.estado), fontWeight: 600 }}>{d.estado}</span></td>
                    <td style={tdStyle}>{d.area}</td>
                    <td style={tdStyle}>{d.nro_padre ?? '—'}</td>
                    <td style={tdStyle}>
                      {d.estado_padre ? <span style={{ color: colorEstado(d.estado_padre), fontWeight: 600 }}>{d.estado_padre}</span> : '—'}
                    </td>
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
      <rect x={rx} y={y - 9} width={w} height={17} rx={5} fill="rgba(38,37,30,0.78)" />
      <text x={x} y={y} textAnchor={anchorStart ? 'start' : 'end'} dominantBaseline="central"
        fontFamily="var(--font-display)" fontSize={11} fontWeight={600} fill="#f7f7f4">
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
