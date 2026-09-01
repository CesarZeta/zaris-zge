import { useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, LabelList, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { SegLabel, SegLabelH, TotalLabel, TotalLabelH } from '../components/barLabels'
import { ChartCard, CenterMsg, KpiCard, KpiRow } from '../components/ui'
import { AXIS, KpisComparativos, Seccion, fmt, legendStyle, tooltipStyle } from '../components/SeccionHeader'
import { exportarCsv, hoyISO } from '../components/exportCsv'
import { biApi } from '../lib/api'
import { useComparativo, useEvolucionDias, useSlaResumen, useTiemposMensual, useTiemposPorTipo } from '../hooks/useBi'
import { periodoEnLetras } from '../lib/periodo'
import type { BiFiltros } from '../lib/types'
import { COLOR_TRAMO_0_3, COLOR_TRAMO_4_7, COLOR_TRAMO_MAS7, labelCanal, labelMes } from '../lib/theme'

// Sección RESPUESTA: los reclamos CERRADOS (resueltos con fecha de cierre) y sus
// tiempos — equivale al tablero "Tiempos de respuesta" de Power BI.
export function RespuestaSection({ filtros }: { filtros: BiFiltros }) {
  const sla = useSlaResumen(filtros)
  const tMes = useTiemposMensual(filtros)
  const tTipo = useTiemposPorTipo(filtros, 10)
  const evol = useEvolucionDias(filtros)
  const comp = useComparativo('respuesta', filtros)
  const [exportando, setExportando] = useState(false)

  const s = sla.data
  const difPos = (s?.dif_pct ?? 0) >= 0

  async function handleExport() {
    setExportando(true)
    try {
      const { data } = await biApi.resueltosDetalle(filtros, 10000, 0)
      exportarCsv(
        `reclamos_resueltos_${hoyISO()}.csv`,
        [
          { header: 'N° Reclamo', value: (r) => r.nro_reclamo },
          { header: 'Fecha cierre', value: (r) => (r.fecha_cierre ? r.fecha_cierre.slice(0, 10) : '') },
          { header: 'Tipo', value: (r) => r.tipo },
          { header: 'Prioridad', value: (r) => r.prioridad },
          { header: 'Días de cierre', value: (r) => r.dias },
          { header: 'Canal', value: (r) => labelCanal(r.canal) },
          { header: 'Área', value: (r) => r.area },
        ],
        data,
      )
    } finally {
      setExportando(false)
    }
  }

  return (
    <Seccion
      id="respuesta"
      titulo="Respuesta"
      periodo={periodoEnLetras(filtros).actual}
      onExport={handleExport}
      exportando={exportando}
      exportDisabled={!comp.data?.total}
      exportLabel="Exportar resueltos"
    >
      {/* KPIs — UNA fila: totalizador + comparativos + tiempos */}
      <KpiRow n={6}>
        <KpiCard label="Resueltos" value={fmt(comp.data?.total)} accent={COLOR_TRAMO_0_3} sub={comp.data ? comp.data.periodo_actual : 'período filtrado'} />
        <KpisComparativos c={comp.data} etiqueta="resueltos" positivoEsBueno />
        <KpiCard label="Tiempo cierre promedio" value={s?.dias_cierre_promedio != null ? `${s.dias_cierre_promedio} d` : '—'} accent="var(--zaris-orange)" sub="días entre alta y cierre" />
        <KpiCard label="% Dentro de SLA" value={s?.pct_dentro_sla != null ? `${s.pct_dentro_sla}%` : '—'} accent={COLOR_TRAMO_0_3} sub="cierre ≤ SLA del tipo" />
        <KpiCard
          label="Resueltos último mes"
          value={fmt(s?.resueltos_mes_actual)}
          accent={difPos ? COLOR_TRAMO_0_3 : COLOR_TRAMO_MAS7}
          sub={s ? `${difPos ? '+' : ''}${s.dif_pct}% vs. mes anterior (${fmt(s.resueltos_mes_anterior)})` : undefined}
        />
      </KpiRow>

      {/* Tiempos de respuesta por mes (apiladas por tramo) */}
      <ChartCard title="Tiempos de respuesta por mes de cierre" height={300}>
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

      {/* Tiempos por tipo + evolución */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 16 }}>
        <ChartCard title="Tiempos por tipo de reclamo" height={Math.max(240, (tTipo.data?.length ?? 1) * 42 + 60)}>
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
                <Line type="monotone" dataKey="dias_prom" name="Días promedio" stroke="var(--zaris-orange)" strokeWidth={2.5} dot={{ r: 4, fill: 'var(--zaris-orange)' }}>
                  <LabelList dataKey="dias_prom" position="top" content={LineLabel} />
                </Line>
              </LineChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      </div>
    </Seccion>
  )
}

// Label de punto de línea con pastilla de contraste invertible (§13).
function LineLabel(p: { x?: string | number; y?: string | number; value?: string | number }) {
  const x = Number(p.x ?? 0), y = Number(p.y ?? 0), value = p.value
  if (value == null) return null
  const txt = String(value)
  const w = txt.length * 7 + 10
  return (
    <g>
      <rect x={x - w / 2} y={y - 22} width={w} height={16} rx={5} fill="var(--fg-1)" fillOpacity={0.82} />
      <text x={x} y={y - 14} textAnchor="middle" dominantBaseline="central" fontFamily="var(--font-display)" fontSize={11} fontWeight={700} fill="var(--surface-100)">
        {txt}
      </text>
    </g>
  )
}
