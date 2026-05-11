import type { CalendarioMes } from '../types/agenda'
import { diasEnMes, fromIsoDate, mismaFecha, nombreMes, primerDiaDelMes } from '../../../lib/dates'

interface Props {
  data: CalendarioMes
  onDiaClick: (fechaIso: string) => void
}

const DIAS_LABEL = ['L', 'M', 'X', 'J', 'V', 'S', 'D']

export function MonthlyCalendar({ data, onDiaClick }: Props) {
  const primer = primerDiaDelMes(data.anio, data.mes)
  const offset = (primer.getDay() + 6) % 7  // 0=lunes
  const total = diasEnMes(data.anio, data.mes)
  const celdas: ({ fechaIso: string; dia: number } | null)[] = []
  for (let i = 0; i < offset; i++) celdas.push(null)
  const mapPorFecha = new Map(data.dias.map((d) => [d.fecha, d]))
  for (let d = 1; d <= total; d++) {
    const f = new Date(data.anio, data.mes - 1, d)
    const iso = `${data.anio}-${String(data.mes).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    celdas.push({ fechaIso: iso, dia: d })
    // hack para usar `f`
    void f
  }

  return (
    <div style={{
      background: 'var(--surface-100)', borderRadius: 'var(--radius-lg)',
      padding: 16, border: '1px solid var(--border-primary)',
    }}>
      <h3 style={{
        margin: '0 0 12px', fontFamily: 'var(--font-display)', fontSize: 'var(--size-title-sm)',
        fontWeight: 500, color: 'var(--fg-1)', textTransform: 'capitalize',
      }}>
        {nombreMes(data.mes).toLowerCase()} {data.anio}
      </h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 6 }}>
        {DIAS_LABEL.map((l) => (
          <div key={l} style={{
            textAlign: 'center', fontSize: 11, color: 'var(--fg-3)',
            fontFamily: 'var(--font-mono)', padding: '4px 0',
          }}>{l}</div>
        ))}
        {celdas.map((c, i) => {
          if (!c) return <div key={`v-${i}`} />
          const info = mapPorFecha.get(c.fechaIso)
          const f = fromIsoDate(c.fechaIso)
          const esHoy = mismaFecha(f, new Date())
          const tieneActividad = info && (info.eventos + info.ocupaciones_total + info.ausencias) > 0
          return (
            <button
              key={c.fechaIso}
              onClick={() => onDiaClick(c.fechaIso)}
              style={{
                background: esHoy ? 'rgba(245,78,0,.10)' : 'var(--surface-200)',
                border: `1px solid ${esHoy ? 'var(--zaris-orange)' : 'var(--border-primary)'}`,
                borderRadius: 'var(--radius-md)', padding: 8, minHeight: 84,
                textAlign: 'left', cursor: 'pointer', fontFamily: 'var(--font-display)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontWeight: esHoy ? 600 : 400, color: 'var(--fg-1)', fontSize: 13 }}>{c.dia}</span>
                {tieneActividad && (
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--zaris-orange)' }} />
                )}
              </div>
              {info && tieneActividad && (
                <div style={{ marginTop: 6, display: 'flex', flexDirection: 'column', gap: 2 }}>
                  {info.eventos > 0           && <span style={{ fontSize: 10, color: '#5a8fb8' }}>{info.eventos} evt</span>}
                  {info.ocupaciones_total > 0 && <span style={{ fontSize: 10, color: 'var(--fg-2)' }}>{info.ocupaciones_total} ocup</span>}
                  {info.ausencias > 0         && <span style={{ fontSize: 10, color: 'var(--zaris-gold)' }}>{info.ausencias} lic</span>}
                </div>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
