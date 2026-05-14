import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Modal } from '../Modal'
import { Button } from '../../../../ui'
import { useActualizarDisponibilidad, useCrearDisponibilidad } from '../../hooks/useDisponibilidad'
import { useEspacios } from '../../hooks/useEspacios'
import { listarRecursosAgenda } from '../../api/agendaApi'
import { DIA_LABEL_CORTO, deserialize, incluye, togglearDia, format as formatBitmask, type DiaIndex } from '../../../../lib/diasSemana'
import type { DisponibilidadRecurso, DisponibilidadRecursoCreatePayload, RecursoItem, TipoRecurso } from '../../types/agenda'

interface Props {
  open: boolean
  onClose: () => void
  disp: DisponibilidadRecurso | null
}

interface FormState {
  tipo_recurso: TipoRecurso
  id_recurso: number | null
  dias_semana: number
  hora_inicio: string   // HH:MM
  hora_fin: string
  vigente_desde: string  // YYYY-MM-DD o ''
  vigente_hasta: string
  etiqueta: string
}

const emptyForm: FormState = {
  tipo_recurso: 'agente',
  id_recurso: null,
  dias_semana: 31,  // Lun a Vie default
  hora_inicio: '09:00',
  hora_fin: '17:00',
  vigente_desde: '',
  vigente_hasta: '',
  etiqueta: '',
}

function fromDisp(d: DisponibilidadRecurso): FormState {
  return {
    tipo_recurso: d.tipo_recurso,
    id_recurso: d.id_recurso,
    dias_semana: d.dias_semana,
    hora_inicio: d.hora_inicio.slice(0, 5),
    hora_fin:    d.hora_fin.slice(0, 5),
    vigente_desde: d.vigente_desde ?? '',
    vigente_hasta: d.vigente_hasta ?? '',
    etiqueta:     d.etiqueta ?? '',
  }
}

export function DisponibilidadFormModal({ open, onClose, disp }: Props) {
  const isEdit = disp != null
  const [form, setForm] = useState<FormState>(emptyForm)
  const [error, setError] = useState<string | null>(null)
  const crear  = useCrearDisponibilidad()
  const editar = useActualizarDisponibilidad()

  useEffect(() => {
    if (!open) return
    setError(null)
    setForm(disp ? fromDisp(disp) : emptyForm)
  }, [open, disp])

  const agentes  = useQuery<RecursoItem[]>({ queryKey: ['agenda', 'recursos', 'agente'],  queryFn: () => listarRecursosAgenda({ tipo: 'agente',  limit: 500 }), staleTime: 60_000, enabled: form.tipo_recurso === 'agente' })
  const equipos  = useQuery<RecursoItem[]>({ queryKey: ['agenda', 'recursos', 'equipo'],  queryFn: () => listarRecursosAgenda({ tipo: 'equipo',  limit: 500 }), staleTime: 60_000, enabled: form.tipo_recurso === 'equipo' })
  const espacios = useEspacios()

  const opciones: { id: number; label: string }[] = (() => {
    if (form.tipo_recurso === 'agente')  return (agentes.data ?? []).map((a) => ({ id: a.id_recurso, label: a.nombre }))
    if (form.tipo_recurso === 'equipo')  return (equipos.data ?? []).map((e) => ({ id: e.id_recurso, label: e.nombre }))
    return (espacios.data ?? []).map((sp) => ({ id: sp.id_espacio, label: sp.nombre }))
  })()

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!form.id_recurso)         { setError('Elegi un recurso.'); return }
    if (form.dias_semana === 0)   { setError('Elegi al menos un dia.'); return }
    if (form.hora_fin <= form.hora_inicio) { setError('La hora fin debe ser mayor que la hora inicio.'); return }
    if (form.vigente_desde && form.vigente_hasta && form.vigente_hasta < form.vigente_desde) {
      setError('vigente_hasta debe ser >= vigente_desde.'); return
    }

    const payload: DisponibilidadRecursoCreatePayload = {
      tipo_recurso: form.tipo_recurso,
      id_recurso:   form.id_recurso,
      dias_semana:  form.dias_semana,
      hora_inicio:  `${form.hora_inicio}:00`,
      hora_fin:     `${form.hora_fin}:00`,
      vigente_desde: form.vigente_desde || null,
      vigente_hasta: form.vigente_hasta || null,
      etiqueta:      form.etiqueta.trim() || null,
    }

    try {
      if (isEdit && disp) {
        // En update no mandamos tipo_recurso ni id_recurso (no editables segun el schema).
        await editar.mutateAsync({
          id: disp.id_disponibilidad,
          payload: {
            dias_semana: payload.dias_semana,
            hora_inicio: payload.hora_inicio,
            hora_fin:    payload.hora_fin,
            vigente_desde: payload.vigente_desde,
            vigente_hasta: payload.vigente_hasta,
            etiqueta:      payload.etiqueta,
          },
        })
      } else {
        await crear.mutateAsync(payload)
      }
      onClose()
    } catch (err) {
      setError((err as Error).message || 'Error al guardar.')
    }
  }

  const submitting = crear.isPending || editar.isPending
  const diasActivos = deserialize(form.dias_semana)

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isEdit ? `Editar disponibilidad #${disp?.id_disponibilidad}` : 'Nueva disponibilidad'}
      footer={(
        <>
          <Button variant="ghost" onClick={onClose} disabled={submitting}>Cancelar</Button>
          <Button variant="accent" onClick={onSubmit} disabled={submitting}>{submitting ? 'Guardando...' : (isEdit ? 'Guardar cambios' : 'Crear')}</Button>
        </>
      )}
    >
      <form onSubmit={onSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {!isEdit && (
          <>
            <Field label="Tipo de recurso">
              <select
                value={form.tipo_recurso}
                onChange={(e) => setForm((f) => ({ ...f, tipo_recurso: e.target.value as TipoRecurso, id_recurso: null }))}
                style={inputStyle}
              >
                <option value="agente">Agente</option>
                <option value="equipo">Equipo</option>
                <option value="espacio">Espacio</option>
              </select>
            </Field>
            <Field label="Recurso">
              <select
                value={form.id_recurso ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, id_recurso: e.target.value ? Number(e.target.value) : null }))}
                style={inputStyle}
              >
                <option value="">Seleccionar...</option>
                {opciones.map((o) => (
                  <option key={o.id} value={o.id}>{o.label}</option>
                ))}
              </select>
            </Field>
          </>
        )}

        <Field label="Dias de la semana">
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {DIA_LABEL_CORTO.map((lbl, i) => {
              const idx = i as DiaIndex
              const active = incluye(form.dias_semana, idx)
              return (
                <button
                  key={lbl}
                  type="button"
                  onClick={() => setForm((f) => ({ ...f, dias_semana: togglearDia(f.dias_semana, idx) }))}
                  style={{
                    width: 44, padding: '6px 0', borderRadius: 'var(--radius-md)',
                    border: active ? '1px solid var(--zaris-orange)' : '1px solid var(--border-primary)',
                    background: active ? 'var(--zaris-orange)' : 'var(--surface-100)',
                    color: active ? '#fff' : 'var(--fg-2)',
                    fontFamily: 'var(--font-display)', fontSize: 12, cursor: 'pointer',
                  }}
                >
                  {lbl}
                </button>
              )
            })}
          </div>
          <div style={{ fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
            {diasActivos.length === 0 ? '(sin dias)' : formatBitmask(form.dias_semana)}
          </div>
        </Field>

        <div style={{ display: 'flex', gap: 12 }}>
          <Field label="Hora inicio" style={{ flex: 1 }}>
            <input type="time" value={form.hora_inicio} onChange={(e) => setForm((f) => ({ ...f, hora_inicio: e.target.value }))} style={inputStyle} />
          </Field>
          <Field label="Hora fin" style={{ flex: 1 }}>
            <input type="time" value={form.hora_fin} onChange={(e) => setForm((f) => ({ ...f, hora_fin: e.target.value }))} style={inputStyle} />
          </Field>
        </div>

        <div style={{ display: 'flex', gap: 12 }}>
          <Field label="Vigente desde (opcional)" style={{ flex: 1 }}>
            <input type="date" value={form.vigente_desde} onChange={(e) => setForm((f) => ({ ...f, vigente_desde: e.target.value }))} style={inputStyle} />
          </Field>
          <Field label="Vigente hasta (opcional)" style={{ flex: 1 }}>
            <input type="date" value={form.vigente_hasta} onChange={(e) => setForm((f) => ({ ...f, vigente_hasta: e.target.value }))} style={inputStyle} />
          </Field>
        </div>

        <Field label="Etiqueta (opcional)">
          <input
            value={form.etiqueta}
            onChange={(e) => setForm((f) => ({ ...f, etiqueta: e.target.value }))}
            placeholder='ej: "turno mañana", "guardia rotativa"'
            maxLength={60}
            style={inputStyle}
          />
        </Field>

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
