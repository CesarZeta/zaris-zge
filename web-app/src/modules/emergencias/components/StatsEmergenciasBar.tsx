// KPI cards del tablero del dispatcher (estilo StatsBar de Reclamos):
// abiertos AHORA en tarjeta roja + totales del rango por subarea y por estado.
// El rango temporal se elige con un selector (ultima hora / 24h / 7d / todo).
import { useStatsEmergencias } from '../hooks/useEmergencias'
import { ESTADO_COLOR } from '../lib/ui'

export const RANGOS: { label: string; horas?: number }[] = [
  { label: 'Última hora', horas: 1 },
  { label: 'Últimas 24 h', horas: 24 },
  { label: 'Últimos 7 días', horas: 168 },
  { label: 'Histórico completo', horas: undefined },
]

interface Props {
  horas?: number
  onHoras: (h?: number) => void
  estadoActivo: string
  onSelectEstado: (codigo: string) => void
}

export function StatsEmergenciasBar({ horas, onHoras, estadoActivo, onSelectEstado }: Props) {
  const stats = useStatsEmergencias(horas)
  const d = stats.data

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* fila 1: abiertos ahora (rojo) + totales generales por subarea + rango */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'stretch' }}>
        <div style={cardRoja}>
          <div style={{ ...kpiLabel, color: 'rgba(255,255,255,.85)' }}>Abiertos ahora</div>
          <div style={{ ...kpiValor, color: '#fff' }}>{d ? d.abiertos.total : '—'}</div>
        </div>
        {(d?.rango.por_subarea ?? []).map((s) => (
          <div key={s.id_subarea} style={card}>
            <div style={kpiLabel}>{s.subarea_nombre}</div>
            <div style={{ ...kpiValor, color: 'var(--fg-1)' }}>{s.total}</div>
            <div style={kpiSub}>
              {d?.abiertos.por_subarea.find((a) => a.id_subarea === s.id_subarea)?.total ?? 0} abiertos
            </div>
          </div>
        ))}
        <div style={{ marginLeft: 'auto', display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 4 }}>
          <label style={{ fontFamily: 'var(--font-display)', fontSize: 11, fontWeight: 600, color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Período de los totales
          </label>
          <select
            style={selectRango}
            value={horas ?? ''}
            onChange={(e) => onHoras(e.target.value === '' ? undefined : Number(e.target.value))}
          >
            {RANGOS.map((r) => (
              <option key={r.label} value={r.horas ?? ''}>{r.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* fila 2: totales del rango por estado (los no terminales filtran la lista) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 10 }}>
        {(d?.rango.por_estado ?? []).map((e) => {
          const color = ESTADO_COLOR[e.codigo] ?? 'var(--fg-2)'
          const filtrable = !e.es_terminal
          const activo = filtrable && estadoActivo === e.codigo
          return (
            <button
              key={e.codigo}
              disabled={!filtrable}
              onClick={() => onSelectEstado(activo ? '' : e.codigo)}
              title={filtrable ? 'Filtrar la lista por este estado' : 'Estado terminal (informativo)'}
              style={{
                ...cardEstado,
                cursor: filtrable ? 'pointer' : 'default',
                border: `1px solid ${activo ? color : 'var(--border-primary)'}`,
                background: activo ? 'var(--surface-400)' : 'var(--surface-100)',
                opacity: e.es_terminal ? 0.75 : 1,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: color, flexShrink: 0 }} />
                <span style={kpiLabel}>{e.nombre}</span>
              </div>
              <div style={{ ...kpiValor, fontSize: '1.35rem', color }}>{e.total}</div>
            </button>
          )
        })}
      </div>
    </div>
  )
}

const card: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 12, padding: '12px 18px', minWidth: 150,
  fontFamily: 'var(--font-display)',
}
const cardRoja: React.CSSProperties = {
  ...card,
  background: '#c62828', border: '1px solid #c62828',
}
const cardEstado: React.CSSProperties = {
  borderRadius: 12, padding: '10px 12px', textAlign: 'left',
  fontFamily: 'var(--font-display)', transition: 'border-color 150ms, background 150ms',
}
const kpiLabel: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: 11, fontWeight: 600,
  textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--fg-3)',
}
const kpiValor: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '1.75rem', fontWeight: 600, marginTop: 2,
}
const kpiSub: React.CSSProperties = {
  fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-3)', marginTop: 2,
}
const selectRango: React.CSSProperties = {
  padding: '7px 10px', border: '1px solid var(--border-medium)', borderRadius: 8,
  background: 'var(--surface-100)', color: 'var(--fg-1)',
  fontFamily: 'var(--font-display)', fontSize: 13,
}
