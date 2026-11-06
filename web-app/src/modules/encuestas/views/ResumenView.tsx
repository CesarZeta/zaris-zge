import { useMemo, useState } from 'react'
import { Star, TrendingUp, ThumbsDown, PhoneCall, MessageSquare } from 'lucide-react'
import { useResumen, usePorArea, usePorCircuito, useEvolucion, useComentarios } from '../hooks/useEncuestas'
import { BarrasDistribucion, LineaEvolucion, KpiCard, colorCsat } from '../components/charts'
import { ThOrden, ordenarFilas, useOrden } from '../../../ui/orden'
import type { Circuito } from '../lib/types'

const CIRCUITO_LABEL: Record<Circuito, string> = {
  reclamos: 'Reclamos',
  turnos: 'Turnos',
  tramites: 'Trámites',
  entradas: 'Entradas',
}

// Período por defecto: últimos 90 días (más útil que 30 para ver tendencia,
// y el backend ya filtra por fecha). El usuario puede ajustar desde/hasta.
function isoHaceDias(d: number): string {
  const dt = new Date()
  dt.setDate(dt.getDate() - d)
  return dt.toISOString().slice(0, 10)
}
const HOY = new Date().toISOString().slice(0, 10)

export function ResumenView() {
  const [desde, setDesde] = useState(isoHaceDias(90))
  const [hasta, setHasta] = useState(HOY)
  const [circuito, setCircuito] = useState<Circuito | ''>('')
  const tipo = circuito || undefined

  const periodo = useMemo(() => ({ desde, hasta }), [desde, hasta])
  const resumen = useResumen({ ...periodo, tipo })
  const porArea = usePorArea({ ...periodo, tipo, limit: 100 })
  // La tabla por circuito no se filtra: es la comparación entre los cuatro.
  const porCircuito = usePorCircuito(periodo)
  const evolucion = useEvolucion(6, tipo)
  const comentarios = useComentarios({ limit: 8, tipo })

  // Orden por columna (§23): el tablero trae todas las áreas → en pantalla.
  const { orden: ordenArea, alternar: alternarArea } = useOrden<'area' | 'respuestas' | 'csat'>()
  const areas = ordenarFilas(porArea.data ?? [], ordenArea, {
    area: (a) => a.nombre_area,
    respuestas: (a) => a.total_respuestas,
    csat: (a) => a.csat_promedio,
  })
  const { orden: ordenCircuito, alternar: alternarCircuito } =
    useOrden<'circuito' | 'enviadas' | 'respuestas' | 'tasa' | 'csat' | 'insatisfechos'>()
  const circuitos = ordenarFilas(porCircuito.data ?? [], ordenCircuito, {
    circuito: (c) => CIRCUITO_LABEL[c.tipo],
    enviadas: (c) => c.total_enviadas,
    respuestas: (c) => c.total_respuestas,
    tasa: (c) => c.tasa_respuesta_pct,
    csat: (c) => c.csat_promedio,
    insatisfechos: (c) => c.pct_insatisfechos,
  })

  const r = resumen.data

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Selector de período */}
      <div style={toolbar}>
        <div style={field}>
          <label style={lbl}>Desde</label>
          <input type="date" value={desde} max={hasta} onChange={(e) => setDesde(e.target.value)} style={inp} />
        </div>
        <div style={field}>
          <label style={lbl}>Hasta</label>
          <input type="date" value={hasta} min={desde} max={HOY} onChange={(e) => setHasta(e.target.value)} style={inp} />
        </div>
        <div style={field}>
          <label style={lbl} htmlFor="encuestas-circuito">Circuito</label>
          <select
            id="encuestas-circuito"
            value={circuito}
            onChange={(e) => setCircuito(e.target.value as Circuito | '')}
            style={inp}
          >
            <option value="">Todos</option>
            {(Object.keys(CIRCUITO_LABEL) as Circuito[]).map((c) => (
              <option key={c} value={c}>{CIRCUITO_LABEL[c]}</option>
            ))}
          </select>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'flex-end' }}>
          <button style={btnGhost} onClick={() => { setDesde(isoHaceDias(30)); setHasta(HOY) }}>30 días</button>
          <button style={btnGhost} onClick={() => { setDesde(isoHaceDias(90)); setHasta(HOY) }}>90 días</button>
          <button style={btnGhost} onClick={() => { setDesde(isoHaceDias(365)); setHasta(HOY) }}>1 año</button>
        </div>
      </div>

      {resumen.isError && <div style={errorBanner}>{(resumen.error as Error)?.message ?? 'Error al cargar el resumen'}</div>}

      {/* KPIs */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
        <KpiCard
          label="CSAT promedio"
          value={resumen.isLoading ? '…' : `${(r?.csat_promedio ?? 0).toFixed(2)}`}
          sub="sobre 5"
          accent={r ? colorCsat(r.csat_promedio) : undefined}
          icon={<Star size={16} strokeWidth={1.5} />}
        />
        <KpiCard
          label="Tasa de respuesta"
          value={resumen.isLoading ? '…' : `${(r?.tasa_respuesta_pct ?? 0).toFixed(1)}%`}
          sub={r ? `${r.total_completadas} de ${r.total_enviadas} enviadas` : undefined}
          icon={<TrendingUp size={16} strokeWidth={1.5} />}
        />
        <KpiCard
          label="% insatisfechos"
          value={resumen.isLoading ? '…' : `${(r?.pct_insatisfechos ?? 0).toFixed(1)}%`}
          sub="puntuaron 1 o 2"
          accent={r && r.pct_insatisfechos > 20 ? 'var(--color-error)' : undefined}
          icon={<ThumbsDown size={16} strokeWidth={1.5} />}
        />
        <KpiCard
          label="Contactos pendientes"
          value={resumen.isLoading ? '…' : (r?.alertas_contacto_pendientes ?? 0)}
          sub="vecinos esperando llamada"
          accent={r && r.alertas_contacto_pendientes > 0 ? 'var(--zaris-orange)' : undefined}
          icon={<PhoneCall size={16} strokeWidth={1.5} />}
        />
      </div>

      {/* Distribución + Evolución */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1.2fr)', gap: 16 }}>
        <div style={card}>
          <h3 style={cardTitle}>Distribución de puntajes</h3>
          {resumen.isLoading
            ? <Cargando />
            : <BarrasDistribucion data={r?.distribucion ?? []} />}
        </div>
        <div style={card}>
          <h3 style={cardTitle}>Evolución mensual del CSAT</h3>
          {evolucion.isLoading
            ? <Cargando />
            : <LineaEvolucion data={evolucion.data ?? []} />}
        </div>
      </div>

      {/* CSAT por circuito: siempre los cuatro, no sigue al selector */}
      <div style={card}>
        <h3 style={cardTitle}>CSAT por circuito</h3>
        {porCircuito.isError && <div style={errorBanner}>{(porCircuito.error as Error)?.message ?? 'Error al cargar los circuitos'}</div>}
        {porCircuito.isLoading ? <Cargando /> : !porCircuito.isError && (
          <table style={table}>
            <thead>
              <tr>
                <ThOrden campo="circuito" orden={ordenCircuito} onOrdenar={alternarCircuito} style={th}>Circuito</ThOrden>
                <ThOrden campo="enviadas" orden={ordenCircuito} onOrdenar={alternarCircuito} style={{ ...th, textAlign: 'right' }}>Enviadas</ThOrden>
                <ThOrden campo="respuestas" orden={ordenCircuito} onOrdenar={alternarCircuito} style={{ ...th, textAlign: 'right' }}>Respuestas</ThOrden>
                <ThOrden campo="tasa" orden={ordenCircuito} onOrdenar={alternarCircuito} style={{ ...th, textAlign: 'right' }}>Tasa</ThOrden>
                <ThOrden campo="csat" orden={ordenCircuito} onOrdenar={alternarCircuito} style={{ ...th, textAlign: 'right' }}>CSAT</ThOrden>
                <ThOrden campo="insatisfechos" orden={ordenCircuito} onOrdenar={alternarCircuito} style={{ ...th, textAlign: 'right' }}>% insatisfechos</ThOrden>
              </tr>
            </thead>
            <tbody>
              {circuitos.map((c) => (
                <tr key={c.tipo}>
                  <td style={td}>{CIRCUITO_LABEL[c.tipo]}</td>
                  <td style={{ ...td, textAlign: 'right', fontFamily: 'var(--font-mono)' }}>{c.total_enviadas}</td>
                  <td style={{ ...td, textAlign: 'right', fontFamily: 'var(--font-mono)' }}>{c.total_respuestas}</td>
                  <td style={{ ...td, textAlign: 'right', fontFamily: 'var(--font-mono)' }}>{c.tasa_respuesta_pct.toFixed(1)}%</td>
                  <td style={{ ...td, textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: 600, color: c.total_respuestas ? colorCsat(c.csat_promedio) : 'var(--fg-3)' }}>
                    {c.total_respuestas ? c.csat_promedio.toFixed(2) : '—'}
                  </td>
                  <td style={{ ...td, textAlign: 'right', fontFamily: 'var(--font-mono)' }}>
                    {c.total_respuestas ? `${c.pct_insatisfechos.toFixed(1)}%` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* CSAT por área */}
      <div style={card}>
        <h3 style={cardTitle}>CSAT por área</h3>
        {porArea.isLoading ? <Cargando /> : (
          (porArea.data ?? []).length === 0
            ? <p style={vacio}>Sin respuestas en el período.</p>
            : (
              <table style={table}>
                <thead>
                  <tr>
                    <ThOrden campo="area" orden={ordenArea} onOrdenar={alternarArea} style={th}>Área</ThOrden>
                    <ThOrden campo="respuestas" orden={ordenArea} onOrdenar={alternarArea} style={{ ...th, textAlign: 'right' }}>Respuestas</ThOrden>
                    <ThOrden campo="csat" orden={ordenArea} onOrdenar={alternarArea} style={{ ...th, textAlign: 'right' }}>CSAT</ThOrden>
                  </tr>
                </thead>
                <tbody>
                  {areas.map((a) => (
                    <tr key={a.id_area ?? 'null'}>
                      <td style={td}>{a.nombre_area ?? '(sin área)'}</td>
                      <td style={{ ...td, textAlign: 'right', fontFamily: 'var(--font-mono)' }}>{a.total_respuestas}</td>
                      <td style={{ ...td, textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: 600, color: colorCsat(a.csat_promedio) }}>
                        {a.csat_promedio.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )
        )}
      </div>

      {/* Comentarios recientes */}
      <div style={card}>
        <h3 style={{ ...cardTitle, display: 'flex', alignItems: 'center', gap: 6 }}>
          <MessageSquare size={15} strokeWidth={1.5} /> Comentarios recientes
        </h3>
        {comentarios.isLoading ? <Cargando /> : (
          (comentarios.data ?? []).length === 0
            ? <p style={vacio}>Todavía no hay comentarios de texto libre.</p>
            : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {(comentarios.data ?? []).map((c, i) => (
                  <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                    <span style={{
                      flexShrink: 0, fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600,
                      color: colorCsat(c.clasificacion_inicial), display: 'inline-flex', alignItems: 'center', gap: 2,
                    }}>
                      {c.clasificacion_inicial}<Star size={11} fill="currentColor" strokeWidth={0} />
                    </span>
                    <p style={{ margin: 0, fontSize: '0.86rem', color: 'var(--fg-2)', lineHeight: 1.45 }}>
                      “{c.comentario}”
                    </p>
                  </div>
                ))}
              </div>
            )
        )}
      </div>
    </div>
  )
}

function Cargando() {
  return <p style={{ color: 'var(--fg-3)', fontSize: 13, padding: '12px 0' }}>Cargando…</p>
}

const toolbar: React.CSSProperties = {
  display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end',
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)', borderRadius: 12, padding: 14,
}
const field: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: 4 }
const lbl: React.CSSProperties = { fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--fg-3)' }
const inp: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: 13, padding: '6px 10px',
  borderRadius: 'var(--radius-md)', border: '1px solid var(--border-primary)', background: 'var(--surface-100)', outline: 'none',
}
const btnGhost: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.78rem', cursor: 'pointer', borderRadius: 8,
  padding: '6px 10px', background: 'transparent', color: 'var(--fg-2)', border: '1px solid var(--border-medium)',
}
const card: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)', borderRadius: 12, padding: 16,
}
const cardTitle: React.CSSProperties = {
  margin: '0 0 14px', fontFamily: 'var(--font-display)', fontSize: '0.92rem', fontWeight: 600, color: 'var(--fg-1)',
}
const table: React.CSSProperties = { width: '100%', borderCollapse: 'separate', borderSpacing: 0, fontSize: '0.84rem' }
const th: React.CSSProperties = {
  textAlign: 'left', fontWeight: 600, fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.04em',
  color: 'var(--fg-3)', padding: '8px 10px', borderBottom: '1px solid var(--border-primary)',
}
const td: React.CSSProperties = { padding: '9px 10px', borderBottom: '1px solid var(--border-primary)', color: 'var(--fg-1)' }
const vacio: React.CSSProperties = { color: 'var(--fg-3)', fontSize: 13, textAlign: 'center', padding: 20, margin: 0 }
const errorBanner: React.CSSProperties = {
  background: '#ffebee', border: '1px solid #ffcdd2', borderLeft: '4px solid var(--color-error)',
  borderRadius: 8, padding: '12px 16px', color: '#c62828', fontSize: '0.86rem',
}
