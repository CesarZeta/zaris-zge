// Modales de acciones sobre un evento, compartidos por Tablero y Detalle.
// ConfirmModal explicito (no window.confirm) segun CLAUDE.md s29.
import { useState } from 'react'
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
  return (
    <Modal
      open={open}
      onClose={onCancel}
      title={titulo}
      width={460}
      footer={
        <>
          <Button variant="ghost" onClick={onCancel}>Cancelar</Button>
          <Button variant="accent" disabled={busy} onClick={() => { onConfirm(obs.trim() || undefined); setObs('') }}>
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
            onClick={() => { onConfirm(idOrg as number, obs.trim() || undefined); setObs('') }}
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
