import { Bar, BarChart, CartesianGrid, Cell, Label, LabelList, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { UseQueryResult } from '@tanstack/react-query'
import { ChartCard, CenterMsg } from '../components/ui'
import { AXIS, DonaCentro, Seccion, legendStyle, pieLabel, tooltipStyle, totalDe } from '../components/SeccionHeader'
import { SegLabel, TotalLabel } from '../components/barLabels'
import { useEjHistorico, useEjPorLocalidad, usePorCanal } from '../hooks/useBi'
import { periodoEnLetras } from '../lib/periodo'
import type { BiFiltros, HistogramaDinamico } from '../lib/types'
import { COLOR_OTROS, PALETA_CATEGORICA, labelCanal, labelMes } from '../lib/theme'

// Sección HISTÓRICO del tablero Ejecutivo (VL "Histórico por área, localidad y
// origen"): series mensuales apiladas por subárea / canal / localidad + la
// composición del período por canal y por localidad.

function HistoricoChart({
  titulo,
  query,
  mapNombre,
}: {
  titulo: string
  query: UseQueryResult<HistogramaDinamico>
  /** Etiqueta legible de cada serie (ej. canales crudos → labelCanal). */
  mapNombre?: (name: string) => string
}) {
  const data = (query.data?.items ?? []).map((m) => ({ ...m, label: labelMes(m.mes!) }))
  const series = (query.data?.series ?? []).map((s, i) => ({
    key: s.key,
    name: mapNombre ? mapNombre(s.name) : s.name,
    color: s.key === 'g_otros' ? COLOR_OTROS : PALETA_CATEGORICA[i % PALETA_CATEGORICA.length],
  }))
  return (
    <ChartCard title={titulo} height={300}>
      {query.isLoading ? (
        <CenterMsg>Cargando…</CenterMsg>
      ) : !data.length ? (
        <CenterMsg>Sin datos en el período seleccionado.</CenterMsg>
      ) : (
        <ResponsiveContainer>
          <BarChart data={data} margin={{ top: 24, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" vertical={false} />
            <XAxis dataKey="label" tick={AXIS} interval={0} />
            <YAxis tick={AXIS} allowDecimals={false} />
            <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(245,78,0,0.06)' }} />
            <Legend wrapperStyle={legendStyle} />
            {series.map((s, i) => {
              const ultima = i === series.length - 1
              return (
                <Bar key={s.key} dataKey={s.key} name={s.name} stackId="a" fill={s.color} radius={ultima ? [4, 4, 0, 0] : undefined}>
                  <LabelList dataKey={s.key} position="center" content={SegLabel} />
                  {ultima && <LabelList dataKey="total" position="top" content={TotalLabel} />}
                </Bar>
              )
            })}
          </BarChart>
        </ResponsiveContainer>
      )}
    </ChartCard>
  )
}

export function HistoricoEjSection({ filtros }: { filtros: BiFiltros }) {
  const porSubarea = useEjHistorico(filtros, 'subarea')
  const porCanalHist = useEjHistorico(filtros, 'canal')
  const porLocalidadHist = useEjHistorico(filtros, 'localidad')
  const donaCanal = usePorCanal(filtros)
  const donaLocalidad = useEjPorLocalidad(filtros)

  return (
    <Seccion
      id="historico"
      titulo="Histórico"
      periodo={periodoEnLetras(filtros).actual}
    >
      <HistoricoChart titulo="Incidentes mensuales por subárea" query={porSubarea} />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 16 }}>
        <HistoricoChart titulo="Incidentes mensuales por canal de origen" query={porCanalHist} mapNombre={labelCanal} />
        <ChartCard title="Composición por canal de origen" height={300}>
          {donaCanal.isLoading ? (
            <CenterMsg>Cargando…</CenterMsg>
          ) : !donaCanal.data?.length ? (
            <CenterMsg>Sin datos.</CenterMsg>
          ) : (
            <ResponsiveContainer>
              <PieChart>
                <Pie
                  data={donaCanal.data.map((c) => ({ ...c, label: labelCanal(c.canal) }))}
                  dataKey="total" nameKey="label" innerRadius="50%" outerRadius="78%" paddingAngle={2} label={pieLabel} labelLine={false}
                >
                  <Label content={DonaCentro} position="center" value={totalDe(donaCanal.data)} />
                  {donaCanal.data.map((_, i) => <Cell key={i} fill={PALETA_CATEGORICA[i % PALETA_CATEGORICA.length]} />)}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={legendStyle} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <HistoricoChart titulo="Incidentes mensuales por localidad" query={porLocalidadHist} />
        <ChartCard title="Composición por localidad" height={300}>
          {donaLocalidad.isLoading ? (
            <CenterMsg>Cargando…</CenterMsg>
          ) : !donaLocalidad.data?.length ? (
            <CenterMsg>Sin datos.</CenterMsg>
          ) : (
            <ResponsiveContainer>
              <PieChart>
                <Pie data={donaLocalidad.data} dataKey="total" nameKey="localidad" innerRadius="50%" outerRadius="78%" paddingAngle={2} label={pieLabel} labelLine={false}>
                  <Label content={DonaCentro} position="center" value={totalDe(donaLocalidad.data)} />
                  {donaLocalidad.data.map((_, i) => <Cell key={i} fill={PALETA_CATEGORICA[i % PALETA_CATEGORICA.length]} />)}
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
