import { useState } from 'react'
import { Cell, Label, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { ChartCard, CenterMsg, KpiCard, KpiRow } from '../components/ui'
import { DonaCentro, Seccion, fmt, legendStyle, pieLabel, tooltipStyle, totalDe } from '../components/SeccionHeader'
import { exportarCsv, hoyISO } from '../components/exportCsv'
import { useEjCierresPorEstado, useEjMatriz, useEjScore } from '../hooks/useBi'
import { periodoEnLetras } from '../lib/periodo'
import type { BiFiltros, EjFilaBase } from '../lib/types'

// Sección RESUMEN del tablero Ejecutivo (VL "Resumen de incidentes del mes"):
// score del período (% cierre / % SLA / % satisfacción), niveles de
// satisfacción y la matriz subárea → tipo expandible.
// Los emojis del tablero de referencia NO se replican (§13: prohibidos).

const NIVEL_LABEL: Record<number, string> = {
  1: 'Muy insatisfecho', 2: 'Insatisfecho', 3: 'Neutro', 4: 'Satisfecho', 5: 'Muy satisfecho',
}
// Semáforo de satisfacción (es sentimiento, no estado — el semáforo es válido).
const NIVEL_COLOR: Record<number, string> = {
  1: '#c62828', 2: '#cf2d56', 3: '#f57f17', 4: '#00897b', 5: '#1f8a65',
}

const pct = (v: number | null | undefined) => (v == null ? '—' : `${v}%`)
const dias = (v: number | null | undefined) => (v == null ? '—' : `${v} d`)

// % Var de demanda: bajar es bueno (verde), subir es alerta (rojo).
function varColor(v: number | null | undefined): string {
  if (v == null) return 'var(--fg-3)'
  return v <= 0 ? '#1f8a65' : '#cf2d56'
}
function varTxt(v: number | null | undefined): string {
  if (v == null) return '—'
  return `${v > 0 ? '+' : ''}${v}%`
}

// Triangulito de variación vs período anterior (César 2026-08-30): dirección
// real (▲ subió / ▼ bajó), color por VALORACIÓN (verde mejora / rojo empeora;
// `invertir` para "menos es mejor", ej. días de demora). Sin variación o sin
// dato previo → cuadradito gris.
function Tri({ actual, anterior, invertir }: {
  actual: number | null | undefined
  anterior: number | null | undefined
  invertir?: boolean
}) {
  const base: React.CSSProperties = { marginLeft: 5, fontSize: '0.6rem', verticalAlign: 'middle' }
  if (actual == null || anterior == null) {
    return <span aria-hidden="true" style={{ ...base, color: 'var(--fg-3)', opacity: 0.55 }} title="Sin dato del período anterior">■</span>
  }
  const delta = actual - anterior
  if (Math.abs(delta) < 0.05) {
    return <span aria-hidden="true" style={{ ...base, color: 'var(--fg-3)' }} title={`Sin variación (anterior: ${anterior})`}>■</span>
  }
  const mejora = invertir ? delta < 0 : delta > 0
  return (
    <span
      aria-hidden="true"
      style={{ ...base, color: mejora ? '#1f8a65' : '#cf2d56' }}
      title={`Período anterior: ${anterior}`}
    >
      {delta > 0 ? '▲' : '▼'}
    </span>
  )
}

export function ResumenEjSection({ filtros }: { filtros: BiFiltros }) {
  const score = useEjScore(filtros)
  const matriz = useEjMatriz(filtros)
  const cierres = useEjCierresPorEstado(filtros)
  const totalCierres = totalDe(cierres.data ?? [])
  const [abiertas, setAbiertas] = useState<Set<number | null>>(new Set())
  const [exportando, setExportando] = useState(false)
  const s = score.data
  const periodo = periodoEnLetras(filtros)

  const niveles = (s?.niveles ?? []).map((n) => ({
    ...n,
    label: NIVEL_LABEL[n.clasificacion] ?? `Nivel ${n.clasificacion}`,
  }))

  function toggle(id: number | null) {
    setAbiertas((prev) => {
      const n = new Set(prev)
      if (n.has(id)) n.delete(id)
      else n.add(id)
      return n
    })
  }

  function handleExport() {
    if (!matriz.data) return
    setExportando(true)
    try {
      const filas = matriz.data.filas.flatMap((f) => [
        { nivel: 'Subárea', nombre: f.subarea, ...f },
        ...f.tipos.map((t) => ({ nivel: 'Tipo', nombre: `${f.subarea} › ${t.tipo}`, ...t })),
      ])
      exportarCsv(
        `demanda_matriz_${hoyISO()}.csv`,
        [
          { header: 'Nivel', value: (d) => d.nivel },
          { header: 'Subárea / Tipo', value: (d) => d.nombre },
          { header: 'Total', value: (d) => d.total },
          { header: '% Var', value: (d) => d.var_pct ?? '' },
          { header: 'Prom. días', value: (d) => d.prom_dias ?? '' },
          { header: '% Cierre', value: (d) => d.pct_cierre ?? '' },
          { header: '% SLA', value: (d) => d.pct_sla ?? '' },
          { header: '% Satisfacción', value: (d) => d.pct_sat ?? '' },
        ],
        filas,
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
      exportDisabled={!matriz.data?.filas.length}
      exportLabel="Exportar matriz (CSV)"
    >
      {/* Score en una fila (regla del módulo: KPIs en UNA línea) */}
      <KpiRow n={6}>
        <KpiCard
          label="Incidentes del período"
          value={fmt(s?.total)}
          sub={s?.total_anterior != null && periodo.anterior ? `${periodo.anterior}: ${fmt(s.total_anterior)}` : 'período filtrado'}
        />
        <KpiCard
          label="Variación vs anterior"
          value={<span style={{ color: varColor(s?.var_pct) }}>{varTxt(s?.var_pct)}</span>}
          sub={periodo.anterior
            ? (s?.var_pct != null ? `vs ${periodo.anterior}` : `sin datos en ${periodo.anterior}`)
            : 'sin período comparable'}
        />
        <KpiCard label="Prom. días de cierre" value={dias(s?.prom_dias)} />
        <KpiCard label="% Cierre" value={pct(s?.pct_cierre)} accent="#2f7fd1" sub="resueltos / ingresados" />
        <KpiCard label="% SLA" value={pct(s?.pct_sla)} accent="#1f8a65" sub="cierres dentro del SLA del tipo" />
        <KpiCard
          label="% Satisfacción"
          value={pct(s?.pct_sat)}
          accent="#6a1b9a"
          sub={s ? `respuesta ${pct(s.tasa_respuesta)} · ${fmt(s.encuestas_respondidas)}/${fmt(s.encuestas_enviadas)} encuestas` : undefined}
        />
      </KpiRow>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 16 }}>
        {/* Matriz subárea → tipo (la tabla central del tablero de referencia).
            A lo ancho completo: compartir fila con la dona le imponía scroll horizontal.
            Debajo, las DOS donas lado a lado (César 2026-08-31): Niveles de
            satisfacción + Cierres por estado (movida desde Evolución). */}
        <div style={cardStyle}>
          <h3 style={h3Style}>Indicadores por subárea y tipo</h3>
          <p style={notaStyle}>
            ▲▼ variación de cada indicador vs {periodo.anterior ?? 'el período anterior'} (verde mejora, rojo empeora) · ■ sin variación o sin dato previo
          </p>
          {matriz.isLoading ? (
            <div style={{ padding: 24 }}><CenterMsg>Cargando…</CenterMsg></div>
          ) : !matriz.data?.filas.length ? (
            <div style={{ padding: 24 }}><CenterMsg>Sin datos para el filtro elegido.</CenterMsg></div>
          ) : (
            <div>
              <table style={tableStyle}>
                <thead>
                  <tr>
                    <th style={{ ...thStyle, textAlign: 'left', width: 'auto' }}>Subárea / tipo</th>
                    <th style={thStyle}>Total</th>
                    <th style={thStyle}>% Var</th>
                    <th style={thStyle}>Prom. días</th>
                    <th style={thStyle}>% Cierre</th>
                    <th style={thStyle}>% SLA</th>
                    <th style={thStyle}>% Sat</th>
                  </tr>
                </thead>
                <tbody>
                  {matriz.data.filas.map((f) => (
                    <FilaGrupo
                      key={f.id_subarea ?? 'sin'}
                      abierta={abiertas.has(f.id_subarea)}
                      onToggle={() => toggle(f.id_subarea)}
                      nombre={f.subarea}
                      fila={f}
                      tipos={f.tipos}
                    />
                  ))}
                  <tr style={{ background: 'var(--surface-400)' }}>
                    <td style={{ ...tdNombreStyle, fontWeight: 700 }}>Total</td>
                    <Celdas fila={matriz.data.total} bold />
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
          {/* Niveles de satisfacción (dona; sin emojis, §13). El total del centro
              son ENCUESTAS RESPONDIDAS, no incidentes (aclaración pedida por César). */}
          <ChartCard
            title="Niveles de satisfacción"
            height={300}
            action={
              <span style={notaStyle}>
                El total son las {fmt(s?.encuestas_respondidas)} encuestas respondidas del período, no los {fmt(s?.total)} incidentes
              </span>
            }
          >
            {score.isLoading ? (
              <CenterMsg>Cargando…</CenterMsg>
            ) : !niveles.length ? (
              <CenterMsg>Sin respuestas de encuestas en el período.</CenterMsg>
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

          {/* Cierres por estado (Cumplido vs Auditado). */}
          <ChartCard title="Cierres por estado" height={300}>
            {cierres.isLoading ? (
              <CenterMsg>Cargando…</CenterMsg>
            ) : !totalCierres ? (
              <CenterMsg>Sin cierres en el período.</CenterMsg>
            ) : (
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={cierres.data} dataKey="total" nameKey="estado" innerRadius="50%" outerRadius="78%" paddingAngle={2} label={pieLabel} labelLine={false}>
                    <Label content={DonaCentro} position="center" value={totalCierres} />
                    {(cierres.data ?? []).map((c) => (
                      <Cell key={c.estado} fill={c.estado === 'Auditado' ? '#6a1b9a' : '#1f8a65'} />
                    ))}
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

function Celdas({ fila, bold }: { fila: EjFilaBase; bold?: boolean }) {
  const w = bold ? 700 : 500
  const ant = fila.ant
  return (
    <>
      <td style={{ ...tdStyle, fontWeight: w }}>{fmt(fila.total)}</td>
      <td style={{ ...tdStyle, color: varColor(fila.var_pct), fontWeight: w }}>{varTxt(fila.var_pct)}</td>
      <td style={{ ...tdStyle, fontWeight: w }}>
        {fila.prom_dias ?? '—'}<Tri actual={fila.prom_dias} anterior={ant?.prom_dias} invertir />
      </td>
      <td style={{ ...tdStyle, color: '#2f7fd1', fontWeight: w }}>
        {pct(fila.pct_cierre)}<Tri actual={fila.pct_cierre} anterior={ant?.pct_cierre} />
      </td>
      <td style={{ ...tdStyle, color: '#1f8a65', fontWeight: w }}>
        {pct(fila.pct_sla)}<Tri actual={fila.pct_sla} anterior={ant?.pct_sla} />
      </td>
      <td style={{ ...tdStyle, color: '#6a1b9a', fontWeight: w }}>
        {pct(fila.pct_sat)}<Tri actual={fila.pct_sat} anterior={ant?.pct_sat} />
      </td>
    </>
  )
}

function FilaGrupo({
  abierta, onToggle, nombre, fila, tipos,
}: {
  abierta: boolean
  onToggle: () => void
  nombre: string
  fila: EjFilaBase
  tipos: Array<EjFilaBase & { id_tipo: number | null; tipo: string }>
}) {
  return (
    <>
      <tr style={{ borderTop: '1px solid var(--border-primary)' }}>
        <td style={tdNombreStyle}>
          <button type="button" onClick={onToggle} style={expandBtnStyle} aria-expanded={abierta}>
            <span aria-hidden="true" style={{ display: 'inline-block', width: 14 }}>{abierta ? '▾' : '▸'}</span>
            <span style={{ fontWeight: 600 }}>{nombre}</span>
            <span style={{ color: 'var(--fg-3)', fontSize: '0.72rem' }}> ({tipos.length} {tipos.length === 1 ? 'tipo' : 'tipos'})</span>
          </button>
        </td>
        <Celdas fila={fila} />
      </tr>
      {abierta && tipos.map((t) => (
        <tr key={t.id_tipo ?? 'sin'} style={{ background: 'var(--surface-100)' }}>
          <td style={{ ...tdNombreStyle, paddingLeft: 34, color: 'var(--fg-2)' }}>{t.tipo}</td>
          <Celdas fila={t} />
        </tr>
      ))}
    </>
  )
}

const cardStyle: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 12, padding: '14px 16px', minWidth: 0,
}
const h3Style: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.92rem', fontWeight: 600,
  color: 'var(--fg-1)', margin: '0 0 4px',
}
const notaStyle: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.72rem', color: 'var(--fg-3)',
  margin: '0 0 10px',
}
// Sin scroll horizontal (César 2026-09-01): las columnas numéricas van a su
// ancho mínimo (width 1% + nowrap) y la PRIMERA columna (nombres) absorbe el
// resto envolviendo el texto. Vale para toda tabla del módulo.
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
  // 'anywhere' (no 'break-word'): es el único valor que reduce el min-content
  // de la columna — con break-word la tabla puede seguir midiendo más que la
  // card y quedar recortada a la derecha (cazado por César en prod, zoom alto).
  ...tdStyle, textAlign: 'left', whiteSpace: 'normal', overflowWrap: 'anywhere',
}
const expandBtnStyle: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'baseline', gap: 4,
  background: 'none', border: 'none', cursor: 'pointer', padding: 0,
  fontFamily: 'var(--font-display)', fontSize: '0.8rem', color: 'var(--fg-1)', textAlign: 'left',
}
