import { useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, Cell, LabelList, Label, Legend, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { HistogramaTemporal } from '../components/HistogramaTemporal'
import { TotalLabelH } from '../components/barLabels'
import { ChartCard, CenterMsg, KpiCard, KpiRow } from '../components/ui'
import { AXIS, DonaCentro, KpisComparativos, Seccion, totalDe, fmt, legendStyle, pieLabel, tooltipStyle } from '../components/SeccionHeader'
import { exportarCsv, hoyISO } from '../components/exportCsv'
import { biApi } from '../lib/api'
import { useComparativo, useSubreclamosPorTipo, useSubreclamosResumen } from '../hooks/useBi'
import type { BiFiltros } from '../lib/types'
import { colorEstado } from '../lib/theme'

// Sección SUBRECLAMOS (breve, al pie): reclamos con id_reclamo_padre —
// "intervenciones" en la jerga de los tableros de referencia. No existe en Power BI.
export function SubreclamosSection({ filtros }: { filtros: BiFiltros }) {
  const resumen = useSubreclamosResumen(filtros)
  const porTipo = useSubreclamosPorTipo(filtros, 10)
  const comp = useComparativo('subreclamos', filtros)
  const [exportando, setExportando] = useState(false)
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
    <Seccion
      id="subreclamos"
      titulo="Subreclamos"
      subtitulo="Intervenciones derivadas de un reclamo padre (cross-área)."
      onExport={handleExport}
      exportando={exportando}
      exportDisabled={!r?.total}
      exportLabel="Exportar subreclamos"
    >
      {/* KPIs — UNA fila: totalizador + comparativos + padres */}
      <KpiRow n={4}>
        <KpiCard label="Subreclamos" value={fmt(r?.total)} accent="var(--zaris-orange)" sub={comp.data ? comp.data.periodo_actual : 'período filtrado'} />
        <KpisComparativos c={comp.data} etiqueta="subreclamos" />
        <KpiCard label="Reclamos padre" value={fmt(r?.padres)} sub="con subreclamos asociados" />
      </KpiRow>

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
                  <Label content={DonaCentro} position="center" value={totalDe(r.por_estado)} />
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
                  <Label content={DonaCentro} position="center" value={totalDe(r.por_estado_padre)} />
                  {r.por_estado_padre.map((e) => <Cell key={e.estado} fill={colorEstado(e.estado)} />)}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={legendStyle} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      </div>

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
    </Seccion>
  )
}
