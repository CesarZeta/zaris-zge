// Pagina "Mi turno" — vista posterior a reservar un turno por autoservicio.
// Path: /turno/:tokenTurno
// SIN AppShell, SIN JWT — el ciudadano vuelve via el link compartible.
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getTurnoPublico, deleteTurnoPublico, type TurnoPublico } from './api'
import { layoutStyles as s, ZarisMark } from './shared'

function formatFecha(iso: string): string {
  const d = new Date(iso + 'T12:00:00')
  return d.toLocaleDateString('es-AR', { weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' })
}
function formatHora(t: string): string {
  return t.slice(0, 5)
}

export function MiTurnoPage() {
  const { tokenTurno = '' } = useParams<{ tokenTurno: string }>()
  const [turno, setTurno] = useState<TurnoPublico | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [confirmCancel, setConfirmCancel] = useState(false)
  const [cancelando, setCancelando] = useState(false)

  useEffect(() => {
    let cancel = false
    setLoading(true); setError(null)
    getTurnoPublico(tokenTurno)
      .then((t) => { if (!cancel) setTurno(t) })
      .catch((e: Error) => { if (!cancel) setError(e.message) })
      .finally(() => { if (!cancel) setLoading(false) })
    return () => { cancel = true }
  }, [tokenTurno])

  async function doCancelar() {
    setCancelando(true)
    try {
      const t = await deleteTurnoPublico(tokenTurno)
      setTurno(t)
      setConfirmCancel(false)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setCancelando(false)
    }
  }

  if (loading) return <Shell><div style={s.center}>Cargando turno...</div></Shell>
  if (error || !turno) {
    return (
      <Shell>
        <div style={s.center}>
          <h2 style={{ margin: 0, fontFamily: 'var(--font-display)' }}>Turno no encontrado</h2>
          <p style={{ color: 'var(--fg-2)', marginTop: 10 }}>
            {error ?? 'Verifica el link que recibiste.'}
          </p>
        </div>
      </Shell>
    )
  }

  const cancelado = turno.estado === 'cancelado'
  const cumplido = turno.estado === 'cumplido'

  return (
    <Shell>
      <h1 style={s.h1}>{turno.tipo_servicio_nombre ?? 'Turno'}</h1>
      <p style={s.desc}>
        {cancelado
          ? 'Tu turno fue cancelado.'
          : cumplido
          ? 'Turno atendido. Gracias!'
          : 'Tu turno esta confirmado.'}
      </p>

      <div style={s.metaRow}>
        <div style={s.metaCell}>
          <div style={s.metaLabel}>Fecha</div>
          <div style={{ ...s.metaValue, textTransform: 'capitalize' }}>{formatFecha(turno.fecha)}</div>
        </div>
        <div style={s.metaCell}>
          <div style={s.metaLabel}>Horario</div>
          <div style={s.metaValue}>{formatHora(turno.hora_inicio)} &ndash; {formatHora(turno.hora_fin)}</div>
        </div>
        <div style={s.metaCell}>
          <div style={s.metaLabel}>Agente</div>
          <div style={s.metaValue}>{turno.agente_nombre ?? '-'}</div>
        </div>
        <div style={s.metaCell}>
          <div style={s.metaLabel}>Estado</div>
          <div style={{ ...s.metaValue, color: cancelado ? 'var(--color-error)' : cumplido ? 'var(--zaris-orange)' : 'var(--fg-1)' }}>
            {turno.estado}
          </div>
        </div>
      </div>

      <div style={{ marginTop: 22, padding: 16, background: 'var(--surface-200)', borderRadius: 'var(--radius-md)' }}>
        <h2 style={s.h2}>A nombre de</h2>
        <div style={{ fontSize: 14, color: 'var(--fg-1)' }}>
          {turno.ciudadano_apellido}, {turno.ciudadano_nombre}
        </div>
        {turno.ciudadano_dni && (
          <div style={{ fontSize: 12, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
            DNI {turno.ciudadano_dni}
          </div>
        )}
      </div>

      {!cancelado && !cumplido && (
        <>
          {!confirmCancel ? (
            <button onClick={() => setConfirmCancel(true)} style={cancelBtn}>Cancelar mi turno</button>
          ) : (
            <div style={confirmBox}>
              <div style={{ marginBottom: 10 }}>Seguro que queres cancelar el turno?</div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button onClick={() => setConfirmCancel(false)} style={ghostBtn} disabled={cancelando}>Volver</button>
                <button onClick={doCancelar} style={dangerBtn} disabled={cancelando}>
                  {cancelando ? 'Cancelando...' : 'Si, cancelar'}
                </button>
              </div>
            </div>
          )}
        </>
      )}

      <div style={{ marginTop: 20, fontSize: 12, color: 'var(--fg-3)' }}>
        Guarda este link para volver a ver tu turno.
      </div>

      {error && <div style={s.err}>{error}</div>}
    </Shell>
  )
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div style={s.page}>
      <div style={s.brand}><ZarisMark /></div>
      <div style={s.card}>{children}</div>
      <div style={s.footer}>ZARIS &middot; Gestion Estatal</div>
    </div>
  )
}

const cancelBtn: React.CSSProperties = {
  marginTop: 22, width: '100%', padding: '10px 14px',
  background: 'transparent', color: 'var(--color-error)',
  border: '1px solid var(--color-error)', borderRadius: 'var(--radius-md)',
  fontSize: 14, fontFamily: 'var(--font-display)', cursor: 'pointer',
}
const confirmBox: React.CSSProperties = {
  marginTop: 22, padding: 14,
  background: 'rgba(207,45,86,.08)', border: '1px solid rgba(207,45,86,.25)',
  borderRadius: 'var(--radius-md)',
}
const ghostBtn: React.CSSProperties = {
  padding: '8px 14px', background: 'transparent', color: 'var(--fg-1)',
  border: '1px solid var(--border-medium)', borderRadius: 'var(--radius-md)',
  fontFamily: 'var(--font-display)', fontSize: 13, cursor: 'pointer',
}
const dangerBtn: React.CSSProperties = {
  padding: '8px 14px', background: 'var(--color-error)', color: '#fff',
  border: 'none', borderRadius: 'var(--radius-md)',
  fontFamily: 'var(--font-display)', fontSize: 13, cursor: 'pointer',
}
