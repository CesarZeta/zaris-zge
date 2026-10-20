import { useEffect, useState } from 'react'
import { Modal } from '../../agenda/components/Modal'
import { useNotificationsStore } from '../../../stores/notifications'
import { useAprobarOT, useObservarOT } from '../hooks/useOT'
import type { MesaAuditoriaRow } from '../types/ot'
import { nombreAgente } from '../lib/format'

// Auditoría posterior al cierre (mig 112): aprobar → reclamo Auditado/aprobado
// (cierre definitivo); observar → Auditado/observado y un pop-up pregunta si se
// inicia un incidente nuevo (F4): Sí = reclamo de retrabajo + mail al vecino;
// No = la observación solo queda registrada. Antes 'rechazar' devolvía el reclamo
// a En gestión con una OT pendiente.
type Kind = 'aprobar' | 'observar'

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
  const mutObservar = useObservarOT()

  const [obs, setObs] = useState('')
  const [preguntaRetrabajo, setPreguntaRetrabajo] = useState(false)

  useEffect(() => {
    if (open) { setObs(''); setPreguntaRetrabajo(false) }
  }, [open, kind, ot])

  if (!ot || !kind) return null

  const subtitle = `${ot.nro_ot ?? ''} · ${ot.nro_reclamo ?? ''} — ${ot.tipo_nombre ?? ''}`
  const origenAg = nombreAgente(ot.ot_origen_agente_apellido, ot.ot_origen_agente_nombre)
  const requiereObs = kind === 'observar'
  const cierre = ot.reclamo_fecha_cierre
    ? new Date(ot.reclamo_fecha_cierre).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' })
    : '—'
  const puedeConfirmar = !requiereObs || obs.trim().length > 0

  // Regla §23: el modal se cierra AL CONFIRMAR y el resultado llega por toast.
  function aprobar() {
    if (!ot || !puedeConfirmar) return
    const idOt = ot.id_ot
    const texto = obs.trim()
    onClose()
    mutAprobar.mutateAsync({ id_ot: idOt, observaciones: texto })
      .then(() => {
        push({ kind: 'success', title: 'Auditoría aprobada — reclamo Auditado' })
        onSuccess?.()
      })
      .catch((err: unknown) => push({ kind: 'error', title: 'Error al aprobar', body: (err as Error).message }))
  }

  function observar(generarRetrabajo: boolean) {
    if (!ot || !puedeConfirmar) return
    const idOt = ot.id_ot
    const texto = obs.trim()
    setPreguntaRetrabajo(false)
    onClose()
    mutObservar.mutateAsync({ id_ot: idOt, observaciones: texto, generar_retrabajo: generarRetrabajo })
      .then((res) => {
        push(res.id_reclamo_retrabajo
          ? {
              kind: 'success',
              title: 'Auditoría observada — se inició un nuevo incidente',
              body: `Reclamo ${res.nro_reclamo_retrabajo ?? ''}. Se le avisó al vecino por correo.`,
            }
          : { kind: 'success', title: 'Auditoría observada — sin incidente nuevo' })
        onSuccess?.()
      })
      .catch((err: unknown) => push({ kind: 'error', title: 'Error al observar', body: (err as Error).message }))
  }

  const title = kind === 'aprobar' ? 'Aprobar auditoría' : 'Observar auditoría'
  const btn = kind === 'aprobar'
    ? { label: 'Aprobar', style: btnSuccess, onClick: aprobar }
    : { label: 'Observar', style: btnDanger, onClick: () => { if (puedeConfirmar) setPreguntaRetrabajo(true) } }

  return (
    <>
    <Modal
      open={open}
      // Con el pop-up abierto, Escape lo cierra solo a él (vuelve a este modal).
      onClose={preguntaRetrabajo ? () => {} : onClose}
      title={title}
      width={560}
      footer={
        <>
          <button onClick={onClose} style={btnGhost}>Cancelar</button>
          <button onClick={btn.onClick} disabled={!puedeConfirmar} style={btn.style}>{btn.label}</button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ fontSize: '0.82rem', color: 'var(--fg-3)' }}>{subtitle}</div>

        <div style={infoBox}>
          Reclamo resuelto el: <strong>{cierre}</strong><br />
          OT operativa origen: <strong>{ot.ot_origen_nro ?? '—'}</strong><br />
          Agente que realizó el trabajo: <strong>{origenAg}</strong><br />
          Observaciones del agente: {ot.ot_origen_obs?.trim() || '(sin observaciones)'}
          {ot.observaciones?.trim() ? <><br />Indicaciones de la supervisión: {ot.observaciones.trim()}</> : null}
        </div>

        <div style={warnBox}>
          {kind === 'aprobar' ? (
            <>Al aprobar, el reclamo queda <strong>Auditado</strong> (aprobado) y se cierra definitivamente. Su fecha de cierre no cambia y el vecino no recibe aviso.</>
          ) : (
            <>Al observar, el reclamo queda <strong>Auditado</strong> (observado). Después te vamos a preguntar si querés <strong>iniciar un nuevo incidente</strong> para volver a hacer el trabajo.</>
          )}
        </div>

        <Field
          label={kind === 'aprobar' ? 'Observaciones' : 'Observación del auditor'}
          required={requiereObs}
          hint={kind === 'aprobar'
            ? 'Opcional.'
            : 'Obligatorio. Describí qué quedó mal o sin hacer. Es interna: el vecino no la ve.'}
        >
          <textarea
            value={obs}
            onChange={(e) => setObs(e.target.value)}
            placeholder={kind === 'aprobar' ? 'Comentarios de la auditoría...' : 'Ej: quedó un pozo sin tapar en la esquina...'}
            rows={4}
            maxLength={500}
            style={{ ...inputStyle, resize: 'vertical', fontFamily: 'var(--font-display)' }}
          />
        </Field>
      </div>
    </Modal>

    <Modal
      open={open && preguntaRetrabajo}
      onClose={() => setPreguntaRetrabajo(false)}
      title="¿Iniciar un nuevo incidente?"
      width={480}
      footer={
        <>
          <button onClick={() => setPreguntaRetrabajo(false)} style={btnGhost}>Volver</button>
          <button onClick={() => observar(false)} style={btnOutline}>No, solo registrar</button>
          <button onClick={() => observar(true)} style={btnPrimary}>Sí, iniciar nuevo incidente</button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: '0.86rem', color: 'var(--fg-2)', lineHeight: 1.45 }}>
        <div>La auditoría de <strong>{ot.nro_reclamo ?? 'este reclamo'}</strong> queda observada. ¿Querés abrir un reclamo nuevo para volver a hacer el trabajo?</div>
        <div style={infoBox}>
          <strong>Sí:</strong> se crea un reclamo de oficio, sin asignar, con tu observación, y el vecino recibe un correo que le avisa que se va a volver a hacer la tarea (sin tu observación). Al resolverlo se le envía la encuesta de satisfacción.<br />
          <strong>No:</strong> la auditoría queda registrada como observada y el vecino no recibe ningún aviso.
        </div>
      </div>
    </Modal>
    </>
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

const btnPrimary: React.CSSProperties = {
  padding: '8px 16px', background: 'var(--zaris-orange)', color: 'white',
  border: 'none', borderRadius: 8,
  fontFamily: 'var(--font-display)', fontSize: '0.84rem',
  fontWeight: 500, cursor: 'pointer',
}

const btnOutline: React.CSSProperties = {
  padding: '8px 16px', background: 'transparent', color: 'var(--fg-1)',
  border: '1px solid var(--border-medium)', borderRadius: 8,
  fontFamily: 'var(--font-display)', fontSize: '0.84rem', cursor: 'pointer',
}

const btnGhost: React.CSSProperties = {
  padding: '8px 16px', background: 'var(--surface-100)', color: 'var(--fg-1)',
  border: '1px solid var(--border-medium)', borderRadius: 8,
  fontFamily: 'var(--font-display)', fontSize: '0.84rem', cursor: 'pointer',
}
