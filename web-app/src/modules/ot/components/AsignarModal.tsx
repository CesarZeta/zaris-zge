import { useEffect, useState } from 'react'
import { Modal } from '../../agenda/components/Modal'
import { useNotificationsStore } from '../../../stores/notifications'
import { useAgentesActivos, useCrearOT, useEquiposActivos } from '../hooks/useOT'
import type { MesaSupervisorRow } from '../types/ot'
import { nombreAgente } from '../lib/format'

interface Props {
  open: boolean
  reclamos: MesaSupervisorRow[]
  onClose: () => void
  onSuccess?: () => void
}

type Modo = 'agente' | 'equipo'

export function AsignarModal({ open, reclamos, onClose, onSuccess }: Props) {
  const push = useNotificationsStore((s) => s.push)
  const mut = useCrearOT()
  const agentesQ = useAgentesActivos(open)
  const equiposQ = useEquiposActivos(open)

  const [modo, setModo] = useState<Modo>('agente')
  const [idAgente, setIdAgente] = useState<number | ''>('')
  const [idEquipo, setIdEquipo] = useState<number | ''>('')
  const [obs, setObs] = useState('')

  useEffect(() => {
    if (open) {
      setModo('agente')
      setIdAgente('')
      setIdEquipo('')
      setObs('')
    }
  }, [open])

  const isLote = reclamos.length > 1
  const title = isLote ? `Asignar OT en lote (${reclamos.length})` : 'Asignar orden de trabajo'

  const r = reclamos[0]
  const subtitle = isLote
    ? 'Mismo agente o equipo se asignará a todos los seleccionados.'
    : r ? `${r.nro_reclamo ?? ''} — ${r.tipo_nombre ?? ''} (${r.subarea_nombre ?? ''})` : '—'

  const agentes = agentesQ.data?.filter((a) => a.activo) ?? []
  const equipos = equiposQ.data?.filter((e) => e.activo) ?? []

  const puedeConfirmar =
    !mut.isPending && reclamos.length > 0 &&
    ((modo === 'agente' && idAgente !== '') || (modo === 'equipo' && idEquipo !== ''))

  async function confirmar() {
    if (!puedeConfirmar) return
    const base = { observaciones: obs.trim() || undefined } as { observaciones?: string }
    let ok = 0
    let fail = 0
    let lastErr: string | null = null
    for (const r of reclamos) {
      try {
        await mut.mutateAsync({
          id_reclamo: r.id_reclamo,
          id_agente: modo === 'agente' ? (idAgente as number) : null,
          id_equipo: modo === 'equipo' ? (idEquipo as number) : null,
          ...base,
        })
        ok++
      } catch (err) {
        fail++
        lastErr = (err as Error).message
      }
    }

    if (fail === 0) {
      push({ kind: 'success', title: `${ok} OT(s) creada(s) correctamente` })
    } else if (ok === 0) {
      push({ kind: 'error', title: 'Error al crear OTs', body: lastErr ?? `${fail} fallos` })
    } else {
      push({ kind: 'error', title: `${ok} OT(s) creadas, ${fail} fallaron`, body: lastErr ?? undefined })
    }
    onSuccess?.()
    onClose()
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      width={560}
      footer={
        <>
          <button onClick={onClose} disabled={mut.isPending} style={btnGhost}>Cancelar</button>
          <button onClick={confirmar} disabled={!puedeConfirmar} style={btnPrimary}>
            {mut.isPending ? 'Creando…' : 'Crear OT'}
          </button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ fontSize: '0.82rem', color: 'var(--fg-3)' }}>{subtitle}</div>

        {isLote && (
          <div style={{
            display: 'flex', flexWrap: 'wrap', gap: 5, maxHeight: 100, overflowY: 'auto',
            padding: 8, background: 'var(--surface-300)', borderRadius: 8,
          }}>
            {reclamos.map((r) => (
              <span key={r.id_reclamo} style={chipStyle}>{r.nro_reclamo}</span>
            ))}
          </div>
        )}

        <div style={{ display: 'flex', gap: 14 }}>
          <label style={radioLabel}>
            <input type="radio" checked={modo === 'agente'} onChange={() => setModo('agente')} /> Agente individual
          </label>
          <label style={radioLabel}>
            <input type="radio" checked={modo === 'equipo'} onChange={() => setModo('equipo')} /> Equipo
          </label>
        </div>

        {modo === 'agente' ? (
          <Field label="Agente">
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
          <Field label="Equipo">
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

        <Field label={`Observaciones${isLote ? ' (aplica a todas las OTs)' : ''}`} hint="Opcional. Notas para el agente o equipo.">
          <textarea
            value={obs}
            onChange={(e) => setObs(e.target.value)}
            placeholder="Notas para el agente/equipo..."
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

const radioLabel: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 6,
  fontSize: '0.86rem', cursor: 'pointer',
}

const chipStyle: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-medium)',
  borderRadius: 999, padding: '2px 9px',
  fontSize: '0.7rem', fontFamily: 'var(--font-mono)', color: 'var(--fg-2)',
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 11px',
  fontFamily: 'var(--font-display)', fontSize: '0.86rem',
  color: 'var(--fg-1)', background: 'var(--surface-100)',
  border: '1px solid var(--border-medium)', borderRadius: 8, outline: 'none',
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
