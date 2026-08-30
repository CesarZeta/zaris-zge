import { Cell, CartesianGrid, Label, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ChartCard, CenterMsg } from '../components/ui'
import { AXIS, DonaCentro, Seccion, legendStyle, pieLabel, tooltipStyle, totalDe } from '../components/SeccionHeader'
import { useEjAltasCierres, useEjCierresPorEstado, useEjEvolucion } from '../hooks/useBi'
import type { BiFiltros } from '../lib/types'
import { labelMes } from '../lib/theme'

// Sección EVOLUCIÓN del tablero Ejecutivo (VL "Evolución de indicadores"):
// relación altas vs cierres por mes, evolución de % cierre / % SLA / % sat,
// y cierres por estado (Cumplido vs Auditado).

const COLOR_ALTAS = '#2f7fd1'
const COLOR_CIERRES = '#1f8a65'
const COLOR_PCT_CIERRE = '#2f7fd1'
const COLOR_PCT_SLA = '#1f8a65'
const COLOR_PCT_SAT = '#6a1b9a'
const COLOR_CUMPLIDO = '#1f8a65'
const COLOR_AUDITADO = '#6a1b9a'

const lineaLabel = { fontFamily: 'var(--font-display)', fontSize: 10, fill: 'var(--fg-3)' }

export function EvolucionEjSection({ filtros }: { filtros: BiFiltros }) {
  const altasCierres = useEjAltasCierres(filtros)
  const evolucion = useEjEvolucion(filtros)
  const cierres = useEjCierresPorEstado(filtros)

  const totalCierres = totalDe(cierres.data ?? [])

  return (
    <Seccion
      id="evolucion"
      titulo="Evolución"
      subtitulo="Relación entre incidentes ingresados y cerrados, y evolución mensual de los indicadores."
    >
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 16 }}>
        <ChartCard title="Incidentes ingresados vs. cerrados por mes" height={300}>
          {altasCierres.isLoading ? (
            <CenterMsg>Cargando…</CenterMsg>
          ) : !altasCierres.data?.length ? (
            <CenterMsg>Sin datos.</CenterMsg>
          ) : (
            <ResponsiveContainer>
              <LineChart data={altasCierres.data} margin={{ top: 18, right: 18, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
                <XAxis dataKey="mes" tick={AXIS} tickFormatter={labelMes} />
                <YAxis tick={AXIS} allowDecimals={false} />
                <Tooltip contentStyle={tooltipStyle} labelFormatter={(m) => labelMes(String(m))} />
                <Legend wrapperStyle={legendStyle} />
                <Line type="monotone" dataKey="altas" name="Ingresados" stroke={COLOR_ALTAS} strokeWidth={2} dot label={lineaLabel} />
                <Line type="monotone" dataKey="cierres" name="Cerrados" stroke={COLOR_CIERRES} strokeWidth={2} dot label={lineaLabel} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard title="Evolución de indicadores (%)" height={300}>
          {evolucion.isLoading ? (
            <CenterMsg>Cargando…</CenterMsg>
          ) : !evolucion.data?.length ? (
            <CenterMsg>Sin datos.</CenterMsg>
          ) : (
            <ResponsiveContainer>
              <LineChart data={evolucion.data} margin={{ top: 18, right: 18, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
                <XAxis dataKey="mes" tick={AXIS} tickFormatter={labelMes} />
                <YAxis tick={AXIS} domain={[0, 100]} />
                <Tooltip contentStyle={tooltipStyle} labelFormatter={(m) => labelMes(String(m))} />
                <Legend wrapperStyle={legendStyle} />
                <Line type="monotone" dataKey="pct_cierre" name="% Cierre" stroke={COLOR_PCT_CIERRE} strokeWidth={2} dot label={lineaLabel} connectNulls />
                <Line type="monotone" dataKey="pct_sla" name="% SLA" stroke={COLOR_PCT_SLA} strokeWidth={2} dot label={lineaLabel} connectNulls />
                <Line type="monotone" dataKey="pct_sat" name="% Satisfacción" stroke={COLOR_PCT_SAT} strokeWidth={2} dot label={lineaLabel} connectNulls />
              </LineChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard title="Cierres por estado" height={300}>
          {cierres.isLoading ? (
            <CenterMsg>Cargando…</CenterMsg>
          ) : !totalCierres ? (
            <CenterMsg>Sin cierres en el período.</CenterMsg>
          ) : (
            <ResponsiveContainer>
              <PieChart>
                <Pie data={cierres.data} dataKey="total" nameKey="estado" innerRadius="50%" outerRadius="78%" paddingAngle={2} label={pieLabel} labelLine={false}>
                  <Label content={DonaCentro} position="center" value={totalCierres} />
                  {(cierres.data ?? []).map((c) => (
                    <Cell key={c.estado} fill={c.estado === 'Auditado' ? COLOR_AUDITADO : COLOR_CUMPLIDO} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={legendStyle} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      </div>
    </Seccion>
  )
}
