import React from 'react'
import type { DashboardDistribucionItem, DashboardEvolucionItem } from '../lib/types'

// Gráficos hechos a mano con SVG/CSS y tokens del DS — cero dependencias nuevas.
// Suficiente para barras de distribución (1..5) y una línea de evolución mensual.

// Color por nivel de satisfacción (CSAT 1..5). Verde DS para alto, rojo para bajo.
export function colorCsat(valor: number): string {
  if (valor >= 4) return '#1f8a65'     // --color-success
  if (valor >= 3) return 'var(--zaris-gold)'
  return 'var(--color-error)'
}

// Color fijo por estrella (para la barra de distribución).
const COLOR_ESTRELLA: Record<number, string> = {
  1: 'var(--color-error)',
  2: '#d9534f',
  3: 'var(--zaris-gold)',
  4: '#5aa17f',
  5: '#1f8a65',
}

/* ── Barras de distribución 1..5 ──────────────────────────── */
export function BarrasDistribucion({ data }: { data: DashboardDistribucionItem[] }) {
  const max = Math.max(1, ...data.map((d) => d.count))
  const total = data.reduce((s, d) => s + d.count, 0)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {[5, 4, 3, 2, 1].map((star) => {
        const item = data.find((d) => d.clasificacion === star)
        const count = item?.count ?? 0
        const pct = total ? Math.round((count / total) * 100) : 0
        const w = max ? (count / max) * 100 : 0
        return (
          <div key={star} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{
              width: 42, flexShrink: 0, fontFamily: 'var(--font-display)', fontSize: 13,
              color: 'var(--fg-2)', display: 'inline-flex', alignItems: 'center', gap: 3,
            }}>
              {star}<Estrella />
            </span>
            <div style={{ flex: 1, height: 18, background: 'var(--surface-300)', borderRadius: 6, overflow: 'hidden' }}>
              <div style={{
                width: `${w}%`, height: '100%', background: COLOR_ESTRELLA[star],
                borderRadius: 6, transition: 'width 400ms ease',
              }} />
            </div>
            <span style={{
              width: 78, flexShrink: 0, textAlign: 'right', fontFamily: 'var(--font-mono)',
              fontSize: 12, color: 'var(--fg-3)',
            }}>
              {count} · {pct}%
            </span>
          </div>
        )
      })}
    </div>
  )
}

function Estrella() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" style={{ color: 'var(--zaris-gold)' }}>
      <path d="M12 2l2.9 6.3L22 9.2l-5 4.8 1.2 6.9L12 17.6 5.8 20.9 7 14 2 9.2l7.1-.9z" />
    </svg>
  )
}

/* ── Línea de evolución mensual ───────────────────────────── */
export function LineaEvolucion({ data }: { data: DashboardEvolucionItem[] }) {
  if (data.length === 0) {
    return <p style={{ color: 'var(--fg-3)', fontSize: 13, textAlign: 'center', padding: 24 }}>Sin datos en el período.</p>
  }

  const W = 520, H = 180, padX = 36, padY = 24
  const innerW = W - padX * 2
  const innerH = H - padY * 2
  // Escala fija 1..5 (CSAT) para que la línea sea comparable mes a mes.
  const yMin = 1, yMax = 5
  const x = (i: number) => padX + (data.length === 1 ? innerW / 2 : (i / (data.length - 1)) * innerW)
  const y = (v: number) => padY + innerH - ((v - yMin) / (yMax - yMin)) * innerH

  const pts = data.map((d, i) => ({ cx: x(i), cy: y(d.csat_promedio), d }))
  const path = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.cx.toFixed(1)},${p.cy.toFixed(1)}`).join(' ')

  return (
    <div style={{ width: '100%', overflowX: 'auto' }}>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', minWidth: 360, height: 'auto' }}>
        {/* Gridlines horizontales en 1..5 */}
        {[1, 2, 3, 4, 5].map((v) => (
          <g key={v}>
            <line x1={padX} y1={y(v)} x2={W - padX} y2={y(v)} stroke="var(--border-primary)" strokeWidth={1} />
            <text x={padX - 8} y={y(v) + 3} textAnchor="end" fontSize={10} fill="var(--fg-3)" fontFamily="var(--font-mono)">{v}</text>
          </g>
        ))}
        {/* Línea */}
        <path d={path} fill="none" stroke="var(--zaris-orange)" strokeWidth={2} strokeLinejoin="round" />
        {/* Puntos + etiquetas */}
        {pts.map((p, i) => (
          <g key={i}>
            <circle cx={p.cx} cy={p.cy} r={3.5} fill="var(--zaris-orange)" />
            <text x={p.cx} y={p.cy - 8} textAnchor="middle" fontSize={10} fill="var(--fg-2)" fontFamily="var(--font-mono)">
              {p.d.csat_promedio.toFixed(1)}
            </text>
            <text x={p.cx} y={H - 6} textAnchor="middle" fontSize={9} fill="var(--fg-3)" fontFamily="var(--font-mono)">
              {p.d.anio_mes.slice(2)}
            </text>
          </g>
        ))}
      </svg>
    </div>
  )
}

/* ── KPI card ─────────────────────────────────────────────── */
export function KpiCard({
  label, value, sub, accent, icon,
}: {
  label: string
  value: React.ReactNode
  sub?: string
  accent?: string
  icon?: React.ReactNode
}) {
  return (
    <div style={{
      flex: '1 1 160px', minWidth: 160,
      background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
      borderRadius: 12, padding: '14px 16px',
      display: 'flex', flexDirection: 'column', gap: 4,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        {icon && <span style={{ color: accent ?? 'var(--fg-3)', display: 'flex' }}>{icon}</span>}
        <span style={{
          fontSize: 11, fontWeight: 600, textTransform: 'uppercase',
          letterSpacing: '0.04em', color: 'var(--fg-3)',
        }}>{label}</span>
      </div>
      <span style={{
        fontFamily: 'var(--font-display)', fontSize: '1.6rem', fontWeight: 500,
        color: accent ?? 'var(--fg-1)', lineHeight: 1.1,
      }}>{value}</span>
      {sub && <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>{sub}</span>}
    </div>
  )
}
