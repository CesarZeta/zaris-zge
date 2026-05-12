import { useEffect, useState } from 'react'
import { Modal } from '../../agenda/components/Modal'
import { useNotificationsStore } from '../../../stores/notifications'
import { useAgentesActivos, useEquiposActivos, useReasignarOT } from '../hooks/useOT'
import type { MesaSupervisorRow } from '../types/ot'
import { nombreAgente } from '../lib/format'

interface Props {
  open: boolean
  reclamo: MesaSupervisorRow | null
  onClose: () => void
  onSuccess?: () => void
}

type Modo = 'agente' | 'equipo'

export function ReasignarModal({ open, reclamo, onClose, onSuccess }: Props) {
  const push = useNotificationsStore((s) => s.push)
  const mut = useReasignarOT()
  const agentesQ = useAgentesActivos(open)
  const equiposQ = useEquiposActivos(open)

  const [modo, setModo] = useState<Modo>('agente')
  const [idAgente, setIdAgente] = useState<number | ''>('')
  const [idEquipo, setIdEquipo] = useState<number | ''>('')
  const [nota, setNota] = useState('')

  useEffect(() => {
    if (open) {
      setModo('agente')
      setIdAgente('')
      setIdEquipo('')
      setNota('')
    }
  }, [open])

  if (!reclamo || !reclamo.ot_activa_id) return null

  const subtitle = `${reclamo.nro_reclamo ?? ''} — ${reclamo.tipo_nombre ?? ''} (${reclamo.subarea_nombre ?? ''})`
  const actual = reclamo.ot_agente_nombre
    ? <>Asignado actualmente al <strong>agente {reclamo.ot_agente_nombre}</strong> (OT {reclamo.ot_activa_nro ?? ''})</>
    : reclamo.ot_equipo_nombre
      ? <>Asignado actualmente al <strong>equipo {reclamo.ot_equipo_nombre}</strong> (OT {reclamo.ot_activa_nro ?? ''})</>
      : <>OT {reclamo.ot_activa_nro ?? ''} — sin destinatario</>

  const agentes = agentesQ.data?.filter((a) => a.activo) ?? []
  const equipos = equiposQ.data?.filter((e) => e.activo) ?? []

  const puedeConfirmar =
    !mut.isPending && nota.trim().length > 0 &&
    ((modo === 'agente' && idAgente !== '') || (modo === 'equipo' && idEquipo !== ''))

  async function confirmar() {
    if (!reclamo?.ot_activa_id || !puedeConfirmar) return
    try {
      const data = await mut.mutateAsync({
        id_ot: reclamo.ot_activa_id,
        body: {
          id_agente: modo === 'agente' ? (idAgente as number) : null,
          id_equipo: modo === 'equipo' ? (idEquipo as number) : null,
          nota: nota.trim(),
        },
      })
      push({ kind: 'success', title: `OT reasignada a ${data.asignado_a}` })
      onSuccess?.()
      onClose()
    } catch (err) {
      push({ kind: 'error', title: 'Error al reasignar OT', body: (err as Error).message })
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Reasignar OT"
      width={560}
      footer={
        <>
          <button onClick={onClose} disabled={mut.isPending} style={btnGhost}>Cancelar</button>
          <button onClick={confirmar} disabled={!puedeConfirmar} style={btnWarn}>
            {mut.isPending ? 'Reasignando…' : 'Reasignar'}
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
          {actual}
        </div>

        <div style={{ display: 'flex', gap: 14 }}>
          <label style={radioLabel}>
            <input type="radio" checked={modo === 'agente'} onChange={() => setModo('agente')} /> Agente individual
          </label>
          <label style={radioLabel}>
            <input type="radio" checked={modo === 'equipo'} onChange={() => setModo('equipo')} /> Equipo
          </label>
        </div>

        {modo === 'agente' ? (
          <Field label="Nuevo agente">
            <select
              value={idAgente}
              onChange={(e) => setIdAgente(e.target.value ? Number(e.target.value) : '')}
              style={inputStyle}
              disabled={agentesQ.isLoading}
            >
              <option value="">— Seleccionar —</option>
              {agentes.map((a) => (
                <option key={a.id_agente} value={a.id_agente}>
                  {nombreAgente(a.apellido, a.nombre)}{a.legajo ? ` · #${a.legajo}` : ''}
                </option>
              ))}
            </select>
          </Field>
        ) : (
          <Field label="Nuevo equipo">
            <select
              value={idEquipo}
              onChange={(e) => setIdEquipo(e.target.value ? Number(e.target.value) : '')}
              style={inputStyle}
              disabled={equiposQ.isLoading}
            >
              <option value="">— Seleccionar —</option>
              {equipos.map((e) => (
                <option key={e.id_equipo} value={e.id_equipo}>
                  {e.nombre ?? `Equipo #${e.id_equipo}`}
                </option>
              ))}
            </select>
          </Field>
        )}

        <Field label="Motivo de la reasignación" required hint="Queda guardado en el historial del reclamo.">
          <textarea
            value={nota}
            onChange={(e) => setNota(e.target.value)}
            placeholder="Indicá por qué se reasigna..."
            rows={3}
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

const radioLabel: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 6,
  fontSize: '0.86rem', cursor: 'pointer',
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 11px',
  fontFamily: 'var(--font-display)', fontSize: '0.86rem',
  color: 'var(--fg-1)', background: 'var(--surface-100)',
  border: '1px solid var(--border-medium)', borderRadius: 8, outline: 'none',
}

const btnWarn: React.CSSProperties = {
  padding: '8px 16px', background: '#ef6c00', color: 'white',
  border: 'none', borderRadius: 8,
  fontFamily: 'var(--font-display)', fontSize: '0.84rem',
  fontWeight: 500, cursor: 'pointer',
}

const btnGhost: React.CSSProperties = {
  padding: '8px 16px', background: 'var(--surface-100)', color: 'var(--fg-1)',
  border: '1px solid var(--border-medium)', borderRadius: 8,
  fontFamily: 'var(--font-display)', fontSize: '0.84rem', cursor: 'pointer',
}
