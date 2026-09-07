// Modales de acciones sobre un evento, compartidos por Tablero y Detalle.
// ConfirmModal explicito (no window.confirm) segun CLAUDE.md s29.
import { useEffect, useState } from 'react'
import { Modal } from '../../agenda/components/Modal'
import { Button } from '../../../ui'
import { useOrganismosEmergencia } from '../hooks/useEmergencias'

const label: React.CSSProperties = {
  display: 'block', fontFamily: 'var(--font-display)', fontSize: 12,
  fontWeight: 600, color: 'var(--fg-2)', margin: '12px 0 4px',
}
const inputBase: React.CSSProperties = {
  width: '100%', boxSizing: 'border-box', padding: '8px 10px',
  border: '1px solid var(--border-medium)', borderRadius: 8,
  background: 'var(--surface-100)', color: 'var(--fg-1)',
  fontFamily: 'var(--font-display)', fontSize: 14,
}

export function CambiarEstadoModal({
  open, destino, titulo, onConfirm, onCancel, busy,
}: {
  open: boolean
  destino: string
  titulo: string
  busy?: boolean
  onConfirm: (observaciones?: string) => void
  onCancel: () => void
}) {
  const [obs, setObs] = useState('')
  // Modal montado con open=false: limpiar la observacion al abrir para no
  // arrastrar texto de un uso anterior (variante del patron s29).
  useEffect(() => { if (open) setObs('') }, [open])
  return (
    <Modal
      open={open}
      onClose={onCancel}
      title={titulo}
      width={460}
      footer={
        <>
          <Button variant="ghost" onClick={onCancel}>Cancelar</Button>
          <Button variant="accent" disabled={busy} onClick={() => onConfirm(obs.trim() || undefined)}>
            Confirmar {destino.replace(/_/g, ' ')}
          </Button>
        </>
      }
    >
      <label style={label}>Observaciones (opcional)</label>
      <textarea
        style={{ ...inputBase, minHeight: 70, resize: 'vertical' }}
        value={obs}
        onChange={(e) => setObs(e.target.value)}
        placeholder="Detalle del cambio de estado..."
      />
    </Modal>
  )
}

export function DerivarModal({
  open, onConfirm, onCancel, busy,
}: {
  open: boolean
  busy?: boolean
  onConfirm: (idOrganismo: number, observaciones?: string) => void
  onCancel: () => void
}) {
  const organismos = useOrganismosEmergencia()
  const [idOrg, setIdOrg] = useState<number | ''>('')
  const [obs, setObs] = useState('')
  useEffect(() => { if (open) { setIdOrg(''); setObs('') } }, [open])
  return (
    <Modal
      open={open}
      onClose={onCancel}
      title="Derivar a organismo"
      width={460}
      footer={
        <>
          <Button variant="ghost" onClick={onCancel}>Cancelar</Button>
          <Button
            variant="accent"
            disabled={busy || idOrg === ''}
            onClick={() => onConfirm(idOrg as number, obs.trim() || undefined)}
          >
            Derivar
          </Button>
        </>
      }
    >
      <label style={label}>Organismo de derivación</label>
      <select style={inputBase} value={idOrg} onChange={(e) => setIdOrg(e.target.value ? Number(e.target.value) : '')}>
        <option value="">Elegir organismo...</option>
        {(organismos.data ?? []).map((o) => (
          <option key={o.id_emergencia_organismo_derivacion} value={o.id_emergencia_organismo_derivacion}>
            {o.nombre}{o.telefono_contacto ? ` (${o.telefono_contacto})` : ''}{o.es_municipal ? ' · municipal' : ''}
          </option>
        ))}
      </select>
      <label style={label}>Observaciones (opcional)</label>
      <textarea
        style={{ ...inputBase, minHeight: 70, resize: 'vertical' }}
        value={obs}
        onChange={(e) => setObs(e.target.value)}
        placeholder="Motivo / detalle de la derivación..."
      />
    </Modal>
  )
}

export function CerrarModal({
  open, onConfirm, onCancel, busy, permiteResuelto, permiteDesestimado,
}: {
  open: boolean
  busy?: boolean
  permiteResuelto: boolean
  permiteDesestimado: boolean
  onConfirm: (body: { veracidad: string; terminal_positivo: boolean; observaciones_cierre?: string }) => void
  onCancel: () => void
}) {
  const [positivo, setPositivo] = useState(permiteResuelto)
  const [veracidad, setVeracidad] = useState('CONFIRMADA')
  const [obs, setObs] = useState('')
  // El modal vive montado con open=false: re-sincronizar el resultado default
  // al abrir, segun el estado del evento elegido. Sin esto el radio queda con
  // el valor del PRIMER mount y ofrece un cierre que el FSM va a rechazar
  // (cazado en QA navegador prod 2026-06-10: "Cerrar como DESESTIMADO" sobre
  // un evento EN_SITIO -> 422 del backend).
  useEffect(() => {
    if (open) { setPositivo(permiteResuelto); setVeracidad('CONFIRMADA'); setObs('') }
  }, [open, permiteResuelto])
  return (
    <Modal
      open={open}
      onClose={onCancel}
      title="Cerrar evento"
      width={480}
      footer={
        <>
          <Button variant="ghost" onClick={onCancel}>Cancelar</Button>
          <Button
            variant="accent"
            disabled={busy}
            onClick={() => onConfirm({ veracidad, terminal_positivo: positivo, observaciones_cierre: obs.trim() || undefined })}
          >
            {positivo ? 'Cerrar como RESUELTO' : 'Cerrar como DESESTIMADO'}
          </Button>
        </>
      }
    >
      <label style={label}>Resultado del cierre</label>
      <div style={{ display: 'flex', gap: 16 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 14, color: permiteResuelto ? 'var(--fg-1)' : 'var(--fg-3)' }}>
          <input type="radio" checked={positivo} disabled={!permiteResuelto} onChange={() => setPositivo(true)} />
          Resuelto
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 14, color: permiteDesestimado ? 'var(--fg-1)' : 'var(--fg-3)' }}>
          <input type="radio" checked={!positivo} disabled={!permiteDesestimado} onChange={() => setPositivo(false)} />
          Desestimado
        </label>
      </div>
      <label style={label}>Veracidad</label>
      <select style={inputBase} value={veracidad} onChange={(e) => setVeracidad(e.target.value)}>
        <option value="CONFIRMADA">Confirmada</option>
        <option value="FALSA_ALARMA">Falsa alarma</option>
        <option value="NO_VERIFICABLE">No verificable</option>
      </select>
      <label style={label}>Observaciones de cierre (opcional)</label>
      <textarea
        style={{ ...inputBase, minHeight: 70, resize: 'vertical' }}
        value={obs}
        onChange={(e) => setObs(e.target.value)}
        placeholder="Como se resolvio / por que se desestima..."
      />
    </Modal>
  )
}

/** Guardia (mig 106, F4): deriva al vecino a la Guardia de Salud SIN cambiar el
 *  estado del evento. El paciente por defecto es el denunciante (si tiene
 *  nombre); se puede indicar otro. Motivo obligatorio: es lo que lee la Guardia. */
export function DerivarGuardiaModal({
  open, onConfirm, onCancel, busy, pacienteDefault,
}: {
  open: boolean
  busy?: boolean
  /** Nombre del denunciante del evento (BUC o contacto eventual), si lo hay. */
  pacienteDefault: string | null
  onConfirm: (motivo: string, paciente_nombre?: string) => void
  onCancel: () => void
}) {
  const [motivo, setMotivo] = useState('')
  const [otro, setOtro] = useState(false)
  const [paciente, setPaciente] = useState('')
  useEffect(() => { if (open) { setMotivo(''); setOtro(false); setPaciente('') } }, [open])
  const pacienteFinal = otro || !pacienteDefault ? paciente.trim() : ''
  return (
    <Modal
      open={open}
      onClose={onCancel}
      title="Derivar a la Guardia"
      width={480}
      footer={
        <>
          <Button variant="ghost" onClick={onCancel}>Cancelar</Button>
          <Button
            variant="accent"
            disabled={busy || motivo.trim().length < 3}
            onClick={() => onConfirm(motivo.trim(), pacienteFinal || undefined)}
          >
            Derivar a la Guardia
          </Button>
        </>
      }
    >
      <p style={{ margin: '0 0 4px', fontSize: 13, color: 'var(--fg-2)', lineHeight: 1.5 }}>
        La Guardia de Salud recibe la derivación en su mesa y registra la atención. El evento no cambia de estado.
      </p>
      <label style={label}>Motivo de la derivación *</label>
      <textarea
        style={{ ...inputBase, minHeight: 80, resize: 'vertical' }}
        value={motivo}
        onChange={(e) => setMotivo(e.target.value)}
        placeholder="Qué tiene que saber la Guardia (lesión, síntomas, cómo llega)..."
      />
      <label style={label}>Paciente</label>
      {pacienteDefault && !otro ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 14, color: 'var(--fg-1)' }}>
          <span>{pacienteDefault} <span style={{ color: 'var(--fg-3)', fontSize: 12 }}>(denunciante del evento)</span></span>
          <button type="button" onClick={() => setOtro(true)} style={{ background: 'none', border: 'none', color: 'var(--zaris-orange)', cursor: 'pointer', fontFamily: 'inherit', fontSize: 12, fontWeight: 600 }}>
            Es otra persona
          </button>
        </div>
      ) : (
        <input
          style={inputBase}
          value={paciente}
          onChange={(e) => setPaciente(e.target.value.slice(0, 150))}
          placeholder="Nombre del paciente (opcional; la Guardia lo puede completar)"
        />
      )}
    </Modal>
  )
}
