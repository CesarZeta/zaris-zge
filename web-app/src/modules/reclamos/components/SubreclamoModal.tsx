import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Modal } from '../../agenda/components/Modal'
import { useNotificationsStore } from '../../../stores/notifications'
import { useCrearSubreclamo } from '../hooks/useReclamos'
import { TipoReclamoPicker } from './TipoReclamoPicker'
import type { Prioridad } from '../types/reclamo'

interface Props {
  open: boolean
  idReclamo: number
  nroReclamo?: string | null
  onClose: () => void
  onSuccess?: () => void
}

const PRIORIDADES: Prioridad[] = ['Baja', 'Media', 'Alta']

/**
 * Modal para generar un subreclamo. Hereda ciudadano/empresa del padre
 * (el backend lo resuelve), solo pide tipo + descripcion + prioridad.
 * Al confirmar, el reclamo padre pasa a "En espera".
 */
export function SubreclamoModal({ open, idReclamo, nroReclamo, onClose, onSuccess }: Props) {
  const navigate = useNavigate()
  const push = useNotificationsStore((s) => s.push)
  const mut = useCrearSubreclamo(idReclamo)
  const [idTipo, setIdTipo] = useState<number | null>(null)
  const [descripcion, setDescripcion] = useState('')
  const [prioridad, setPrioridad] = useState<Prioridad>('Media')
  const [observaciones, setObservaciones] = useState('')

  useEffect(() => {
    if (open) {
      setIdTipo(null)
      setDescripcion('')
      setPrioridad('Media')
      setObservaciones('')
    }
  }, [open])

  const valido = idTipo != null && descripcion.trim().length > 0

  async function confirmar() {
    if (!valido) return
    try {
      const res = await mut.mutateAsync({
        id_tipo_reclamo: idTipo as number,
        descripcion: descripcion.trim(),
        prioridad,
        observaciones: observaciones.trim() || undefined,
      })
      push({
        kind: 'success',
        title: `Subreclamo ${res.nro_reclamo} creado`,
        body: 'El reclamo padre pasó a "En espera".',
      })
      onSuccess?.()
      onClose()
      navigate(`/reclamos/${res.id_reclamo}`)
    } catch (err) {
      push({ kind: 'error', title: 'Error al crear subreclamo', body: (err as Error).message })
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Generar subreclamo"
      width={520}
      footer={
        <>
          <button onClick={onClose} disabled={mut.isPending} style={btnGhost}>Cancelar</button>
          <button onClick={confirmar} disabled={mut.isPending || !valido} style={btnPrimary}>
            {mut.isPending ? 'Creando...' : 'Crear subreclamo'}
          </button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={infoBox}>
          El subreclamo hereda el ciudadano y la empresa del reclamo
          {nroReclamo ? ` ${nroReclamo}` : ` #${idReclamo}`}. Al crearlo, el reclamo
          padre pasa a estado <strong>En espera</strong>.
        </div>

        <Field label="Tipo de reclamo" required>
          <TipoReclamoPicker
            value={idTipo}
            onChange={(id) => setIdTipo(id)}
            placeholder="Tipear nombre del tipo de reclamo..."
          />
        </Field>

        <Field label="Descripción" required>
          <textarea
            value={descripcion}
            onChange={(e) => setDescripcion(e.target.value)}
            placeholder="Qué se necesita resolver en este subreclamo."
            rows={3}
            maxLength={1000}
            style={{ ...inputStyle, resize: 'vertical', fontFamily: 'var(--font-display)' }}
          />
        </Field>

        <Field label="Prioridad">
          <select
            value={prioridad}
            onChange={(e) => setPrioridad(e.target.value as Prioridad)}
            style={inputStyle}
          >
            {PRIORIDADES.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </Field>

        <Field label="Observaciones" hint="Opcional.">
          <textarea
            value={observaciones}
            onChange={(e) => setObservaciones(e.target.value)}
            rows={2}
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

const infoBox: React.CSSProperties = {
  padding: '10px 12px', background: 'var(--surface-300)',
  border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)',
  color: 'var(--fg-2)', fontSize: 'var(--size-caption)', lineHeight: 1.5,
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '9px 12px',
  fontFamily: 'var(--font-display)', fontSize: 'var(--size-ui)',
  color: 'var(--fg-1)', background: 'var(--surface-100)',
  border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)',
  outline: 'none',
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
