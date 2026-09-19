import { useState } from 'react'
import { Cell, Label, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { ChartCard, CenterMsg, KpiCard, KpiRow } from '../components/ui'
import { DonaCentro, Seccion, fmt, legendStyle, pieLabel, tooltipStyle, totalDe } from '../components/SeccionHeader'
import { exportarCsv, hoyISO } from '../components/exportCsv'
import { Tri, VAR_NEUTRO, cardStyle, h3Style, minutos, notaStyle, pct, varTxt } from '../components/atUtils'
import { useAtMatriz, useAtScore } from '../hooks/useBi'
import { biApi } from '../lib/api'
import { periodoEnLetras } from '../lib/periodo'
import { PALETA_CATEGORICA, colorTurno, labelOrigen, labelTurno } from '../lib/theme'
import type { AtFila, AtPrestacionFila, BiFiltros } from '../lib/types'

// Sección RESUMEN del tablero de ATENCIÓN: KPIs del período, matriz
// UBICACIÓN → PRESTACIÓN (expandible, con variación vs período anterior) y las
// tres donas de composición: estado, origen y niveles de satisfacción (CSAT §42).

const NIVEL_LABEL: Record<number, string> = {
  1: 'Muy insatisfecho', 2: 'Insatisfecho', 3: 'Neutro', 4: 'Satisfecho', 5: 'Muy satisfecho',
}
const NIVEL_COLOR: Record<number, string> = {
  1: '#c62828', 2: '#cf2d56', 3: '#f57f17', 4: '#00897b', 5: '#1f8a65',
}

export function ResumenAtSection({ filtros }: { filtros: BiFiltros }) {
  const score = useAtScore(filtros)
  const matriz = useAtMatriz(filtros)
  const [abiertas, setAbiertas] = useState<Set<number | null>>(new Set())
  const [exportando, setExportando] = useState(false)
  const s = score.data
  const periodo = periodoEnLetras(filtros)

  const porEstado = (s?.por_estado ?? []).map((e) => ({ ...e, label: labelTurno(e.estado) }))
  const porOrigen = (s?.por_origen ?? []).map((o) => ({ ...o, label: labelOrigen(o.origen) }))
  const niveles = (s?.niveles ?? []).map((n) => ({ ...n, label: NIVEL_LABEL[n.clasificacion] ?? `Nivel ${n.clasificacion}` }))

  function toggle(id: number | null) {
    setAbiertas((prev) => {
      const n = new Set(prev)
      if (n.has(id)) n.delete(id)
      else n.add(id)
      return n
    })
  }

  // Exporta los TURNOS del universo filtrado (sin datos personales del vecino).
  async function handleExport() {
    setExportando(true)
    try {
      const { data } = await biApi.atTurnosDetalle(filtros, 10000, 0)
      exportarCsv(
        `atencion_turnos_${hoyISO()}.csv`,
        [
          { header: 'Turno', value: (d) => d.id_turno },
          { header: 'Fecha', value: (d) => d.fecha },
          { header: 'Hora', value: (d) => d.hora_inicio?.slice(0, 5) ?? '' },
          { header: 'Número', value: (d) => d.numero_diario ?? '' },
          { header: 'Estado', value: (d) => labelTurno(d.estado) },
          { header: 'Origen', value: (d) => labelOrigen(d.origen) },
          { header: 'Gestión', value: (d) => d.gestion },
          { header: 'Ubicación', value: (d) => d.ubicacion },
          { header: 'Prestación', value: (d) => d.prestacion },
          { header: 'Agente', value: (d) => d.agente ?? '' },
          { header: 'Primer llamado', value: (d) => d.primer_llamado ?? '' },
          { header: 'Llamados', value: (d) => d.n_llamados },
          { header: 'Espera (min)', value: (d) => d.espera_min ?? '' },
          { header: 'Atención registrada', value: (d) => (d.atencion_registrada ? 'Sí' : 'No') },
          { header: 'CSAT (1-5)', value: (d) => d.csat ?? '' },
        ],
        data,
      )
    } finally {
      setExportando(false)
    }
  }

  return (
    <Seccion
      id="resumen"
      titulo="Resumen"
      periodo={periodo.actual}
      onExport={handleExport}
      exportando={exportando}
      exportDisabled={!s?.total}
      exportLabel="Exportar turnos filtrados"
    >
      <KpiRow n={6}>
        <KpiCard
          label="Turnos otorgados"
          value={fmt(s?.total)}
          sub={s?.anterior && periodo.anterior ? `${periodo.anterior}: ${fmt(s.anterior.total)}` : `${fmt(s?.pendientes)} pendientes`}
        />
        <KpiCard
          label="Variación vs anterior"
          value={<span style={{ color: VAR_NEUTRO }}>{varTxt(s?.var_pct)}</span>}
          sub={periodo.anterior
            ? (s?.var_pct != null ? `vs ${periodo.anterior}` : `sin datos en ${periodo.anterior}`)
            : 'sin período comparable'}
        />
        <KpiCard
          label="% Cumplimiento"
          value={<>{pct(s?.pct_cumplimiento)}<Tri actual={s?.pct_cumplimiento} anterior={s?.anterior?.pct_cumplimiento} /></>}
          accent="#1f8a65"
          sub={s ? `${fmt(s.cumplidos)} cumplidos / ${fmt(s.total - s.pendientes)} con desenlace` : undefined}
        />
        <KpiCard
          label="% Ausentismo"
          value={<>{pct(s?.pct_ausentismo)}<Tri actual={s?.pct_ausentismo} anterior={s?.anterior?.pct_ausentismo} invertir /></>}
          accent="#c62828"
          sub={s ? `${fmt(s.ausentes)} ausentes · ${fmt(s.cancelados)} cancelados (${pct(s.pct_cancelacion)})` : undefined}
        />
        <KpiCard
          label="Espera promedio"
          value={<>{minutos(s?.espera_prom_min)}<Tri actual={s?.espera_prom_min} anterior={s?.anterior?.espera_prom_min} invertir /></>}
          accent="#2f7fd1"
          sub={s ? (s.llamados ? `${pct(s.pct_a_tiempo)} a tiempo · ${fmt(s.llamados)} llamados` : 'sin llamados en el período') : undefined}
        />
        <KpiCard
          label="% Satisfacción"
          value={<>{pct(s?.pct_sat)}<Tri actual={s?.pct_sat} anterior={s?.anterior?.pct_sat} /></>}
          accent="#6a1b9a"
          sub={s ? `respuesta ${pct(s.tasa_respuesta)} · ${fmt(s.respuestas)}/${fmt(s.enviadas)} encuestas` : undefined}
        />
      </KpiRow>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 16 }}>
        <div style={cardStyle}>
          <h3 style={h3Style}>Indicadores por ubicación y prestación</h3>
          <p style={notaStyle}>
            ▲▼ variación de cada indicador vs {periodo.anterior ?? 'el período anterior'} (verde mejora, rojo empeora) · ■ sin variación o sin dato previo
          </p>
          {matriz.isLoading ? (
            <div style={{ padding: 24 }}><CenterMsg>Cargando…</CenterMsg></div>
          ) : !matriz.data?.filas.length ? (
            <div style={{ padding: 24 }}><CenterMsg>Sin turnos para el filtro elegido.</CenterMsg></div>
          ) : (
            <table style={tableStyle}>
              <thead>
                <tr>
                  <th style={{ ...thStyle, textAlign: 'left', width: 'auto' }}>Ubicación / prestación</th>
                  <th style={thStyle}>Otorgados</th>
                  <th style={thStyle}>% Var</th>
                  <th style={thStyle}>Cumplidos</th>
                  <th style={thStyle}>% Aus.</th>
                  <th style={thStyle}>Espera</th>
                  <th style={thStyle}>% Sat</th>
                </tr>
              </thead>
              <tbody>
                {matriz.data.filas.map((f) => (
                  <FilaGrupo
                    key={f.id_espacio ?? 'sin'}
                    abierta={abiertas.has(f.id_espacio)}
                    onToggle={() => toggle(f.id_espacio)}
                    nombre={f.ubicacion}
                    gestion={f.gestion}
                    fila={f}
                    prestaciones={f.prestaciones}
                  />
                ))}
                <tr style={{ background: 'var(--surface-400)' }}>
                  <td style={{ ...tdNombreStyle, fontWeight: 700 }}>Total</td>
                  <Celdas fila={matriz.data.total} bold />
                </tr>
              </tbody>
            </table>
          )}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16 }}>
          <ChartCard title="Turnos por estado" height={300}>
            {score.isLoading ? (
              <CenterMsg>Cargando…</CenterMsg>
            ) : !porEstado.length ? (
              <CenterMsg>Sin turnos en el período.</CenterMsg>
            ) : (
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={porEstado} dataKey="total" nameKey="label" innerRadius="50%" outerRadius="78%" paddingAngle={2} label={pieLabel} labelLine={false}>
                    <Label content={DonaCentro} position="center" value={totalDe(porEstado)} />
                    {porEstado.map((e) => <Cell key={e.estado} fill={colorTurno(e.estado)} />)}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} />
                  <Legend wrapperStyle={legendStyle} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </ChartCard>

          <ChartCard title="Turnos por origen" height={300}>
            {score.isLoading ? (
              <CenterMsg>Cargando…</CenterMsg>
            ) : !porOrigen.length ? (
              <CenterMsg>Sin turnos en el período.</CenterMsg>
            ) : (
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={porOrigen} dataKey="total" nameKey="label" innerRadius="50%" outerRadius="78%" paddingAngle={2} label={pieLabel} labelLine={false}>
                    <Label content={DonaCentro} position="center" value={totalDe(porOrigen)} />
                    {porOrigen.map((o, i) => <Cell key={o.origen} fill={PALETA_CATEGORICA[(i + 2) % PALETA_CATEGORICA.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} />
                  <Legend wrapperStyle={legendStyle} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </ChartCard>

          <ChartCard
            title="Niveles de satisfacción"
            height={300}
            action={<span style={notaStyle}>El total son las {fmt(s?.respuestas)} encuestas respondidas, no los {fmt(s?.total)} turnos</span>}
          >
            {score.isLoading ? (
              <CenterMsg>Cargando…</CenterMsg>
            ) : !niveles.length ? (
              <CenterMsg>Sin respuestas de encuestas de turnos en el período.</CenterMsg>
            ) : (
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={niveles} dataKey="total" nameKey="label" innerRadius="50%" outerRadius="78%" paddingAngle={2} label={pieLabel} labelLine={false}>
                    <Label content={DonaCentro} position="center" value={totalDe(niveles)} />
                    {niveles.map((n) => <Cell key={n.clasificacion} fill={NIVEL_COLOR[n.clasificacion] ?? '#9e9e9e'} />)}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} />
                  <Legend wrapperStyle={legendStyle} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </ChartCard>
        </div>
      </div>
    </Seccion>
  )
}

function Celdas({ fila, bold }: { fila: AtFila; bold?: boolean }) {
  const w = bold ? 700 : 500
  const ant = fila.ant
  return (
    <>
      <td style={{ ...tdStyle, fontWeight: w }}>{fmt(fila.total)}</td>
      <td style={{ ...tdStyle, fontWeight: w }}>{varTxt(fila.var_pct)}</td>
      <td style={{ ...tdStyle, color: '#1f8a65', fontWeight: w }}>
        {fmt(fila.cumplidos)}<Tri actual={fila.pct_cumplimiento} anterior={ant?.pct_cumplimiento} />
      </td>
      <td style={{ ...tdStyle, color: '#c62828', fontWeight: w }}>
        {pct(fila.pct_ausentismo)}<Tri actual={fila.pct_ausentismo} anterior={ant?.pct_ausentismo} invertir />
      </td>
      <td style={{ ...tdStyle, color: '#2f7fd1', fontWeight: w }}>
        {minutos(fila.espera_prom_min)}<Tri actual={fila.espera_prom_min} anterior={ant?.espera_prom_min} invertir />
      </td>
      <td style={{ ...tdStyle, color: '#6a1b9a', fontWeight: w }}>
        {pct(fila.pct_sat)}<Tri actual={fila.pct_sat} anterior={ant?.pct_sat} />
      </td>
    </>
  )
}

function FilaGrupo({
  abierta, onToggle, nombre, gestion, fila, prestaciones,
}: {
  abierta: boolean
  onToggle: () => void
  nombre: string
  gestion: string
  fila: AtFila
  prestaciones: AtPrestacionFila[]
}) {
  return (
    <>
      <tr style={{ borderTop: '1px solid var(--border-primary)' }}>
        <td style={tdNombreStyle}>
          <button type="button" onClick={onToggle} style={expandBtnStyle} aria-expanded={abierta}>
            <span aria-hidden="true" style={{ display: 'inline-block', width: 14 }}>{abierta ? '▾' : '▸'}</span>
            <span style={{ fontWeight: 600 }}>{nombre}</span>
            <span style={{ color: 'var(--fg-3)', fontSize: '0.72rem' }}> · {gestion} ({prestaciones.length} {prestaciones.length === 1 ? 'prestación' : 'prestaciones'})</span>
          </button>
        </td>
        <Celdas fila={fila} />
      </tr>
      {abierta && prestaciones.map((p) => (
        <tr key={p.id_tipo_prestacion ?? 'sin'} style={{ background: 'var(--surface-100)' }}>
          <td style={{ ...tdNombreStyle, paddingLeft: 34, color: 'var(--fg-2)' }}>{p.prestacion}</td>
          <Celdas fila={p} />
        </tr>
      ))}
    </>
  )
}

// Sin scroll horizontal (regla del módulo): numéricas a ancho mínimo, la
// primera columna absorbe el resto envolviendo con 'anywhere'.
const tableStyle: React.CSSProperties = {
  width: '100%', borderCollapse: 'collapse',
  fontFamily: 'var(--font-display)', fontSize: '0.8rem', color: 'var(--fg-1)',
}
const thStyle: React.CSSProperties = {
  textAlign: 'right', padding: '6px 10px', fontSize: '0.68rem', textTransform: 'uppercase',
  letterSpacing: '0.05em', color: 'var(--fg-3)', fontWeight: 700,
  borderBottom: '2px solid var(--zaris-orange)', whiteSpace: 'nowrap', width: '1%',
}
const tdStyle: React.CSSProperties = {
  textAlign: 'right', padding: '6px 10px', whiteSpace: 'nowrap',
  borderBottom: '1px solid var(--border-primary)',
}
const tdNombreStyle: React.CSSProperties = {
  ...tdStyle, textAlign: 'left', whiteSpace: 'normal', overflowWrap: 'anywhere',
}
const expandBtnStyle: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'baseline', gap: 4,
  background: 'none', border: 'none', cursor: 'pointer', padding: 0,
  fontFamily: 'var(--font-display)', fontSize: '0.8rem', color: 'var(--fg-1)', textAlign: 'left',
}
