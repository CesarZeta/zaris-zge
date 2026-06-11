// Helpers visuales compartidos del modulo Emergencias.
import { useEffect, useState } from 'react'

/** Pill de prioridad: usa el token DS --prio-pN definido en tokens.css (s13). */
export function PrioridadPill({ codigo, colorToken }: { codigo: string; colorToken?: string | null }) {
  const token = colorToken || `prio-${codigo.toLowerCase()}`
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 700,
      color: '#f7f7f4', background: `var(--${token}, var(--fg-2))`,
      borderRadius: 999, padding: '2px 10px', letterSpacing: '0.04em',
    }}>
      {codigo}
    </span>
  )
}

const ESTADO_COLOR: Record<string, string> = {
  PENDIENTE: '#c62828',
  EN_PREPARACION: '#f57f17',
  EN_CAMINO: '#1565c0',
  EN_SITIO: '#1f8a65',
  DERIVADO: '#6a1b9a',
  RESUELTO: '#1f8a65',
  DESESTIMADO: '#616161',
}

export function EstadoBadge({ codigo, nombre }: { codigo: string; nombre?: string }) {
  const color = ESTADO_COLOR[codigo] ?? 'var(--fg-2)'
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      fontFamily: 'var(--font-display)', fontSize: 12, fontWeight: 600,
      color, border: `1px solid ${color}`, borderRadius: 999, padding: '2px 10px',
      background: 'var(--surface-100)', whiteSpace: 'nowrap',
    }}>
      <span style={{ width: 7, height: 7, borderRadius: '50%', background: color }} />
      {nombre ?? codigo.replace(/_/g, ' ')}
    </span>
  )
}

/** Marca de origen App Vecinos (plan Fase 5): el evento NO entro por un
 * operador del COM sino por el reporte del vecino desde la PWA. */
export function CanalAppVecinoBadge({ canalCodigo }: { canalCodigo?: string | null }) {
  if (canalCodigo !== 'APP_VECINO') return null
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      fontFamily: 'var(--font-display)', fontSize: 11, fontWeight: 700,
      color: 'var(--zaris-cream)', background: 'var(--fg-1)',
      borderRadius: 999, padding: '3px 10px', letterSpacing: '0.05em',
      textTransform: 'uppercase', whiteSpace: 'nowrap',
    }}>
      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect width="14" height="20" x="5" y="2" rx="2" ry="2" /><path d="M12 18h.01" />
      </svg>
      App Vecinos
    </span>
  )
}

export function formatFechaHora(iso?: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('es-AR', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

export function transcurridoDesde(iso: string, ahora: number): string {
  const ms = ahora - new Date(iso).getTime()
  if (ms < 0) return '0m'
  const min = Math.floor(ms / 60000)
  if (min < 60) return `${min}m`
  const h = Math.floor(min / 60)
  if (h < 24) return `${h}h ${min % 60}m`
  return `${Math.floor(h / 24)}d ${h % 24}h`
}

/** Reloj compartido que tickea cada 30s para los "tiempo transcurrido" en vivo. */
export function useAhora(intervaloMs = 30_000): number {
  const [ahora, setAhora] = useState(() => Date.now())
  useEffect(() => {
    const t = setInterval(() => setAhora(Date.now()), intervaloMs)
    return () => clearInterval(t)
  }, [intervaloMs])
  return ahora
}

/** Cronometro mm:ss desde el mount (header de Recepcion, plan 5.1). */
export function useCronometro(): string {
  const [seg, setSeg] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setSeg((s) => s + 1), 1000)
    return () => clearInterval(t)
  }, [])
  const mm = String(Math.floor(seg / 60)).padStart(2, '0')
  const ss = String(seg % 60).padStart(2, '0')
  return `${mm}:${ss}`
}
