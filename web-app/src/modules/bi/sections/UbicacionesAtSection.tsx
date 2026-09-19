import { Bar, BarChart, CartesianGrid, LabelList, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ChartCard, CenterMsg } from '../components/ui'
import { AXIS, Seccion, fmt, legendStyle, tooltipStyle } from '../components/SeccionHeader'
import { SegLabelH, TotalLabelH } from '../components/barLabels'
import { TablaAt, cardStyle, h3Style, minutos, notaStyle, num, pct } from '../components/atUtils'
import { useAtPorAgente, useAtPorUbicacion } from '../hooks/useBi'
import { periodoEnLetras } from '../lib/periodo'
import type { AtPorAgente, AtPorUbicacion, BiFiltros } from '../lib/types'
import { COLOR_TURNO, LABEL_TURNO } from '../lib/theme'

// Sección UBICACIONES del tablero de ATENCIÓN: ocupación por ubicación (turnos
// apilados por estado + horas atendidas) y atención por agente (turnos cuyo
// recurso es un agente: cumplidos, ausentes, espera, atenciones registradas).

const SERIES = [
  { key: 'cumplidos', name: LABEL_TURNO.cumplido, color: COLOR_TURNO.cumplido },
  { key: 'ausentes', name: LABEL_TURNO.ausente, color: COLOR_TURNO.ausente },
  { key: 'cancelados', name: LABEL_TURNO.cancelado, color: COLOR_TURNO.cancelado },
  { key: 'pendientes', name: LABEL_TURNO.pendiente, color: COLOR_TURNO.pendiente },
]

export function UbicacionesAtSection({ filtros }: { filtros: BiFiltros }) {
  const ubic = useAtPorUbicacion(filtros)
  const agentes = useAtPorAgente(filtros, 15)
  const filas = ubic.data ?? []
  const altoBarras = Math.max(260, 70 + filas.length * 38)

  return (
    <Seccion id="ubicaciones" titulo="Ubicaciones y agentes" periodo={periodoEnLetras(filtros).actual}>
      <ChartCard title="Turnos por ubicación" height={altoBarras}>
        {ubic.isLoading ? (
          <CenterMsg>Cargando…</CenterMsg>
        ) : !filas.length ? (
          <CenterMsg>Sin turnos en el período.</CenterMsg>
        ) : (
          <ResponsiveContainer>
            <BarChart data={filas} layout="vertical" margin={{ top: 4, right: 56, left: 8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" horizontal={false} />
              <XAxis type="number" tick={AXIS} allowDecimals={false} />
              <YAxis type="category" dataKey="ubicacion" tick={AXIS} width={190} interval={0} />
              <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(245,78,0,0.06)' }} />
              <Legend wrapperStyle={legendStyle} />
              {SERIES.map((s, i) => {
                const ultima = i === SERIES.length - 1
                return (
                  <Bar key={s.key} dataKey={s.key} name={s.name} stackId="a" fill={s.color} radius={ultima ? [0, 4, 4, 0] : undefined}>
                    <LabelList dataKey={s.key} position="center" content={SegLabelH} />
                    {ultima && <LabelList dataKey="total" position="right" content={TotalLabelH} />}
                  </Bar>
                )
              })}
            </BarChart>
          </ResponsiveContainer>
        )}
      </ChartCard>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: 16 }}>
        <div style={cardStyle}>
          <h3 style={h3Style}>Ocupación por ubicación</h3>
          <p style={notaStyle}>Horas atendidas = duración de los turnos cumplidos · % Aus. = ausentes / (cumplidos + ausentes)</p>
          {ubic.isLoading ? (
            <div style={{ padding: 24 }}><CenterMsg>Cargando…</CenterMsg></div>
          ) : !filas.length ? (
            <div style={{ padding: 24 }}><CenterMsg>Sin turnos en el período.</CenterMsg></div>
          ) : (
            <TablaAt<AtPorUbicacion>
              columnas={[
                { header: 'Ubicación', texto: true, render: (r) => <><span style={{ fontWeight: 600 }}>{r.ubicacion}</span><span style={{ color: 'var(--fg-3)', fontSize: '0.72rem' }}> · {r.gestion}</span></> },
                { header: 'Otorgados', render: (r) => <strong>{fmt(r.total)}</strong> },
                { header: 'Cumplidos', color: '#1f8a65', render: (r) => fmt(r.cumplidos) },
                { header: 'Horas', render: (r) => (r.horas_atendidas == null ? '—' : `${r.horas_atendidas} h`) },
                { header: '% Aus.', color: '#c62828', render: (r) => pct(r.pct_ausentismo) },
                { header: 'Espera', color: '#2f7fd1', render: (r) => minutos(r.espera_prom_min) },
                { header: 'Atenc. reg.', render: (r) => num(r.atenciones_registradas) },
                { header: '% Autoserv.', render: (r) => pct(r.pct_autoservicio) },
              ]}
              filas={filas}
              keyOf={(r) => r.id_espacio ?? 'sin'}
              maxAlto={420}
            />
          )}
        </div>

        <div style={cardStyle}>
          <h3 style={h3Style}>Atención por agente</h3>
          <p style={notaStyle}>Turnos cuyo recurso es un agente (top 15 por otorgados) · Atenc. reg. = atenciones con intervención registrada</p>
          {agentes.isLoading ? (
            <div style={{ padding: 24 }}><CenterMsg>Cargando…</CenterMsg></div>
          ) : !agentes.data?.length ? (
            <div style={{ padding: 24 }}><CenterMsg>Sin turnos por agente en el período.</CenterMsg></div>
          ) : (
            <TablaAt<AtPorAgente>
              columnas={[
                { header: 'Agente', texto: true, render: (r) => <><span style={{ fontWeight: 600 }}>{r.agente}</span>{r.ubicaciones && <span style={{ color: 'var(--fg-3)', fontSize: '0.72rem' }}> · {r.ubicaciones}</span>}</> },
                { header: 'Otorgados', render: (r) => <strong>{fmt(r.total)}</strong> },
                { header: 'Cumplidos', color: '#1f8a65', render: (r) => fmt(r.cumplidos) },
                { header: 'Ausentes', color: '#c62828', render: (r) => fmt(r.ausentes) },
                { header: '% Aus.', color: '#c62828', render: (r) => pct(r.pct_ausentismo) },
                { header: 'Espera', color: '#2f7fd1', render: (r) => minutos(r.espera_prom_min) },
                { header: 'Atenc. reg.', render: (r) => num(r.atenciones_registradas) },
              ]}
              filas={agentes.data}
              keyOf={(r) => r.id_agente}
              maxAlto={420}
            />
          )}
        </div>
      </div>
    </Seccion>
  )
}
