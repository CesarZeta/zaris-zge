import { useEffect, useState } from 'react'
import { Modal } from '../../agenda/components/Modal'
import { CiudadanoSearch } from '../../agenda/components/CiudadanoSearch'
import { Button } from '../../../ui'
import { useNotificationsStore } from '../../../stores/notifications'
import { useAgentesActivos, useCrearTurno, useReprogramarTurno, useTiposServicio } from '../hooks/useTurnos'
import type { CiudadanoMinimo } from '../../agenda/types/agenda'
import type { Turno } from '../types/turno'

interface Props {
  open: boolean
  onClose: () => void
  /** Si viene, el modal reprograma ese turno en lugar de crear uno nuevo. */
  turno?: Turno | null
}

const HOY = () => new Date().toISOString().slice(0, 10)

export function TurnoFormModal({ open, onClose, turno }: Props) {
  const push = useNotificationsStore((s) => s.push)
  const esEdicion = turno != null
  const tipos = useTiposServicio()
  const agentes = useAgentesActivos()
  const crear = useCrearTurno()
  const reprogramar = useReprogramarTurno()

  const [cid, setCid] = useState<CiudadanoMinimo | null>(null)
  const [idAgente, setIdAgente] = useState<number | ''>('')
  const [idTipo, setIdTipo] = useState<number | ''>('')
  const [fecha, setFecha] = useState(HOY())
  const [horaInicio, setHoraInicio] = useState('09:00')
  const [observaciones, setObservaciones] = useState('')

  // Reset / hidratacion al abrir. Separado del resto de deps para no pisar
  // lo que el usuario tipea (patron CLAUDE.md §29).
  useEffect(() => {
    if (!open) return
    if (turno) {
      setCid(null)
      setIdAgente(turno.id_agente)
      setIdTipo(turno.id_tipo_servicio_turno)
      setFecha(turno.fecha)
      setHoraInicio(turno.hora_inicio.slice(0, 5))
      setObservaciones(turno.observaciones ?? '')
    } else {
      setCid(null)
      setIdAgente('')
      setIdTipo('')
      setFecha(HOY())
      setHoraInicio('09:00')
      setObservaciones('')
    }
  }, [open, turno])

  const tipoSel = tipos.data?.find((t) => t.id_tipo_servicio_turno === idTipo)

  async function onSubmit() {
    if (!esEdicion && !cid) {
      push({ kind: 'error', title: 'Elegí un ciudadano' })
      return
    }
    if (idAgente === '' || idTipo === '') {
      push({ kind: 'error', title: 'Completá agente y tipo de servicio' })
      return
    }
    try {
      if (esEdicion && turno) {
        await reprogramar.mutateAsync({
          id_turno: turno.id_turno,
          body: {
            id_tipo_servicio_turno: idTipo,
            fecha,
            hora_inicio: `${horaInicio}:00`,
            observaciones: observaciones.trim() || null,
          },
        })
        push({ kind: 'success', title: 'Turno reprogramado' })
      } else {
        await crear.mutateAsync({
          id_ciudadano: cid!.id_ciudadano,
          id_agente: idAgente,
          id_tipo_servicio_turno: idTipo,
          fecha,
          hora_inicio: `${horaInicio}:00`,
          observaciones: observaciones.trim() || null,
        })
        push({ kind: 'success', title: 'Turno reservado' })
      }
      onClose()
    } catch (e) {
      push({ kind: 'error', title: esEdicion ? 'No se pudo reprogramar' : 'No se pudo reservar', body: (e as Error).message })
    }
  }

  const pending = crear.isPending || reprogramar.isPending

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={esEdicion ? `Reprogramar turno #${turno?.id_turno}` : 'Nuevo turno'}
      width={560}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button variant="accent" onClick={onSubmit} disabled={pending}>
            {esEdicion ? 'Guardar cambios' : 'Reservar turno'}
          </Button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {/* Ciudadano */}
        <div>
          <label style={lbl}>Ciudadano</label>
          {esEdicion ? (
            <div style={{ ...readonlyBox }}>
              {turno?.ciudadano_nombre ?? '—'}
              {turno?.ciudadano_dni && <span style={{ color: 'var(--fg-3)' }}> · DNI {turno.ciudadano_dni}</span>}
              <span style={{ color: 'var(--fg-3)', fontSize: 11, marginLeft: 6 }}>(no editable)</span>
            </div>
          ) : (
            <>
              <CiudadanoSearch onSelect={(c) => setCid(c)} />
              {cid && (
                <div style={{ marginTop: 6, fontSize: 13, color: 'var(--fg-2)' }}>
                  Seleccionado: <strong>{cid.apellido}, {cid.nombre}</strong>
                  {cid.doc_nro && <span style={{ color: 'var(--fg-3)' }}> · DNI {cid.doc_nro}</span>}
                </div>
              )}
            </>
          )}
        </div>

        {/* Agente */}
        <div>
          <label style={lbl}>Agente</label>
          <select
            value={idAgente}
            onChange={(e) => setIdAgente(e.target.value === '' ? '' : Number(e.target.value))}
            disabled={esEdicion}
            style={inp}
          >
            <option value="">Elegí un agente…</option>
            {(agentes.data ?? []).filter((a) => a.activo !== false).map((a) => (
              <option key={a.id_agente} value={a.id_agente}>
                {a.apellido}, {a.nombre}
              </option>
            ))}
          </select>
          {esEdicion && <div style={hint}>El agente no se puede cambiar al reprogramar.</div>}
        </div>

        {/* Tipo de servicio */}
        <div>
          <label style={lbl}>Tipo de servicio</label>
          <select
            value={idTipo}
            onChange={(e) => setIdTipo(e.target.value === '' ? '' : Number(e.target.value))}
            style={inp}
          >
            <option value="">Elegí un tipo…</option>
            {(tipos.data ?? []).map((t) => (
              <option key={t.id_tipo_servicio_turno} value={t.id_tipo_servicio_turno}>
                {t.nombre} ({t.duracion_min} min)
              </option>
            ))}
          </select>
          {tipoSel && (
            <div style={hint}>
              Duración estimada: {tipoSel.duracion_min} min. La hora de fin se calcula automáticamente.
            </div>
          )}
        </div>

        {/* Fecha + hora */}
        <div style={{ display: 'flex', gap: 12 }}>
          <div style={{ flex: 1 }}>
            <label style={lbl}>Fecha</label>
            <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} style={inp} />
          </div>
          <div style={{ flex: 1 }}>
            <label style={lbl}>Hora de inicio</label>
            <input type="time" value={horaInicio} onChange={(e) => setHoraInicio(e.target.value)} style={inp} />
          </div>
        </div>

        {/* Observaciones */}
        <div>
          <label style={lbl}>Observaciones (opcional)</label>
          <textarea
            value={observaciones}
            onChange={(e) => setObservaciones(e.target.value)}
            rows={2}
            style={{ ...inp, resize: 'vertical', fontFamily: 'var(--font-display)' }}
          />
        </div>
      </div>
    </Modal>
  )
}

const lbl: React.CSSProperties = {
  display: 'block', fontSize: 12, fontWeight: 500, color: 'var(--fg-2)', marginBottom: 4,
}

const inp: React.CSSProperties = {
  width: '100%', fontFamily: 'var(--font-display)', fontSize: 13,
  padding: '7px 10px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-primary)',
  background: 'var(--surface-100)', outline: 'none', boxSizing: 'border-box',
}

const readonlyBox: React.CSSProperties = {
  fontSize: 13, color: 'var(--fg-2)', padding: '7px 10px',
  background: 'var(--surface-200)', borderRadius: 'var(--radius-md)',
}

const hint: React.CSSProperties = {
  fontSize: 11, color: 'var(--fg-3)', marginTop: 4,
}
