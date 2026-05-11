import { useEffect, useState } from 'react'
import { Modal } from '../components/Modal'
import { ConfirmModal } from '../components/ConfirmModal'
import { Button } from '../../../ui'
import { useNotificationsStore } from '../../../stores/notifications'
import { useEventoDetalle, useCrearEvento, useActualizarEvento, useCancelarEvento, useEliminarEvento } from '../hooks/useEventos'
import type { EventoCreatePayload, TipoQR } from '../types/agenda'
import { toIsoDate, hoy } from '../../../lib/dates'

interface Props {
  open: boolean
  onClose: () => void
  idEvento: number | null            // null = creacion
  defaultDate?: string
  onCreated?: (id: number) => void
}

const TIPOS_QR: TipoQR[] = ['ninguno', 'nominal', 'generico']

function emptyPayload(defaultDate?: string): EventoCreatePayload {
  return {
    nombre: '',
    descripcion: '',
    fecha: defaultDate ?? toIsoDate(hoy()),
    hora_inicio: '09:00',
    hora_fin: '10:00',
    capacidad_ciudadanos: 10,
    cantidad_encargados: 1,
    tipo_qr: 'ninguno',
    admite_autoservicio: false,
    id_municipio: 1,
  }
}

export function EventoModal({ open, onClose, idEvento, defaultDate, onCreated }: Props) {
  const push = useNotificationsStore((s) => s.push)
  const detalle = useEventoDetalle(open ? idEvento : null)
  const crear = useCrearEvento()
  const actualizar = useActualizarEvento(idEvento ?? 0)
  const cancelar = useCancelarEvento()
  const eliminar = useEliminarEvento()
  const [form, setForm] = useState<EventoCreatePayload>(() => emptyPayload(defaultDate))
  const [confirm, setConfirm] = useState<'cancelar' | 'eliminar' | null>(null)

  // Reset al abrir o al cambiar el evento editado; NO al cambiar defaultDate
  // (eso reiniciaba el form pisando lo que el usuario ya habia tipeado/marcado).
  useEffect(() => {
    if (!open) return
    if (!idEvento) {
      setForm(emptyPayload(defaultDate))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, idEvento])

  // Cuando llega el detalle del evento en edicion, hidratar el form una vez.
  useEffect(() => {
    if (!open || !idEvento || !detalle.data) return
    setForm({
      nombre: detalle.data.nombre,
      descripcion: detalle.data.descripcion ?? '',
      id_subarea: detalle.data.id_subarea,
      fecha: detalle.data.fecha,
      hora_inicio: detalle.data.hora_inicio.slice(0, 5),
      hora_fin: detalle.data.hora_fin.slice(0, 5),
      capacidad_ciudadanos: detalle.data.capacidad_ciudadanos,
      cantidad_encargados: detalle.data.cantidad_encargados,
      tipo_qr: detalle.data.tipo_qr,
      admite_autoservicio: detalle.data.admite_autoservicio,
      id_municipio: detalle.data.id_municipio,
    })
  }, [open, idEvento, detalle.data])

  function update<K extends keyof EventoCreatePayload>(k: K, v: EventoCreatePayload[K]) {
    setForm((f) => ({ ...f, [k]: v }))
  }

  async function submit() {
    if (form.hora_fin <= form.hora_inicio) {
      push({ kind: 'error', title: 'Horario invalido', body: 'hora_fin debe ser mayor que hora_inicio' })
      return
    }
    try {
      if (idEvento) {
        await actualizar.mutateAsync(form)
        push({ kind: 'success', title: 'Evento actualizado' })
      } else {
        const r = await crear.mutateAsync(form)
        push({ kind: 'success', title: 'Evento creado', body: `id=${r.id_evento}` })
        onCreated?.(r.id_evento)
      }
      onClose()
    } catch (e) {
      push({ kind: 'error', title: 'No se pudo guardar', body: (e as Error).message })
    }
  }

  async function doCancel() {
    if (!idEvento) return
    setConfirm(null)
    try {
      await cancelar.mutateAsync(idEvento)
      push({ kind: 'success', title: 'Evento cancelado' })
      onClose()
    } catch (e) {
      push({ kind: 'error', title: 'No se pudo cancelar', body: (e as Error).message })
    }
  }

  async function doDelete() {
    if (!idEvento) return
    setConfirm(null)
    try {
      await eliminar.mutateAsync(idEvento)
      push({ kind: 'success', title: 'Evento dado de baja' })
      onClose()
    } catch (e) {
      push({ kind: 'error', title: 'No se pudo eliminar', body: (e as Error).message })
    }
  }

  const titulo = idEvento ? `Evento #${idEvento}` : 'Nuevo evento'

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={titulo}
      width={620}
      footer={
        <>
          {idEvento != null && (
            <>
              <Button variant="ghost" onClick={() => setConfirm('eliminar')}>Eliminar</Button>
              <Button variant="ghost" onClick={() => setConfirm('cancelar')}>Cancelar evento</Button>
            </>
          )}
          <Button variant="ghost" onClick={onClose}>Cerrar</Button>
          <Button variant="accent" onClick={submit}>{idEvento ? 'Guardar' : 'Crear'}</Button>
        </>
      }
    >
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Field label="Nombre" full>
          <input type="text" value={form.nombre} onChange={(e) => update('nombre', e.target.value)} style={inp} />
        </Field>
        <Field label="Descripcion" full>
          <textarea value={form.descripcion ?? ''} onChange={(e) => update('descripcion', e.target.value)} rows={2} style={{ ...inp, resize: 'vertical' }} />
        </Field>
        <Field label="Fecha"><input type="date" value={form.fecha} onChange={(e) => update('fecha', e.target.value)} style={inp} /></Field>
        <Field label="ID Subarea (opcional)"><input type="number" value={form.id_subarea ?? ''} onChange={(e) => update('id_subarea', e.target.value ? Number(e.target.value) : null)} style={inp} /></Field>
        <Field label="Hora inicio"><input type="time" value={form.hora_inicio} onChange={(e) => update('hora_inicio', e.target.value)} style={inp} /></Field>
        <Field label="Hora fin"><input type="time" value={form.hora_fin} onChange={(e) => update('hora_fin', e.target.value)} style={inp} /></Field>
        <Field label="Capacidad ciudadanos"><input type="number" min={0} value={form.capacidad_ciudadanos} onChange={(e) => update('capacidad_ciudadanos', Number(e.target.value))} style={inp} /></Field>
        <Field label="Cantidad encargados"><input type="number" min={0} value={form.cantidad_encargados} onChange={(e) => update('cantidad_encargados', Number(e.target.value))} style={inp} /></Field>
        <Field label="Tipo QR">
          <select value={form.tipo_qr} onChange={(e) => update('tipo_qr', e.target.value as TipoQR)} style={inp}>
            {TIPOS_QR.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </Field>
        <Field label="Autoservicio">
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <input type="checkbox" checked={form.admite_autoservicio} onChange={(e) => update('admite_autoservicio', e.target.checked)} />
            <span style={{ fontSize: 13 }}>permite reservas publicas</span>
          </label>
        </Field>
      </div>
      {idEvento && detalle.data && (
        <div style={{ marginTop: 16, padding: 12, background: 'var(--surface-200)', borderRadius: 'var(--radius-md)' }}>
          <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', fontSize: 12, fontFamily: 'var(--font-mono)' }}>
            <span>estado: {detalle.data.estado_codigo}</span>
            <span>cupo disponible: {detalle.data.cupo_disponible}</span>
            <span>reservas activas: {detalle.data.reservas_activas}</span>
            <span>encargados: {detalle.data.encargados.length}</span>
          </div>
        </div>
      )}
      <ConfirmModal
        open={confirm === 'cancelar'}
        title="Cancelar evento"
        message="Cancelar este evento? No cancela reservas automaticamente — el operador debe revisarlas manualmente."
        confirmLabel="Cancelar evento"
        danger
        onConfirm={doCancel}
        onCancel={() => setConfirm(null)}
      />
      <ConfirmModal
        open={confirm === 'eliminar'}
        title="Eliminar evento"
        message="Baja logica del evento? Se podra reactivar manualmente desde la base."
        confirmLabel="Eliminar"
        danger
        onConfirm={doDelete}
        onCancel={() => setConfirm(null)}
      />
    </Modal>
  )
}

function Field({ label, children, full }: { label: string; children: React.ReactNode; full?: boolean }) {
  return (
    <div style={{ gridColumn: full ? '1 / -1' : undefined, display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label style={{ fontFamily: 'var(--font-display)', fontSize: 11, color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '.04em' }}>{label}</label>
      {children}
    </div>
  )
}

const inp: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: 'var(--size-ui)', color: 'var(--fg-1)',
  padding: '8px 10px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-primary)',
  background: 'var(--surface-100)', outline: 'none', width: '100%',
}
