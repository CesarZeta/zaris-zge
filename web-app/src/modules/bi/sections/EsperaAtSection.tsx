import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ChartCard, CenterMsg, KpiCard, KpiRow } from '../components/ui'
import { AXIS, Seccion, fmt, tooltipStyle } from '../components/SeccionHeader'
import { TotalLabel } from '../components/barLabels'
import { TablaAt, cardStyle, h3Style, minutos, notaStyle, pct } from '../components/atUtils'
import { useAtEspera } from '../hooks/useBi'
import { periodoEnLetras } from '../lib/periodo'
import type { AtEsperaUbicacion, BiFiltros } from '../lib/types'

// Sección ESPERA del tablero de ATENCIÓN: tiempo de espera REAL (primer llamado
// del colero vs hora del turno, mig 105) — KPIs, distribución por tramos y el
// detalle por ubicación. Solo cuentan los llamados del mismo día del turno.

// Semáforo por tramo: es tiempo, no estado (mismo criterio que los tramos de
// respuesta del Operativo).
const COLOR_TRAMO: Record<string, string> = {
  'A tiempo': '#1f8a65',
  '5-15 min': '#f5b800',
  '15-30 min': '#f57f17',
  '30-60 min': '#cf2d56',
  'Más de 60 min': '#c62828',
}

export function EsperaAtSection({ filtros }: { filtros: BiFiltros }) {
  const espera = useAtEspera(filtros)
  const e = espera.data
  const tramos = e?.tramos ?? []
  const hayLlamados = !!e?.llamados

  return (
    <Seccion id="espera" titulo="Espera y llamados" periodo={periodoEnLetras(filtros).actual}>
      <KpiRow n={4}>
        <KpiCard label="Turnos llamados" value={fmt(e?.llamados)} sub="con al menos un llamado el día del turno" />
        <KpiCard label="Espera promedio" value={minutos(e?.espera_prom_min)} accent="#2f7fd1" sub={e?.espera_max_min != null ? `máxima ${minutos(e.espera_max_min)}` : undefined} />
        <KpiCard label="% Llamados a tiempo" value={pct(e?.pct_a_tiempo)} accent="#1f8a65" sub={e ? `hasta ${e.tolerancia_min} min después de la hora del turno` : undefined} />
        <KpiCard label="Re-llamados" value={fmt(e?.re_llamados)} accent="#f57f17" sub="turnos llamados más de una vez" />
      </KpiRow>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 16 }}>
        <ChartCard title="Distribución de la espera" height={300}>
          {espera.isLoading ? (
            <CenterMsg>Cargando…</CenterMsg>
          ) : !hayLlamados ? (
            <CenterMsg>Sin llamados en el período (la espera real se mide desde el colero).</CenterMsg>
          ) : (
            <ResponsiveContainer>
              <BarChart data={tramos} margin={{ top: 24, right: 12, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" vertical={false} />
                <XAxis dataKey="tramo" tick={AXIS} interval={0} />
                <YAxis tick={AXIS} allowDecimals={false} />
                <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(245,78,0,0.06)' }} />
                <Bar dataKey="total" name="Turnos" radius={[4, 4, 0, 0]}>
                  {tramos.map((t) => <Cell key={t.tramo} fill={COLOR_TRAMO[t.tramo] ?? '#9e9e9e'} />)}
                  <LabelList dataKey="total" position="top" content={TotalLabel} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <div style={cardStyle}>
          <h3 style={h3Style}>Espera por ubicación</h3>
          <p style={notaStyle}>Promedio sobre los turnos llamados · a tiempo = dentro de la tolerancia</p>
          {espera.isLoading ? (
            <div style={{ padding: 24 }}><CenterMsg>Cargando…</CenterMsg></div>
          ) : !e?.por_ubicacion.length ? (
            <div style={{ padding: 24 }}><CenterMsg>Sin llamados en el período.</CenterMsg></div>
          ) : (
            <TablaAt<AtEsperaUbicacion>
              columnas={[
                { header: 'Ubicación', texto: true, render: (r) => <><span style={{ fontWeight: 600 }}>{r.ubicacion}</span><span style={{ color: 'var(--fg-3)', fontSize: '0.72rem' }}> · {r.gestion}</span></> },
                { header: 'Llamados', render: (r) => <strong>{fmt(r.llamados)}</strong> },
                { header: 'Re-llam.', color: '#f57f17', render: (r) => fmt(r.re_llamados) },
                { header: '% A tiempo', color: '#1f8a65', render: (r) => pct(r.pct_a_tiempo) },
                { header: 'Espera prom.', color: '#2f7fd1', render: (r) => minutos(r.espera_prom_min) },
                { header: 'Máx.', render: (r) => minutos(r.espera_max_min) },
              ]}
              filas={e.por_ubicacion}
              keyOf={(r) => r.id_espacio ?? 'sin'}
              maxAlto={260}
            />
          )}
        </div>
      </div>
    </Seccion>
  )
}
