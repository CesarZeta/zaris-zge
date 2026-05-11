import { useState } from 'react'
import { CheckCircle, X as XIcon } from 'lucide-react'
import { Modal } from '../components/Modal'
import { ConfirmModal } from '../components/ConfirmModal'
import { CiudadanoSearch } from '../components/CiudadanoSearch'
import { Button } from '../../../ui'
import { useEventoDetalle } from '../hooks/useEventos'
import { useReservas, useCrearReserva, useMarcarAsistio, useCancelarReserva } from '../hooks/useReservas'
import { useNotificationsStore } from '../../../stores/notifications'
import type { CiudadanoMinimo, OrigenReserva } from '../types/agenda'

interface Props {
  open: boolean
  onClose: () => void
  idEvento: number | null
}

export function ReservaModal({ open, onClose, idEvento }: Props) {
  const push = useNotificationsStore((s) => s.push)
  const detalle = useEventoDetalle(open ? idEvento : null)
  const reservas = useReservas(open ? idEvento : null)
  const crear = useCrearReserva(idEvento ?? 0)
  const asistio = useMarcarAsistio()
  const cancelar = useCancelarReserva()
  const [cid, setCid] = useState<CiudadanoMinimo | null>(null)
  const [origen, setOrigen] = useState<OrigenReserva>('backoffice')
  const [qr, setQr] = useState<string | null>(null)
  const [confirmCancelId, setConfirmCancelId] = useState<number | null>(null)

  async function onCrear() {
    if (!idEvento || !cid) return
    try {
      const r = await crear.mutateAsync({ id_ciudadano: cid.id_ciudadano, origen })
      push({ kind: 'success', title: 'Reserva creada' })
      setQr(r.qr_codigo ?? null)
      setCid(null)
    } catch (e) {
      push({ kind: 'error', title: 'No se pudo reservar', body: (e as Error).message })
    }
  }

  async function onAsistio(id: number) {
    try {
      await asistio.mutateAsync(id)
      push({ kind: 'success', title: 'Asistencia marcada' })
    } catch (e) {
      push({ kind: 'error', title: 'No se pudo marcar asistencia', body: (e as Error).message })
    }
  }

  async function doCancelar(id: number) {
    setConfirmCancelId(null)
    try {
      await cancelar.mutateAsync(id)
      push({ kind: 'success', title: 'Reserva cancelada' })
    } catch (e) {
      push({ kind: 'error', title: 'No se pudo cancelar', body: (e as Error).message })
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Reservas · evento #${idEvento ?? ''}`}
      width={680}
      footer={<Button variant="ghost" onClick={onClose}>Cerrar</Button>}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 14, fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--fg-3)' }}>
        <span>capacidad: {detalle.data?.capacidad_ciudadanos ?? '?'}</span>
        <span>reservas activas: {detalle.data?.reservas_activas ?? '?'}</span>
        <span><strong style={{ color: 'var(--fg-1)' }}>cupo disponible: {detalle.data?.cupo_disponible ?? '?'}</strong></span>
      </div>

      <div style={{ padding: 12, background: 'var(--surface-200)', borderRadius: 'var(--radius-md)', marginBottom: 16 }}>
        <h3 style={{ margin: '0 0 8px', fontSize: 13, fontWeight: 500, color: 'var(--fg-1)' }}>Nueva reserva</h3>
        <CiudadanoSearch onSelect={(c) => setCid(c)} />
        {cid && (
          <div style={{ marginTop: 6, fontSize: 13, color: 'var(--fg-2)' }}>
            Seleccionado: <strong>{cid.apellido}, {cid.nombre}</strong>
            {cid.doc_nro && <span style={{ color: 'var(--fg-3)' }}> · DNI {cid.doc_nro}</span>}
          </div>
        )}
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginTop: 10 }}>
          <label style={{ fontSize: 12, color: 'var(--fg-3)' }}>origen</label>
          <select value={origen} onChange={(e) => setOrigen(e.target.value as OrigenReserva)} style={inp}>
            <option value="backoffice">backoffice</option>
            <option value="autoservicio">autoservicio</option>
          </select>
          <Button variant="accent" onClick={onCrear} style={{ marginLeft: 'auto' }}>Reservar</Button>
        </div>
        {qr && (
          <div style={{ marginTop: 10, padding: 8, background: 'rgba(159,187,224,.20)', borderRadius: 'var(--radius-md)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
            QR generado: {qr}
          </div>
        )}
      </div>

      <h3 style={{ margin: '0 0 8px', fontSize: 13, fontWeight: 500, color: 'var(--fg-1)' }}>Reservas activas</h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {(reservas.data ?? []).length === 0 && (
          <div style={{ padding: 16, textAlign: 'center', color: 'var(--fg-3)', fontSize: 13 }}>Sin reservas</div>
        )}
        {(reservas.data ?? []).map((r) => (
          <div key={r.id_evento_reserva} style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '8px 10px', background: 'var(--surface-200)', borderRadius: 'var(--radius-md)',
            opacity: r.estado_codigo === 'cancelada' ? 0.55 : 1,
          }}>
            <div>
              <div style={{ fontSize: 13 }}>
                <strong>{r.ciudadano_apellido}, {r.ciudadano_nombre}</strong>
                <span style={{ color: 'var(--fg-3)', marginLeft: 6, fontFamily: 'var(--font-mono)', fontSize: 11 }}>· {r.estado_codigo}</span>
              </div>
              {r.qr_codigo && <div style={{ fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>{r.qr_codigo}</div>}
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              {r.estado_codigo !== 'asistio' && r.estado_codigo !== 'cancelada' && (
                <button onClick={() => onAsistio(r.id_evento_reserva)} aria-label="Marcar asistencia" style={iconBtn}>
                  <CheckCircle size={14} strokeWidth={1.5} />
                </button>
              )}
              {r.estado_codigo !== 'cancelada' && (
                <button onClick={() => setConfirmCancelId(r.id_evento_reserva)} aria-label="Cancelar reserva" style={iconBtn}>
                  <XIcon size={14} strokeWidth={1.5} />
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
      <ConfirmModal
        open={confirmCancelId != null}
        title="Cancelar reserva"
        message="Cancelar esta reserva? Libera el cupo del evento."
        confirmLabel="Cancelar reserva"
        danger
        onConfirm={() => confirmCancelId != null && doCancelar(confirmCancelId)}
        onCancel={() => setConfirmCancelId(null)}
      />
    </Modal>
  )
}

const inp: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: 13,
  padding: '6px 10px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-primary)',
  background: 'var(--surface-100)', outline: 'none',
}

const iconBtn: React.CSSProperties = {
  background: 'transparent', border: 'none', cursor: 'pointer',
  color: 'var(--fg-2)', padding: 6, borderRadius: 'var(--radius-md)',
}
