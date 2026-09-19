import { useState } from 'react'
import { Cell, Label, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { ChartCard, CenterMsg, KpiCard, KpiRow } from '../components/ui'
import { DonaCentro, Seccion, fmt, legendStyle, pieLabel, tooltipStyle, totalDe } from '../components/SeccionHeader'
import { HistogramaTemporal } from '../components/HistogramaTemporal'
import { exportarCsv, hoyISO } from '../components/exportCsv'
import { TablaAt, Tri, VAR_NEUTRO, cardStyle, h3Style, minutos, notaStyle, pct, varTxt } from '../components/atUtils'
import { useAtGuardia } from '../hooks/useBi'
import { biApi } from '../lib/api'
import { periodoEnLetras } from '../lib/periodo'
import type { AtGuardiaInd, BiFiltros } from '../lib/types'
import { COLOR_GUARDIA, LABEL_GUARDIA } from '../lib/theme'

// Sección GUARDIA del tablero de ATENCIÓN: atenciones derivadas desde
// Emergencias (emergencia_atencion, mig 106; sin turno de por medio, decisión de
// César 2026-09-01). KPIs, histograma de derivaciones, dona por estado y el
// desglose por médico, tipo de emergencia y prioridad. El filtro de prestación
// no aplica acá (la guardia no tiene prestaciones).

const SERIES = [
  { key: 'pendiente', name: LABEL_GUARDIA.pendiente, color: COLOR_GUARDIA.pendiente },
  { key: 'atendida', name: LABEL_GUARDIA.atendida, color: COLOR_GUARDIA.atendida },
  { key: 'ausente', name: LABEL_GUARDIA.ausente, color: COLOR_GUARDIA.ausente },
]

type FilaAgente = AtGuardiaInd & { id_agente: number; agente: string }
type FilaTipo = AtGuardiaInd & { id_tipo: number | null; tipo: string }
type FilaPrioridad = AtGuardiaInd & { id_prioridad: number | null; prioridad: string }

export function GuardiaAtSection({ filtros }: { filtros: BiFiltros }) {
  const guardia = useAtGuardia(filtros)
  const g = guardia.data
  const periodo = periodoEnLetras(filtros)
  const [exportando, setExportando] = useState(false)
  const porEstado = (g?.por_estado ?? []).map((e) => ({ ...e, label: LABEL_GUARDIA[e.estado] ?? e.estado }))

  async function handleExport() {
    setExportando(true)
    try {
      const { data } = await biApi.atGuardiaDetalle(filtros, 10000, 0)
      exportarCsv(
        `atencion_guardia_${hoyISO()}.csv`,
        [
          { header: 'Atención', value: (d) => d.id_emergencia_atencion },
          { header: 'Evento', value: (d) => d.numero_operativo ?? '' },
          { header: 'Estado', value: (d) => LABEL_GUARDIA[d.estado] ?? d.estado },
          { header: 'Derivado', value: (d) => d.derivado_en },
          { header: 'Atendido', value: (d) => d.atendido_en ?? '' },
          { header: 'Demora (min)', value: (d) => d.demora_min ?? '' },
          { header: 'Tipo', value: (d) => d.tipo },
          { header: 'Prioridad', value: (d) => d.prioridad },
          { header: 'Ubicación', value: (d) => d.ubicacion },
          { header: 'Médico', value: (d) => d.agente ?? '' },
          { header: 'Vecino identificado', value: (d) => (d.con_ciudadano ? 'Sí' : 'No') },
        ],
        data,
      )
    } finally {
      setExportando(false)
    }
  }

  return (
    <Seccion
      id="guardia"
      titulo="Guardia"
      periodo={periodo.actual}
      onExport={handleExport}
      exportando={exportando}
      exportDisabled={!g?.derivaciones}
      exportLabel="Exportar derivaciones"
    >
      {filtros.id_tipo_prestacion && (
        <p style={{ ...notaStyle, margin: '-16px 0 0' }}>El filtro de prestación no aplica a la Guardia (las atenciones derivadas no van con turno).</p>
      )}
      <KpiRow n={6}>
        <KpiCard
          label="Derivaciones"
          value={fmt(g?.derivaciones)}
          sub={g?.anterior && periodo.anterior ? `${periodo.anterior}: ${fmt(g.anterior.derivaciones)}` : `${fmt(g?.con_ciudadano)} con vecino identificado`}
        />
        <KpiCard
          label="Variación vs anterior"
          value={<span style={{ color: VAR_NEUTRO }}>{varTxt(g?.var_pct)}</span>}
          sub={periodo.anterior ? (g?.var_pct != null ? `vs ${periodo.anterior}` : `sin datos en ${periodo.anterior}`) : 'sin período comparable'}
        />
        <KpiCard
          label="% Atendidas"
          value={<>{pct(g?.pct_atendidas)}<Tri actual={g?.pct_atendidas} anterior={g?.anterior?.pct_atendidas} /></>}
          accent="#1f8a65"
          sub={g ? `${fmt(g.atendidas)} atendidas / ${fmt(g.atendidas + g.ausentes)} con desenlace` : undefined}
        />
        <KpiCard
          label="% Ausentes"
          value={<>{pct(g?.pct_ausentes)}<Tri actual={g?.pct_ausentes} anterior={g?.anterior?.pct_ausentes} invertir /></>}
          accent="#c62828"
          sub={g ? `${fmt(g.ausentes)} no se presentaron` : undefined}
        />
        <KpiCard label="Pendientes" value={fmt(g?.pendientes)} accent="#f57f17" sub="derivadas sin atender" />
        <KpiCard
          label="Demora derivación → atención"
          value={<>{minutos(g?.demora_prom_min)}<Tri actual={g?.demora_prom_min} anterior={g?.anterior?.demora_prom_min} invertir /></>}
          accent="#2f7fd1"
          sub={g?.demora_max_min != null ? `máxima ${minutos(g.demora_max_min)}` : undefined}
        />
      </KpiRow>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 2fr) minmax(300px, 1fr)', gap: 16 }}>
        <HistogramaTemporal
          tituloBase="Derivaciones a la Guardia"
          series={SERIES}
          fetchMensual={(f) => biApi.atGuardiaMensual(f)}
          fetchDiario={(mes, f) => biApi.atGuardiaDiario(mes, f)}
          cacheKey="at-guardia"
          filtros={filtros}
        />
        <ChartCard title="Derivaciones por estado" height={300}>
          {guardia.isLoading ? (
            <CenterMsg>Cargando…</CenterMsg>
          ) : !porEstado.length ? (
            <CenterMsg>Sin derivaciones en el período.</CenterMsg>
          ) : (
            <ResponsiveContainer>
              <PieChart>
                <Pie data={porEstado} dataKey="total" nameKey="label" innerRadius="50%" outerRadius="78%" paddingAngle={2} label={pieLabel} labelLine={false}>
                  <Label content={DonaCentro} position="center" value={totalDe(porEstado)} />
                  {porEstado.map((e) => <Cell key={e.estado} fill={COLOR_GUARDIA[e.estado] ?? '#9e9e9e'} />)}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={legendStyle} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 16 }}>
        <div style={cardStyle}>
          <h3 style={h3Style}>Atenciones por médico</h3>
          <p style={notaStyle}>Agente que registró la atención · demora = derivación → atención</p>
          {guardia.isLoading ? (
            <div style={{ padding: 24 }}><CenterMsg>Cargando…</CenterMsg></div>
          ) : !g?.por_agente.length ? (
            <div style={{ padding: 24 }}><CenterMsg>Sin atenciones registradas en el período.</CenterMsg></div>
          ) : (
            <TablaAt<FilaAgente>
              columnas={[
                { header: 'Médico', texto: true, render: (r) => <span style={{ fontWeight: 600 }}>{r.agente}</span> },
                { header: 'Atendidas', color: '#1f8a65', render: (r) => <strong>{fmt(r.atendidas)}</strong> },
                { header: 'Demora prom.', color: '#2f7fd1', render: (r) => minutos(r.demora_prom_min) },
                { header: 'Máx.', render: (r) => minutos(r.demora_max_min) },
              ]}
              filas={g.por_agente}
              keyOf={(r) => r.id_agente}
              maxAlto={320}
            />
          )}
        </div>

        <div style={cardStyle}>
          <h3 style={h3Style}>Derivaciones por tipo de emergencia</h3>
          <p style={notaStyle}>Top 10 por derivaciones</p>
          {guardia.isLoading ? (
            <div style={{ padding: 24 }}><CenterMsg>Cargando…</CenterMsg></div>
          ) : !g?.por_tipo.length ? (
            <div style={{ padding: 24 }}><CenterMsg>Sin derivaciones en el período.</CenterMsg></div>
          ) : (
            <TablaAt<FilaTipo>
              columnas={[
                { header: 'Tipo', texto: true, render: (r) => r.tipo },
                { header: 'Deriv.', render: (r) => <strong>{fmt(r.derivaciones)}</strong> },
                { header: 'Atend.', color: '#1f8a65', render: (r) => fmt(r.atendidas) },
                { header: 'Aus.', color: '#c62828', render: (r) => fmt(r.ausentes) },
                { header: 'Demora', color: '#2f7fd1', render: (r) => minutos(r.demora_prom_min) },
              ]}
              filas={g.por_tipo}
              keyOf={(r) => r.id_tipo ?? 'sin'}
              maxAlto={320}
            />
          )}
        </div>

        <div style={cardStyle}>
          <h3 style={h3Style}>Derivaciones por prioridad</h3>
          <p style={notaStyle}>Prioridad del evento de emergencia</p>
          {guardia.isLoading ? (
            <div style={{ padding: 24 }}><CenterMsg>Cargando…</CenterMsg></div>
          ) : !g?.por_prioridad.length ? (
            <div style={{ padding: 24 }}><CenterMsg>Sin derivaciones en el período.</CenterMsg></div>
          ) : (
            <TablaAt<FilaPrioridad>
              columnas={[
                { header: 'Prioridad', texto: true, render: (r) => r.prioridad },
                { header: 'Deriv.', render: (r) => <strong>{fmt(r.derivaciones)}</strong> },
                { header: 'Atend.', color: '#1f8a65', render: (r) => fmt(r.atendidas) },
                { header: 'Aus.', color: '#c62828', render: (r) => fmt(r.ausentes) },
                { header: 'Demora', color: '#2f7fd1', render: (r) => minutos(r.demora_prom_min) },
              ]}
              filas={g.por_prioridad}
              keyOf={(r) => r.id_prioridad ?? 'sin'}
              maxAlto={320}
            />
          )}
        </div>
      </div>
    </Seccion>
  )
}
