import { useEffect, useState } from 'react'
import { ClipboardList } from 'lucide-react'
import { Modal } from '../components/Modal'
import { Button } from '../../../ui'
import { OTSearch } from '../components/OTSearch'
import { RecursoPicker } from '../components/RecursoPicker'
import { useCrearOcupacion } from '../hooks/useOcupaciones'
import { useNotificationsStore } from '../../../stores/notifications'
import type { OcupacionCreatePayload, OTBusquedaItem, TipoRecurso } from '../types/agenda'

interface Props {
  open: boolean
  onClose: () => void
  // Defaults pre-cargados (fecha/recurso/horario al abrir desde la grilla).
  defaults?: Partial<OcupacionCreatePayload>
}

interface OTForm {
  tipo_recurso: TipoRecurso
  id_recurso: number
  fecha: string
  hora_inicio: string
  hora_fin: string
  id_municipio: number
}

function emptyForm(d?: Partial<OcupacionCreatePayload>): OTForm {
  return {
    tipo_recurso: d?.tipo_recurso ?? 'agente',
    id_recurso: d?.id_recurso ?? 0,
    fecha: d?.fecha ?? new Date().toISOString().slice(0, 10),
    hora_inicio: d?.hora_inicio ?? '09:00',
    hora_fin: d?.hora_fin ?? '10:00',
    id_municipio: d?.id_municipio ?? 1,
  }
}

/**
 * Modal dedicado a ocupaciones tipo OT. A diferencia del modal generico de
 * turno/evento, este SIEMPRE arranca por la OT (que ya esta ligada a un
 * reclamo en la DB) y muestra el reclamo asociado como contexto de lo que se
 * esta planificando.
 */
export function OcupacionOTModal({ open, onClose, defaults }: Props) {
  const push = useNotificationsStore((s) => s.push)
  const crear = useCrearOcupacion()
  const [form, setForm] = useState<OTForm>(() => emptyForm(defaults))
  const [otSel, setOtSel] = useState<OTBusquedaItem | null>(null)

  useEffect(() => {
    if (open) {
      setForm(emptyForm(defaults))
      setOtSel(null)
    }
  }, [open, defaults])

  function update<K extends keyof OTForm>(k: K, v: OTForm[K]) {
    setForm((f) => ({ ...f, [k]: v }))
  }

  async function submit() {
    if (!otSel) {
      push({ kind: 'error', title: 'Falta la OT', body: 'Busca y selecciona una orden de trabajo.' })
      return
    }
    if (!form.id_recurso) {
      push({ kind: 'error', title: 'Falta el recurso', body: 'Selecciona un agente o equipo.' })
      return
    }
    if (form.hora_fin <= form.hora_inicio) {
      push({ kind: 'error', title: 'Horario invalido', body: 'hora_fin debe ser mayor que hora_inicio' })
      return
    }
    const payload: OcupacionCreatePayload = {
      tipo: 'ot',
      tipo_recurso: form.tipo_recurso,
      id_recurso: form.id_recurso,
      fecha: form.fecha,
      hora_inicio: form.hora_inicio,
      hora_fin: form.hora_fin,
      id_orden_trabajo: otSel.id_ot,
      id_evento: null,
      id_ciudadano: null,
      duracion_aplicada_min: null,
      rol_en_evento: null,
      motivo: null,
      id_municipio: form.id_municipio,
    }
    try {
      const r = await crear.mutateAsync(payload)
      const conConflicto = (r.conflictos?.length ?? 0) > 0
      push({
        kind: conConflicto ? 'error' : 'success',
        title: conConflicto ? 'Ocupacion creada con conflicto' : 'Ocupacion de OT creada',
        body: r.mensaje ?? undefined,
        ttl: conConflicto ? 7000 : 4000,
      })
      onClose()
    } catch (e) {
      push({ kind: 'error', title: 'No se pudo crear', body: (e as Error).message })
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Planificar orden de trabajo"
      width={620}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cerrar</Button>
          <Button variant="accent" onClick={submit}>Crear ocupacion</Button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {/* Paso 1: la OT. Es el punto de partida de este modal. */}
        <div>
          <label style={lbl}>Orden de trabajo</label>
          <OTSearch onSelect={(ot) => setOtSel(ot)} />
        </div>

        {/* Panel del reclamo asociado: contexto de lo que se planifica. */}
        {otSel && (
          <div style={{
            display: 'flex', gap: 10, padding: '12px 14px',
            background: 'var(--surface-200)', borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--border-primary)',
          }}>
            <ClipboardList size={18} strokeWidth={1.5} style={{ color: 'var(--zaris-orange)', flexShrink: 0, marginTop: 2 }} />
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 13, color: 'var(--fg-1)', fontFamily: 'var(--font-display)', fontWeight: 500 }}>
                {otSel.nro_ot ?? `OT #${otSel.id_ot}`}
                {otSel.estado_nombre && <span style={{ color: 'var(--fg-3)', fontWeight: 400 }}> · {otSel.estado_nombre}</span>}
              </div>
              <div style={{ fontSize: 12, color: 'var(--fg-2)', fontFamily: 'var(--font-display)', marginTop: 2 }}>
                Reclamo: <strong>{otSel.nro_reclamo ?? '(sin reclamo asociado)'}</strong>
              </div>
              {otSel.reclamo_descripcion && (
                <div style={{ fontSize: 12, color: 'var(--fg-3)', marginTop: 2 }}>
                  {otSel.reclamo_descripcion}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Paso 2: recurso + horario. */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <Field label="Tipo de recurso">
            <select value={form.tipo_recurso} onChange={(e) => update('tipo_recurso', e.target.value as TipoRecurso)} style={inp}>
              <option value="agente">agente</option>
              <option value="equipo">equipo</option>
            </select>
          </Field>
          <Field label={form.tipo_recurso === 'agente' ? 'Agente' : 'Equipo'}>
            <RecursoPicker
              tipo={form.tipo_recurso as 'agente' | 'equipo'}
              value={form.id_recurso || null}
              onChange={(id) => update('id_recurso', id ?? 0)}
              idMunicipio={form.id_municipio}
            />
          </Field>
          <Field label="Fecha">
            <input type="date" value={form.fecha} onChange={(e) => update('fecha', e.target.value)} style={inp} />
          </Field>
          <div />
          <Field label="Hora inicio">
            <input type="time" value={form.hora_inicio} onChange={(e) => update('hora_inicio', e.target.value)} style={inp} />
          </Field>
          <Field label="Hora fin">
            <input type="time" value={form.hora_fin} onChange={(e) => update('hora_fin', e.target.value)} style={inp} />
          </Field>
        </div>
      </div>
    </Modal>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label style={lbl}>{label}</label>
      {children}
    </div>
  )
}

const inp: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: 'var(--size-ui)', color: 'var(--fg-1)',
  padding: '8px 10px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-primary)',
  background: 'var(--surface-100)', outline: 'none', width: '100%',
}

const lbl: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: 11, color: 'var(--fg-3)',
  textTransform: 'uppercase', letterSpacing: '.04em', marginBottom: 4, display: 'block',
}
