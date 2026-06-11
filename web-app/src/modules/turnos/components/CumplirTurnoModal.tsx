import { useEffect, useState } from 'react'
import { Modal } from '../../agenda/components/Modal'
import { Button } from '../../../ui'
import { HistorialAtenciones } from './HistorialAtenciones'
import type { CumplirTurnoBody, Turno } from '../types/turno'

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
        <div style={{ marginBottom: 14 }}>
          <HistorialAtenciones idCiudadano={turno.id_ciudadano} />
        </div>
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
