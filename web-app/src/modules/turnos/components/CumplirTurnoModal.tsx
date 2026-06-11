import { useEffect, useState } from 'react'
import { Modal } from '../../agenda/components/Modal'
import { Button } from '../../../ui'
import { useAtencionesCiudadano } from '../hooks/useTurnos'
import type { CumplirTurnoBody, Turno, TurnoAtencion } from '../types/turno'

interface Props {
  turno: Turno | null
  onConfirm: (body: CumplirTurnoBody) => void
  onCancel: () => void
}

/**
 * Modal de cumplir turno. Dos modos según la prestación (mig 86):
 *  - Normal: confirmación + observación opcional (comportamiento histórico).
 *  - Con historia de atención (registra_atencion): muestra las atenciones
 *    anteriores del ciudadano y exige registrar la intervención del día
 *    (+ recomendaciones opcionales). El backend valida lo mismo (422).
 */
export function CumplirTurnoModal({ turno, onConfirm, onCancel }: Props) {
  const [obs, setObs] = useState('')
  const [intervencion, setIntervencion] = useState('')
  const [recomendaciones, setRecomendaciones] = useState('')
  const [faltaIntervencion, setFaltaIntervencion] = useState(false)

  const conHistoria = turno?.registra_atencion === true

  useEffect(() => {
    if (turno) {
      setObs('')
      setIntervencion('')
      setRecomendaciones('')
      setFaltaIntervencion(false)
    }
  }, [turno])

  function confirmar() {
    if (conHistoria) {
      if (!intervencion.trim()) {
        setFaltaIntervencion(true)
        return
      }
      onConfirm({
        intervencion: intervencion.trim(),
        recomendaciones: recomendaciones.trim() || undefined,
      })
    } else {
      onConfirm({ observaciones: obs.trim() || undefined })
    }
  }

  return (
    <Modal
      open={turno != null}
      onClose={onCancel}
      title={conHistoria ? 'Registrar atención y cumplir turno' : 'Marcar turno como cumplido'}
      width={conHistoria ? 640 : 460}
      footer={
        <>
          <Button variant="ghost" onClick={onCancel}>Cancelar</Button>
          <Button variant="accent" onClick={confirmar}>
            {conHistoria ? 'Registrar y cumplir' : 'Marcar cumplido'}
          </Button>
        </>
      }
    >
      <p style={{ margin: '0 0 14px', fontSize: 14, color: 'var(--fg-1)', lineHeight: 1.5 }}>
        {conHistoria ? (
          <>
            Atención de <strong>{turno?.ciudadano_nombre ?? ''}</strong>
            {turno?.prestacion_nombre ? <> — {turno.prestacion_nombre}</> : null}.
            Al cumplir se envía una encuesta de satisfacción al ciudadano.
          </>
        ) : (
          <>
            Confirmás que el turno de <strong>{turno?.ciudadano_nombre ?? ''}</strong> fue atendido?
            Al cumplirlo se envía una encuesta de satisfacción al ciudadano.
          </>
        )}
      </p>

      {conHistoria && turno && (
        <HistorialAtenciones idCiudadano={turno.id_ciudadano} />
      )}

      {conHistoria ? (
        <>
          <label style={lbl}>Intervención realizada (obligatoria)</label>
          <textarea
            value={intervencion}
            onChange={(e) => { setIntervencion(e.target.value); if (e.target.value.trim()) setFaltaIntervencion(false) }}
            rows={3}
            placeholder="Qué se hizo en la atención de hoy. Ej: Control y limpieza; se detectó caries en pieza 26, se realizó obturación."
            style={{ ...txt, borderColor: faltaIntervencion ? 'var(--color-error)' : 'var(--border-primary)' }}
          />
          <div style={{ fontSize: 11, color: faltaIntervencion ? 'var(--color-error)' : 'var(--fg-3)', margin: '4px 0 12px' }}>
            {faltaIntervencion
              ? 'Completá la intervención para poder cumplir el turno.'
              : 'Queda registrada en la historia de atenciones del ciudadano.'}
          </div>

          <label style={lbl}>Recomendaciones / indicaciones (opcional)</label>
          <textarea
            value={recomendaciones}
            onChange={(e) => setRecomendaciones(e.target.value)}
            rows={2}
            placeholder="Indicaciones para el ciudadano. Ej: Volver a control en 6 meses; evitar alimentos duros por 48 hs."
            style={txt}
          />
        </>
      ) : (
        <>
          <label style={lbl}>Observación de la atención (opcional)</label>
          <textarea
            value={obs}
            onChange={(e) => setObs(e.target.value)}
            rows={3}
            placeholder="Ej: Atendido en mostrador 3, sin demoras."
            style={txt}
          />
        </>
      )}
    </Modal>
  )
}

/** Atenciones anteriores del ciudadano (scopeadas por nivel en el backend). */
function HistorialAtenciones({ idCiudadano }: { idCiudadano: number }) {
  const { data, isLoading, isError } = useAtencionesCiudadano(idCiudadano)
  const atenciones = data ?? []
  return (
    <div style={{
      border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-md)',
      background: 'var(--surface-300)', padding: '10px 12px', marginBottom: 14,
    }}>
      <div style={{
        fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em',
        color: 'var(--fg-3)', marginBottom: 8,
      }}>
        Atenciones anteriores {!isLoading && !isError ? `(${atenciones.length})` : ''}
      </div>
      {isLoading && <div style={metaTxt}>Cargando historial…</div>}
      {isError && <div style={{ ...metaTxt, color: 'var(--color-error)' }}>No se pudo cargar el historial.</div>}
      {!isLoading && !isError && atenciones.length === 0 && (
        <div style={metaTxt}>Sin atenciones previas registradas. Esta es la primera atención del ciudadano.</div>
      )}
      {atenciones.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 180, overflowY: 'auto' }}>
          {atenciones.map((a) => <AtencionItem key={a.id_turno_atencion} a={a} />)}
        </div>
      )}
    </div>
  )
}

function AtencionItem({ a }: { a: TurnoAtencion }) {
  return (
    <div style={{
      background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
      borderRadius: 'var(--radius-md)', padding: '8px 10px',
    }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'baseline', flexWrap: 'wrap' }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5, color: 'var(--fg-2)' }}>{a.fecha}</span>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg-1)' }}>{a.prestacion_nombre ?? 'Atención'}</span>
        {a.atendido_por && <span style={{ ...metaTxt, marginLeft: 'auto' }}>atendió: {a.atendido_por}</span>}
      </div>
      <div style={{ fontSize: 12.5, color: 'var(--fg-1)', marginTop: 4, whiteSpace: 'pre-wrap' }}>{a.intervencion}</div>
      {a.recomendaciones && (
        <div style={{ fontSize: 12, color: 'var(--fg-2)', marginTop: 4, whiteSpace: 'pre-wrap' }}>
          <span style={{ fontWeight: 600 }}>Recomendaciones:</span> {a.recomendaciones}
        </div>
      )}
    </div>
  )
}

const lbl: React.CSSProperties = {
  display: 'block', fontSize: 11, fontWeight: 600, textTransform: 'uppercase',
  letterSpacing: '0.04em', color: 'var(--fg-3)', marginBottom: 4,
}
const txt: React.CSSProperties = {
  width: '100%', fontFamily: 'var(--font-display)', fontSize: 13,
  padding: '8px 10px', borderRadius: 'var(--radius-md)',
  border: '1px solid var(--border-primary)', background: 'var(--surface-100)',
  outline: 'none', resize: 'vertical', boxSizing: 'border-box',
}
const metaTxt: React.CSSProperties = { fontSize: 11.5, color: 'var(--fg-3)' }
