import { useMemo } from 'react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ChartCard, CenterMsg } from '../components/ui'
import { AXIS, Seccion, legendStyle, tooltipStyle } from '../components/SeccionHeader'
import { useEjAltasCierres, useEjEvolucion } from '../hooks/useBi'
import { mesesEjeSerie, periodoEnLetras, ultimos12MesesRango } from '../lib/periodo'
import type { BiFiltros } from '../lib/types'
import { labelMes } from '../lib/theme'

// Sección EVOLUCIÓN del tablero Ejecutivo (VL "Evolución de indicadores"):
// los dos gráficos de líneas (altas vs cierres, y % cierre / % SLA / % sat).
// La dona "Cierres por estado" se movió al Resumen, junto a la de niveles
// (César 2026-08-31: las dos donas lado a lado y abajo las líneas).

const COLOR_ALTAS = '#2f7fd1'
const COLOR_CIERRES = '#1f8a65'
const COLOR_PCT_CIERRE = '#2f7fd1'
const COLOR_PCT_SLA = '#1f8a65'
const COLOR_PCT_SAT = '#6a1b9a'

const lineaLabel = { fontFamily: 'var(--font-display)', fontSize: 10, fill: 'var(--fg-3)' }

export function EvolucionEjSection({ filtros }: { filtros: BiFiltros }) {
  // Series mensuales SIEMPRE con ventana fija de últimos 12 meses (César
  // 2026-08-31): ignoran el filtro de período (respetan área/subárea/localidad).
  const filtros12m = useMemo<BiFiltros>(
    () => ({ ...filtros, anio: undefined, meses: undefined, ...ultimos12MesesRango() }),
    [filtros],
  )
  const altasCierres = useEjAltasCierres(filtros12m)
  const evolucion = useEjEvolucion(filtros12m)

  // Eje: del primer al último mes CON datos dentro de la ventana de 12
  // (huecos intermedios en cero; sin ceros al inicio si los datos no llegan).
  const altasCierres12 = useMemo(() => {
    const por = new Map((altasCierres.data ?? []).map((x) => [x.mes, x]))
    return mesesEjeSerie([...por.keys()]).map((mes) => por.get(mes) ?? { mes, altas: 0, cierres: 0 })
  }, [altasCierres.data])
  const evolucion12 = useMemo(() => {
    const por = new Map((evolucion.data ?? []).map((x) => [x.mes, x]))
    return mesesEjeSerie([...por.keys()]).map((mes) => por.get(mes) ?? { mes, total: 0, pct_cierre: null, pct_sla: null, pct_sat: null })
  }, [evolucion.data])

  return (
    <Seccion
      id="evolucion"
      titulo="Evolución"
      periodo={periodoEnLetras(filtros).actual}
    >
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 16 }}>
        <ChartCard title="Incidentes ingresados vs. cerrados por mes" nota="últimos 12 meses" height={300}>
          {altasCierres.isLoading ? (
            <CenterMsg>Cargando…</CenterMsg>
          ) : !altasCierres.data?.length ? (
            <CenterMsg>Sin datos.</CenterMsg>
          ) : (
            <ResponsiveContainer>
              <LineChart data={altasCierres12} margin={{ top: 18, right: 18, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
                <XAxis dataKey="mes" tick={AXIS} tickFormatter={labelMes} interval={0} />
                <YAxis tick={AXIS} allowDecimals={false} />
                <Tooltip contentStyle={tooltipStyle} labelFormatter={(m) => labelMes(String(m))} />
                <Legend wrapperStyle={legendStyle} />
                <Line type="monotone" dataKey="altas" name="Ingresados" stroke={COLOR_ALTAS} strokeWidth={2} dot label={lineaLabel} />
                <Line type="monotone" dataKey="cierres" name="Cerrados" stroke={COLOR_CIERRES} strokeWidth={2} dot label={lineaLabel} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard title="Evolución de indicadores (%)" nota="últimos 12 meses" height={300}>
          {evolucion.isLoading ? (
            <CenterMsg>Cargando…</CenterMsg>
          ) : !evolucion.data?.length ? (
            <CenterMsg>Sin datos.</CenterMsg>
          ) : (
            <ResponsiveContainer>
              <LineChart data={evolucion12} margin={{ top: 18, right: 18, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
                <XAxis dataKey="mes" tick={AXIS} tickFormatter={labelMes} interval={0} />
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

      </div>
    </Seccion>
  )
}
