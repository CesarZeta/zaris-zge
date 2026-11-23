// Página pública de un evento: lo muestra y lleva al portal del vecino a reservar (desde el 2026-11-23
// la entrada exige la cuenta; antes se reservaba con solo el DNI). Sin AppShell, sin JWT.
// Path: /autoservicio/:tokenPublico
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getEventoPublico, type EventoPublico } from './api'
import { IrAlPortal, layoutStyles as s, ZarisMark } from './shared'

function formatFecha(iso: string): string {
  // YYYY-MM-DD -> "Lun 11 may 2026"
  const d = new Date(iso + 'T12:00:00')
  return d.toLocaleDateString('es-AR', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' })
}

function formatHora(t: string): string {
  return t.slice(0, 5)
}

export function AutoservicioPage() {
  const { tokenPublico = '' } = useParams<{ tokenPublico: string }>()
  const [evento, setEvento] = useState<EventoPublico | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancel = false
    setLoading(true); setError(null)
    getEventoPublico(tokenPublico)
      .then((e) => { if (!cancel) setEvento(e) })
      .catch((e: Error) => { if (!cancel) setError(e.message) })
      .finally(() => { if (!cancel) setLoading(false) })
    return () => { cancel = true }
  }, [tokenPublico])

  if (loading) {
    return <Shell><div style={s.center}>Cargando evento…</div></Shell>
  }

  if (error || !evento) {
    return (
      <Shell>
        <div style={s.center}>
          <h2 style={{ margin: 0, fontFamily: 'var(--font-display)' }}>Link no disponible</h2>
          <p style={{ color: 'var(--fg-2)', marginTop: 10 }}>
            El enlace puede haber expirado o el evento ya no está disponible.
          </p>
        </div>
      </Shell>
    )
  }

  return (
    <Shell>
      <h1 style={s.h1}>{evento.nombre}</h1>
      {evento.descripcion && <p style={s.desc}>{evento.descripcion}</p>}

      <div style={s.metaRow}>
        <div style={s.metaCell}>
          <div style={s.metaLabel}>Fecha</div>
          <div style={s.metaValue}>{formatFecha(evento.fecha)}</div>
        </div>
        <div style={s.metaCell}>
          <div style={s.metaLabel}>Horario</div>
          <div style={s.metaValue}>{formatHora(evento.hora_inicio)} – {formatHora(evento.hora_fin)}</div>
        </div>
        <div style={s.metaCell}>
          <div style={s.metaLabel}>Cupos disponibles</div>
          <div style={s.metaValue}>{evento.cupo_disponible}</div>
        </div>
      </div>

      {evento.cupo_disponible <= 0 ? (
        <div style={s.warn}>
          Este evento ya alcanzó su cupo máximo.
        </div>
      ) : (
        <IrAlPortal texto="La entrada se reserva desde el portal del vecino, con tu cuenta. Si todavía no la tenés, registrate: solo hace falta una vez." />
      )}
    </Shell>
  )
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div style={s.page}>
      <div style={s.brand}><ZarisMark /></div>
      <div style={s.card}>{children}</div>
      <div style={s.footer}>ZARIS · Gestión Estado</div>
    </div>
  )
}
