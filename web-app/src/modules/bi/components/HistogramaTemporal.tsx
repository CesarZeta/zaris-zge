import { useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useQuery } from '@tanstack/react-query'
import { ChartCard, CenterMsg } from './ui'
import type { BiFiltros, ItemTemporal } from '../lib/types'
import { labelDia, labelMes, labelMesLargo } from '../lib/theme'
import { SegLabel, TotalLabel } from './barLabels'

const AXIS = { fontFamily: 'var(--font-display)', fontSize: 11, fill: 'var(--fg-3)' as const }
const tooltipStyle: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.8rem', background: 'var(--surface-100)',
  border: '1px solid var(--border-medium)', borderRadius: 8, color: 'var(--fg-1)',
}
const legendStyle: React.CSSProperties = { fontFamily: 'var(--font-display)', fontSize: '0.78rem' }

type Gran = 'mes' | 'dia'

// Una serie apilada del histograma: la dataKey en los items, su nombre y color.
export interface SerieHistograma {
  key: string
  name: string
  color: string
}

interface Props {
  /** Título base (sin el sufijo de granularidad). Ej: "Reclamos ingresados". */
  tituloBase: string
  /** Series apiladas (orden = orden de apilado, de abajo hacia arriba). */
  series: SerieHistograma[]
  /** Fetch de la serie mensual. */
  fetchMensual: (f: BiFiltros) => Promise<ItemTemporal[]>
  /** Fetch de la serie diaria (mes != null => drill a ese mes; null => período completo). */
  fetchDiario: (mes: string | null, f: BiFiltros) => Promise<ItemTemporal[]>
  /** Clave única para react-query (distinta por cada uso del componente). */
  cacheKey: string
  filtros: BiFiltros
}

// Histograma temporal con toggle Mes/Día + drill-down. Genérico: las series y los
// fetchers se inyectan, así sirve a Resumen (resuelto/pendiente/cancelado) y a
// Pendientes (por estado). ESTÁNDAR del módulo: etiqueta de total arriba +
// toggle Mes/Día + drill por clic. Ver memoria reference_bi_lineamientos_visualizaciones.
export function HistogramaTemporal({ tituloBase, series, fetchMensual, fetchDiario, cacheKey, filtros }: Props) {
  const [gran, setGran] = useState<Gran>('mes')
  const [mesDrill, setMesDrill] = useState<string | null>(null)

  const fkey = [cacheKey, filtros.desde, filtros.hasta, filtros.id_area, filtros.prioridad] as const
  const mensual = useQuery({ queryKey: ['bi-hist', ...fkey, 'mes'], queryFn: () => fetchMensual(filtros) })

  const mostrandoDias = gran === 'dia' || !!mesDrill
  const diario = useQuery({
    queryKey: ['bi-hist', ...fkey, 'dia', mesDrill],
    queryFn: () => fetchDiario(mesDrill, filtros),
    enabled: mostrandoDias,
  })

  // Si cambian los filtros y el mes drillado ya no existe, salir del drill.
  const mesesDisponibles = new Set((mensual.data ?? []).map((m) => m.mes))
  if (mesDrill && mensual.data && !mesesDisponibles.has(mesDrill)) {
    setMesDrill(null)
  }

  const titulo = mesDrill
    ? `${tituloBase} por día — ${labelMesLargo(mesDrill)}`
    : mostrandoDias
      ? `${tituloBase} por día`
      : `${tituloBase} por mes`

  const data: (ItemTemporal & { label: string })[] = mostrandoDias
    ? (diario.data ?? []).map((d) => ({ ...d, label: labelDia(d.dia!) }))
    : (mensual.data ?? []).map((m) => ({ ...m, label: labelMes(m.mes!) }))

  const cargando = mostrandoDias ? diario.isLoading : mensual.isLoading
  const clickeable = gran === 'mes' && !mesDrill

  const onBarClick = (d: { payload?: { mes?: string } }) => {
    if (clickeable && d?.payload?.mes) setMesDrill(d.payload.mes)
  }

  return (
    <ChartCard
      title={titulo}
      height={300}
      action={
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {mesDrill && (
            <button onClick={() => setMesDrill(null)} style={backBtnStyle}>← Volver</button>
          )}
          {clickeable && (
            <span style={{ fontSize: '0.72rem', color: 'var(--fg-3)' }}>Click en un mes para ver sus días</span>
          )}
          <div style={toggleWrapStyle}>
            <button onClick={() => { setGran('mes'); setMesDrill(null) }} style={pillStyle(gran === 'mes')}>Mes</button>
            <button onClick={() => { setGran('dia'); setMesDrill(null) }} style={pillStyle(gran === 'dia')}>Día</button>
          </div>
        </div>
      }
    >
      {cargando ? (
        <CenterMsg>Cargando…</CenterMsg>
      ) : !data.length ? (
        <CenterMsg>Sin datos en el período seleccionado.</CenterMsg>
      ) : (
        <ResponsiveContainer>
          <BarChart data={data} margin={{ top: 24, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" vertical={false} />
            <XAxis dataKey="label" tick={AXIS} interval={mostrandoDias ? 'preserveStartEnd' : 0} />
            <YAxis tick={AXIS} allowDecimals={false} />
            <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(245,78,0,0.06)' }} />
            <Legend wrapperStyle={legendStyle} />
            {series.map((s, i) => {
              const ultima = i === series.length - 1
              return (
                <Bar
                  key={s.key}
                  dataKey={s.key}
                  name={s.name}
                  stackId="a"
                  fill={s.color}
                  radius={ultima ? [4, 4, 0, 0] : undefined}
                  cursor={clickeable ? 'pointer' : 'default'}
                  onClick={onBarClick}
                >
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

const backBtnStyle: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.78rem', fontWeight: 600,
  padding: '5px 12px', border: '1px solid var(--zaris-orange)', borderRadius: 8,
  background: 'transparent', color: 'var(--zaris-orange)', cursor: 'pointer',
}
const toggleWrapStyle: React.CSSProperties = {
  display: 'inline-flex', border: '1px solid var(--border-medium)', borderRadius: 8, overflow: 'hidden',
}
function pillStyle(active: boolean): React.CSSProperties {
  return {
    fontFamily: 'var(--font-display)', fontSize: '0.78rem', fontWeight: 600,
    padding: '5px 14px', border: 'none', cursor: 'pointer',
    background: active ? 'var(--zaris-orange)' : 'var(--surface-100)',
    color: active ? '#fff' : 'var(--fg-2)',
  }
}
