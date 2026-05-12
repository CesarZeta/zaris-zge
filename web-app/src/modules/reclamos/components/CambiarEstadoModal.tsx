import { useEffect, useState } from 'react'
import { Modal } from '../../agenda/components/Modal'
import { useNotificationsStore } from '../../../stores/notifications'
import { useCambiarEstadoReclamo } from '../hooks/useReclamos'
import type { EstadoReclamo } from '../types/reclamo'

interface Props {
  open: boolean
  idReclamo: number
  estadoActual: EstadoReclamo
  onClose: () => void
  onSuccess?: () => void
}

// Solo se permite transicionar a estados vivos. Cancelado usa el endpoint
// dedicado /cancelar (motivo requerido + cascade OTs). Resuelto se logra
// desde el flujo de auditoría (OT aprobada), no acá.
const ESTADOS_TRANSICIONABLES: EstadoReclamo[] = [
  'Sin asignar',
  'En gestión',
  'En espera',
  'En auditoría',
  'Resuelto',
]

export function CambiarEstadoModal({ open, idReclamo, estadoActual, onClose, onSuccess }: Props) {
  const push = useNotificationsStore((s) => s.push)
  const mut = useCambiarEstadoReclamo(idReclamo)
  const [estadoNuevo, setEstadoNuevo] = useState<EstadoReclamo>(estadoActual)
  const [nota, setNota] = useState('')

  useEffect(() => {
    if (open) {
      setEstadoNuevo(estadoActual)
      setNota('')
    }
  }, [open, estadoActual])

  async function confirmar() {
    if (estadoNuevo === estadoActual) {
      push({ kind: 'info', title: 'El estado nuevo es igual al actual' })
      return
    }
    try {
      await mut.mutateAsync({ estado: estadoNuevo, nota: nota.trim() || undefined })
      push({ kind: 'success', title: `Estado actualizado a "${estadoNuevo}"` })
      onSuccess?.()
      onClose()
    } catch (err) {
      push({ kind: 'error', title: 'Error al cambiar estado', body: (err as Error).message })
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Cambiar estado del reclamo"
      width={480}
      footer={
        <>
          <button onClick={onClose} disabled={mut.isPending} style={btnGhost}>Cancelar</button>
          <button onClick={confirmar} disabled={mut.isPending || estadoNuevo === estadoActual} style={btnPrimary}>
            {mut.isPending ? 'Guardando...' : 'Aplicar cambio'}
          </button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <Field label="Estado actual">
          <div style={readonlyField}>{estadoActual}</div>
        </Field>

        <Field label="Nuevo estado" required>
          <select
            value={estadoNuevo}
            onChange={(e) => setEstadoNuevo(e.target.value as EstadoReclamo)}
            style={inputStyle}
          >
            {ESTADOS_TRANSICIONABLES.map((e) => (
              <option key={e} value={e}>{e}</option>
            ))}
          </select>
        </Field>

        <Field label="Nota para el historial" hint="Opcional. Aparece en el timeline del reclamo y se concatena en observaciones.">
          <textarea
            value={nota}
            onChange={(e) => setNota(e.target.value)}
            placeholder="Ej: contactado el reclamante, equipo asignado mañana 9hs."
            rows={3}
            maxLength={500}
            style={{ ...inputStyle, resize: 'vertical', fontFamily: 'var(--font-display)' }}
          />
        </Field>
      </div>
    </Modal>
  )
}

function Field({ label, required, hint, children }: {
  label: string; required?: boolean; hint?: string; children: React.ReactNode
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label style={{ fontSize: 'var(--size-caption)', fontWeight: 600, color: 'var(--fg-2)' }}>
        {label}{required && <span style={{ color: 'var(--zaris-orange)', marginLeft: 4 }}>*</span>}
      </label>
      {children}
      {hint && <div style={{ fontSize: 'var(--size-caption)', color: 'var(--fg-3)' }}>{hint}</div>}
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '9px 12px',
  fontFamily: 'var(--font-display)', fontSize: 'var(--size-ui)',
  color: 'var(--fg-1)', background: 'var(--surface-100)',
  border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)',
  outline: 'none',
}

const readonlyField: React.CSSProperties = {
  padding: '9px 12px', background: 'var(--surface-300)',
  border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)',
  color: 'var(--fg-2)', fontSize: 'var(--size-ui)',
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
