import { useEffect, useState } from 'react'
import { Modal } from '../../agenda/components/Modal'
import { Button } from '../../../ui'
import type { Turno } from '../types/turno'

interface Props {
  turno: Turno | null
  onConfirm: (observaciones: string) => void
  onCancel: () => void
}

export function CumplirTurnoModal({ turno, onConfirm, onCancel }: Props) {
  const [obs, setObs] = useState('')

  useEffect(() => {
    if (turno) setObs('')
  }, [turno])

  return (
    <Modal
      open={turno != null}
      onClose={onCancel}
      title="Marcar turno como cumplido"
      width={460}
      footer={
        <>
          <Button variant="ghost" onClick={onCancel}>Cancelar</Button>
          <Button variant="accent" onClick={() => onConfirm(obs.trim())}>Marcar cumplido</Button>
        </>
      }
    >
      <p style={{ margin: '0 0 14px', fontSize: 14, color: 'var(--fg-1)', lineHeight: 1.5 }}>
        Confirmás que el turno de <strong>{turno?.ciudadano_nombre ?? ''}</strong> fue atendido?
        Al cumplirlo se envía una encuesta de satisfacción al ciudadano.
      </p>
      <label style={{ display: 'block', fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--fg-3)', marginBottom: 4 }}>
        Observación de la atención (opcional)
      </label>
      <textarea
        value={obs}
        onChange={(e) => setObs(e.target.value)}
        rows={3}
        placeholder="Ej: Atendido en mostrador 3, sin demoras."
        style={{
          width: '100%', fontFamily: 'var(--font-display)', fontSize: 13,
          padding: '8px 10px', borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-primary)', background: 'var(--surface-100)',
          outline: 'none', resize: 'vertical', boxSizing: 'border-box',
        }}
      />
    </Modal>
  )
}
