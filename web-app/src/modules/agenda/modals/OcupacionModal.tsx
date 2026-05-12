import { useEffect, useState } from 'react'
import { Modal } from '../components/Modal'
import { ConfirmModal } from '../components/ConfirmModal'
import { Button } from '../../../ui'
import { CiudadanoSearch } from '../components/CiudadanoSearch'
import { OTSearch } from '../components/OTSearch'
import { EventoSearch } from '../components/EventoSearch'
import { RecursoPicker } from '../components/RecursoPicker'
import { useCrearOcupacion, useEliminarOcupacion } from '../hooks/useOcupaciones'
import { useNotificationsStore } from '../../../stores/notifications'
import type { CiudadanoMinimo, EventoBusquedaItem, Ocupacion, OcupacionCreatePayload, OTBusquedaItem, TipoOcupacion, TipoRecurso } from '../types/agenda'

interface Props {
  open: boolean
  onClose: () => void
  // Modo creacion: defaults pre-cargados
  defaults?: Partial<OcupacionCreatePayload>
  // Modo lectura/borrar: ocupacion existente
  ocupacion?: Ocupacion | null
}

function emptyOcup(d?: Partial<OcupacionCreatePayload>): OcupacionCreatePayload {
  return {
    tipo: d?.tipo ?? 'turno',
    tipo_recurso: d?.tipo_recurso ?? 'agente',
    id_recurso: d?.id_recurso ?? 1,
    fecha: d?.fecha ?? new Date().toISOString().slice(0, 10),
    hora_inicio: d?.hora_inicio ?? '09:00',
    hora_fin: d?.hora_fin ?? '10:00',
    id_orden_trabajo: d?.id_orden_trabajo ?? null,
    id_evento: d?.id_evento ?? null,
    id_ciudadano: d?.id_ciudadano ?? null,
    duracion_aplicada_min: d?.duracion_aplicada_min ?? null,
    rol_en_evento: d?.rol_en_evento ?? null,
    motivo: d?.motivo ?? null,
    id_municipio: d?.id_municipio ?? 1,
  }
}

export function OcupacionModal({ open, onClose, defaults, ocupacion }: Props) {
  const push = useNotificationsStore((s) => s.push)
  const crear = useCrearOcupacion()
  const eliminar = useEliminarOcupacion()
  const [form, setForm] = useState<OcupacionCreatePayload>(() => emptyOcup(defaults))
  const [ciudadano, setCiudadano] = useState<CiudadanoMinimo | null>(null)
  const [otSel, setOtSel] = useState<OTBusquedaItem | null>(null)
  const [evSel, setEvSel] = useState<EventoBusquedaItem | null>(null)
  const [confirmDel, setConfirmDel] = useState(false)

  useEffect(() => {
    if (open) {
      setForm(emptyOcup(defaults))
      setCiudadano(null)
      setOtSel(null)
      setEvSel(null)
    }
  }, [open, defaults])

  function update<K extends keyof OcupacionCreatePayload>(k: K, v: OcupacionCreatePayload[K]) {
    setForm((f) => ({ ...f, [k]: v }))
  }

  async function submit() {
    // Limpiar FKs segun tipo
    const payload: OcupacionCreatePayload = { ...form }
    if (payload.tipo === 'ot')     { payload.id_evento = null; payload.id_ciudadano = null }
    if (payload.tipo === 'evento') { payload.id_orden_trabajo = null; payload.id_ciudadano = null }
    if (payload.tipo === 'turno')  { payload.id_orden_trabajo = null; payload.id_evento = null }
    if (payload.hora_fin <= payload.hora_inicio) {
      push({ kind: 'error', title: 'Horario invalido', body: 'hora_fin > hora_inicio' })
      return
    }
    try {
      const r = await crear.mutateAsync(payload)
      const conConflicto = (r.conflictos?.length ?? 0) > 0
      push({
        kind: conConflicto ? 'error' : 'success',
        title: conConflicto ? 'Ocupacion creada con conflicto' : 'Ocupacion creada',
        body: r.mensaje ?? undefined,
        ttl: conConflicto ? 7000 : 4000,
      })
      onClose()
    } catch (e) {
      push({ kind: 'error', title: 'No se pudo crear', body: (e as Error).message })
    }
  }

  async function doDelete() {
    if (!ocupacion) return
    setConfirmDel(false)
    try {
      await eliminar.mutateAsync(ocupacion.id_ocupacion)
      push({ kind: 'success', title: 'Ocupacion dada de baja' })
      onClose()
    } catch (e) {
      push({ kind: 'error', title: 'No se pudo eliminar', body: (e as Error).message })
    }
  }

  const titulo = ocupacion ? `Ocupacion #${ocupacion.id_ocupacion}` : 'Nueva ocupacion'

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={titulo}
      width={620}
      footer={
        <>
          {ocupacion && <Button variant="ghost" onClick={() => setConfirmDel(true)}>Eliminar</Button>}
          <Button variant="ghost" onClick={onClose}>Cerrar</Button>
          {!ocupacion && <Button variant="accent" onClick={submit}>Crear</Button>}
        </>
      }
    >
      {ocupacion ? (
        <ReadonlyOcupacion o={ocupacion} />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <Field label="Tipo">
            <select value={form.tipo} onChange={(e) => update('tipo', e.target.value as TipoOcupacion)} style={inp}>
              <option value="turno">turno</option>
              <option value="evento">evento</option>
              <option value="ot">ot (orden de trabajo)</option>
            </select>
          </Field>
          <Field label="Tipo de recurso">
            <select value={form.tipo_recurso} onChange={(e) => update('tipo_recurso', e.target.value as TipoRecurso)} style={inp}>
              <option value="agente">agente</option>
              <option value="equipo">equipo</option>
            </select>
          </Field>
          <Field label={form.tipo_recurso === 'agente' ? 'Agente' : 'Equipo'}>
            <RecursoPicker
              tipo={form.tipo_recurso}
              value={form.id_recurso || null}
              onChange={(id) => update('id_recurso', id ?? 0)}
              idMunicipio={form.id_municipio}
            />
          </Field>
          <Field label="Fecha">
            <input type="date" value={form.fecha} onChange={(e) => update('fecha', e.target.value)} style={inp} />
          </Field>
          <Field label="Hora inicio">
            <input type="time" value={form.hora_inicio} onChange={(e) => update('hora_inicio', e.target.value)} style={inp} />
          </Field>
          <Field label="Hora fin">
            <input type="time" value={form.hora_fin} onChange={(e) => update('hora_fin', e.target.value)} style={inp} />
          </Field>

          {form.tipo === 'ot' && (
            <div style={{ gridColumn: '1 / -1' }}>
              <label style={lbl}>Orden de trabajo</label>
              <OTSearch
                onSelect={(ot) => { setOtSel(ot); update('id_orden_trabajo', ot.id_ot) }}
              />
              {otSel && (
                <div style={{ marginTop: 6, fontSize: 13, color: 'var(--fg-2)' }}>
                  Seleccionado: <strong>{otSel.nro_ot ?? `OT #${otSel.id_ot}`}</strong>
                  {otSel.estado_nombre && <span style={{ color: 'var(--fg-3)' }}> · {otSel.estado_nombre}</span>}
                </div>
              )}
            </div>
          )}
          {form.tipo === 'evento' && (
            <div style={{ gridColumn: '1 / -1' }}>
              <label style={lbl}>Evento</label>
              <EventoSearch
                onSelect={(ev) => { setEvSel(ev); update('id_evento', ev.id_evento) }}
                idMunicipio={form.id_municipio}
              />
              {evSel && (
                <div style={{ marginTop: 6, fontSize: 13, color: 'var(--fg-2)' }}>
                  Seleccionado: <strong>{evSel.nombre}</strong>
                  <span style={{ color: 'var(--fg-3)' }}> · {evSel.fecha} {evSel.hora_inicio.slice(0, 5)}-{evSel.hora_fin.slice(0, 5)}</span>
                </div>
              )}
            </div>
          )}
          {form.tipo === 'turno' && (
            <>
              <div style={{ gridColumn: '1 / -1' }}>
                <label style={lbl}>Ciudadano</label>
                <CiudadanoSearch onSelect={(c) => { setCiudadano(c); update('id_ciudadano', c.id_ciudadano) }} />
                {ciudadano && (
                  <div style={{ marginTop: 6, fontSize: 13, color: 'var(--fg-2)' }}>
                    Seleccionado: <strong>{ciudadano.apellido}, {ciudadano.nombre}</strong>
                  </div>
                )}
              </div>
              <Field label="Motivo" full>
                <textarea value={form.motivo ?? ''} rows={2} onChange={(e) => update('motivo', e.target.value)} style={{ ...inp, resize: 'vertical' }} />
              </Field>
            </>
          )}
        </div>
      )}
      <ConfirmModal
        open={confirmDel}
        title="Dar de baja ocupacion"
        message="Dar de baja esta ocupacion? Se libera el slot del recurso en la grilla."
        confirmLabel="Dar de baja"
        danger
        onConfirm={doDelete}
        onCancel={() => setConfirmDel(false)}
      />
    </Modal>
  )
}

function Field({ label, children, full }: { label: string; children: React.ReactNode; full?: boolean }) {
  return (
    <div style={{ gridColumn: full ? '1 / -1' : undefined, display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label style={lbl}>{label}</label>
      {children}
    </div>
  )
}

function ReadonlyOcupacion({ o }: { o: Ocupacion }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <Row k="Tipo"  v={o.tipo} />
      <Row k="Recurso" v={`${o.tipo_recurso} #${o.id_recurso}`} />
      <Row k="Fecha" v={`${o.fecha} ${o.hora_inicio.slice(0, 5)} - ${o.hora_fin.slice(0, 5)}`} />
      {o.id_evento && <Row k="Evento" v={`#${o.id_evento}`} />}
      {o.id_orden_trabajo && <Row k="OT" v={`#${o.id_orden_trabajo}`} />}
      {o.id_ciudadano && <Row k="Ciudadano" v={`#${o.id_ciudadano}`} />}
      {o.descripcion_corta && <Row k="Descripcion" v={o.descripcion_corta} />}
      {o.motivo && <Row k="Motivo" v={o.motivo} />}
      {o.rol_en_evento && <Row k="Rol" v={o.rol_en_evento} />}
    </div>
  )
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'baseline' }}>
      <span style={{ width: 110, fontSize: 11, color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '.04em', fontFamily: 'var(--font-display)' }}>{k}</span>
      <span style={{ fontSize: 14, color: 'var(--fg-1)', fontFamily: 'var(--font-display)' }}>{v}</span>
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
