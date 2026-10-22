import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useNotificationsStore } from '../../../stores/notifications'
import { crearCuentaVecino } from '../api/ciudadanosApi'
import { useCuentasCiudadano } from '../hooks/useCiudadanos'

/**
 * Chips de estado de las dos cuentas de una persona de la BUC (mig 110): App Vecinos
 * (sin cuenta / pendiente de activar / activa) y ZARIS (usuario · nivel, o sin cuenta).
 * Lee GET /buc/ciudadanos/{id}/cuentas; se muestra en consulta/edición, no en el alta.
 *
 * Las cuentas se crean solas al guardar la ficha (no hay botón). La única acción acá es
 * «Reenviar correo de activación» cuando la cuenta de App Vecinos quedó pendiente: reusa
 * POST /cuenta-vecino, que regenera el token y manda el mail al email de la ficha.
 */
const NIVEL_LABEL: Record<number, string> = {
  1: 'Administrador', 2: 'Supervisor', 3: 'Atención', 4: 'Gestión', 5: 'Consultor',
}

export function CuentasChips({ idCiudadano }: { idCiudadano: number }) {
  const cuentas = useCuentasCiudadano(idCiudadano)
  const qc = useQueryClient()
  const push = useNotificationsStore((s) => s.push)
  const [reenviando, setReenviando] = useState(false)

  async function reenviarActivacion() {
    if (reenviando) return
    setReenviando(true)
    try {
      const r = await crearCuentaVecino(idCiudadano)
      if (r.ya_activada) {
        push({ kind: 'info', title: 'La cuenta ya está activa', body: `Este vecino ya usa la App Vecinos (${r.email})` })
      } else {
        push({ kind: 'success', title: 'Correo de activación reenviado', body: `Le llega a ${r.email} para que elija su contraseña` })
      }
      qc.invalidateQueries({ queryKey: ['buc', 'ciudadanos', idCiudadano, 'cuentas'] })
    } catch (err) {
      push({ kind: 'error', title: 'No se pudo reenviar', body: (err as Error).message })
    } finally {
      setReenviando(false)
    }
  }

  if (cuentas.isLoading) {
    return <div style={{ fontSize: 'var(--size-caption)', color: 'var(--fg-3)' }}>Consultando cuentas…</div>
  }
  if (!cuentas.data) return null
  const { vecino, zaris } = cuentas.data

  const vecinoChip = vecino.estado === 'activa'
    ? { texto: 'App Vecinos: activa', tono: tonoOk, ayuda: vecino.email }
    : vecino.estado === 'pendiente'
      ? { texto: 'App Vecinos: pendiente de activar', tono: tonoWarn, ayuda: vecino.email }
      : vecino.ficha_demo
        ? {
            texto: 'App Vecinos: no aplica (DNI de prueba)',
            tono: tonoNeutro,
            ayuda: 'Ficha demo con DNI del rango 99.000.000: al cargar el DNI real y guardar, se le crea la cuenta.',
          }
        : { texto: 'App Vecinos: sin cuenta', tono: tonoNeutro, ayuda: null }

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
      <span style={{ ...chip, ...vecinoChip.tono }} title={vecinoChip.ayuda ?? undefined}>{vecinoChip.texto}</span>
      {vecino.estado === 'pendiente' && (
        <button
          type="button"
          onClick={() => { void reenviarActivacion() }}
          disabled={reenviando}
          style={{ ...linkBtn, opacity: reenviando ? 0.6 : 1, cursor: reenviando ? 'wait' : 'pointer' }}
          title={`Vuelve a mandar el correo de activación a ${vecino.email ?? 'el email de la ficha'}`}
        >
          {reenviando ? 'Enviando…' : 'Reenviar correo de activación'}
        </button>
      )}
      <span style={{ ...chip, ...zarisChip.tono }}>{zarisChip.texto}</span>
    </div>
  )
}

const chip: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', padding: '3px 10px',
  borderRadius: 'var(--radius-pill)', fontSize: 'var(--size-caption)', fontWeight: 600,
  fontFamily: 'var(--font-display)', border: '1px solid transparent',
}
const linkBtn: React.CSSProperties = {
  background: 'transparent', border: 'none', padding: '2px 4px',
  fontFamily: 'var(--font-display)', fontSize: 'var(--size-caption)', fontWeight: 600,
  color: 'var(--zaris-orange)', textDecoration: 'underline',
}
const tonoOk: React.CSSProperties = { background: 'rgba(31,138,101,.12)', color: 'var(--color-success)' }
const tonoWarn: React.CSSProperties = { background: 'rgba(245,127,23,.14)', color: '#b35c00' }
const tonoNeutro: React.CSSProperties = { background: 'var(--surface-400)', color: 'var(--fg-2)' }
