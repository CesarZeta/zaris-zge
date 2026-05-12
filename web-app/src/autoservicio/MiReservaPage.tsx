// Pagina "Mi reserva" — vista posterior al alta de la reserva publica.
// Path: /autoservicio/:tokenPublico/reserva/:tokenReserva
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getReservaPublica, deleteReservaPublica, type ReservaPublica } from './api'
import { layoutStyles as s, ZarisMark } from './shared'
import { QRDisplay } from '../modules/agenda/components/QRDisplay'

function formatFecha(iso: string): string {
  const d = new Date(iso + 'T12:00:00')
  return d.toLocaleDateString('es-AR', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' })
}
function formatHora(t: string): string {
  return t.slice(0, 5)
}

export function MiReservaPage() {
  const { tokenReserva = '' } = useParams<{ tokenPublico: string; tokenReserva: string }>()
  const [reserva, setReserva] = useState<ReservaPublica | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [confirmCancel, setConfirmCancel] = useState(false)
  const [cancelando, setCancelando] = useState(false)

  useEffect(() => {
    let cancel = false
    setLoading(true); setError(null)
    getReservaPublica(tokenReserva)
      .then((r) => { if (!cancel) setReserva(r) })
      .catch((e: Error) => { if (!cancel) setError(e.message) })
      .finally(() => { if (!cancel) setLoading(false) })
    return () => { cancel = true }
  }, [tokenReserva])

  async function doCancelar() {
    setCancelando(true)
    try {
      const r = await deleteReservaPublica(tokenReserva)
      setReserva(r)
      setConfirmCancel(false)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setCancelando(false)
    }
  }

  if (loading) return <Shell><div style={s.center}>Cargando reserva…</div></Shell>
  if (error || !reserva) {
    return (
      <Shell>
        <div style={s.center}>
          <h2 style={{ margin: 0, fontFamily: 'var(--font-display)' }}>Reserva no encontrada</h2>
          <p style={{ color: 'var(--fg-2)', marginTop: 10 }}>
            {error ?? 'Verifica el link que recibiste.'}
          </p>
        </div>
      </Shell>
    )
  }

  const cancelada = reserva.estado_codigo === 'cancelada'
  const asistio = reserva.estado_codigo === 'asistio'

  return (
    <Shell>
      <h1 style={s.h1}>{reserva.evento.nombre}</h1>
      <p style={s.desc}>
        {cancelada ? 'Tu reserva fue cancelada.' : asistio ? 'Asistencia registrada. Gracias!' : 'Tu reserva esta confirmada.'}
      </p>

      <div style={s.metaRow}>
        <div style={s.metaCell}>
          <div style={s.metaLabel}>Fecha</div>
          <div style={s.metaValue}>{formatFecha(reserva.evento.fecha)}</div>
        </div>
        <div style={s.metaCell}>
          <div style={s.metaLabel}>Horario</div>
          <div style={s.metaValue}>{formatHora(reserva.evento.hora_inicio)} – {formatHora(reserva.evento.hora_fin)}</div>
        </div>
        <div style={s.metaCell}>
          <div style={s.metaLabel}>Estado</div>
          <div style={{ ...s.metaValue, color: cancelada ? 'var(--color-error)' : asistio ? 'var(--zaris-orange)' : 'var(--fg-1)' }}>
            {reserva.estado_codigo}
          </div>
        </div>
      </div>

      <div style={{ marginTop: 22, padding: 16, background: 'var(--surface-200)', borderRadius: 'var(--radius-md)' }}>
        <h2 style={s.h2}>A nombre de</h2>
        <div style={{ fontSize: 14, color: 'var(--fg-1)' }}>
          {reserva.ciudadano_apellido}, {reserva.ciudadano_nombre}
        </div>
        {reserva.ciudadano_dni && (
          <div style={{ fontSize: 12, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
            DNI {reserva.ciudadano_dni}
          </div>
        )}
      </div>

      {reserva.qr_codigo && !cancelada && (
        <div style={{ marginTop: 22, padding: 18, background: 'var(--surface-200)', borderRadius: 'var(--radius-md)', textAlign: 'center' }}>
          <h2 style={{ ...s.h2, textAlign: 'left' }}>Tu codigo de ingreso</h2>
          <p style={{ color: 'var(--fg-3)', fontSize: 13, margin: '0 0 12px', textAlign: 'left' }}>
            Mostralo al ingresar al evento. Lo van a escanear para acreditar tu asistencia.
          </p>
          <div style={{ display: 'inline-block' }}>
            <QRDisplay value={reserva.qr_codigo} size={180} showText />
          </div>
        </div>
      )}

      {!cancelada && !asistio && (
        <>
          {!confirmCancel ? (
            <button onClick={() => setConfirmCancel(true)} style={cancelBtn}>Cancelar mi reserva</button>
          ) : (
            <div style={confirmBox}>
              <div style={{ marginBottom: 10 }}>Seguro que queres cancelar la reserva?</div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button onClick={() => setConfirmCancel(false)} style={ghostBtn} disabled={cancelando}>Volver</button>
                <button onClick={doCancelar} style={dangerBtn} disabled={cancelando}>
                  {cancelando ? 'Cancelando…' : 'Si, cancelar'}
                </button>
              </div>
            </div>
          )}
        </>
      )}

      <div style={{ marginTop: 20, fontSize: 12, color: 'var(--fg-3)' }}>
        Guarda este link para volver a ver tu reserva.
      </div>
    </Shell>
  )
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div style={s.page}>
      <div style={s.brand}><ZarisMark /></div>
      <div style={s.card}>{children}</div>
      <div style={s.footer}>ZARIS · Gestion Estatal</div>
    </div>
  )
}

const cancelBtn: React.CSSProperties = {
  marginTop: 22,
  width: '100%',
  padding: '10px 14px',
  background: 'transparent',
  color: 'var(--color-error)',
  border: '1px solid var(--color-error)',
  borderRadius: 'var(--radius-md)',
  fontSize: 14,
  fontFamily: 'var(--font-display)',
  cursor: 'pointer',
}

const confirmBox: React.CSSProperties = {
  marginTop: 22,
  padding: 14,
  background: 'rgba(207,45,86,.08)',
  border: '1px solid rgba(207,45,86,.25)',
  borderRadius: 'var(--radius-md)',
}

const ghostBtn: React.CSSProperties = {
  padding: '8px 14px',
  background: 'transparent',
  color: 'var(--fg-1)',
  border: '1px solid var(--border-medium)',
  borderRadius: 'var(--radius-md)',
  fontFamily: 'var(--font-display)',
  fontSize: 13,
  cursor: 'pointer',
}

const dangerBtn: React.CSSProperties = {
  padding: '8px 14px',
  background: 'var(--color-error)',
  color: '#fff',
  border: 'none',
  borderRadius: 'var(--radius-md)',
  fontFamily: 'var(--font-display)',
  fontSize: 13,
  cursor: 'pointer',
}
