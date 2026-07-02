import { useEffect, useState } from 'react'
import { Modal } from '../../agenda/components/Modal'
import { useNotificationsStore } from '../../../stores/notifications'
import { useAvisarSupervisor } from '../hooks/useReclamos'

// Espeja ACCIONES_AVISO_SUPERVISOR de backend/app/api/routes/reclamos.py —
// si modificás la lista, tocá los DOS lugares.
const ACCIONES = [
  { valor: 'Generar OT', hint: 'Pedir que se asigne una orden de trabajo' },
  { valor: 'Pasar a En espera', hint: 'El reclamo está bloqueado por algo externo' },
  { valor: 'Resolver', hint: 'Ya está solucionado o no requiere gestión' },
  { valor: 'Cancelar', hint: 'Duplicado, fuera de jurisdicción, sin información' },
  { valor: 'Revisar', hint: 'Otro pedido — detallalo en el comentario' },
]

interface Props {
  open: boolean
  idReclamo: number
  nroReclamo: string | null
  onClose: () => void
  onSuccess?: () => void
}

/**
 * Fase 3 roles — el operador (nivel 3) no cambia estados: con este modal le
 * pide al supervisor de la subárea una acción concreta sobre el reclamo
 * (notificación in-app + mail; fallback a admins si la subárea no tiene
 * supervisor). Cierra AL CONFIRMAR y reporta por toast (regla §23: la latencia
 * Railway↔Supabase hace que esperar el onSuccess se sienta como "no hizo nada").
 */
export function AvisarSupervisorModal({ open, idReclamo, nroReclamo, onClose, onSuccess }: Props) {
  const push = useNotificationsStore((s) => s.push)
  const mut = useAvisarSupervisor(idReclamo)
  const [accion, setAccion] = useState(ACCIONES[0].valor)
  const [comentario, setComentario] = useState('')

  // Reset al abrir: el modal vive montado con open=false y un cancelar dejaría
  // texto residual para el próximo uso (§29).
  useEffect(() => {
    if (open) { setAccion(ACCIONES[0].valor); setComentario('') }
  }, [open])

  function confirmar() {
    const body = { accion_sugerida: accion, comentario: comentario.trim() || undefined }
    onClose()
    mut.mutate(body, {
      onSuccess: () => {
        push({ kind: 'success', title: 'Aviso enviado al supervisor', body: nroReclamo ?? `#${idReclamo}` })
        onSuccess?.()
      },
      onError: (err) => {
        push({ kind: 'error', title: 'No se pudo enviar el aviso', body: (err as Error).message })
      },
    })
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Avisar al supervisor"
      width={480}
      footer={
        <>
          <button onClick={onClose} style={btnGhost}>Volver</button>
          <button onClick={confirmar} style={btnPrimary}>Enviar aviso</button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--fg-1)', lineHeight: 1.5 }}>
          El cambio de estado del reclamo <strong>{nroReclamo ?? `#${idReclamo}`}</strong> lo
          gestiona Supervisión. Elegí qué acción pedís y el supervisor de la subárea
          recibe el aviso (in-app y por mail). Queda registrado en el historial.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label style={labelStyle}>
            Acción que pedís<span style={{ color: 'var(--zaris-orange)', marginLeft: 4 }}>*</span>
          </label>
          {ACCIONES.map((a) => (
            <label
              key={a.valor}
              style={{
                display: 'flex', alignItems: 'baseline', gap: 8, cursor: 'pointer',
                padding: '7px 10px', borderRadius: 'var(--radius-md)',
                border: `1px solid ${accion === a.valor ? 'var(--zaris-orange)' : 'var(--border-primary)'}`,
                background: accion === a.valor ? 'var(--surface-400)' : 'var(--surface-100)',
              }}
            >
              <input
                type="radio"
                name="accion-aviso"
                checked={accion === a.valor}
                onChange={() => setAccion(a.valor)}
                style={{ accentColor: 'var(--zaris-orange)' }}
              />
              <span style={{ fontSize: '0.86rem', color: 'var(--fg-1)', fontWeight: 500 }}>{a.valor}</span>
              <span style={{ fontSize: '0.74rem', color: 'var(--fg-3)' }}>{a.hint}</span>
            </label>
          ))}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={labelStyle}>Comentario (opcional)</label>
          <textarea
            value={comentario}
            onChange={(e) => setComentario(e.target.value)}
            placeholder="Contexto para el supervisor: qué viste, qué te pidió el vecino..."
            rows={3}
            maxLength={500}
            style={{
              width: '100%', padding: '9px 12px',
              fontFamily: 'var(--font-display)', fontSize: 'var(--size-ui)',
              color: 'var(--fg-1)', background: 'var(--surface-100)',
              border: '1px solid var(--border-primary)',
              borderRadius: 'var(--radius-lg)', outline: 'none', resize: 'vertical',
            }}
          />
          <div style={{ fontSize: 'var(--size-caption)', color: 'var(--fg-3)' }}>
            {comentario.length}/500 caracteres
          </div>
        </div>
      </div>
    </Modal>
  )
}

const labelStyle: React.CSSProperties = {
  fontSize: 'var(--size-caption)', fontWeight: 600, color: 'var(--fg-2)',
}

const btnPrimary: React.CSSProperties = {
  padding: '8px 16px', background: 'var(--zaris-orange)', color: '#fff',
  border: 'none', borderRadius: 'var(--radius-lg)',
  fontFamily: 'var(--font-display)', fontSize: 'var(--size-btn)',
  fontWeight: 500, cursor: 'pointer',
}

const btnGhost: React.CSSProperties = {
  padding: '8px 16px', background: 'transparent', color: 'var(--fg-2)',
  border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)',
  fontFamily: 'var(--font-display)', fontSize: 'var(--size-btn)', cursor: 'pointer',
}
