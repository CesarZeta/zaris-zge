import { useState } from 'react'
import { Cell, Label, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { ChartCard, CenterMsg, KpiCard, KpiRow } from '../components/ui'
import { DonaCentro, Seccion, fmt, legendStyle, pieLabel, tooltipStyle, totalDe } from '../components/SeccionHeader'
import { HistogramaTemporal } from '../components/HistogramaTemporal'
import { exportarCsv, hoyISO } from '../components/exportCsv'
import { TablaAt, Tri, VAR_NEUTRO, cardStyle, h3Style, notaStyle, pct, varTxt } from '../components/atUtils'
import { useAtEventos } from '../hooks/useBi'
import { biApi } from '../lib/api'
import { periodoEnLetras } from '../lib/periodo'
import type { AtEventoFila, BiFiltros } from '../lib/types'
import { COLOR_RESERVA, LABEL_RESERVA, labelDia } from '../lib/theme'

// Sección EVENTOS del tablero de ATENCIÓN (Cultura: Entradas + Agenda):
// eventos del período con su cupo, reservas vigentes / asistencias /
// cancelaciones, % asistencia (solo eventos ya realizados), % cupo utilizado,
// origen, histograma de reservas y la tabla por evento. El filtro de prestación
// no aplica (los eventos no son prestaciones).

const SERIES = [
  { key: 'reservada', name: 'Reservadas', color: COLOR_RESERVA.reservada },
  { key: 'asistio', name: LABEL_RESERVA.asistio, color: COLOR_RESERVA.asistio },
  { key: 'cancelada', name: LABEL_RESERVA.cancelada, color: COLOR_RESERVA.cancelada },
]
const ESTADO_EVENTO: Record<string, string> = { activo: 'Activo', finalizado: 'Finalizado', cancelado: 'Cancelado' }

export function EventosAtSection({ filtros }: { filtros: BiFiltros }) {
  const eventos = useAtEventos(filtros, 30)
  const ev = eventos.data
  const periodo = periodoEnLetras(filtros)
  const [exportando, setExportando] = useState(false)
  const porEstado = (ev?.por_estado ?? []).map((e) => ({ ...e, label: LABEL_RESERVA[e.estado] ?? e.estado }))

  function handleExport() {
    if (!ev?.por_evento.length) return
    setExportando(true)
    try {
      exportarCsv(
        `atencion_eventos_${hoyISO()}.csv`,
        [
          { header: 'Evento', value: (d) => d.evento },
          { header: 'Fecha', value: (d) => d.fecha },
          { header: 'Hora', value: (d) => d.hora_inicio?.slice(0, 5) ?? '' },
          { header: 'Estado', value: (d) => ESTADO_EVENTO[d.estado] ?? d.estado },
          { header: 'Gestión', value: (d) => d.gestion },
          { header: 'Ubicación', value: (d) => d.ubicacion },
          { header: 'Cupo', value: (d) => d.cupo ?? '' },
          { header: 'Reservas vigentes', value: (d) => d.vigentes },
          { header: 'Asistieron', value: (d) => d.asistieron },
          { header: 'Canceladas', value: (d) => d.canceladas },
          { header: 'Autoservicio', value: (d) => d.autoservicio },
          { header: '% Cupo', value: (d) => d.pct_cupo ?? '' },
          { header: '% Asistencia', value: (d) => d.pct_asistencia ?? '' },
        ],
        ev.por_evento,
      )
    } finally {
      setExportando(false)
    }
  }

  return (
    <Seccion
      id="eventos"
      titulo="Eventos y reservas"
      periodo={periodo.actual}
      onExport={handleExport}
      exportando={exportando}
      exportDisabled={!ev?.por_evento.length}
      exportLabel="Exportar eventos (CSV)"
    >
      {filtros.id_tipo_prestacion && (
        <p style={{ ...notaStyle, margin: '-16px 0 0' }}>El filtro de prestación no aplica a los eventos.</p>
      )}
      <KpiRow n={6}>
        <KpiCard
          label="Eventos"
          value={fmt(ev?.eventos)}
          sub={ev ? `${fmt(ev.eventos_realizados)} realizados · ${fmt(ev.eventos_cancelados)} cancelados` : undefined}
        />
        <KpiCard
          label="Reservas"
          value={fmt(ev?.reservas)}
          sub={ev?.anterior && periodo.anterior ? `${periodo.anterior}: ${fmt(ev.anterior.reservas)} (${varTxt(ev.var_pct)})` : `${fmt(ev?.vigentes)} vigentes`}
        />
        <KpiCard label="Asistieron" value={<span style={{ color: VAR_NEUTRO }}>{fmt(ev?.asistieron)}</span>} accent="#1f8a65" sub={ev ? `${fmt(ev.canceladas)} reservas canceladas` : undefined} />
        <KpiCard
          label="% Asistencia"
          value={<>{pct(ev?.pct_asistencia)}<Tri actual={ev?.pct_asistencia} anterior={ev?.anterior?.pct_asistencia} /></>}
          accent="#1f8a65"
          sub="asistieron / reservas vigentes de eventos realizados"
        />
        <KpiCard
          label="% Cupo utilizado"
          value={<>{pct(ev?.pct_cupo)}<Tri actual={ev?.pct_cupo} anterior={ev?.anterior?.pct_cupo} /></>}
          accent="#2f7fd1"
          sub={ev ? `${fmt(ev.vigentes)} vigentes / ${fmt(ev.cupo_total)} cupos` : undefined}
        />
        <KpiCard label="% Autoservicio" value={pct(ev?.pct_autoservicio)} accent="#6a1b9a" sub="reservas hechas por el vecino" />
      </KpiRow>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 2fr) minmax(300px, 1fr)', gap: 16 }}>
        <HistogramaTemporal
          tituloBase="Reservas de eventos"
          series={SERIES}
          fetchMensual={(f) => biApi.atEventosMensual(f)}
          fetchDiario={(mes, f) => biApi.atEventosDiario(mes, f)}
          cacheKey="at-eventos"
          filtros={filtros}
        />
        <ChartCard title="Reservas por estado" height={300}>
          {eventos.isLoading ? (
            <CenterMsg>Cargando…</CenterMsg>
          ) : !porEstado.length ? (
            <CenterMsg>Sin reservas en el período.</CenterMsg>
          ) : (
            <ResponsiveContainer>
              <PieChart>
                <Pie data={porEstado} dataKey="total" nameKey="label" innerRadius="50%" outerRadius="78%" paddingAngle={2} label={pieLabel} labelLine={false}>
                  <Label content={DonaCentro} position="center" value={totalDe(porEstado)} />
                  {porEstado.map((e) => <Cell key={e.estado} fill={COLOR_RESERVA[e.estado] ?? '#9e9e9e'} />)}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={legendStyle} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      </div>

      <div style={cardStyle}>
        <h3 style={h3Style}>Eventos del período</h3>
        <p style={notaStyle}>Últimos 30 por fecha · % Asist. solo en eventos ya realizados · Vigentes = reservadas + asistieron</p>
        {eventos.isLoading ? (
          <div style={{ padding: 24 }}><CenterMsg>Cargando…</CenterMsg></div>
        ) : !ev?.por_evento.length ? (
          <div style={{ padding: 24 }}><CenterMsg>Sin eventos en el período.</CenterMsg></div>
        ) : (
          <TablaAt<AtEventoFila>
            columnas={[
              { header: 'Evento', texto: true, render: (r) => <><span style={{ fontWeight: 600 }}>{r.evento}</span><span style={{ color: 'var(--fg-3)', fontSize: '0.72rem' }}> · {labelDia(r.fecha)}{r.hora_inicio ? ` ${r.hora_inicio.slice(0, 5)}` : ''} · {r.ubicacion} · {r.gestion}</span></> },
              { header: 'Estado', render: (r) => ESTADO_EVENTO[r.estado] ?? r.estado },
              { header: 'Cupo', render: (r) => (r.cupo == null ? '—' : fmt(r.cupo)) },
              { header: 'Vigentes', color: '#2f7fd1', render: (r) => <strong>{fmt(r.vigentes)}</strong> },
              { header: 'Asist.', color: '#1f8a65', render: (r) => fmt(r.asistieron) },
              { header: 'Canc.', render: (r) => fmt(r.canceladas) },
              { header: '% Cupo', render: (r) => pct(r.pct_cupo) },
              { header: '% Asist.', color: '#1f8a65', render: (r) => pct(r.pct_asistencia) },
            ]}
            filas={ev.por_evento}
            keyOf={(r) => r.id_evento}
            maxAlto={460}
          />
        )}
      </div>
    </Seccion>
  )
}
