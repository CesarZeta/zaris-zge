import { useEffect, useState } from 'react'
import { Modal } from '../../agenda/components/Modal'
import { useNotificationsStore } from '../../../stores/notifications'
import { useAprobarOT, useRechazarOT } from '../hooks/useOT'
import type { MesaAuditoriaRow } from '../types/ot'
import { nombreAgente } from '../lib/format'

type Kind = 'aprobar' | 'rechazar'

interface Props {
  open: boolean
  kind: Kind | null
  ot: MesaAuditoriaRow | null
  onClose: () => void
  onSuccess?: () => void
}

export function AuditarModal({ open, kind, ot, onClose, onSuccess }: Props) {
  const push = useNotificationsStore((s) => s.push)
  const mutAprobar = useAprobarOT()
  const mutRechazar = useRechazarOT()
  const mut = kind === 'aprobar' ? mutAprobar : mutRechazar

  const [obs, setObs] = useState('')

  useEffect(() => {
    if (open) setObs('')
  }, [open, kind, ot])

  if (!ot || !kind) return null

  const subtitle = `${ot.nro_ot ?? ''} · ${ot.nro_reclamo ?? ''} — ${ot.tipo_nombre ?? ''}`
  const origenAg = nombreAgente(ot.ot_origen_agente_apellido, ot.ot_origen_agente_nombre)
  const requiereObs = kind === 'rechazar'
  const puedeConfirmar = !mut.isPending && (!requiereObs || obs.trim().length > 0)

  async function confirmar() {
    if (!ot || !kind || !puedeConfirmar) return
    try {
      if (kind === 'aprobar') {
        await mutAprobar.mutateAsync({ id_ot: ot.id_ot, observaciones: obs.trim() })
        push({ kind: 'success', title: 'Auditoría aprobada — reclamo resuelto' })
      } else {
        await mutRechazar.mutateAsync({ id_ot: ot.id_ot, observaciones: obs.trim() })
        push({ kind: 'success', title: 'Auditoría rechazada — nueva OT pendiente generada' })
      }
      onSuccess?.()
      onClose()
    } catch (err) {
      push({
        kind: 'error',
        title: kind === 'aprobar' ? 'Error al aprobar' : 'Error al rechazar',
        body: (err as Error).message,
      })
    }
  }

  const title = kind === 'aprobar' ? 'Aprobar auditoría' : 'Rechazar auditoría'
  const btn = kind === 'aprobar'
    ? { label: mut.isPending ? 'Aprobando…' : 'Aprobar', style: btnSuccess }
    : { label: mut.isPending ? 'Rechazando…' : 'Rechazar', style: btnDanger }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      width={560}
      footer={
        <>
          <button onClick={onClose} disabled={mut.isPending} style={btnGhost}>Cancelar</button>
          <button onClick={confirmar} disabled={!puedeConfirmar} style={btn.style}>{btn.label}</button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ fontSize: '0.82rem', color: 'var(--fg-3)' }}>{subtitle}</div>

        <div style={infoBox}>
          OT operativa origen: <strong>{ot.ot_origen_nro ?? '—'}</strong><br />
          Agente que realizó el trabajo: <strong>{origenAg}</strong><br />
          Observaciones del agente: {ot.ot_origen_obs?.trim() || '(sin observaciones)'}
        </div>

        <div style={warnBox}>
          {kind === 'aprobar' ? (
            <>Al aprobar, el reclamo pasa a estado <strong>Resuelto</strong> y el ciclo se cierra.</>
          ) : (
            <>Al rechazar, se genera una <strong>nueva OT Pendiente</strong> con el agente del trabajo original y el reclamo vuelve a <strong>En gestión</strong>.</>
          )}
        </div>

        <Field
          label={kind === 'aprobar' ? 'Observaciones' : 'Motivo del rechazo'}
          required={requiereObs}
          hint={kind === 'aprobar' ? 'Opcional.' : 'Obligatorio. Describí qué no cumple.'}
        >
          <textarea
            value={obs}
            onChange={(e) => setObs(e.target.value)}
            placeholder={kind === 'aprobar' ? 'Comentarios de la auditoría...' : 'Describí qué no cumple...'}
            rows={4}
            maxLength={500}
            style={{ ...inputStyle, resize: 'vertical', fontFamily: 'var(--font-display)' }}
          />
        </Field>
      </div>
    </Modal>
  )
}

function Field({ label, hint, required, children }: {
  label: string; hint?: string; required?: boolean; children: React.ReactNode
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label style={{ fontSize: '0.78rem', color: 'var(--fg-2)', fontWeight: 500 }}>
        {label}{required && <span style={{ color: 'var(--color-error)', marginLeft: 4 }}>*</span>}
      </label>
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

const infoBox: React.CSSProperties = {
  background: 'var(--surface-300)', borderRadius: 8,
  padding: '10px 13px', fontSize: '0.82rem', color: 'var(--fg-2)',
  lineHeight: 1.4,
}

const warnBox: React.CSSProperties = {
  background: '#fff3e0', borderLeft: '3px solid #ef6c00', borderRadius: 6,
  padding: '8px 12px', fontSize: '0.8rem', color: '#6a4500',
}

const btnSuccess: React.CSSProperties = {
  padding: '8px 16px', background: '#2e7d32', color: 'white',
  border: 'none', borderRadius: 8,
  fontFamily: 'var(--font-display)', fontSize: '0.84rem',
  fontWeight: 500, cursor: 'pointer',
}

const btnDanger: React.CSSProperties = {
  padding: '8px 16px', background: 'var(--color-error)', color: 'white',
  border: 'none', borderRadius: 8,
  fontFamily: 'var(--font-display)', fontSize: '0.84rem',
  fontWeight: 500, cursor: 'pointer',
}

const btnGhost: React.CSSProperties = {
  padding: '8px 16px', background: 'var(--surface-100)', color: 'var(--fg-1)',
  border: '1px solid var(--border-medium)', borderRadius: 8,
  fontFamily: 'var(--font-display)', fontSize: '0.84rem', cursor: 'pointer',
}
