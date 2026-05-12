import { useEffect, useState } from 'react'
import { Modal } from '../../agenda/components/Modal'
import { useNotificationsStore } from '../../../stores/notifications'
import { useCambiarEstadoOT } from '../hooks/useOT'
import type { EstadoOT, MesaAgenteRow } from '../types/ot'

interface Props {
  open: boolean
  ot: MesaAgenteRow | null
  onClose: () => void
  onSuccess?: () => void
}

const ESTADOS: EstadoOT[] = ['En gestión', 'En espera', 'Pendiente', 'Terminada']

export function CambiarEstadoOTModal({ open, ot, onClose, onSuccess }: Props) {
  const push = useNotificationsStore((s) => s.push)
  const mut = useCambiarEstadoOT()

  const [estadoNuevo, setEstadoNuevo] = useState<EstadoOT>('En gestión')
  const [obs, setObs] = useState('')

  useEffect(() => {
    if (open && ot) {
      // Sugerencia por defecto: si está En gestión, ofrecer En espera; sino, En gestión.
      setEstadoNuevo(ot.estado_nombre === 'En gestión' ? 'En espera' : 'En gestión')
      setObs('')
    }
  }, [open, ot])

  if (!ot) return null

  const subtitle = `${ot.nro_ot ?? ''} · ${ot.nro_reclamo ?? ''} — ${ot.tipo_nombre ?? ''}`
  const isTerminada = estadoNuevo === 'Terminada'

  async function confirmar() {
    if (!ot) return
    try {
      await mut.mutateAsync({
        id_ot: ot.id_ot,
        body: { estado: estadoNuevo, observaciones: obs.trim() || undefined },
      })
      push({
        kind: 'success',
        title: isTerminada ? 'OT cerrada' : `OT actualizada a "${estadoNuevo}"`,
        body: isTerminada && ot.tipo_audit
          ? 'El reclamo pasa a auditoría y se generó una OT de auditoría.'
          : undefined,
      })
      onSuccess?.()
      onClose()
    } catch (err) {
      push({ kind: 'error', title: 'Error al cambiar estado', body: (err as Error).message })
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Cambiar estado de la OT"
      width={520}
      footer={
        <>
          <button onClick={onClose} disabled={mut.isPending} style={btnGhost}>Cancelar</button>
          <button onClick={confirmar} disabled={mut.isPending} style={btnPrimary}>
            {mut.isPending ? 'Aplicando…' : 'Confirmar'}
          </button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ fontSize: '0.82rem', color: 'var(--fg-3)' }}>{subtitle}</div>
        <div style={{
          background: 'var(--surface-300)', borderRadius: 8,
          padding: '8px 11px', fontSize: '0.8rem', color: 'var(--fg-2)',
        }}>
          Estado actual: <strong style={{ color: 'var(--fg-1)' }}>{ot.estado_nombre}</strong>
        </div>

        {isTerminada && ot.tipo_audit && (
          <div style={warnBox}>
            Al marcar <strong>Terminada</strong> el reclamo pasa a <strong>En auditoría</strong> y se crea automáticamente una OT de auditoría.
          </div>
        )}
        {isTerminada && !ot.tipo_audit && (
          <div style={warnBox}>
            Al marcar <strong>Terminada</strong> el reclamo pasa directo a <strong>Resuelto</strong> (sin auditoría).
          </div>
        )}

        <Field label="Nuevo estado">
          <select
            value={estadoNuevo}
            onChange={(e) => setEstadoNuevo(e.target.value as EstadoOT)}
            style={inputStyle}
          >
            {ESTADOS.map((e) => (
              <option key={e} value={e}>{e === 'Terminada' ? 'Terminada (cerrar OT)' : e}</option>
            ))}
          </select>
        </Field>

        <Field label="Observaciones" hint="Opcional. Queda en el detalle de la OT.">
          <textarea
            value={obs}
            onChange={(e) => setObs(e.target.value)}
            placeholder="Notas del trabajo realizado..."
            rows={3}
            maxLength={500}
            style={{ ...inputStyle, resize: 'vertical', fontFamily: 'var(--font-display)' }}
          />
        </Field>
      </div>
    </Modal>
  )
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label style={{ fontSize: '0.78rem', color: 'var(--fg-2)', fontWeight: 500 }}>{label}</label>
      {children}
      {hint && <div style={{ fontSize: '0.72rem', color: 'var(--fg-3)' }}>{hint}</div>}
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 11px',
  fontFamily: 'var(--font-display)', fontSize: '0.86rem',
  color: 'var(--fg-1)', background: 'var(--surface-100)',
  border: '1px solid var(--border-medium)', borderRadius: 8, outline: 'none',
}

const warnBox: React.CSSProperties = {
  background: '#fff3e0', borderLeft: '3px solid #ef6c00', borderRadius: 6,
  padding: '8px 12px', fontSize: '0.8rem', color: '#6a4500',
}

const btnPrimary: React.CSSProperties = {
  padding: '8px 16px', background: 'var(--zaris-orange)', color: 'white',
  border: 'none', borderRadius: 8,
  fontFamily: 'var(--font-display)', fontSize: '0.84rem',
  fontWeight: 500, cursor: 'pointer',
}

const btnGhost: React.CSSProperties = {
  padding: '8px 16px', background: 'var(--surface-100)', color: 'var(--fg-1)',
  border: '1px solid var(--border-medium)', borderRadius: 8,
  fontFamily: 'var(--font-display)', fontSize: '0.84rem', cursor: 'pointer',
}
