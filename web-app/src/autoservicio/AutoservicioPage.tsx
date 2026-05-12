// Pagina publica de reserva por autoservicio. Sin AppShell, sin JWT.
// Path: /autoservicio/:tokenPublico
import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getEventoPublico, postReservaPublica, type EventoPublico, type ReservaPublicaCreate } from './api'
import { layoutStyles as s, ZarisMark } from './shared'

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
  const navigate = useNavigate()
  const [evento, setEvento] = useState<EventoPublico | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [form, setForm] = useState<ReservaPublicaCreate>({ dni: '', apellido: '', nombre: '', telefono: '', email: '' })
  const [submitError, setSubmitError] = useState<string | null>(null)

  useEffect(() => {
    let cancel = false
    setLoading(true); setError(null)
    getEventoPublico(tokenPublico)
      .then((e) => { if (!cancel) setEvento(e) })
      .catch((e: Error) => { if (!cancel) setError(e.message) })
      .finally(() => { if (!cancel) setLoading(false) })
    return () => { cancel = true }
  }, [tokenPublico])

  async function onSubmit(ev: React.FormEvent) {
    ev.preventDefault()
    setSubmitError(null)
    if (!form.dni || form.dni.replace(/\D/g, '').length < 6) {
      setSubmitError('DNI invalido: ingresa al menos 6 numeros'); return
    }
    if (!form.apellido.trim() || !form.nombre.trim()) {
      setSubmitError('Apellido y nombre son obligatorios'); return
    }
    setSubmitting(true)
    try {
      const payload: ReservaPublicaCreate = {
        dni: form.dni.replace(/\D/g, ''),
        apellido: form.apellido.trim(),
        nombre: form.nombre.trim(),
        telefono: form.telefono?.trim() || undefined,
        email: form.email?.trim() || undefined,
      }
      const r = await postReservaPublica(tokenPublico, payload)
      navigate(`/autoservicio/${tokenPublico}/reserva/${r.token_reserva}`, { replace: true })
    } catch (e) {
      setSubmitError((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return <Shell><div style={s.center}>Cargando evento…</div></Shell>
  }

  if (error || !evento) {
    return (
      <Shell>
        <div style={s.center}>
          <h2 style={{ margin: 0, fontFamily: 'var(--font-display)' }}>Link no disponible</h2>
          <p style={{ color: 'var(--fg-2)', marginTop: 10 }}>
            El enlace puede haber expirado o el evento ya no acepta reservas en linea.
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
          Este evento ya alcanzo su cupo maximo. No es posible reservar en linea.
        </div>
      ) : (
        <form onSubmit={onSubmit} style={{ marginTop: 24 }}>
          <h2 style={s.h2}>Tus datos</h2>
          <p style={{ color: 'var(--fg-3)', fontSize: 13, margin: '0 0 16px' }}>
            Necesitamos estos datos para registrar la reserva. Tu DNI es el unico requerido para validar la asistencia.
          </p>

          <div style={s.formGrid}>
            <Field label="DNI" required>
              <input
                style={s.input}
                inputMode="numeric"
                autoComplete="off"
                value={form.dni}
                onChange={(e) => setForm((f) => ({ ...f, dni: e.target.value }))}
                disabled={submitting}
              />
            </Field>
            <Field label="Apellido" required>
              <input
                style={s.input}
                autoComplete="family-name"
                value={form.apellido}
                onChange={(e) => setForm((f) => ({ ...f, apellido: e.target.value }))}
                disabled={submitting}
              />
            </Field>
            <Field label="Nombre" required>
              <input
                style={s.input}
                autoComplete="given-name"
                value={form.nombre}
                onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))}
                disabled={submitting}
              />
            </Field>
            <Field label="Telefono">
              <input
                style={s.input}
                inputMode="tel"
                autoComplete="tel"
                value={form.telefono ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, telefono: e.target.value }))}
                disabled={submitting}
              />
            </Field>
            <Field label="Email" full>
              <input
                style={s.input}
                type="email"
                autoComplete="email"
                value={form.email ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                disabled={submitting}
              />
            </Field>
          </div>

          {submitError && <div style={s.err}>{submitError}</div>}

          <button type="submit" style={s.submit} disabled={submitting}>
            {submitting ? 'Reservando…' : 'Confirmar reserva'}
          </button>
        </form>
      )}
    </Shell>
  )
}

function Field({ label, required, children, full }: { label: string; required?: boolean; children: React.ReactNode; full?: boolean }) {
  return (
    <label style={{ gridColumn: full ? '1 / -1' : undefined, display: 'flex', flexDirection: 'column', gap: 6 }}>
      <span style={s.fieldLabel}>{label}{required && <span style={{ color: 'var(--color-error)', marginLeft: 4 }}>*</span>}</span>
      {children}
    </label>
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
