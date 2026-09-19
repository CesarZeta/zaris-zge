import { useMemo } from 'react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ChartCard, CenterMsg } from '../components/ui'
import { AXIS, Seccion, legendStyle, tooltipStyle } from '../components/SeccionHeader'
import { HistogramaTemporal } from '../components/HistogramaTemporal'
import { useAtEvolucion } from '../hooks/useBi'
import { biApi } from '../lib/api'
import { mesesEjeSerie, periodoEnLetras, ultimos12MesesRango } from '../lib/periodo'
import type { BiFiltros } from '../lib/types'
import { COLOR_TURNO, LABEL_TURNO, labelMes } from '../lib/theme'

// Sección EVOLUCIÓN del tablero de ATENCIÓN: histograma de turnos por estado
// (toggle Mes/Día + drill-down, respeta el período filtrado) y las dos líneas
// mensuales con ventana FIJA de últimos 12 meses (regla del Ejecutivo):
// otorgados vs cumplidos, e indicadores (% cumplimiento / % ausentismo / % sat).

const SERIES_TURNOS = [
  { key: 'pendiente', name: LABEL_TURNO.pendiente, color: COLOR_TURNO.pendiente },
  { key: 'cumplido', name: LABEL_TURNO.cumplido, color: COLOR_TURNO.cumplido },
  { key: 'ausente', name: LABEL_TURNO.ausente, color: COLOR_TURNO.ausente },
  { key: 'cancelado', name: LABEL_TURNO.cancelado, color: COLOR_TURNO.cancelado },
]
const lineaLabel = { fontFamily: 'var(--font-display)', fontSize: 10, fill: 'var(--fg-3)' }

export function EvolucionAtSection({ filtros }: { filtros: BiFiltros }) {
  const filtros12m = useMemo<BiFiltros>(
    () => ({ ...filtros, anio: undefined, meses: undefined, ...ultimos12MesesRango() }),
    [filtros],
  )
  const evolucion = useAtEvolucion(filtros12m)

  const serie12 = useMemo(() => {
    const por = new Map((evolucion.data ?? []).map((x) => [x.mes, x]))
    return mesesEjeSerie([...por.keys()]).map((mes) => por.get(mes) ?? {
      mes, total: 0, cumplidos: 0, ausentes: 0, cancelados: 0,
      pct_cumplimiento: null, pct_ausentismo: null, espera_prom_min: null, pct_sat: null,
    })
  }, [evolucion.data])

  return (
    <Seccion id="evolucion" titulo="Evolución" periodo={periodoEnLetras(filtros).actual}>
      <HistogramaTemporal
        tituloBase="Turnos otorgados"
        series={SERIES_TURNOS}
        fetchMensual={(f) => biApi.atMensual(f)}
        fetchDiario={(mes, f) => biApi.atDiario(mes, f)}
        cacheKey="at-turnos"
        filtros={filtros}
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 16 }}>
        <ChartCard title="Turnos otorgados vs. cumplidos por mes" nota="últimos 12 meses" height={300}>
          {evolucion.isLoading ? (
            <CenterMsg>Cargando…</CenterMsg>
          ) : !evolucion.data?.length ? (
            <CenterMsg>Sin datos.</CenterMsg>
          ) : (
            <ResponsiveContainer>
              <LineChart data={serie12} margin={{ top: 18, right: 18, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
                <XAxis dataKey="mes" tick={AXIS} tickFormatter={labelMes} interval={0} />
                <YAxis tick={AXIS} allowDecimals={false} />
                <Tooltip contentStyle={tooltipStyle} labelFormatter={(m) => labelMes(String(m))} />
                <Legend wrapperStyle={legendStyle} />
                <Line type="monotone" dataKey="total" name="Otorgados" stroke={COLOR_TURNO.pendiente} strokeWidth={2} dot label={lineaLabel} />
                <Line type="monotone" dataKey="cumplidos" name="Cumplidos" stroke={COLOR_TURNO.cumplido} strokeWidth={2} dot label={lineaLabel} />
                <Line type="monotone" dataKey="ausentes" name="Ausentes" stroke={COLOR_TURNO.ausente} strokeWidth={2} dot label={lineaLabel} />
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
              <LineChart data={serie12} margin={{ top: 18, right: 18, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
                <XAxis dataKey="mes" tick={AXIS} tickFormatter={labelMes} interval={0} />
                <YAxis tick={AXIS} domain={[0, 100]} />
                <Tooltip contentStyle={tooltipStyle} labelFormatter={(m) => labelMes(String(m))} />
                <Legend wrapperStyle={legendStyle} />
                <Line type="monotone" dataKey="pct_cumplimiento" name="% Cumplimiento" stroke={COLOR_TURNO.cumplido} strokeWidth={2} dot label={lineaLabel} connectNulls />
                <Line type="monotone" dataKey="pct_ausentismo" name="% Ausentismo" stroke={COLOR_TURNO.ausente} strokeWidth={2} dot label={lineaLabel} connectNulls />
                <Line type="monotone" dataKey="pct_sat" name="% Satisfacción" stroke="#6a1b9a" strokeWidth={2} dot label={lineaLabel} connectNulls />
              </LineChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      </div>
    </Seccion>
  )
}
