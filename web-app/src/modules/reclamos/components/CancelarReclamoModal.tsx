import { useEffect, useState } from 'react'
import { Modal } from '../../agenda/components/Modal'
import { useNotificationsStore } from '../../../stores/notifications'
import { useCancelarReclamo } from '../hooks/useReclamos'

interface Props {
  open: boolean
  idReclamo: number
  nroReclamo: string | null
  onClose: () => void
  onSuccess?: () => void
}

export function CancelarReclamoModal({ open, idReclamo, nroReclamo, onClose, onSuccess }: Props) {
  const push = useNotificationsStore((s) => s.push)
  const mut = useCancelarReclamo(idReclamo)
  const [motivo, setMotivo] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (open) { setMotivo(''); setError('') }
  }, [open])

  async function confirmar() {
    const m = motivo.trim()
    if (!m) {
      setError('Ingresá un motivo de cancelación.')
      return
    }
    if (m.length < 5) {
      setError('El motivo es muy corto (mín. 5 caracteres).')
      return
    }
    try {
      await mut.mutateAsync({ motivo: m })
      push({ kind: 'success', title: 'Reclamo cancelado', body: nroReclamo ?? `#${idReclamo}` })
      onSuccess?.()
      onClose()
    } catch (err) {
      push({ kind: 'error', title: 'Error al cancelar', body: (err as Error).message })
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Cancelar reclamo"
      width={480}
      footer={
        <>
          <button onClick={onClose} disabled={mut.isPending} style={btnGhost}>Volver</button>
          <button onClick={confirmar} disabled={mut.isPending} style={btnDanger}>
            {mut.isPending ? 'Cancelando...' : 'Confirmar cancelación'}
          </button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--fg-1)', lineHeight: 1.5 }}>
          Esta acción marca el reclamo <strong>{nroReclamo ?? `#${idReclamo}`}</strong> como <strong>Cancelado</strong>
          {' '}y cierra en cascada las órdenes de trabajo activas asociadas. Se registra en el historial.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 'var(--size-caption)', fontWeight: 600, color: 'var(--fg-2)' }}>
            Motivo<span style={{ color: 'var(--zaris-orange)', marginLeft: 4 }}>*</span>
          </label>
          <textarea
            value={motivo}
            onChange={(e) => { setMotivo(e.target.value); if (error) setError('') }}
            placeholder="Ej: reclamo duplicado, fuera de jurisdicción, sin información suficiente..."
            rows={4}
            maxLength={500}
            autoFocus
            style={{
              width: '100%', padding: '9px 12px',
              fontFamily: 'var(--font-display)', fontSize: 'var(--size-ui)',
              color: 'var(--fg-1)', background: 'var(--surface-100)',
              border: `1px solid ${error ? 'var(--color-error)' : 'var(--border-primary)'}`,
              borderRadius: 'var(--radius-lg)', outline: 'none', resize: 'vertical',
            }}
          />
          {error && <div style={{ fontSize: 'var(--size-caption)', color: 'var(--color-error)' }}>{error}</div>}
          {!error && (
            <div style={{ fontSize: 'var(--size-caption)', color: 'var(--fg-3)' }}>
              {motivo.length}/500 caracteres
            </div>
          )}
        </div>
      </div>
    </Modal>
  )
}

const btnDanger: React.CSSProperties = {
  padding: '8px 16px', background: 'var(--color-error)', color: '#fff',
  border: 'none', borderRadius: 'var(--radius-lg)',
  fontFamily: 'var(--font-display)', fontSize: 'var(--size-btn)',
  fontWeight: 500, cursor: 'pointer',
}

const btnGhost: React.CSSProperties = {
  padding: '8px 16px', background: 'transparent', color: 'var(--fg-2)',
  border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)',
  fontFamily: 'var(--font-display)', fontSize: 'var(--size-btn)', cursor: 'pointer',
}
