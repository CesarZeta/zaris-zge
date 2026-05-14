import { useEffect, useState } from 'react'
import { Modal } from '../Modal'
import { Button } from '../../../../ui'
import { useActualizarEspacio, useCrearEspacio } from '../../hooks/useEspacios'
import type { EspacioAgenda, EspacioAgendaCreatePayload } from '../../types/agenda'

interface Props {
  open: boolean
  onClose: () => void
  espacio: EspacioAgenda | null
}

interface FormState {
  nombre: string
  descripcion: string
  direccion: string
  capacidad_personas: string  // string para input, parsea en submit
  atendido: boolean
  id_subarea: string
}

const emptyForm: FormState = {
  nombre: '',
  descripcion: '',
  direccion: '',
  capacidad_personas: '',
  atendido: true,
  id_subarea: '',
}

function fromEspacio(e: EspacioAgenda): FormState {
  return {
    nombre: e.nombre,
    descripcion: e.descripcion ?? '',
    direccion: e.direccion ?? '',
    capacidad_personas: e.capacidad_personas != null ? String(e.capacidad_personas) : '',
    atendido: e.atendido,
    id_subarea: e.id_subarea != null ? String(e.id_subarea) : '',
  }
}

export function EspacioFormModal({ open, onClose, espacio }: Props) {
  const isEdit = espacio != null
  const [form, setForm] = useState<FormState>(emptyForm)
  const [error, setError] = useState<string | null>(null)
  const crear = useCrearEspacio()
  const editar = useActualizarEspacio()

  // Reset al abrir o cambiar de espacio. Sin defaultDate en deps para evitar
  // que props externas pisen lo que el usuario escribio (patron §29).
  useEffect(() => {
    if (!open) return
    setError(null)
    setForm(espacio ? fromEspacio(espacio) : emptyForm)
  }, [open, espacio])

  function buildPayload(): EspacioAgendaCreatePayload {
    return {
      nombre: form.nombre.trim(),
      descripcion: form.descripcion.trim() || null,
      direccion: form.direccion.trim() || null,
      capacidad_personas: form.capacidad_personas ? Number(form.capacidad_personas) : null,
      atendido: form.atendido,
      id_subarea: form.id_subarea ? Number(form.id_subarea) : null,
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!form.nombre.trim()) { setError('El nombre es obligatorio.'); return }
    try {
      if (isEdit && espacio) {
        await editar.mutateAsync({ id: espacio.id_espacio, payload: buildPayload() })
      } else {
        await crear.mutateAsync(buildPayload())
      }
      onClose()
    } catch (err) {
      setError((err as Error).message || 'Error al guardar.')
    }
  }

  const submitting = crear.isPending || editar.isPending

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isEdit ? `Editar espacio - ${espacio?.nombre}` : 'Nuevo espacio'}
      footer={(
        <>
          <Button variant="ghost" onClick={onClose} disabled={submitting}>Cancelar</Button>
          <Button variant="accent" onClick={onSubmit} disabled={submitting}>{submitting ? 'Guardando...' : (isEdit ? 'Guardar cambios' : 'Crear espacio')}</Button>
        </>
      )}
    >
      <form onSubmit={onSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <Field label="Nombre *">
          <input
            value={form.nombre}
            onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))}
            maxLength={150}
            required
            style={inputStyle}
          />
        </Field>
        <Field label="Descripcion">
          <textarea
            value={form.descripcion}
            onChange={(e) => setForm((f) => ({ ...f, descripcion: e.target.value }))}
            rows={2}
            style={{ ...inputStyle, resize: 'vertical', minHeight: 56 }}
          />
        </Field>
        <Field label="Direccion">
          <input
            value={form.direccion}
            onChange={(e) => setForm((f) => ({ ...f, direccion: e.target.value }))}
            maxLength={300}
            style={inputStyle}
          />
        </Field>
        <div style={{ display: 'flex', gap: 12 }}>
          <Field label="Capacidad personas" style={{ flex: 1 }}>
            <input
              type="number"
              min={0}
              value={form.capacidad_personas}
              onChange={(e) => setForm((f) => ({ ...f, capacidad_personas: e.target.value }))}
              style={inputStyle}
            />
          </Field>
          <Field label="ID Subarea (opcional)" style={{ flex: 1 }}>
            <input
              type="number"
              min={1}
              value={form.id_subarea}
              onChange={(e) => setForm((f) => ({ ...f, id_subarea: e.target.value }))}
              style={inputStyle}
            />
          </Field>
        </div>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontFamily: 'var(--font-display)', fontSize: 13, color: 'var(--fg-1)' }}>
          <input
            type="checkbox"
            checked={form.atendido}
            onChange={(e) => setForm((f) => ({ ...f, atendido: e.target.checked }))}
          />
          Espacio atendido (requiere vincular agentes para tener disponibilidad efectiva)
        </label>
        {error && (
          <div style={{ color: 'var(--color-error)', fontSize: 13, fontFamily: 'var(--font-mono)' }}>
            {error}
          </div>
        )}
      </form>
    </Modal>
  )
}

function Field({ label, children, style }: { label: string; children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 4, ...style }}>
      <span style={{ fontFamily: 'var(--font-display)', fontSize: 11, color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '.04em' }}>
        {label}
      </span>
      {children}
    </label>
  )
}

const inputStyle: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: 13,
  padding: '8px 10px', border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-md)', background: 'var(--surface-100)',
  color: 'var(--fg-1)', outline: 'none',
}
