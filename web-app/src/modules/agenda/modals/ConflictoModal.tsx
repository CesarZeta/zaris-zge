import { useState } from 'react'
import { Modal } from '../components/Modal'
import { Button } from '../../../ui'
import { useResolverConflicto } from '../hooks/useConflictos'
import { useNotificationsStore } from '../../../stores/notifications'
import type { Conflicto } from '../types/agenda'

interface Props {
  open: boolean
  onClose: () => void
  conflicto: Conflicto | null
}

export function ConflictoModal({ open, onClose, conflicto }: Props) {
  const push = useNotificationsStore((s) => s.push)
  const resolver = useResolverConflicto()
  const [obs, setObs] = useState('')

  async function onResolver() {
    if (!conflicto) return
    try {
      await resolver.mutateAsync({ id: conflicto.id_conflicto, observaciones: obs || undefined })
      push({ kind: 'success', title: 'Conflicto resuelto' })
      onClose()
    } catch (e) {
      push({ kind: 'error', title: 'No se pudo resolver', body: (e as Error).message })
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Conflicto #${conflicto?.id_conflicto ?? ''}`}
      width={680}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cerrar</Button>
          {!conflicto?.resuelto && <Button variant="accent" onClick={onResolver}>Marcar como resuelto</Button>}
        </>
      }
    >
      {!conflicto && <div style={{ color: 'var(--fg-3)' }}>Sin datos</div>}
      {conflicto && (
        <>
          <div style={{ fontSize: 12, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', marginBottom: 12 }}>
            detectado: {new Date(conflicto.fecha_deteccion).toLocaleString('es-AR')} ·
            recurso: {conflicto.tipo_recurso} #{conflicto.id_recurso} ·
            estado: <strong style={{ color: conflicto.resuelto ? 'var(--color-success)' : 'var(--color-error)' }}>{conflicto.resuelto ? 'resuelto' : 'pendiente'}</strong>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 14 }}>
            <Lado titulo="Ocupacion origen" det={conflicto.ocupacion_origen_detalle} idAlt={conflicto.id_ocupacion_origen} />
            <Lado titulo="Ocupacion en conflicto" det={conflicto.ocupacion_conflicto_detalle} idAlt={conflicto.id_ocupacion_conflicto} />
          </div>
          {conflicto.observaciones && (
            <div style={{ padding: 8, background: 'var(--surface-200)', borderRadius: 'var(--radius-md)', marginBottom: 10, fontSize: 13 }}>
              <strong>Obs:</strong> {conflicto.observaciones}
            </div>
          )}
          {!conflicto.resuelto && (
            <div>
              <label style={{ fontSize: 11, color: 'var(--fg-3)', textTransform: 'uppercase' }}>Observaciones</label>
              <textarea rows={3} value={obs} onChange={(e) => setObs(e.target.value)} placeholder="Detalle de la resolucion (opcional)"
                style={{
                  width: '100%', padding: '8px 10px', borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-primary)', background: 'var(--surface-100)',
                  fontFamily: 'var(--font-display)', fontSize: 14, resize: 'vertical', outline: 'none',
                }}
              />
            </div>
          )}
        </>
      )}
    </Modal>
  )
}

function Lado({ titulo, det, idAlt }: { titulo: string; det: Record<string, unknown> | null; idAlt: number | null }) {
  return (
    <div style={{ padding: 12, background: 'var(--surface-200)', borderRadius: 'var(--radius-md)' }}>
      <h4 style={{ margin: '0 0 8px', fontSize: 12, color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '.04em' }}>{titulo}</h4>
      {!det && <span style={{ color: 'var(--fg-3)', fontSize: 13 }}>#{idAlt ?? '?'} (sin detalle)</span>}
      {det && (
        <dl style={{ margin: 0, display: 'grid', gridTemplateColumns: '90px 1fr', rowGap: 4, columnGap: 8, fontSize: 13 }}>
          {Object.entries(det).map(([k, v]) => (
            <Fragment key={k}>
              <dt style={{ color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>{k}</dt>
              <dd style={{ margin: 0, color: 'var(--fg-1)' }}>{String(v)}</dd>
            </Fragment>
          ))}
        </dl>
      )}
    </div>
  )
}

// Helper para usar Fragment sin import explicito
import { Fragment } from 'react'
