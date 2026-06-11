// Recepcion de llamado (plan 5.1): carga rapida con cronometro, identificacion
// del denunciante (anonimo / BUC / contacto eventual / alta al vuelo) y datos
// del evento con prioridad autocompletada por tipo/subtipo.
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '../../../ui'
import { AddressSearch } from '../../../ui/AddressSearch'
import { useNotificationsStore } from '../../../stores/notifications'
import { GeocodingSearch } from '../../reclamos/components/GeocodingSearch'
import { buscarDenunciante } from '../api/emergenciasApi'
import {
  useCanalesEmergencia,
  useCrearContactoEventual,
  useCrearEvento,
  usePrioridadesEmergencia,
  useSubtiposDeTipo,
  useTiposEmergencia,
} from '../hooks/useEmergencias'
import type { CiudadanoBucMatch, ContactoEventual, DenuncianteBusqueda } from '../types'
import { useCronometro } from '../lib/ui'

type DenuncianteSel =
  | { clase: 'buc'; ciudadano: CiudadanoBucMatch }
  | { clase: 'eventual'; contacto: ContactoEventual }

export function Recepcion() {
  const navigate = useNavigate()
  const push = useNotificationsStore((s) => s.push)
  const crono = useCronometro()

  // ---- denunciante ----
  const [anonimo, setAnonimo] = useState(false)
  const [qDni, setQDni] = useState('')
  const [qTel, setQTel] = useState('')
  const [qNombre, setQNombre] = useState('')
  const [busqueda, setBusqueda] = useState<DenuncianteBusqueda | null>(null)
  const [buscando, setBuscando] = useState(false)
  const [sel, setSel] = useState<DenuncianteSel | null>(null)

  // alta de contacto eventual (origen NUEVO)
  const [nuevo, setNuevo] = useState({ dni: '', nombre_apellido: '', telefono: '', direccion: '', contacto_alt_nombre: '', contacto_alt_telefono: '' })
  const crearContacto = useCrearContactoEventual()

  // ---- evento ----
  const tipos = useTiposEmergencia()
  const prioridades = usePrioridadesEmergencia()
  const canales = useCanalesEmergencia()
  const [idSubarea, setIdSubarea] = useState<number | ''>('')
  const [idTipo, setIdTipo] = useState<number | ''>('')
  const [idSubtipo, setIdSubtipo] = useState<number | ''>('')
  const [idPrioridad, setIdPrioridad] = useState<number | ''>('')
  const [prioridadTocada, setPrioridadTocada] = useState(false)
  const [direccion, setDireccion] = useState('')
  const [latitud, setLatitud] = useState<number | null>(null)
  const [longitud, setLongitud] = useState<number | null>(null)
  const [referencia, setReferencia] = useState('')
  const [obs, setObs] = useState('')
  const [grabarAudio, setGrabarAudio] = useState(false)
  const subtipos = useSubtiposDeTipo(idTipo === '' ? null : idTipo)
  const crear = useCrearEvento()

  const subareas = useMemo(() => {
    const m = new Map<number, string>()
    for (const t of tipos.data ?? []) m.set(t.id_subarea, t.subarea_nombre ?? `Subárea ${t.id_subarea}`)
    return [...m.entries()].sort((a, b) => a[1].localeCompare(b[1]))
  }, [tipos.data])

  const tiposDeSubarea = useMemo(
    () => (tipos.data ?? []).filter((t) => idSubarea !== '' && t.id_subarea === idSubarea),
    [tipos.data, idSubarea],
  )
  const tipoSel = tiposDeSubarea.find((t) => t.id_emergencia_tipo === idTipo)
  const subtipoSel = (subtipos.data ?? []).find((s) => s.id_emergencia_subtipo === idSubtipo)

  // prioridad autocompletada: subtipo.override > tipo.default (editable por el operador)
  const prioridadEfectiva = prioridadTocada
    ? idPrioridad
    : (subtipoSel?.id_prioridad_override ?? tipoSel?.id_prioridad_default ?? '')

  const buscar = async (criterio: 'dni' | 'telefono' | 'nombre', valor: string) => {
    if (!valor.trim()) return
    setBuscando(true)
    setSel(null)
    try {
      const r = await buscarDenunciante(criterio, valor.trim())
      setBusqueda(r)
      if (r.origen === 'NUEVO') {
        setNuevo((n) => ({ ...n, dni: criterio === 'dni' ? valor.trim() : n.dni, telefono: criterio === 'telefono' ? valor.trim() : n.telefono }))
      }
    } catch (e) {
      push({ kind: 'error', title: 'Error buscando denunciante', body: e instanceof Error ? e.message : String(e) })
    } finally {
      setBuscando(false)
    }
  }

  const registrarYUsar = () => {
    const { dni, nombre_apellido, telefono, direccion: dir } = nuevo
    if (!dni || !nombre_apellido || !telefono || !dir) {
      push({ kind: 'error', title: 'Faltan datos del contacto', body: 'DNI, nombre y apellido, teléfono y dirección son obligatorios.' })
      return
    }
    crearContacto.mutate(
      {
        dni, nombre_apellido, telefono, direccion: dir,
        contacto_alt_nombre: nuevo.contacto_alt_nombre || undefined,
        contacto_alt_telefono: nuevo.contacto_alt_telefono || undefined,
      },
      {
        onSuccess: (c) => {
          setSel({ clase: 'eventual', contacto: c })
          setBusqueda(null)
          push({ kind: 'success', title: 'Contacto eventual registrado', body: c.nombre_apellido })
        },
        onError: (e) => push({ kind: 'error', title: 'No se pudo registrar el contacto', body: e instanceof Error ? e.message : String(e) }),
      },
    )
  }

  const canalLlamada = (canales.data ?? []).find((c) => c.codigo === 'LLAMADA_TEL')
  const minimosCompletos =
    idSubarea !== '' && idTipo !== '' && prioridadEfectiva !== '' && direccion.trim().length >= 3 &&
    (anonimo || sel != null) && canalLlamada != null

  const crearEvento = () => {
    if (!minimosCompletos || !canalLlamada) return
    crear.mutate(
      {
        id_subarea: idSubarea as number,
        id_tipo: idTipo as number,
        id_subtipo: idSubtipo === '' ? undefined : idSubtipo,
        id_prioridad: prioridadEfectiva as number,   // el guard minimosCompletos ya lo exige
        id_canal_ingreso: canalLlamada.id_emergencia_canal_ingreso,
        denunciante_anonimo: anonimo,
        id_ciudadano_buc: !anonimo && sel?.clase === 'buc' ? sel.ciudadano.id_ciudadano : undefined,
        id_contacto_eventual: !anonimo && sel?.clase === 'eventual' ? sel.contacto.id_emergencia_contacto_eventual : undefined,
        direccion_evento: direccion.trim(),
        latitud: latitud ?? undefined,
        longitud: longitud ?? undefined,
        referencia_ubicacion: referencia.trim() || undefined,
        observaciones_recepcion: obs.trim() || undefined,
      },
      {
        onSuccess: (ev) => {
          push({ kind: 'success', title: `Evento ${ev.numero_operativo} creado`, body: `${ev.tipo_nombre} · prioridad ${ev.prioridad_codigo}` })
          navigate(`/emergencias/evento/${ev.id_emergencia_evento}`)
        },
        onError: (e) => push({ kind: 'error', title: 'No se pudo crear el evento', body: e instanceof Error ? e.message : String(e) }),
      },
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* header con cronometro */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: '1.1rem', color: 'var(--fg-1)' }}>
          Recepción de llamado
        </h2>
        <span style={{
          marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: 18, fontWeight: 700,
          color: 'var(--zaris-orange)', border: '1px solid var(--border-medium)',
          borderRadius: 8, padding: '4px 12px', background: 'var(--surface-100)',
        }}>
          {crono}
        </span>
      </div>

      {/* BLOQUE 1 - DENUNCIANTE */}
      <section style={bloque}>
        <div style={bloqueTitulo}>1 · Denunciante</div>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14, color: 'var(--fg-1)', marginBottom: 10 }}>
          <input type="checkbox" checked={anonimo} onChange={(e) => { setAnonimo(e.target.checked); if (e.target.checked) { setSel(null); setBusqueda(null) } }} />
          Denunciante anónimo
        </label>

        {!anonimo && (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10 }}>
              <CampoBusqueda label="DNI" value={qDni} onChange={setQDni} onBuscar={() => buscar('dni', qDni)} busy={buscando} />
              <CampoBusqueda label="Teléfono" value={qTel} onChange={setQTel} onBuscar={() => buscar('telefono', qTel)} busy={buscando} />
              <CampoBusqueda label="Nombre" value={qNombre} onChange={setQNombre} onBuscar={() => buscar('nombre', qNombre)} busy={buscando} />
            </div>

            {sel && (
              <div style={seleccionado}>
                {sel.clase === 'buc' ? (
                  <>Ciudadano BUC: <strong>{sel.ciudadano.apellido}, {sel.ciudadano.nombre}</strong> · DNI {sel.ciudadano.doc_nro} · {sel.ciudadano.telefono ?? 'sin teléfono'}</>
                ) : (
                  <>Contacto eventual: <strong>{sel.contacto.nombre_apellido}</strong> · DNI {sel.contacto.dni} · {sel.contacto.telefono}</>
                )}
                <button style={quitarBtn} onClick={() => setSel(null)}>cambiar</button>
              </div>
            )}

            {!sel && busqueda?.origen === 'BUC' && (
              <ResultadoLista titulo={`Encontrado en la BUC (${busqueda.matches.length})`}>
                {busqueda.matches.map((c) => (
                  <ResultadoItem
                    key={c.id_ciudadano}
                    principal={`${c.apellido}, ${c.nombre}`}
                    secundario={`DNI ${c.doc_nro} · ${c.telefono ?? 'sin tel.'} · ${[c.calle, c.altura, c.localidad].filter(Boolean).join(' ') || 'sin domicilio'}`}
                    cta="Usar este ciudadano"
                    onUsar={() => { setSel({ clase: 'buc', ciudadano: c }); setBusqueda(null) }}
                  />
                ))}
              </ResultadoLista>
            )}

            {!sel && busqueda?.origen === 'EVENTUAL' && (
              <ResultadoLista titulo={`Contacto eventual previo (${busqueda.matches.length})`}>
                {busqueda.matches.map((c) => (
                  <ResultadoItem
                    key={c.id_emergencia_contacto_eventual}
                    principal={c.nombre_apellido}
                    secundario={`DNI ${c.dni} · ${c.telefono} · ${c.direccion}`}
                    cta="Usar este contacto"
                    onUsar={() => { setSel({ clase: 'eventual', contacto: c }); setBusqueda(null) }}
                  />
                ))}
              </ResultadoLista>
            )}

            {!sel && busqueda?.origen === 'NUEVO' && (
              <div style={{ marginTop: 12 }}>
                <div style={{ fontSize: 13, color: 'var(--fg-2)', marginBottom: 8 }}>
                  No está en la BUC ni en contactos previos. Registrar contacto eventual:
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10 }}>
                  <CampoTexto label="DNI *" value={nuevo.dni} onChange={(v) => setNuevo({ ...nuevo, dni: v })} />
                  <CampoTexto label="Nombre y apellido *" value={nuevo.nombre_apellido} onChange={(v) => setNuevo({ ...nuevo, nombre_apellido: v })} />
                  <CampoTexto label="Teléfono *" value={nuevo.telefono} onChange={(v) => setNuevo({ ...nuevo, telefono: v })} />
                  <CampoTexto label="Contacto alternativo (nombre)" value={nuevo.contacto_alt_nombre} onChange={(v) => setNuevo({ ...nuevo, contacto_alt_nombre: v })} />
                  <CampoTexto label="Contacto alternativo (teléfono)" value={nuevo.contacto_alt_telefono} onChange={(v) => setNuevo({ ...nuevo, contacto_alt_telefono: v })} />
                </div>
                <div style={{ marginTop: 10 }}>
                  <label style={lbl}>Dirección * — buscar en OpenStreetMap</label>
                  <AddressSearch
                    placeholder="Tipeá calle, altura y localidad y elegí una sugerencia"
                    onPick={(_norm, raw) => setNuevo((n) => ({ ...n, direccion: raw.display_name ?? '' }))}
                  />
                  <input
                    style={{ ...inp, marginTop: 6 }}
                    value={nuevo.direccion}
                    onChange={(e) => setNuevo({ ...nuevo, direccion: e.target.value })}
                    placeholder="Dirección normalizada (editable si OSM no la encuentra)"
                  />
                </div>
                <div style={{ marginTop: 10 }}>
                  <Button variant="accent" disabled={crearContacto.isPending} onClick={registrarYUsar}>
                    Registrar y usar
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </section>

      {/* BLOQUE 2 - EVENTO */}
      <section style={bloque}>
        <div style={bloqueTitulo}>2 · Evento</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10 }}>
          <div>
            <label style={lbl}>Subárea *</label>
            <select style={inp} value={idSubarea} onChange={(e) => {
              setIdSubarea(e.target.value ? Number(e.target.value) : '')
              setIdTipo(''); setIdSubtipo(''); setPrioridadTocada(false)
            }}>
              <option value="">Elegir...</option>
              {subareas.map(([id, nombre]) => <option key={id} value={id}>{nombre}</option>)}
            </select>
          </div>
          <div>
            <label style={lbl}>Tipo *</label>
            <select style={inp} value={idTipo} disabled={idSubarea === ''} onChange={(e) => {
              setIdTipo(e.target.value ? Number(e.target.value) : '')
              setIdSubtipo(''); setPrioridadTocada(false)
            }}>
              <option value="">Elegir...</option>
              {tiposDeSubarea.map((t) => <option key={t.id_emergencia_tipo} value={t.id_emergencia_tipo}>{t.nombre}</option>)}
            </select>
          </div>
          <div>
            <label style={lbl}>Subtipo</label>
            <select style={inp} value={idSubtipo} disabled={idTipo === ''} onChange={(e) => {
              setIdSubtipo(e.target.value ? Number(e.target.value) : ''); setPrioridadTocada(false)
            }}>
              <option value="">(sin subtipo)</option>
              {(subtipos.data ?? []).map((s) => <option key={s.id_emergencia_subtipo} value={s.id_emergencia_subtipo}>{s.nombre}</option>)}
            </select>
          </div>
          <div>
            <label style={lbl}>Prioridad * {!prioridadTocada && tipoSel ? '(auto)' : ''}</label>
            <select style={inp} value={prioridadEfectiva} onChange={(e) => {
              setPrioridadTocada(true); setIdPrioridad(e.target.value ? Number(e.target.value) : '')
            }}>
              <option value="">Elegir...</option>
              {(prioridades.data ?? []).map((p) => (
                <option key={p.id_emergencia_prioridad} value={p.id_emergencia_prioridad}>
                  {p.codigo} — {p.nombre} (SLA {p.sla_minutos_arribo} min)
                </option>
              ))}
            </select>
          </div>
        </div>

        {tipoSel?.requiere_911 && (
          <div style={{
            marginTop: 10, padding: '8px 12px', borderRadius: 8, fontSize: 13, fontWeight: 600,
            color: '#c62828', border: '1px solid #c62828', background: 'var(--surface-100)',
          }}>
            Este tipo requiere aviso al 911 provincial.
          </div>
        )}

        <div style={{ marginTop: 10 }}>
          <label style={lbl}>Buscar dirección del evento (OpenStreetMap)</label>
          <GeocodingSearch
            placeholder="Tipeá calle y altura (o un lugar: club, plaza, comercio) y elegí una sugerencia"
            onPick={(r) => {
              setDireccion(r.display_name ?? '')
              setLatitud(r.lat)
              setLongitud(r.lon)
            }}
          />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 10, marginTop: 10 }}>
          <div>
            <label style={lbl}>Dirección del evento *</label>
            <input
              style={inp}
              value={direccion}
              onChange={(e) => { setDireccion(e.target.value); setLatitud(null); setLongitud(null) }}
              placeholder="Calle y altura / intersección"
            />
            <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 3, fontFamily: 'var(--font-mono)' }}>
              {latitud != null && longitud != null
                ? `Coordenadas OSM: ${latitud.toFixed(6)}, ${longitud.toFixed(6)}`
                : 'Sin coordenadas — buscá arriba para normalizar y georreferenciar'}
            </div>
          </div>
          <div>
            <label style={lbl}>Referencia de ubicación</label>
            <input style={inp} value={referencia} onChange={(e) => setReferencia(e.target.value)} placeholder="Ej: frente a la plaza" />
          </div>
        </div>
        <div style={{ marginTop: 10 }}>
          <label style={lbl}>Observaciones</label>
          <textarea style={{ ...inp, minHeight: 70, resize: 'vertical' }} value={obs} onChange={(e) => setObs(e.target.value)} placeholder="Relato del denunciante / datos para el despacho..." />
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--fg-3)', marginTop: 10 }}>
          <input type="checkbox" checked={grabarAudio} onChange={(e) => setGrabarAudio(e.target.checked)} disabled />
          Grabar audio del llamado (integración futura)
        </label>
      </section>

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
        <Button variant="ghost" onClick={() => navigate('/emergencias')}>Cancelar</Button>
        <Button variant="accent" disabled={!minimosCompletos || crear.isPending} onClick={crearEvento}>
          Crear evento
        </Button>
      </div>
    </div>
  )
}

// ---- piezas locales ----
function CampoBusqueda({ label, value, onChange, onBuscar, busy }: {
  label: string; value: string; onChange: (v: string) => void; onBuscar: () => void; busy: boolean
}) {
  return (
    <div>
      <label style={lbl}>{label}</label>
      <div style={{ display: 'flex', gap: 6 }}>
        <input
          style={{ ...inp, flex: 1 }}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') onBuscar() }}
        />
        <Button disabled={busy || !value.trim()} onClick={onBuscar}>Buscar</Button>
      </div>
    </div>
  )
}

function CampoTexto({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label style={lbl}>{label}</label>
      <input style={inp} value={value} onChange={(e) => onChange(e.target.value)} />
    </div>
  )
}

function ResultadoLista({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ fontFamily: 'var(--font-display)', fontSize: 12, fontWeight: 600, color: 'var(--fg-2)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {titulo}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>{children}</div>
    </div>
  )
}

function ResultadoItem({ principal, secundario, cta, onUsar }: {
  principal: string; secundario: string; cta: string; onUsar: () => void
}) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12, padding: '8px 12px',
      border: '1px solid var(--border-primary)', borderRadius: 10, background: 'var(--surface-100)',
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600, color: 'var(--fg-1)', fontSize: 14 }}>{principal}</div>
        <div style={{ color: 'var(--fg-3)', fontSize: 12 }}>{secundario}</div>
      </div>
      <Button onClick={onUsar}>{cta}</Button>
    </div>
  )
}

const bloque: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 12, padding: '14px 18px',
}
const bloqueTitulo: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: 13, fontWeight: 700,
  textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--fg-2)', marginBottom: 12,
}
const lbl: React.CSSProperties = {
  display: 'block', fontFamily: 'var(--font-display)', fontSize: 12,
  fontWeight: 600, color: 'var(--fg-2)', marginBottom: 4,
}
const inp: React.CSSProperties = {
  width: '100%', boxSizing: 'border-box', padding: '8px 10px',
  border: '1px solid var(--border-medium)', borderRadius: 8,
  background: 'var(--zaris-cream)', color: 'var(--fg-1)',
  fontFamily: 'var(--font-display)', fontSize: 14,
}
const seleccionado: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 8, marginTop: 12,
  padding: '10px 14px', borderRadius: 10, fontSize: 14, color: 'var(--fg-1)',
  border: '1px solid var(--color-success)', background: 'var(--surface-100)',
}
const quitarBtn: React.CSSProperties = {
  marginLeft: 'auto', background: 'transparent', border: 'none', cursor: 'pointer',
  color: 'var(--zaris-orange)', fontFamily: 'var(--font-display)', fontSize: 12,
  fontWeight: 600, textDecoration: 'underline',
}
