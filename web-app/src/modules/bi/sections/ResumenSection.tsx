import { useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, Cell, LabelList, Legend, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { HistogramaTemporal } from '../components/HistogramaTemporal'
import { SegLabelH, TotalLabelH } from '../components/barLabels'
import { ChartCard, CenterMsg, KpiCard, KpiRow } from '../components/ui'
import { AXIS, KpisComparativos, Seccion, fmt, legendStyle, pieLabel, tooltipStyle } from '../components/SeccionHeader'
import { exportarCsv, hoyISO } from '../components/exportCsv'
import { biApi } from '../lib/api'
import { useComparativo, usePorArea, usePorCanal, usePorEstado, useResumen } from '../hooks/useBi'
import type { BiFiltros } from '../lib/types'
import {
  COLOR_CANCELADO, COLOR_PENDIENTE, COLOR_RESUELTO, PALETA_CATEGORICA, colorEstado, labelCanal,
} from '../lib/theme'

// Sección RESUMEN de la página única del Operativo: volumen y composición del
// universo filtrado (todos los estados). Export = todos los tickets del filtro.
export function ResumenSection({ filtros }: { filtros: BiFiltros }) {
  const resumen = useResumen(filtros)
  const porEstado = usePorEstado(filtros)
  const porCanal = usePorCanal(filtros)
  const porArea = usePorArea(filtros)
  const comp = useComparativo('resumen', filtros)
  const [exportando, setExportando] = useState(false)
  const r = resumen.data

  async function handleExport() {
    setExportando(true)
    try {
      const { data } = await biApi.reclamosDetalle(filtros, 10000, 0)
      exportarCsv(
        `reclamos_${hoyISO()}.csv`,
        [
          { header: 'N° Reclamo', value: (d) => d.nro_reclamo },
          { header: 'Fecha alta', value: (d) => (d.fecha_alta ? d.fecha_alta.slice(0, 10) : '') },
          { header: 'Tipo', value: (d) => d.tipo },
          { header: 'Prioridad', value: (d) => d.prioridad },
          { header: 'Estado', value: (d) => d.estado },
          { header: 'Canal', value: (d) => labelCanal(d.canal) },
          { header: 'Área', value: (d) => d.area },
          { header: 'Subárea', value: (d) => d.subarea },
          { header: 'Dirección', value: (d) => d.direccion },
          { header: 'Fecha cierre', value: (d) => (d.fecha_cierre ? d.fecha_cierre.slice(0, 10) : '') },
          { header: 'Días (cierre o demora)', value: (d) => d.dias },
          { header: 'Subreclamo', value: (d) => (d.es_subreclamo ? 'Sí' : 'No') },
        ],
        data,
      )
    } finally {
      setExportando(false)
    }
  }

  return (
    <Seccion
      id="resumen"
      titulo="Resumen"
      subtitulo="Volumen y composición de los reclamos del período (todos los estados)."
      onExport={handleExport}
      exportando={exportando}
      exportDisabled={!r?.total}
    >
      {/* KPIs — UNA fila: totalizador de lo filtrado + comparativos + composición */}
      <KpiRow n={6}>
        <KpiCard label="Reclamos ingresados" value={fmt(r?.total)} sub={comp.data ? comp.data.periodo_actual : 'período filtrado'} />
        <KpisComparativos c={comp.data} etiqueta="reclamos" />
        <KpiCard label="Resueltos" value={fmt(r?.resueltos)} accent={COLOR_RESUELTO} />
        <KpiCard label="Pendientes" value={fmt(r?.pendientes)} accent={COLOR_PENDIENTE} sub={r ? `cancelados: ${fmt(r.cancelados)}` : undefined} />
        <KpiCard label="% Cumplimiento" value={r ? `${r.pct_cumplido}%` : '—'} accent="var(--zaris-orange)" sub="resueltos / cerrados" />
      </KpiRow>

      {/* Histórico: toggle Estado / Tipo (como el "Histórico de reclamos" de Power BI) + Mes/Día + drill */}
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
        alterno={{
          labelBase: 'Estado',
          label: 'Tipo',
          fetchMensual: (f) => biApi.mensualPorTipo(f),
          fetchDiario: (mes, f) => biApi.diarioPorTipo(mes, f),
        }}
      />

      {/* Donas: estado + canal */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
        <ChartCard title="Composición por estado">
          {porEstado.isLoading ? (
            <CenterMsg>Cargando…</CenterMsg>
          ) : !porEstado.data?.length ? (
            <CenterMsg>Sin datos.</CenterMsg>
          ) : (
            <ResponsiveContainer>
              <PieChart>
                <Pie data={porEstado.data} dataKey="total" nameKey="estado" innerRadius="50%" outerRadius="78%" paddingAngle={2} label={pieLabel} labelLine={false}>
                  {porEstado.data.map((e) => <Cell key={e.estado} fill={colorEstado(e.estado)} />)}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={legendStyle} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard title="Composición por canal de origen">
          {porCanal.isLoading ? (
            <CenterMsg>Cargando…</CenterMsg>
          ) : !porCanal.data?.length ? (
            <CenterMsg>Sin datos.</CenterMsg>
          ) : (
            <ResponsiveContainer>
              <PieChart>
                <Pie
                  data={porCanal.data.map((c) => ({ ...c, label: labelCanal(c.canal) }))}
                  dataKey="total" nameKey="label" innerRadius="50%" outerRadius="78%" paddingAngle={2} label={pieLabel} labelLine={false}
                >
                  {porCanal.data.map((_, i) => <Cell key={i} fill={PALETA_CATEGORICA[i % PALETA_CATEGORICA.length]} />)}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={legendStyle} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      </div>

      {/* Barras horizontales por área (con un área filtrada muestra solo esa barra) */}
      <ChartCard title="Reclamos por área y estado" height={Math.max(160, (porArea.data?.length ?? 1) * 48 + 60)}>
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
    </Seccion>
  )
}
