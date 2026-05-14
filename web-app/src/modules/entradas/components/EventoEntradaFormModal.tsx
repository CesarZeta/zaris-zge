import { useEffect, useState } from 'react'
import { Modal } from '../../agenda/components/Modal'
import { Button } from '../../../ui'
import { useNotificationsStore } from '../../../stores/notifications'
import { useEspacios } from '../../agenda/hooks/useEspacios'
import { useCrearEventoEntrada } from '../hooks/useEntradas'
import type { TipoQR } from '../../agenda/types/agenda'

interface Props {
  open: boolean
  onClose: () => void
}

const HOY = () => new Date().toISOString().slice(0, 10)

export function EventoEntradaFormModal({ open, onClose }: Props) {
  const push = useNotificationsStore((s) => s.push)
  const espacios = useEspacios()
  const crear = useCrearEventoEntrada()

  const [nombre, setNombre] = useState('')
  const [descripcion, setDescripcion] = useState('')
  const [idEspacio, setIdEspacio] = useState<number | ''>('')
  const [fecha, setFecha] = useState(HOY())
  const [horaInicio, setHoraInicio] = useState('18:00')
  const [horaFin, setHoraFin] = useState('20:00')
  const [capacidad, setCapacidad] = useState(50)
  const [tipoQr, setTipoQr] = useState<TipoQR>('nominal')
  const [admiteAutoservicio, setAdmiteAutoservicio] = useState(true)

  useEffect(() => {
    if (!open) return
    setNombre('')
    setDescripcion('')
    setIdEspacio('')
    setFecha(HOY())
    setHoraInicio('18:00')
    setHoraFin('20:00')
    setCapacidad(50)
    setTipoQr('nominal')
    setAdmiteAutoservicio(true)
  }, [open])

  async function onSubmit() {
    if (!nombre.trim()) {
      push({ kind: 'error', title: 'Poné un nombre al evento' })
      return
    }
    if (idEspacio === '') {
      push({ kind: 'error', title: 'Elegí un espacio' })
      return
    }
    if (horaFin <= horaInicio) {
      push({ kind: 'error', title: 'La hora de fin debe ser mayor que la de inicio' })
      return
    }
    try {
      await crear.mutateAsync({
        nombre: nombre.trim(),
        descripcion: descripcion.trim() || null,
        id_espacio: idEspacio,
        fecha,
        hora_inicio: `${horaInicio}:00`,
        hora_fin: `${horaFin}:00`,
        capacidad_ciudadanos: capacidad,
        cantidad_encargados: 0,
        tipo_qr: tipoQr,
        admite_autoservicio: admiteAutoservicio,
      })
      push({ kind: 'success', title: 'Evento con entradas creado' })
      onClose()
    } catch (e) {
      push({ kind: 'error', title: 'No se pudo crear el evento', body: (e as Error).message })
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Nuevo evento con entradas"
      width={560}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button variant="accent" onClick={onSubmit} disabled={crear.isPending}>Crear evento</Button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div>
          <label style={lbl}>Nombre del evento</label>
          <input value={nombre} onChange={(e) => setNombre(e.target.value)} style={inp} placeholder="Ej: Concierto en la plaza" />
        </div>

        <div>
          <label style={lbl}>Descripción (opcional)</label>
          <textarea
            value={descripcion}
            onChange={(e) => setDescripcion(e.target.value)}
            rows={2}
            style={{ ...inp, resize: 'vertical', fontFamily: 'var(--font-display)' }}
          />
        </div>

        <div>
          <label style={lbl}>Espacio</label>
          <select value={idEspacio} onChange={(e) => setIdEspacio(e.target.value === '' ? '' : Number(e.target.value))} style={inp}>
            <option value="">Elegí un espacio…</option>
            {(espacios.data ?? []).map((es) => (
              <option key={es.id_espacio} value={es.id_espacio}>
                {es.nombre}{es.capacidad_personas != null ? ` (cap. ${es.capacidad_personas})` : ''}
              </option>
            ))}
          </select>
          <div style={hint}>El evento ocupa este espacio físico en la agenda.</div>
        </div>

        <div style={{ display: 'flex', gap: 12 }}>
          <div style={{ flex: 1 }}>
            <label style={lbl}>Fecha</label>
            <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} style={inp} />
          </div>
          <div style={{ flex: 1 }}>
            <label style={lbl}>Hora inicio</label>
            <input type="time" value={horaInicio} onChange={(e) => setHoraInicio(e.target.value)} style={inp} />
          </div>
          <div style={{ flex: 1 }}>
            <label style={lbl}>Hora fin</label>
            <input type="time" value={horaFin} onChange={(e) => setHoraFin(e.target.value)} style={inp} />
          </div>
        </div>

        <div style={{ display: 'flex', gap: 12 }}>
          <div style={{ flex: 1 }}>
            <label style={lbl}>Capacidad (entradas)</label>
            <input
              type="number"
              min={0}
              value={capacidad}
              onChange={(e) => setCapacidad(Math.max(0, Number(e.target.value) || 0))}
              style={inp}
            />
          </div>
          <div style={{ flex: 1 }}>
            <label style={lbl}>Tipo de QR</label>
            <select value={tipoQr} onChange={(e) => setTipoQr(e.target.value as TipoQR)} style={inp}>
              <option value="nominal">Nominal</option>
              <option value="generico">Genérico</option>
              <option value="ninguno">Ninguno</option>
            </select>
          </div>
        </div>

        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--fg-2)', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={admiteAutoservicio}
            onChange={(e) => setAdmiteAutoservicio(e.target.checked)}
          />
          Permitir que el ciudadano reserve su entrada por autoservicio (link público)
        </label>
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

const hint: React.CSSProperties = {
  fontSize: 11, color: 'var(--fg-3)', marginTop: 4,
}
