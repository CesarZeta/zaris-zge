import { useCuentasCiudadano } from '../hooks/useCiudadanos'

/**
 * Chips de estado de las dos cuentas de una persona de la BUC (mig 110): App Vecinos
 * (sin cuenta / pendiente de activar / activa) y ZARIS (usuario · nivel, o sin cuenta).
 * Lee GET /buc/ciudadanos/{id}/cuentas; se muestra en consulta/edición, no en el alta.
 */
const NIVEL_LABEL: Record<number, string> = {
  1: 'Administrador', 2: 'Supervisor', 3: 'Atención', 4: 'Gestión', 5: 'Consultor',
}

export function CuentasChips({ idCiudadano }: { idCiudadano: number }) {
  const cuentas = useCuentasCiudadano(idCiudadano)
  if (cuentas.isLoading) {
    return <div style={{ fontSize: 'var(--size-caption)', color: 'var(--fg-3)' }}>Consultando cuentas…</div>
  }
  if (!cuentas.data) return null
  const { vecino, zaris } = cuentas.data

  const vecinoChip = vecino.estado === 'activa'
    ? { texto: 'App Vecinos: activa', tono: tonoOk }
    : vecino.estado === 'pendiente'
      ? { texto: 'App Vecinos: pendiente de activar', tono: tonoWarn }
      : { texto: 'App Vecinos: sin cuenta', tono: tonoNeutro }

  const zarisChip = zaris
    ? {
        texto: `ZARIS: ${zaris.username} · ${NIVEL_LABEL[zaris.nivel_acceso] ?? `Nivel ${zaris.nivel_acceso}`}`
          + (!zaris.activo ? ' · inactivo' : zaris.debe_cambiar_password ? ' · clave temporal' : ''),
        tono: zaris.activo ? tonoOk : tonoNeutro,
      }
    : { texto: 'ZARIS: sin cuenta', tono: tonoNeutro }

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
      <span style={{ fontSize: 'var(--size-caption)', fontWeight: 600, color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        Cuentas
      </span>
      <span style={{ ...chip, ...vecinoChip.tono }} title={vecino.email ?? undefined}>{vecinoChip.texto}</span>
      <span style={{ ...chip, ...zarisChip.tono }}>{zarisChip.texto}</span>
    </div>
  )
}

const chip: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', padding: '3px 10px',
  borderRadius: 'var(--radius-pill)', fontSize: 'var(--size-caption)', fontWeight: 600,
  fontFamily: 'var(--font-display)', border: '1px solid transparent',
}
const tonoOk: React.CSSProperties = { background: 'rgba(31,138,101,.12)', color: 'var(--color-success)' }
const tonoWarn: React.CSSProperties = { background: 'rgba(245,127,23,.14)', color: '#b35c00' }
const tonoNeutro: React.CSSProperties = { background: 'var(--surface-400)', color: 'var(--fg-2)' }
