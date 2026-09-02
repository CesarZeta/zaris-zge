import { useEffect, useState } from 'react'
import { Modal } from '../../agenda/components/Modal'
import { RecursoPicker } from '../../agenda/components/RecursoPicker'
import { EntitySelect } from '../../tramites/components/EntitySelect'
import { Button } from '../../../ui'
import { useNotificationsStore } from '../../../stores/notifications'
import { useEspacios } from '../../agenda/hooks/useEspacios'
import { useCrearPrestacion, useEditarPrestacion } from '../hooks/useTurnos'
import type { ClasePrestacion, TipoPrestacion, TipoRecurso } from '../types/turno'

interface Props {
  open: boolean
  onClose: () => void
  /** Si viene, el modal edita esa prestación en lugar de crear una nueva. */
  prestacion?: TipoPrestacion | null
}

export function PrestacionFormModal({ open, onClose, prestacion }: Props) {
  const push = useNotificationsStore((s) => s.push)
  const esEdicion = prestacion != null
  const crear = useCrearPrestacion()
  const editar = useEditarPrestacion()
  const espacios = useEspacios({})

  const [nombre, setNombre] = useState('')
  const [descripcion, setDescripcion] = useState('')
  const [clase, setClase] = useState<ClasePrestacion>('atencion')
  const [duracionMin, setDuracionMin] = useState(30)
  const [tipoRecurso, setTipoRecurso] = useState<TipoRecurso>('agente')
  const [idAgente, setIdAgente] = useState<number | ''>('')
  const [idEspacio, setIdEspacio] = useState<number | ''>('')
  const [idUbicacion, setIdUbicacion] = useState<number | ''>('')
  const [registraAtencion, setRegistraAtencion] = useState(false)
  const [idSubarea, setIdSubarea] = useState<number | null>(null)
  const [subareaActual, setSubareaActual] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    if (prestacion) {
      setNombre(prestacion.nombre)
      setDescripcion(prestacion.descripcion ?? '')
      setClase(prestacion.clase)
      setDuracionMin(prestacion.duracion_min)
      setTipoRecurso(prestacion.tipo_recurso ?? 'agente')
      setIdAgente(prestacion.id_agente ?? '')
      setIdEspacio(prestacion.id_espacio ?? '')
      setIdUbicacion(prestacion.id_espacio_ubicacion ?? '')
      setRegistraAtencion(prestacion.registra_atencion ?? false)
      setIdSubarea(prestacion.id_subarea ?? null)
      setSubareaActual(prestacion.subarea_nombre
        ? `${prestacion.subarea_nombre}${prestacion.area_nombre ? ` (${prestacion.area_nombre})` : ''}`
        : null)
    } else {
      setNombre('')
      setDescripcion('')
      setClase('atencion')
      setDuracionMin(30)
      setTipoRecurso('agente')
      setIdAgente('')
      setIdEspacio('')
      setIdUbicacion('')
      setRegistraAtencion(false)
      setIdSubarea(null)
      setSubareaActual(null)
    }
  }, [open, prestacion])

  // 'reserva_espacio' fuerza recurso = espacio (y no registra atencion).
  function cambiarClase(c: ClasePrestacion) {
    setClase(c)
    if (c === 'reserva_espacio') {
      setTipoRecurso('espacio')
      setIdAgente('')
      setRegistraAtencion(false)
    }
  }

  async function onSubmit() {
    if (!nombre.trim()) {
      push({ kind: 'error', title: 'Ingresá un nombre' }); return
    }
    if (tipoRecurso === 'agente' && idAgente === '') {
      push({ kind: 'error', title: 'Elegí un agente' }); return
    }
    if (tipoRecurso === 'espacio' && idEspacio === '') {
      push({ kind: 'error', title: 'Elegí un lugar de atención' }); return
    }
    // Regla de negocio (2026-09-01): toda prestación declara dónde se atiende.
    if (tipoRecurso === 'agente' && idUbicacion === '') {
      push({ kind: 'error', title: 'Elegí la ubicación de atención', body: 'Toda prestación debe declarar dónde se atiende.' }); return
    }
    const body = {
      nombre: nombre.trim(),
      descripcion: descripcion.trim() || null,
      clase,
      duracion_min: duracionMin,
      tipo_recurso: tipoRecurso,
      id_agente: tipoRecurso === 'agente' ? (idAgente as number) : null,
      id_espacio: tipoRecurso === 'espacio' ? (idEspacio as number) : null,
      // Ubicación (mig 103): para recurso=espacio el backend usa ese mismo
      // espacio; para recurso=agente va la elegida acá (o null = sin ubicación).
      id_espacio_ubicacion:
        tipoRecurso === 'agente' && idUbicacion !== '' ? (idUbicacion as number) : null,
      registra_atencion: clase === 'atencion' && registraAtencion,
      id_subarea: idSubarea,
    }
    try {
      if (esEdicion && prestacion) {
        await editar.mutateAsync({ id: prestacion.id_tipo_prestacion, body })
        push({ kind: 'success', title: 'Prestación actualizada' })
      } else {
        await crear.mutateAsync(body)
        push({ kind: 'success', title: 'Prestación creada' })
      }
      onClose()
    } catch (e) {
      push({ kind: 'error', title: esEdicion ? 'No se pudo actualizar' : 'No se pudo crear', body: (e as Error).message })
    }
  }

  const pending = crear.isPending || editar.isPending

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={esEdicion ? `Editar prestación #${prestacion?.id_tipo_prestacion}` : 'Nueva prestación'}
      width={560}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button variant="accent" onClick={onSubmit} disabled={pending}>
            {esEdicion ? 'Guardar cambios' : 'Crear prestación'}
          </Button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {/* Nombre */}
        <div>
          <label style={lbl}>Nombre</label>
          <input
            type="text"
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            placeholder="Ej. Atención médica - Odontología"
            style={inp}
          />
        </div>

        {/* Clase */}
        <div>
          <label style={lbl}>Tipo de prestación</label>
          <div style={{ display: 'flex', gap: 6 }}>
            <button type="button" onClick={() => cambiarClase('atencion')} style={toggleBtn(clase === 'atencion')}>
              Atención de personas
            </button>
            <button type="button" onClick={() => cambiarClase('reserva_espacio')} style={toggleBtn(clase === 'reserva_espacio')}>
              Reserva de un espacio
            </button>
          </div>
          <div style={hint}>
            {clase === 'atencion'
              ? 'Un ciudadano se atiende con un agente o en un lugar de atención.'
              : 'Se reserva el uso de un espacio físico (ej. salón). Siempre apunta a un lugar.'}
          </div>
        </div>

        {/* Recurso */}
        <div>
          <label style={lbl}>Atendido por</label>
          {clase === 'atencion' && (
            <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
              <button type="button" onClick={() => { setTipoRecurso('agente'); setIdEspacio('') }} style={toggleBtn(tipoRecurso === 'agente')}>
                Un agente
              </button>
              <button type="button" onClick={() => { setTipoRecurso('espacio'); setIdAgente('') }} style={toggleBtn(tipoRecurso === 'espacio')}>
                Un lugar de atención
              </button>
            </div>
          )}
          {tipoRecurso === 'agente' ? (
            <RecursoPicker
              tipo="agente"
              value={idAgente === '' ? null : idAgente}
              onChange={(id) => setIdAgente(id ?? '')}
            />
          ) : (
            <>
              <select
                value={idEspacio}
                onChange={(e) => setIdEspacio(e.target.value === '' ? '' : Number(e.target.value))}
                style={inp}
              >
                <option value="">Elegí un lugar…</option>
                {(espacios.data ?? []).map((e) => (
                  <option key={e.id_espacio} value={e.id_espacio}>
                    {e.nombre} {e.atendido ? '(atendido)' : '(sin atención)'}
                  </option>
                ))}
              </select>
              {(espacios.data ?? []).length === 0 && !espacios.isLoading && (
                <div style={hint}>No hay lugares cargados. Crealos en Agenda → Disponibilidad → Espacios.</div>
              )}
            </>
          )}
        </div>

        {/* Ubicación de atención (mig 103). Para recurso=espacio es ese mismo
            espacio (se muestra fijo); para recurso=agente se elige acá. */}
        <div>
          <label style={lbl}>Ubicación de atención</label>
          {tipoRecurso === 'espacio' ? (
            <div style={{ ...hint, marginTop: 0 }}>
              {idEspacio !== ''
                ? 'Es el mismo lugar de atención elegido arriba.'
                : 'Elegí el lugar de atención arriba: será también la ubicación.'}
            </div>
          ) : (
            <>
              <select
                value={idUbicacion}
                onChange={(e) => setIdUbicacion(e.target.value === '' ? '' : Number(e.target.value))}
                style={inp}
              >
                <option value="">Elegí la ubicación…</option>
                {(espacios.data ?? []).map((e) => (
                  <option key={e.id_espacio} value={e.id_espacio}>{e.nombre}</option>
                ))}
              </select>
              <div style={hint}>
                Edificio o sala donde se atiende esta prestación. Agrupa los turnos por
                ubicación y alimenta la pantalla de sala de espera.
              </div>
            </>
          )}
        </div>

        {/* Historia de atención (solo clase 'atencion') */}
        {clase === 'atencion' && (
          <div>
            <label style={{ display: 'flex', alignItems: 'flex-start', gap: 8, cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={registraAtencion}
                onChange={(e) => setRegistraAtencion(e.target.checked)}
                style={{ marginTop: 2, accentColor: 'var(--zaris-orange)' }}
              />
              <span>
                <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-1)' }}>
                  Registra historia de atención (ej. atención médica)
                </span>
                <span style={{ display: 'block', fontSize: 11, color: 'var(--fg-3)', marginTop: 2 }}>
                  Al cumplir cada turno se exige registrar la intervención realizada y las
                  recomendaciones, y quien atiende ve las atenciones anteriores del ciudadano.
                </span>
              </span>
            </label>
          </div>
        )}

        {/* Área de servicio (subárea de Maestros) */}
        <div>
          <label style={lbl}>Área de servicio (opcional)</label>
          <EntitySelect
            endpoint="/api/v1/buc/subareas/buscar"
            idField="id_subarea"
            labelField="nombre"
            value={idSubarea}
            onChange={(id) => { setIdSubarea(id); if (id == null) setSubareaActual(null) }}
            placeholder="Buscá la subárea que presta el servicio…"
          />
          <div style={hint}>
            {idSubarea != null && subareaActual
              ? `Actual: ${subareaActual}`
              : 'Agrupa la prestación por el área municipal que la presta (habilita el filtro "Área de servicio").'}
          </div>
        </div>

        {/* Duración */}
        <div>
          <label style={lbl}>Duración del turno (minutos)</label>
          <input
            type="number"
            min={5}
            step={5}
            value={duracionMin}
            onChange={(e) => setDuracionMin(Math.max(5, Number(e.target.value) || 0))}
            style={{ ...inp, maxWidth: 160 }}
          />
          <div style={hint}>Define el tamaño de cada slot que se ofrece al reservar.</div>
        </div>

        {/* Descripción */}
        <div>
          <label style={lbl}>Descripción (opcional)</label>
          <textarea
            value={descripcion}
            onChange={(e) => setDescripcion(e.target.value)}
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
const hint: React.CSSProperties = { fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }
function toggleBtn(active: boolean): React.CSSProperties {
  return {
    flex: 1, fontFamily: 'var(--font-display)', fontSize: 12, cursor: 'pointer',
    padding: '7px 10px', borderRadius: 'var(--radius-md)', fontWeight: 500,
    border: '1px solid ' + (active ? 'var(--zaris-orange)' : 'var(--border-medium)'),
    background: active ? 'var(--zaris-orange)' : 'transparent',
    color: active ? 'white' : 'var(--fg-2)',
  }
}
