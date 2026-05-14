// Pagina publica de autoservicio de Turnos.
// Path: /turnos-autoservicio
//
// Flujo de 4 pasos: tipo de servicio -> agente -> slot libre -> datos del
// ciudadano. Al reservar redirige a /turno/:tokenTurno (MiTurnoPage).
// SIN AppShell, SIN JWT — el ciudadano final llega via link compartible.
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  getTiposServicioTurno,
  getAgentesTurno,
  getSlotsTurno,
  postTurnoPublico,
  type TipoServicioTurno,
  type AgenteDisponible,
  type SlotLibre,
} from './api'
import { layoutStyles as s, ZarisMark } from './shared'

function formatFechaLarga(iso: string): string {
  const d = new Date(iso + 'T12:00:00')
  return d.toLocaleDateString('es-AR', { weekday: 'long', day: '2-digit', month: 'long' })
}
function formatHora(t: string): string {
  return t.slice(0, 5)
}

type Paso = 'tipo' | 'agente' | 'slot' | 'datos'

export function TurnosPage() {
  const navigate = useNavigate()
  const [paso, setPaso] = useState<Paso>('tipo')

  // Catalogos
  const [tipos, setTipos] = useState<TipoServicioTurno[]>([])
  const [agentes, setAgentes] = useState<AgenteDisponible[]>([])
  const [slots, setSlots] = useState<SlotLibre[]>([])

  // Seleccion
  const [tipo, setTipo] = useState<TipoServicioTurno | null>(null)
  const [agente, setAgente] = useState<AgenteDisponible | null>(null) // null = cualquiera
  const [slot, setSlot] = useState<SlotLibre | null>(null)

  // Datos del ciudadano
  const [dni, setDni] = useState('')
  const [apellido, setApellido] = useState('')
  const [nombre, setNombre] = useState('')
  const [telefono, setTelefono] = useState('')
  const [email, setEmail] = useState('')

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  // Carga inicial de catalogos
  useEffect(() => {
    let cancel = false
    setLoading(true); setError(null)
    Promise.all([getTiposServicioTurno(), getAgentesTurno()])
      .then(([t, a]) => {
        if (cancel) return
        setTipos(t)
        setAgentes(a)
      })
      .catch((e: Error) => { if (!cancel) setError(e.message) })
      .finally(() => { if (!cancel) setLoading(false) })
    return () => { cancel = true }
  }, [])

  // Carga de slots al entrar al paso 'slot'
  useEffect(() => {
    if (paso !== 'slot' || !tipo) return
    let cancel = false
    setLoading(true); setError(null); setSlots([])
    getSlotsTurno({
      id_tipo_servicio_turno: tipo.id_tipo_servicio_turno,
      id_agente: agente?.id_agente,
      dias: 14,
    })
      .then((sl) => { if (!cancel) setSlots(sl) })
      .catch((e: Error) => { if (!cancel) setError(e.message) })
      .finally(() => { if (!cancel) setLoading(false) })
    return () => { cancel = true }
  }, [paso, tipo, agente])

  // Slots agrupados por fecha para render
  const slotsPorFecha = useMemo(() => {
    const m = new Map<string, SlotLibre[]>()
    for (const sl of slots) {
      const arr = m.get(sl.fecha) ?? []
      arr.push(sl)
      m.set(sl.fecha, arr)
    }
    return [...m.entries()].sort(([a], [b]) => a.localeCompare(b))
  }, [slots])

  async function doReservar() {
    if (!tipo || !slot) return
    setEnviando(true); setError(null)
    try {
      const turno = await postTurnoPublico({
        id_tipo_servicio_turno: tipo.id_tipo_servicio_turno,
        id_agente: slot.id_agente,
        fecha: slot.fecha,
        hora_inicio: slot.hora_inicio,
        dni: dni.trim(),
        apellido: apellido.trim(),
        nombre: nombre.trim(),
        telefono: telefono.trim() || undefined,
        email: email.trim() || undefined,
      })
      navigate(`/turno/${turno.token_turno}`)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setEnviando(false)
    }
  }

  const datosValidos = dni.trim().length >= 6 && apellido.trim() && nombre.trim()

  return (
    <Shell>
      <h1 style={s.h1}>Reservar un turno</h1>
      <p style={s.desc}>Eleg&iacute; el tr&aacute;mite, el d&iacute;a y completa tus datos.</p>

      <StepIndicator paso={paso} />

      {loading && <div style={s.center}>Cargando&hellip;</div>}

      {/* PASO 1: tipo de servicio */}
      {!loading && paso === 'tipo' && (
        <div>
          <h2 style={s.h2}>&iquest;Qu&eacute; tr&aacute;mite necesit&aacute;s?</h2>
          {tipos.length === 0 && <div style={s.warn}>No hay tr&aacute;mites disponibles en este momento.</div>}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 12 }}>
            {tipos.map((t) => (
              <button
                key={t.id_tipo_servicio_turno}
                style={optionBtn}
                onClick={() => { setTipo(t); setAgente(null); setSlot(null); setPaso('agente') }}
              >
                <div style={{ fontWeight: 600, fontSize: 15 }}>{t.nombre}</div>
                {t.descripcion && <div style={{ fontSize: 13, color: 'var(--fg-2)', marginTop: 2 }}>{t.descripcion}</div>}
                <div style={{ fontSize: 12, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
                  Duraci&oacute;n: {t.duracion_min} min
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* PASO 2: agente */}
      {!loading && paso === 'agente' && tipo && (
        <div>
          <h2 style={s.h2}>&iquest;Con qui&eacute;n quer&eacute;s ser atendido?</h2>
          <p style={{ ...s.desc, marginBottom: 12 }}>Tr&aacute;mite: <strong>{tipo.nombre}</strong></p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <button style={optionBtn} onClick={() => { setAgente(null); setSlot(null); setPaso('slot') }}>
              <div style={{ fontWeight: 600, fontSize: 15 }}>Cualquier agente disponible</div>
              <div style={{ fontSize: 13, color: 'var(--fg-2)', marginTop: 2 }}>Te mostramos todos los horarios libres</div>
            </button>
            {agentes.map((a) => (
              <button
                key={a.id_agente}
                style={optionBtn}
                onClick={() => { setAgente(a); setSlot(null); setPaso('slot') }}
              >
                <div style={{ fontWeight: 600, fontSize: 15 }}>{a.nombre}</div>
              </button>
            ))}
          </div>
          <button style={backBtn} onClick={() => setPaso('tipo')}>&larr; Cambiar tr&aacute;mite</button>
        </div>
      )}

      {/* PASO 3: slot */}
      {!loading && paso === 'slot' && tipo && (
        <div>
          <h2 style={s.h2}>Eleg&iacute; d&iacute;a y horario</h2>
          {slotsPorFecha.length === 0 && (
            <div style={s.warn}>No hay horarios disponibles en los pr&oacute;ximos 14 d&iacute;as.</div>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 12 }}>
            {slotsPorFecha.map(([fecha, sl]) => (
              <div key={fecha}>
                <div style={{
                  fontSize: 13, color: 'var(--fg-2)', textTransform: 'capitalize',
                  fontWeight: 600, marginBottom: 6,
                }}>
                  {formatFechaLarga(fecha)}
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {sl.map((slk) => (
                    <button
                      key={`${slk.id_agente}-${slk.hora_inicio}`}
                      style={slotBtn}
                      onClick={() => { setSlot(slk); setPaso('datos') }}
                      title={agente ? undefined : slk.agente_nombre}
                    >
                      {formatHora(slk.hora_inicio)}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <button style={backBtn} onClick={() => setPaso('agente')}>&larr; Cambiar agente</button>
        </div>
      )}

      {/* PASO 4: datos del ciudadano */}
      {!loading && paso === 'datos' && tipo && slot && (
        <div>
          <h2 style={s.h2}>Completa tus datos</h2>
          <div style={{ ...s.metaRow, marginBottom: 18 }}>
            <div style={s.metaCell}>
              <div style={s.metaLabel}>Tr&aacute;mite</div>
              <div style={s.metaValue}>{tipo.nombre}</div>
            </div>
            <div style={s.metaCell}>
              <div style={s.metaLabel}>D&iacute;a</div>
              <div style={{ ...s.metaValue, textTransform: 'capitalize' }}>{formatFechaLarga(slot.fecha)}</div>
            </div>
            <div style={s.metaCell}>
              <div style={s.metaLabel}>Horario</div>
              <div style={s.metaValue}>{formatHora(slot.hora_inicio)} &ndash; {formatHora(slot.hora_fin)}</div>
            </div>
            <div style={s.metaCell}>
              <div style={s.metaLabel}>Agente</div>
              <div style={s.metaValue}>{slot.agente_nombre}</div>
            </div>
          </div>

          <div style={s.formGrid}>
            <Field label="DNI *">
              <input style={s.input} value={dni} onChange={(e) => setDni(e.target.value)}
                inputMode="numeric" placeholder="Sin puntos" />
            </Field>
            <Field label="Telefono">
              <input style={s.input} value={telefono} onChange={(e) => setTelefono(e.target.value)}
                inputMode="tel" />
            </Field>
            <Field label="Apellido *">
              <input style={s.input} value={apellido} onChange={(e) => setApellido(e.target.value)} />
            </Field>
            <Field label="Nombre *">
              <input style={s.input} value={nombre} onChange={(e) => setNombre(e.target.value)} />
            </Field>
            <div style={{ gridColumn: '1 / -1' }}>
              <Field label="Email">
                <input style={s.input} value={email} onChange={(e) => setEmail(e.target.value)}
                  inputMode="email" />
              </Field>
            </div>
          </div>

          <button
            style={{ ...s.submit, opacity: datosValidos && !enviando ? 1 : 0.55, cursor: datosValidos && !enviando ? 'pointer' : 'not-allowed' }}
            onClick={doReservar}
            disabled={!datosValidos || enviando}
          >
            {enviando ? 'Reservando...' : 'Confirmar turno'}
          </button>
          <button style={backBtn} onClick={() => setPaso('slot')}>&larr; Cambiar horario</button>
        </div>
      )}

      {error && <div style={s.err}>{error}</div>}
    </Shell>
  )
}

function StepIndicator({ paso }: { paso: Paso }) {
  const pasos: { key: Paso }[] = [
    { key: 'tipo' }, { key: 'agente' }, { key: 'slot' }, { key: 'datos' },
  ]
  const idx = pasos.findIndex((p) => p.key === paso)
  return (
    <div style={{ display: 'flex', gap: 6, marginBottom: 20 }}>
      {pasos.map((p, i) => (
        <div
          key={p.key}
          style={{
            flex: 1, height: 4, borderRadius: 2,
            background: i <= idx ? 'var(--zaris-orange)' : 'var(--surface-300)',
          }}
        />
      ))}
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
      <span style={s.fieldLabel}>{label}</span>
      {children}
    </label>
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

const optionBtn: React.CSSProperties = {
  textAlign: 'left',
  padding: '14px 16px',
  background: 'var(--surface-100)',
  border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-md)',
  cursor: 'pointer',
  fontFamily: 'var(--font-display)',
  color: 'var(--fg-1)',
}

const slotBtn: React.CSSProperties = {
  padding: '8px 14px',
  background: 'var(--surface-100)',
  border: '1px solid var(--border-medium)',
  borderRadius: 'var(--radius-md)',
  cursor: 'pointer',
  fontFamily: 'var(--font-mono)',
  fontSize: 13,
  color: 'var(--fg-1)',
}

const backBtn: React.CSSProperties = {
  marginTop: 16,
  background: 'transparent',
  border: 'none',
  color: 'var(--fg-3)',
  fontFamily: 'var(--font-display)',
  fontSize: 13,
  cursor: 'pointer',
  padding: 0,
}
