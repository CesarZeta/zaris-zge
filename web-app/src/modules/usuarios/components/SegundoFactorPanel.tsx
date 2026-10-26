import { useState } from 'react'
import { useAuthStore } from '../../../stores/auth'
import { useNotificationsStore } from '../../../stores/notifications'
import { ConfirmModal } from '../../agenda/components/ConfirmModal'
import { useHabilitarSegundoFactor, useSegundoFactor } from '../hooks/useUsuarios'
import type { EstadoSegundoFactor, Usuario } from '../types'

// Segundo factor (IT-01 F3b): estado de la app de códigos de una cuenta de nivel 0 o 1. El botón
// lo ve solo el super administrador; el backend también lo exige (403 para cualquier otro).

function fmt(iso: string | null, conHora: boolean): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '—'
  return d.toLocaleString('es-AR', conHora
    ? { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }
    : { day: '2-digit', month: '2-digit', year: 'numeric' })
}

function textoEstado(e: EstadoSegundoFactor): string {
  if (e.vinculada) {
    const bloqueo = e.bloqueado_hasta
      ? ` · bloqueado hasta las ${new Date(e.bloqueado_hasta).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })}`
      : ''
    return `vinculado el ${fmt(e.confirmado_en, false)}${bloqueo}`
  }
  if (e.habilitada) return `habilitada para vincular hasta el ${fmt(e.habilitado_hasta, true)}`
  return 'sin vincular'
}

export function SegundoFactorPanel({ usuario }: { usuario: Usuario }) {
  const esSuper = useAuthStore((s) => s.user?.es_super_admin === true)
  const push = useNotificationsStore((s) => s.push)
  const requiere = usuario.nivel_acceso <= 1
  const estado = useSegundoFactor(requiere ? usuario.id_usuario : null)
  const habilitar = useHabilitarSegundoFactor()
  const [confirmar, setConfirmar] = useState(false)

  if (!requiere) return null

  function ejecutar() {
    // Se cierra al confirmar; el resultado llega por toast (CLAUDE.md §23).
    setConfirmar(false)
    habilitar.mutate(usuario.id_usuario, {
      onSuccess: () => push({ kind: 'success', title: 'Vinculación habilitada por 24 horas' }),
      onError: (err) => push({ kind: 'error', title: 'No se pudo habilitar', body: (err as Error).message }),
    })
  }

  return (
    <>
      <div style={seccionTitulo}>Segundo factor</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap', fontSize: '0.86rem', color: 'var(--fg-2)' }}>
        <span>
          Segundo factor:
          <strong style={{ color: 'var(--fg-1)', marginLeft: 6 }}>
            {estado.data ? textoEstado(estado.data) : estado.isError ? 'no disponible' : 'cargando…'}
          </strong>
        </span>
        {esSuper && (
          <button type="button" style={boton(habilitar.isPending)} disabled={habilitar.isPending}
            onClick={() => setConfirmar(true)}>
            Restablecer y habilitar vinculación
          </button>
        )}
      </div>
      <ConfirmModal
        open={confirmar}
        title="Restablecer el segundo factor"
        message={`La cuenta ${usuario.username} pierde la app vinculada y sus códigos de emergencia, se cierran sus sesiones abiertas y tiene 24 horas para vincular la app de nuevo desde el login.`}
        confirmLabel="Sí, restablecer" cancelLabel="Cancelar" danger
        onConfirm={ejecutar}
        onCancel={() => setConfirmar(false)}
      />
    </>
  )
}

const seccionTitulo: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.8rem', fontWeight: 600,
  textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--fg-3)',
  borderBottom: '1px solid var(--border-primary)', paddingBottom: 6, marginBottom: 4,
}

function boton(disabled: boolean): React.CSSProperties {
  return {
    display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 12px',
    fontFamily: 'var(--font-display)', fontSize: '0.86rem', fontWeight: 600,
    borderRadius: 8, cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.5 : 1,
    background: 'transparent', color: 'var(--color-error)', border: '1px solid var(--color-error)',
  }
}
