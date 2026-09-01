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
import { useComparativo, usePendientesGeo, usePendientesPorTipo, usePendientesResumen } from '../hooks/useBi'
import { periodoEnLetras } from '../lib/periodo'
import { DashboardMap } from '../../dashboard/components/DashboardMap'
import type { GeoReclamo } from '../../dashboard/hooks/useDashboardData'
import type { BiFiltros, PendienteGeo } from '../lib/types'
import { COLOR_TRAMO_0_3, COLOR_TRAMO_4_7, COLOR_TRAMO_MAS7, colorEstado, colorTramo, labelCanal } from '../lib/theme'

// Sección PENDIENTES: lo abierto hoy (estados no finales), su demora y dónde está
// — equivale a "Pendientes" + "Pendientes geoposicionados" de Power BI.
export function PendientesSection({ filtros }: { filtros: BiFiltros }) {
  const resumen = usePendientesResumen(filtros)
  const porTipo = usePendientesPorTipo(filtros, 10)
  const geo = usePendientesGeo(filtros)
  const comp = useComparativo('pendientes', filtros)
  const [exportando, setExportando] = useState(false)
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
          { header: 'Canal', value: (d) => labelCanal(d.canal) },
          { header: 'Área', value: (d) => d.area },
        ],
        data,
      )
    } finally {
      setExportando(false)
    }
  }

  return (
    <Seccion
      id="pendientes"
      titulo="Pendientes"
      periodo={periodoEnLetras(filtros).actual}
      onExport={handleExport}
      exportando={exportando}
      exportDisabled={!r?.total}
      exportLabel="Exportar pendientes"
    >
      {/* KPIs — UNA fila: totalizador + comparativos + demora */}
      <KpiRow n={6}>
        <KpiCard label="Pendientes" value={fmt(r?.total)} accent="var(--zaris-orange)" sub={comp.data ? comp.data.periodo_actual : 'abiertos hoy'} />
        <KpisComparativos c={comp.data} etiqueta="ingresados aún abiertos" />
        <KpiCard label="Demora promedio" value={r?.dias_demora_promedio != null ? `${r.dias_demora_promedio} d` : '—'} accent={COLOR_TRAMO_4_7} sub="días desde el ingreso" />
        <KpiCard label="Más de 7 días" value={fmt(r?.tmas7)} accent={COLOR_TRAMO_MAS7} sub={r ? `4 a 7: ${fmt(r.t4_7)}` : undefined} />
        <KpiCard label="Hasta 3 días" value={fmt(r?.t0_3)} accent={COLOR_TRAMO_0_3} />
      </KpiRow>

      {/* Pendientes por mes de alta — histograma por estado con Mes/Día + drill */}
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

      {/* Donas: demora + estado */}
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
                  <Label content={DonaCentro} position="center" value={totalDe(demora)} />
                  {demora.map((d) => <Cell key={d.tramo} fill={d.color} />)}
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
                  <Label content={DonaCentro} position="center" value={totalDe(r.por_estado)} />
                  {r.por_estado.map((e) => <Cell key={e.estado} fill={colorEstado(e.estado)} />)}
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

      {/* Mapa con semáforo de demora (como "Pendientes geoposicionados" de Power BI) */}
      <ChartCard
        title="Geoposicionamiento de pendientes"
        height={460}
        action={
          <div style={{ display: 'flex', gap: 12, fontSize: '0.74rem', color: 'var(--fg-2)', fontFamily: 'var(--font-display)' }}>
            <LeyendaDot color={COLOR_TRAMO_0_3} label="0 a 3 días" />
            <LeyendaDot color={COLOR_TRAMO_4_7} label="4 a 7 días" />
            <LeyendaDot color={COLOR_TRAMO_MAS7} label="Más de 7 días" />
          </div>
        }
      >
        {geo.isLoading ? (
          <CenterMsg>Cargando mapa…</CenterMsg>
        ) : !geo.data?.length ? (
          <CenterMsg>No hay reclamos pendientes con ubicación geográfica.</CenterMsg>
        ) : (
          <div style={{ position: 'relative', isolation: 'isolate', zIndex: 0, width: '100%', height: '100%', borderRadius: 8, overflow: 'hidden' }}>
            <DashboardMap
              reclamos={geo.data as unknown as GeoReclamo[]}
              emergencias={[]}
              espacios={[]}
              tramites={[]}
              visibles={{ reclamos: true, emergencias: false, espacios: false, tramites: false }}
              colorReclamo={(x) => colorTramo((x as unknown as PendienteGeo).dias_demora)}
            />
          </div>
        )}
      </ChartCard>
    </Seccion>
  )
}

function LeyendaDot({ color, label }: { color: string; label: string }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
      <span style={{ width: 10, height: 10, borderRadius: '50%', background: color, border: '1.5px solid #fff', boxShadow: '0 0 0 1px rgba(0,0,0,0.15)' }} />
      {label}
    </span>
  )
}
