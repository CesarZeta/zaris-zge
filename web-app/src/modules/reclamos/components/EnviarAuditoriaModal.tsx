import { useEffect, useState } from 'react'
import { Modal } from '../../agenda/components/Modal'
import { useNotificationsStore } from '../../../stores/notifications'
import { useEnviarAuditoria } from '../hooks/useReclamos'

interface Props {
  open: boolean
  idReclamo: number
  nroReclamo: string | null
  onClose: () => void
  onSuccess?: () => void
}

// Auditoría POSTERIOR al cierre (mig 112, PLAN_AUDITORIA_RECLAMOS.md): un
// supervisor de la subárea (o un admin) elige un reclamo Resuelto y lo manda a
// 'En auditoría'. El backend crea la OT de auditoría; la toma un auditor desde
// la mesa de Auditoría. fecha_cierre no cambia y el vecino no se entera.
export function EnviarAuditoriaModal({ open, idReclamo, nroReclamo, onClose, onSuccess }: Props) {
  const push = useNotificationsStore((s) => s.push)
  const mut = useEnviarAuditoria(idReclamo)
  const [obs, setObs] = useState('')

  useEffect(() => {
    if (open) setObs('')
  }, [open])

  async function confirmar() {
    try {
      const res = await mut.mutateAsync({ observaciones: obs.trim() || undefined })
      push({ kind: 'success', title: 'Reclamo enviado a auditoría', body: `Auditoría ${res.nro_ot}` })
      onSuccess?.()
      onClose()
    } catch (err) {
      push({ kind: 'error', title: 'No se pudo enviar a auditoría', body: (err as Error).message })
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Enviar a auditoría"
      width={500}
      footer={
        <>
          <button onClick={onClose} disabled={mut.isPending} style={btnGhost}>Volver</button>
          <button onClick={confirmar} disabled={mut.isPending} style={btnPrimary}>
            {mut.isPending ? 'Enviando...' : 'Enviar a auditoría'}
          </button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--fg-1)', lineHeight: 1.55 }}>
          El reclamo <strong>{nroReclamo ?? `#${idReclamo}`}</strong> pasa a <strong>En auditoría</strong> para
          que lo revise un auditor. Su fecha de cierre y sus tiempos de gestión <strong>no cambian</strong>, y
          el vecino no recibe ningún aviso. El auditor lo cierra como <strong>Auditado</strong> (aprobado u
          observado); si lo observa, puede iniciar un incidente nuevo para rehacer el trabajo, y en ese
          caso el vecino recibe un correo que se lo explica.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 'var(--size-caption)', fontWeight: 600, color: 'var(--fg-2)' }}>
            Motivo o indicaciones para el auditor
          </label>
          <textarea
            value={obs}
            onChange={(e) => setObs(e.target.value)}
            placeholder="Opcional. Ej: control de calidad del mes, verificar que la reparación haya quedado firme..."
            rows={4}
            maxLength={500}
            autoFocus
            style={{
              width: '100%', padding: '9px 12px',
              fontFamily: 'var(--font-display)', fontSize: 'var(--size-ui)',
              color: 'var(--fg-1)', background: 'var(--surface-100)',
              border: '1px solid var(--border-primary)',
              borderRadius: 'var(--radius-lg)', outline: 'none', resize: 'vertical',
            }}
          />
          <div style={{ fontSize: 'var(--size-caption)', color: 'var(--fg-3)' }}>
            {obs.length}/500 caracteres · queda en el historial y en la OT de auditoría.
          </div>
        </div>
      </div>
    </Modal>
  )
}

const btnPrimary: React.CSSProperties = {
  padding: '8px 16px', background: 'var(--zaris-dark)', color: 'var(--zaris-cream)',
  border: 'none', borderRadius: 'var(--radius-lg)',
  fontFamily: 'var(--font-display)', fontSize: 'var(--size-btn)',
  fontWeight: 500, cursor: 'pointer',
}

const btnGhost: React.CSSProperties = {
  padding: '8px 16px', background: 'transparent', color: 'var(--fg-2)',
  border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)',
  fontFamily: 'var(--font-display)', fontSize: 'var(--size-btn)', cursor: 'pointer',
}
