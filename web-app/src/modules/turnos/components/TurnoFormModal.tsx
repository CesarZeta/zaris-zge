import { useEffect, useState } from 'react'
import { Modal } from '../../agenda/components/Modal'
import { CiudadanoSearch } from '../../agenda/components/CiudadanoSearch'
import { RecursoPicker } from '../../agenda/components/RecursoPicker'
import { Button } from '../../../ui'
import { useNotificationsStore } from '../../../stores/notifications'
import { useCrearTurno, useReprogramarTurno, useTiposServicio } from '../hooks/useTurnos'
import { useEspacios } from '../../agenda/hooks/useEspacios'
import type { CiudadanoMinimo } from '../../agenda/types/agenda'
import type { Turno } from '../types/turno'

type TipoRecurso = 'agente' | 'espacio'

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
  const crear = useCrearTurno()
  const reprogramar = useReprogramarTurno()

  const [cid, setCid] = useState<CiudadanoMinimo | null>(null)
  const [tipoRecurso, setTipoRecurso] = useState<TipoRecurso>('agente')
  const [idAgente, setIdAgente] = useState<number | ''>('')
  const [idEspacio, setIdEspacio] = useState<number | ''>('')
  const [idTipo, setIdTipo] = useState<number | ''>('')
  const [fecha, setFecha] = useState(HOY())
  const [horaInicio, setHoraInicio] = useState('09:00')
  const [observaciones, setObservaciones] = useState('')

  const espacios = useEspacios({ atendido: true })

  // Reset / hidratacion al abrir. Separado del resto de deps para no pisar
  // lo que el usuario tipea (patron CLAUDE.md §29).
  useEffect(() => {
    if (!open) return
    if (turno) {
      setCid(null)
      setTipoRecurso(turno.id_espacio != null ? 'espacio' : 'agente')
      setIdAgente(turno.id_agente ?? '')
      setIdEspacio(turno.id_espacio ?? '')
      setIdTipo(turno.id_tipo_servicio_turno)
      setFecha(turno.fecha)
      setHoraInicio(turno.hora_inicio.slice(0, 5))
      setObservaciones(turno.observaciones ?? '')
    } else {
      setCid(null)
      setTipoRecurso('agente')
      setIdAgente('')
      setIdEspacio('')
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
    if (idTipo === '') {
      push({ kind: 'error', title: 'Elegí un tipo de servicio' })
      return
    }
    if (!esEdicion) {
      if (tipoRecurso === 'agente' && idAgente === '') {
        push({ kind: 'error', title: 'Elegí un agente' }); return
      }
      if (tipoRecurso === 'espacio' && idEspacio === '') {
        push({ kind: 'error', title: 'Elegí un lugar de atención' }); return
      }
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
          ...(tipoRecurso === 'espacio'
            ? { id_espacio: idEspacio as number }
            : { id_agente: idAgente as number }),
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

        {/* Recurso: agente o lugar de atencion */}
        <div>
          <label style={lbl}>Atiende</label>
          {esEdicion ? (
            <>
              <div style={{ ...inp, background: 'var(--surface-200)', color: 'var(--fg-2)', display: 'flex', alignItems: 'center' }}>
                {turno?.recurso_nombre ?? turno?.agente_nombre ?? '—'}
                <span style={{ color: 'var(--fg-3)', fontSize: 11, marginLeft: 6 }}>
                  ({turno?.id_espacio != null ? 'lugar' : 'agente'})
                </span>
              </div>
              <div style={hint}>El recurso no se puede cambiar al reprogramar.</div>
            </>
          ) : (
            <>
              <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
                <button type="button" onClick={() => { setTipoRecurso('agente'); setIdEspacio('') }} style={toggleBtn(tipoRecurso === 'agente')}>
                  Agente
                </button>
                <button type="button" onClick={() => { setTipoRecurso('espacio'); setIdAgente('') }} style={toggleBtn(tipoRecurso === 'espacio')}>
                  Lugar de atención
                </button>
              </div>
              {tipoRecurso === 'agente' ? (
                <RecursoPicker
                  tipo="agente"
                  value={idAgente === '' ? null : idAgente}
                  onChange={(id) => setIdAgente(id ?? '')}
                />
              ) : (
                <select
                  value={idEspacio}
                  onChange={(e) => setIdEspacio(e.target.value === '' ? '' : Number(e.target.value))}
                  style={inp}
                >
                  <option value="">Elegí un lugar atendido…</option>
                  {(espacios.data ?? []).map((e) => (
                    <option key={e.id_espacio} value={e.id_espacio}>{e.nombre}</option>
                  ))}
                </select>
              )}
              {tipoRecurso === 'espacio' && (espacios.data ?? []).length === 0 && !espacios.isLoading && (
                <div style={hint}>No hay lugares de atención atendidos cargados. Crealos en Agenda → Config → Espacios.</div>
              )}
            </>
          )}
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

function toggleBtn(active: boolean): React.CSSProperties {
  return {
    flex: 1, fontFamily: 'var(--font-display)', fontSize: 12, cursor: 'pointer',
    padding: '7px 10px', borderRadius: 'var(--radius-md)', fontWeight: 500,
    border: '1px solid ' + (active ? 'var(--zaris-orange)' : 'var(--border-medium)'),
    background: active ? 'var(--zaris-orange)' : 'transparent',
    color: active ? 'white' : 'var(--fg-2)',
  }
}
