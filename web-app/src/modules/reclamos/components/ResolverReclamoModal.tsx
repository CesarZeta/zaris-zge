import { useEffect, useState } from 'react'
import { Modal } from '../../agenda/components/Modal'
import { useNotificationsStore } from '../../../stores/notifications'
import { useResolverReclamo } from '../hooks/useReclamos'

interface Props {
  open: boolean
  idReclamo: number
  nroReclamo: string | null
  onClose: () => void
  onSuccess?: () => void
}

const MIN = 5
const MAX = 2000

// Resolver desde Reclamos (César 2026-10-21): quien tiene la OT, la supervisión
// de la gestión o un admin cierra el reclamo con una resolución que ve el vecino
// (app + aviso de cierre). Termina la OT abierta; sin OT es el cierre directo.
export function ResolverReclamoModal({ open, idReclamo, nroReclamo, onClose, onSuccess }: Props) {
  const push = useNotificationsStore((s) => s.push)
  const mut = useResolverReclamo()
  const [texto, setTexto] = useState('')

  useEffect(() => {
    if (open) setTexto('')
  }, [open])

  const valido = texto.trim().length >= MIN

  async function confirmar() {
    if (!valido) return
    try {
      await mut.mutateAsync({ id: idReclamo, resolucion: texto.trim() })
      push({ kind: 'success', title: 'Reclamo resuelto', body: 'El vecino recibe el aviso con la resolución.' })
      onSuccess?.()
      onClose()
    } catch (err) {
      push({ kind: 'error', title: 'No se pudo resolver', body: (err as Error).message })
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Resolver reclamo"
      width={520}
      footer={
        <>
          <button type="button" onClick={onClose} disabled={mut.isPending} style={btnGhost}>Volver</button>
          <button type="button" onClick={confirmar} disabled={mut.isPending || !valido}
                  style={{ ...btnPrimary, ...(!valido ? { opacity: 0.5, cursor: 'not-allowed' } : {}) }}>
            {mut.isPending ? 'Resolviendo...' : 'Resolver'}
          </button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--fg-1)', lineHeight: 1.55 }}>
          El reclamo <strong>{nroReclamo ?? `#${idReclamo}`}</strong> pasa a <strong>Resuelto</strong> y
          su orden de trabajo se termina. Contale al vecino qué se hizo.
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 'var(--size-caption)', fontWeight: 600, color: 'var(--fg-2)' }}>
            Resolución · la ve el vecino
          </label>
          <textarea
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            placeholder="Ej: Se cambió la lámpara y se verificó el encendido. Gracias por avisarnos."
            rows={5}
            maxLength={MAX}
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
            {texto.length}/{MAX} caracteres · llega al vecino en su app y en el aviso de cierre.
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
