// Recepcion de llamado (plan 5.1): carga rapida con cronometro, identificacion
// del denunciante (anonimo / BUC / contacto eventual / alta al vuelo) y datos
// del evento con prioridad autocompletada por tipo/subtipo.
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '../../../ui'
import { AddressSearch } from '../../../ui/AddressSearch'
import { useNotificationsStore } from '../../../stores/notifications'
import { GeocodingSearch } from '../../reclamos/components/GeocodingSearch'
import { MapaPicker } from '../../reclamos/components/MapaPicker'
import { buscarDenunciante } from '../api/emergenciasApi'
import {
  useCanalesEmergencia,
  useCrearContactoEventual,
  useCrearEvento,
  usePrioridadesEmergencia,
  useSubtiposDeTipo,
  useTiposEmergencia,
} from '../hooks/useEmergencias'
import type { CiudadanoBucMatch, ContactoEventual, DenuncianteBusqueda, EmergenciaTipo } from '../types'
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
  const [intentoGuardar, setIntentoGuardar] = useState(false)
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

  // Validacion secuencial con avisos (QA humano 2026-06-11): el bloque Evento
  // se habilita recien con el denunciante resuelto, y el boton Crear NUNCA
  // queda deshabilitado en silencio — al click lista que falta.
  const bloque1Completo = anonimo || sel != null
  const faltantes = useMemo(() => {
    const f: string[] = []
    if (!bloque1Completo) f.push('Denunciante: seleccioná un ciudadano o contacto, o marcá "Denunciante anónimo"')
    if (idSubarea === '') f.push('Subárea del evento')
    if (idTipo === '') f.push('Tipo de emergencia')
    if (prioridadEfectiva === '') f.push('Prioridad')
    if (direccion.trim().length < 3) f.push('Dirección del evento')
    return f
  }, [bloque1Completo, idSubarea, idTipo, prioridadEfectiva, direccion])

  const crearEvento = () => {
    setIntentoGuardar(true)
    if (faltantes.length > 0) {
      push({ kind: 'error', title: 'Faltan datos para crear el evento', body: faltantes.join(' · ') })
      return
    }
    if (!canalLlamada) {
      push({ kind: 'error', title: 'Catálogo de canales no disponible', body: 'No se encontró el canal LLAMADA_TEL. Recargá la página.' })
      return
    }
    crear.mutate(
      {
        id_subarea: idSubarea as number,
        id_tipo: idTipo as number,
        id_subtipo: idSubtipo === '' ? undefined : idSubtipo,
        id_prioridad: prioridadEfectiva as number,   // ya validado en faltantes
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

      {/* BLOQUE 2 - EVENTO (habilitado recien con el denunciante resuelto) */}
      <section style={bloque}>
        <div style={bloqueTitulo}>2 · Evento</div>
        {!bloque1Completo && (
          <div style={avisoBloqueo}>
            Primero resolvé el denunciante: buscá y seleccioná un ciudadano o contacto,
            o marcá «Denunciante anónimo». Después se habilita esta sección.
          </div>
        )}
        <div style={bloque1Completo ? undefined : { opacity: 0.45, pointerEvents: 'none' }}>
        {/* Subárea: dos botones grandes con el color de la fuerza (pedido del
            usuario 2026-06-11) — verde Defensa Civil, rojo seguridad/policía. */}
        <div style={{ marginBottom: 12 }}>
          <label style={lbl}>Subárea *</label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10 }}>
            {subareas.map(([id, nombre]) => {
              const esDC = nombre.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase().includes('defensa')
              const color = esDC ? '#1f8a65' : '#c62828'
              const activa = idSubarea === id
              return (
                <button
                  key={id}
                  type="button"
                  style={{
                    padding: '13px 14px', borderRadius: 10, cursor: 'pointer',
                    fontFamily: 'var(--font-display)', fontSize: 15, fontWeight: 700,
                    textTransform: 'uppercase', letterSpacing: '0.04em',
                    border: `2px solid ${color}`,
                    background: activa ? color : 'var(--surface-100)',
                    // #fff fijo a proposito: el fondo activo es el color de la
                    // subarea (fijo entre temas), como el avatar del topbar §13.
                    color: activa ? '#fff' : color,
                    transition: 'background 120ms, color 120ms',
                  }}
                  onClick={() => {
                    setIdSubarea(id)
                    setIdTipo(''); setIdSubtipo(''); setPrioridadTocada(false)
                  }}
                >
                  {nombre}
                </button>
              )
            })}
          </div>
        </div>

        {/* Tipo + subtipo en una fila */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10 }}>
          <div>
            <label style={lbl}>Tipo *</label>
            <ComboTipo
              tipos={tiposDeSubarea}
              value={idTipo}
              disabled={idSubarea === ''}
              onPick={(id) => { setIdTipo(id); setIdSubtipo(''); setPrioridadTocada(false) }}
            />
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
        </div>

        {/* Prioridad: tres botones con descripción y SLA. Sigue autocompletada
            por subtipo>tipo; tocar uno la pisa (prioridadTocada). */}
        <div style={{ marginTop: 12 }}>
          <label style={lbl}>
            Prioridad * {!prioridadTocada && tipoSel ? '(sugerida por el tipo — tocá otra para cambiarla)' : ''}
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 10 }}>
            {(prioridades.data ?? []).map((p) => {
              const activa = prioridadEfectiva === p.id_emergencia_prioridad
              const color = `var(--${p.color_token || `prio-${p.codigo.toLowerCase()}`}, var(--fg-2))`
              return (
                <button
                  key={p.id_emergencia_prioridad}
                  type="button"
                  style={{
                    textAlign: 'left', padding: '10px 12px', borderRadius: 10, cursor: 'pointer',
                    border: `2px solid ${activa ? color : 'var(--border-primary)'}`,
                    background: activa ? 'var(--surface-400)' : 'var(--surface-100)',
                    fontFamily: 'var(--font-display)',
                    transition: 'border-color 120ms, background 120ms',
                  }}
                  onClick={() => { setPrioridadTocada(true); setIdPrioridad(p.id_emergencia_prioridad) }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{
                      fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 12,
                      // texto claro fijo a proposito: el fondo es el color de
                      // prioridad (--prio-*, fijo entre temas) — caso avatar §13.
                      color: '#f7f7f4', background: color, borderRadius: 999, padding: '2px 9px',
                    }}>
                      {p.codigo}
                    </span>
                    <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--fg-1)' }}>{p.nombre}</span>
                  </div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-3)', marginTop: 5 }}>
                    SLA de arribo: {p.sla_minutos_arribo} min
                  </div>
                </button>
              )
            })}
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
          <div style={{ fontSize: 11, color: 'var(--fg-3)', margin: '6px 0' }}>
            También podés hacer clic en el mapa (o arrastrar el pin) para fijar el punto exacto.
          </div>
          {/* Mapa con pin manual — regla de diseño del proyecto (s23): todo form
              con dirección normaliza por OSM Y geoposiciona con mapa, como Reclamos. */}
          <MapaPicker
            lat={latitud}
            lon={longitud}
            onChange={(la, lo) => { setLatitud(la); setLongitud(lo) }}
            height={260}
          />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 10, marginTop: 10 }}>
          <div>
            <label style={lbl}>Dirección del evento *</label>
            <input
              style={inp}
              value={direccion}
              onChange={(e) => setDireccion(e.target.value)}
              placeholder="Calle y altura / intersección"
            />
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 11, color: 'var(--fg-3)', marginTop: 3, fontFamily: 'var(--font-mono)' }}>
              {latitud != null && longitud != null ? (
                <>
                  <span>{`Coordenadas: ${latitud.toFixed(6)}, ${longitud.toFixed(6)}`}</span>
                  <button
                    type="button"
                    style={{ ...quitarBtn, marginLeft: 0 }}
                    onClick={() => { setLatitud(null); setLongitud(null) }}
                  >
                    Quitar pin
                  </button>
                </>
              ) : (
                'Sin coordenadas — buscá arriba o marcá el punto en el mapa'
              )}
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
        </div>
      </section>

      {intentoGuardar && faltantes.length > 0 && (
        <div style={avisoFaltantes}>
          <strong>Para crear el evento falta completar:</strong>
          <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
            {faltantes.map((f) => <li key={f}>{f}</li>)}
          </ul>
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
        <Button variant="ghost" onClick={() => navigate('/emergencias')}>Cancelar</Button>
        <Button variant="accent" disabled={crear.isPending} onClick={crearEvento}>
          Crear evento
        </Button>
      </div>
    </div>
  )
}

// ---- piezas locales ----

/** Autocompletar de tipo de emergencia (s23): los catalogos tienen 34/16 tipos
 * por subarea y el <select> era inusable bajo presion de un llamado. Filtra
 * client-side (la lista ya esta cargada), sin debounce ni fetch. */
function ComboTipo({ tipos, value, onPick, disabled }: {
  tipos: EmergenciaTipo[]
  value: number | ''
  disabled: boolean
  onPick: (id: number | '') => void
}) {
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const wrapRef = useRef<HTMLDivElement>(null)
  const sel = tipos.find((t) => t.id_emergencia_tipo === value)

  // Si la seleccion se resetea desde afuera (cambio de subarea), limpiar el texto.
  useEffect(() => { if (value === '') setQ('') }, [value])

  // click-outside cierra el dropdown (s23)
  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])

  const norm = (s: string) => s.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase()
  const filtrados = q.trim() ? tipos.filter((t) => norm(t.nombre).includes(norm(q.trim()))) : tipos

  return (
    <div ref={wrapRef} style={{ position: 'relative' }}>
      <input
        style={inp}
        disabled={disabled}
        value={sel ? sel.nombre : q}
        placeholder={disabled ? 'Elegí primero la subárea' : 'Tipeá para filtrar...'}
        onFocus={() => setOpen(true)}
        onChange={(e) => { setQ(e.target.value); if (sel) onPick(''); setOpen(true) }}
      />
      {open && !disabled && (
        <div style={comboDrop}>
          {filtrados.length === 0 && (
            <div style={{ padding: '8px 12px', fontSize: 13, color: 'var(--fg-3)' }}>Sin coincidencias</div>
          )}
          {filtrados.map((t) => (
            <button
              key={t.id_emergencia_tipo}
              type="button"
              style={comboItem}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--surface-400)' }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
              onClick={() => { onPick(t.id_emergencia_tipo); setQ(t.nombre); setOpen(false) }}
            >
              <span>{t.nombre}</span>
              {t.requiere_911 && <span style={{ color: '#c62828', fontSize: 11, fontWeight: 700, marginLeft: 'auto' }}>911</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

const comboDrop: React.CSSProperties = {
  position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 30,
  maxHeight: 260, overflowY: 'auto', marginTop: 4,
  background: 'var(--surface-100)', border: '1px solid var(--border-medium)',
  borderRadius: 8, boxShadow: '0 6px 18px rgba(38,37,30,.12)',
}
const comboItem: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 8, width: '100%',
  padding: '8px 12px', border: 'none', background: 'transparent',
  cursor: 'pointer', textAlign: 'left',
  fontFamily: 'var(--font-display)', fontSize: 14, color: 'var(--fg-1)',
}

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
const avisoBloqueo: React.CSSProperties = {
  marginBottom: 12, padding: '10px 14px', borderRadius: 8, fontSize: 13,
  color: '#8a5800', border: '1px solid #f57f17', background: 'var(--surface-100)',
  fontFamily: 'var(--font-display)', fontWeight: 600,
}
const avisoFaltantes: React.CSSProperties = {
  padding: '10px 14px', borderRadius: 8, fontSize: 13,
  color: '#c62828', border: '1px solid #c62828', background: 'var(--surface-100)',
  fontFamily: 'var(--font-display)',
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
