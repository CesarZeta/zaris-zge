// Tablero del dispatcher (plan 5.2): KPIs arriba (abiertos + por subarea +
// por estado, con rango temporal), mapa de eventos coloreado por estado,
// lista de abiertos ordenada por prioridad con acciones rapidas y polling 30s.
// Modo "Maximizar tablero": fullscreen NATIVO del navegador (estilo F11, para
// monitor de guardia — desaparecen sidebar y topbar del shell) con las
// tarjetas KPI flotando sobre el mapa. Necesita allowfullscreen en el iframe
// del shell (index.html); si el navegador lo rechaza, cae al overlay fixed
// que cubre el lienzo del modulo.
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, EmptyState, Skeleton } from '../../../ui'
import { useNotificationsStore } from '../../../stores/notifications'
import {
  useCambiarEstado,
  useCerrarEvento,
  useDerivarEvento,
  useEstadosEmergencia,
  useEventos,
  useEventosAbiertos,
  useTiposEmergencia,
} from '../hooks/useEmergencias'
import type { EmergenciaEvento } from '../types'
import { CanalAppVecinoBadge, EstadoBadge, PanicoChip, PrioridadPill, formatFechaHora, transcurridoDesde, useAhora } from '../lib/ui'
import { CambiarEstadoModal, CerrarModal, DerivarModal } from '../components/EventoAccionModals'
import { RANGOS, StatsEmergenciasBar } from '../components/StatsEmergenciasBar'
import { EmergenciasMap } from '../components/EmergenciasMap'

type Accion =
  | { tipo: 'estado'; destino: string; evento: EmergenciaEvento }
  | { tipo: 'derivar'; evento: EmergenciaEvento }
  | { tipo: 'cerrar'; evento: EmergenciaEvento }

// Beep de alerta de panico: 3 pulsos de ~150ms a 880Hz con Web Audio API.
// try/catch silencioso: el navegador puede bloquear audio sin gesto previo
// del usuario y el tablero no debe romperse por eso.
function beepPanico() {
  try {
    const Ctx = window.AudioContext
      ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!Ctx) return
    const ctx = new Ctx()
    const t0 = ctx.currentTime
    for (let i = 0; i < 3; i++) {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.type = 'sine'
      osc.frequency.value = 880
      // envolvente corta para evitar clicks al cortar la onda
      const inicio = t0 + i * 0.25
      gain.gain.setValueAtTime(0.0001, inicio)
      gain.gain.exponentialRampToValueAtTime(0.2, inicio + 0.02)
      gain.gain.exponentialRampToValueAtTime(0.0001, inicio + 0.15)
      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.start(inicio)
      osc.stop(inicio + 0.16)
    }
    window.setTimeout(() => { ctx.close().catch(() => {}) }, 1000)
  } catch {
    // silencioso a proposito
  }
}

export function Dispatcher() {
  const navigate = useNavigate()
  const push = useNotificationsStore((s) => s.push)
  const ahora = useAhora()

  const [fSubarea, setFSubarea] = useState<number | ''>('')
  const [fPrioridad, setFPrioridad] = useState<string>('')
  const [fEstado, setFEstado] = useState<string>('')
  const [fNro, setFNro] = useState<string>('')
  // Rango de fechas (EM002): vacío = tablero en vivo (solo abiertos, polling 30s).
  // Con al menos una fecha, el tablero pasa a "búsqueda histórica" e incluye los
  // eventos cerrados dentro del rango (usa el listado general, no /abiertos).
  const [fDesde, setFDesde] = useState<string>('')
  const [fHasta, setFHasta] = useState<string>('')
  const [horasKpi, setHorasKpi] = useState<number | undefined>(24)
  const [fullscreen, setFullscreen] = useState(false)
  const fsRef = useRef<HTMLDivElement>(null)
  const [accion, setAccion] = useState<Accion | null>(null)
  // Filtro "solo alertas de panico" (mig 97), activado desde el banner rojo.
  // Mismo mecanismo client-side que los filtros por click de los KPIs.
  const [soloPanico, setSoloPanico] = useState(false)
  // Ids de alertas de panico ya vistas por el polling: null hasta el primer
  // dato (el primer render NUNCA suena; solo las alertas NUEVAS).
  const panicoVistasRef = useRef<Set<number> | null>(null)

  // Al abrir el modo maximizado, pedir fullscreen nativo sobre el overlay.
  // El user-activation del click sigue vigente cuando corre el effect.
  // fullscreenchange sincroniza el estado si el navegador sale solo (Esc/F11).
  useEffect(() => {
    if (!fullscreen) return
    if (fsRef.current && document.fullscreenEnabled && !document.fullscreenElement) {
      fsRef.current.requestFullscreen().catch(() => { /* fallback: overlay fixed */ })
    }
    const onFsChange = () => { if (!document.fullscreenElement) setFullscreen(false) }
    document.addEventListener('fullscreenchange', onFsChange)
    // Esc tambien cierra en el modo fallback (sin fullscreen nativo).
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setFullscreen(false) }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('fullscreenchange', onFsChange)
      document.removeEventListener('keydown', onKey)
    }
  }, [fullscreen])

  const salirFullscreen = () => {
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {})
    setFullscreen(false)
  }

  // Modo histórico cuando hay al menos una fecha del rango cargada.
  const modoHistorico = fDesde !== '' || fHasta !== ''
  const abiertos = useEventosAbiertos({ id_subarea: fSubarea === '' ? undefined : fSubarea })
  const historico = useEventos(
    {
      id_subarea: fSubarea === '' ? undefined : fSubarea,
      fecha_desde: fDesde || undefined,
      fecha_hasta: fHasta || undefined,
      limit: 200,
    },
    modoHistorico,
  )
  // Fuente de datos activa según el modo. En histórico no hay polling en vivo.
  const fuente = modoHistorico ? historico : abiertos
  const tipos = useTiposEmergencia()
  const estados = useEstadosEmergencia()

  // Alertas de pánico ABIERTAS, siempre desde la fuente en vivo (/abiertos,
  // polling 30s) aunque el tablero esté en modo histórico: el banner y el
  // sonido son de guardia, no de búsqueda.
  const alertasPanico = useMemo(
    () => (abiertos.data ?? []).filter((e) => e.es_panico && !e.es_terminal),
    [abiertos.data],
  )

  // Sonido al detectar por polling una alerta abierta NUEVA. El Set del ref
  // acumula ids ya vistos: no re-suena por la misma alerta, y en el primer
  // render (ref todavía null) solo siembra el set sin sonar.
  useEffect(() => {
    if (!abiertos.data) return
    if (panicoVistasRef.current === null) {
      panicoVistasRef.current = new Set(alertasPanico.map((e) => e.id_emergencia_evento))
      return
    }
    const vistas = panicoVistasRef.current
    let hayNueva = false
    for (const ev of alertasPanico) {
      if (!vistas.has(ev.id_emergencia_evento)) {
        vistas.add(ev.id_emergencia_evento)
        hayNueva = true
      }
    }
    if (hayNueva) beepPanico()
  }, [abiertos.data, alertasPanico])

  // Auto-curación del filtro: si la última alerta se cierra, el banner (único
  // control del filtro) desaparece — soltamos el filtro para no dejar el
  // tablero vacío sin vía de escape (regla de pantallas-gate, s23).
  useEffect(() => {
    if (soloPanico && abiertos.data && alertasPanico.length === 0) setSoloPanico(false)
  }, [soloPanico, abiertos.data, alertasPanico])

  const cambiar = useCambiarEstado()
  const derivar = useDerivarEvento()
  const cerrar = useCerrarEvento()
  const busy = cambiar.isPending || derivar.isPending || cerrar.isPending

  const subareas = useMemo(() => {
    const m = new Map<number, string>()
    for (const t of tipos.data ?? []) m.set(t.id_subarea, t.subarea_nombre ?? `Subárea ${t.id_subarea}`)
    return [...m.entries()].sort((a, b) => a[1].localeCompare(b[1]))
  }, [tipos.data])

  const eventos = useMemo(() => {
    let lista = fuente.data ?? []
    if (soloPanico) lista = lista.filter((e) => e.es_panico)
    if (fPrioridad) lista = lista.filter((e) => e.prioridad_codigo === fPrioridad)
    if (fEstado) lista = lista.filter((e) => e.estado_codigo === fEstado)
    if (fNro.trim()) {
      const q = fNro.trim().toLowerCase()
      lista = lista.filter((e) => e.numero_operativo.toLowerCase().includes(q))
    }
    return lista
  }, [fuente.data, soloPanico, fPrioridad, fEstado, fNro])

  const onError = (e: unknown) =>
    push({ kind: 'error', title: 'No se pudo aplicar la acción', body: e instanceof Error ? e.message : String(e) })

  const ejecutarAccion = (obsOrBody?: string | { veracidad: string; terminal_positivo: boolean; observaciones_cierre?: string }, idOrg?: number) => {
    if (!accion) return
    const acc = accion
    // Cerrar el modal YA: la mutacion tarda ~2s (latencia Railway, s27) y dejar
    // el modal abierto hasta el onSuccess se percibe como "no cierra" (QA humano
    // 2026-06-11). El resultado se notifica por toast.
    setAccion(null)
    const id = acc.evento.id_emergencia_evento
    const done = (msg: string) => () => push({ kind: 'success', title: msg, body: acc.evento.numero_operativo })
    if (acc.tipo === 'estado') {
      cambiar.mutate({ id, nuevo_estado: acc.destino, observaciones: obsOrBody as string | undefined },
        { onSuccess: done(`Evento ${acc.destino.replace(/_/g, ' ')}`), onError })
    } else if (acc.tipo === 'derivar') {
      derivar.mutate({ id, id_organismo: idOrg as number, observaciones: obsOrBody as string | undefined },
        { onSuccess: done('Evento derivado'), onError })
    } else {
      cerrar.mutate({ id, ...(obsOrBody as { veracidad: string; terminal_positivo: boolean; observaciones_cierre?: string }) },
        { onSuccess: done('Evento cerrado'), onError })
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* BANNER de alertas de pánico activas (mig 97): franja roja fija arriba
          del tablero, clickeable para filtrar la lista a solo-pánico. Texto
          #fff fijo sobre --prio-p1 a propósito (caso avatar, s13). */}
      {alertasPanico.length > 0 && (
        <button
          style={bannerPanico}
          onClick={() => setSoloPanico((v) => !v)}
          title={soloPanico ? 'Quitar el filtro de alertas' : 'Ver solo las alertas de pánico'}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3" />
            <path d="M12 9v4" /><path d="M12 17h.01" />
          </svg>
          <span>
            {alertasPanico.length === 1
              ? '1 ALERTA DE PÁNICO ACTIVA'
              : `${alertasPanico.length} ALERTAS DE PÁNICO ACTIVAS`}
          </span>
          <span style={{ marginLeft: 'auto', fontSize: 11, fontWeight: 600, opacity: 0.85, textTransform: 'none', letterSpacing: 0 }}>
            {soloPanico ? 'Mostrando solo alertas — click para ver todo' : 'Click para ver solo las alertas'}
          </span>
        </button>
      )}

      {/* KPIs (abiertos en rojo + subareas + estados) */}
      <StatsEmergenciasBar
        horas={horasKpi}
        estadoActivo={fEstado}
        onSelectEstado={setFEstado}
        subareaActiva={fSubarea}
        onSelectSubarea={setFSubarea}
      />

      {/* periodo de los totales + maximizar, debajo de las tarjetas */}
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <label style={{ fontFamily: 'var(--font-display)', fontSize: 11, fontWeight: 600, color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Período de los totales
        </label>
        <select
          style={selectStyle}
          value={horasKpi ?? ''}
          onChange={(e) => setHorasKpi(e.target.value === '' ? undefined : Number(e.target.value))}
        >
          {RANGOS.map((r) => <option key={r.label} value={r.horas ?? ''}>{r.label}</option>)}
        </select>
        <Button style={{ marginLeft: 'auto' }} onClick={() => setFullscreen(true)}>
          Maximizar tablero
        </Button>
      </div>

      {/* mapa de eventos abiertos, coloreado por estado; click abre el evento */}
      {!fullscreen && (
        <div style={mapaWrap}>
          <EmergenciasMap
            eventos={eventos}
            onMarkerClick={(ev) => navigate(`/emergencias/evento/${ev.id_emergencia_evento}`)}
          />
        </div>
      )}

      {/* modo maximizado: mapa a pantalla completa + tarjetas flotantes */}
      {fullscreen && (
        <div ref={fsRef} style={fsOverlay}>
          <EmergenciasMap
            eventos={eventos}
            onMarkerClick={(ev) => navigate(`/emergencias/evento/${ev.id_emergencia_evento}`)}
          />
          <div style={fsCardsWrap}>
            <div style={{ pointerEvents: 'auto', flex: 1, minWidth: 0 }}>
              <StatsEmergenciasBar
                horas={horasKpi}
                estadoActivo={fEstado}
                onSelectEstado={setFEstado}
                subareaActiva={fSubarea}
                onSelectSubarea={setFSubarea}
              />
            </div>
          </div>
          {/* Salir: discreto (la vista prioriza tarjetas y geoposiciones) —
              chico, blanco y negro, abajo a la derecha junto al zoom. */}
          <button style={fsSalirBtn} onClick={salirFullscreen}>
            Salir de pantalla completa
          </button>
        </div>
      )}

      {/* filtros */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          style={{ ...selectStyle, width: 180, fontFamily: 'var(--font-mono)' }}
          value={fNro}
          onChange={(e) => setFNro(e.target.value)}
          placeholder="Nº operativo (EM-…)"
        />
        <select style={selectStyle} value={fSubarea} onChange={(e) => setFSubarea(e.target.value ? Number(e.target.value) : '')}>
          <option value="">Todas las subáreas</option>
          {subareas.map(([id, nombre]) => <option key={id} value={id}>{nombre}</option>)}
        </select>
        <select style={selectStyle} value={fPrioridad} onChange={(e) => setFPrioridad(e.target.value)}>
          <option value="">Toda prioridad</option>
          <option value="P1">P1</option>
          <option value="P2">P2</option>
          <option value="P3">P3</option>
        </select>
        <select style={selectStyle} value={fEstado} onChange={(e) => setFEstado(e.target.value)}>
          <option value="">{modoHistorico ? 'Todo estado' : 'Todo estado abierto'}</option>
          {(estados.data ?? []).filter((s) => modoHistorico || !s.es_terminal).map((s) => (
            <option key={s.codigo} value={s.codigo}>{s.nombre}</option>
          ))}
        </select>
        {/* Rango de fechas (EM002). Con una fecha, el tablero pasa a histórico
            (incluye cerrados). Sin fechas, sigue en vivo con solo abiertos. */}
        <label style={dateLabelStyle}>
          Desde
          <input type="date" style={dateInputStyle} value={fDesde} max={fHasta || undefined}
            onChange={(e) => setFDesde(e.target.value)} />
        </label>
        <label style={dateLabelStyle}>
          Hasta
          <input type="date" style={dateInputStyle} value={fHasta} min={fDesde || undefined}
            onChange={(e) => setFHasta(e.target.value)} />
        </label>
        {modoHistorico && (
          <button style={limpiarRangoStyle} onClick={() => { setFDesde(''); setFHasta('') }}>
            Limpiar rango
          </button>
        )}
        <Button variant="accent" style={{ marginLeft: 'auto' }} onClick={() => navigate('/emergencias/recepcion')}>
          + Recibir llamado
        </Button>
      </div>
      {modoHistorico && (
        <div style={{ fontSize: 12, color: 'var(--fg-3)', fontFamily: 'var(--font-display)', marginTop: -4 }}>
          Mostrando eventos (abiertos y cerrados) en el rango seleccionado — sin actualización automática.
        </div>
      )}

      {fuente.isLoading && <Skeleton height={220} />}
      {fuente.isError && (
        <EmptyState title="No se pudo cargar el tablero" description={String(fuente.error)} />
      )}
      {!fuente.isLoading && !fuente.isError && eventos.length === 0 && (
        <EmptyState
          title={modoHistorico ? 'Sin eventos en el rango' : 'Sin eventos abiertos'}
          description={modoHistorico
            ? 'No hay eventos entre las fechas seleccionadas. Ajustá o limpiá el rango.'
            : 'Cuando se reciba un llamado o un reporte de la App Vecinos, aparece acá.'}
          action={<Button variant="accent" onClick={() => navigate('/emergencias/recepcion')}>Recibir llamado</Button>}
        />
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {eventos.map((ev) => (
          // Card DESTACADA para alertas de pánico abiertas (mig 97): borde y
          // tinte rojos de --prio-p1. En eventos cerrados (modo histórico)
          // queda solo el chip, sin destacar.
          <div
            key={ev.id_emergencia_evento}
            style={ev.es_panico && !ev.es_terminal ? { ...cardStyle, ...cardPanicoStyle } : cardStyle}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <PanicoChip esPanico={ev.es_panico} />
              <PrioridadPill codigo={ev.prioridad_codigo} colorToken={ev.prioridad_color_token} />
              <button style={nroBtn} onClick={() => navigate(`/emergencias/evento/${ev.id_emergencia_evento}`)}>
                {ev.numero_operativo}
              </button>
              <EstadoBadge codigo={ev.estado_codigo} nombre={ev.estado_nombre} />
              <CanalAppVecinoBadge canalCodigo={ev.canal_codigo} />
              <span style={{ fontFamily: 'var(--font-display)', fontWeight: 600, color: 'var(--fg-1)' }}>
                {ev.tipo_nombre}{ev.subtipo_nombre ? ` · ${ev.subtipo_nombre}` : ''}
              </span>
              <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--fg-2)' }}>
                {formatFechaHora(ev.fecha_hora_recepcion)} · hace {transcurridoDesde(ev.fecha_hora_recepcion, ahora)}
              </span>
            </div>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginTop: 6, fontSize: 13, color: 'var(--fg-2)' }}>
              <span>{ev.direccion_evento}</span>
              <span>Denunciante: <strong>{ev.denunciante_nombre ?? '—'}</strong></span>
              <span>{ev.subarea_nombre}</span>
              {ev.organismo_nombre && <span>Derivable a: {ev.organismo_nombre}</span>}
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
              <Button onClick={() => navigate(`/emergencias/evento/${ev.id_emergencia_evento}`)}>Ver</Button>
              {ev.estado_codigo === 'PENDIENTE' && (
                <Button onClick={() => setAccion({ tipo: 'estado', destino: 'EN_PREPARACION', evento: ev })}>En preparación</Button>
              )}
              {ev.estado_codigo === 'EN_PREPARACION' && (
                <Button onClick={() => setAccion({ tipo: 'estado', destino: 'EN_CAMINO', evento: ev })}>En camino</Button>
              )}
              {(ev.estado_codigo === 'EN_CAMINO' || ev.estado_codigo === 'DERIVADO') && (
                // EN_SITIO tambien abre el modal de observaciones (QA humano
                // 2026-06-11): va por cambiar-estado, que setea fecha_hora_arribo
                // igual que marcar-en-sitio.
                <Button disabled={busy} onClick={() => setAccion({ tipo: 'estado', destino: 'EN_SITIO', evento: ev })}>
                  En sitio
                </Button>
              )}
              {ev.estado_codigo !== 'DERIVADO' && (
                <Button onClick={() => setAccion({ tipo: 'derivar', evento: ev })}>Derivar</Button>
              )}
              {['PENDIENTE', 'EN_PREPARACION', 'EN_SITIO', 'DERIVADO'].includes(ev.estado_codigo) && (
                <Button onClick={() => setAccion({ tipo: 'cerrar', evento: ev })}>Cerrar</Button>
              )}
            </div>
          </div>
        ))}
      </div>

      <CambiarEstadoModal
        open={accion?.tipo === 'estado'}
        destino={accion?.tipo === 'estado' ? accion.destino : ''}
        titulo={accion?.tipo === 'estado' ? `${accion.evento.numero_operativo} → ${accion.destino.replace(/_/g, ' ')}` : ''}
        busy={busy}
        onConfirm={(obs) => ejecutarAccion(obs)}
        onCancel={() => setAccion(null)}
      />
      <DerivarModal
        open={accion?.tipo === 'derivar'}
        busy={busy}
        onConfirm={(idOrg, obs) => ejecutarAccion(obs, idOrg)}
        onCancel={() => setAccion(null)}
      />
      <CerrarModal
        open={accion?.tipo === 'cerrar'}
        busy={busy}
        permiteResuelto={accion?.tipo === 'cerrar' && ['EN_SITIO', 'DERIVADO'].includes(accion.evento.estado_codigo)}
        permiteDesestimado={accion?.tipo === 'cerrar' && ['PENDIENTE', 'EN_PREPARACION'].includes(accion.evento.estado_codigo)}
        onConfirm={(body) => ejecutarAccion(body)}
        onCancel={() => setAccion(null)}
      />
    </div>
  )
}

const selectStyle: React.CSSProperties = {
  padding: '7px 10px', border: '1px solid var(--border-medium)', borderRadius: 8,
  background: 'var(--surface-100)', color: 'var(--fg-1)',
  fontFamily: 'var(--font-display)', fontSize: 13,
}
const dateLabelStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 6,
  fontFamily: 'var(--font-display)', fontSize: 12, color: 'var(--fg-3)',
  textTransform: 'uppercase', letterSpacing: '0.04em',
}
const dateInputStyle: React.CSSProperties = {
  padding: '6px 9px', border: '1px solid var(--border-medium)', borderRadius: 8,
  background: 'var(--surface-100)', color: 'var(--fg-1)',
  fontFamily: 'var(--font-display)', fontSize: 13,
}
const limpiarRangoStyle: React.CSSProperties = {
  padding: '7px 12px', border: '1px solid var(--border-medium)', borderRadius: 8,
  background: 'transparent', color: 'var(--fg-2)',
  fontFamily: 'var(--font-display)', fontSize: 13, cursor: 'pointer',
}
const cardStyle: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 12, padding: '12px 16px',
}
// Card destacada de alerta de pánico (mig 97). El tinte de fondo usa el rgba
// literal del token --prio-p1 (#c62828): un color-mix() inválido en inline
// style dejaría la card SIN fondo en navegadores sin soporte, así que se usa
// directamente el fallback rgba del token.
const cardPanicoStyle: React.CSSProperties = {
  border: '3px solid var(--prio-p1, #c62828)',
  background: 'rgba(198, 40, 40, 0.07)',
}
// Banner de alertas activas: franja --prio-p1 con texto #fff fijo (caso
// avatar, s13 — el fondo rojo no cambia entre temas).
const bannerPanico: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 10, width: '100%',
  background: 'var(--prio-p1, #c62828)', color: '#fff', border: 'none',
  borderRadius: 10, padding: '10px 16px', cursor: 'pointer',
  fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700,
  letterSpacing: '0.06em', textAlign: 'left',
}
const nroBtn: React.CSSProperties = {
  fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700,
  color: 'var(--zaris-orange)', background: 'transparent', border: 'none',
  cursor: 'pointer', padding: 0, textDecoration: 'underline',
}
const mapaWrap: React.CSSProperties = {
  position: 'relative', height: 300, borderRadius: 12, overflow: 'hidden',
  border: '1px solid var(--border-primary)',
}
// Overlay del modo maximizado: cubre el lienzo del modulo (en prod, el area
// del iframe — sidebar y topbar del shell quedan visibles, s14).
const fsOverlay: React.CSSProperties = {
  position: 'fixed', inset: 0, zIndex: 5000, background: 'var(--zaris-cream)',
}
// Tarjetas flotando sobre el mapa: el wrapper no captura pointer (el mapa se
// arrastra entre tarjetas); cada hijo interactivo rehabilita pointerEvents.
const fsCardsWrap: React.CSSProperties = {
  position: 'absolute', top: 12, left: 12, right: 12, zIndex: 1000,
  display: 'flex', gap: 12, alignItems: 'flex-start', pointerEvents: 'none',
}
// Boton salir minimo, blanco y negro, corrido a la izquierda del control de
// zoom (bottomright) y por encima de la atribucion de Leaflet.
const fsSalirBtn: React.CSSProperties = {
  position: 'absolute', bottom: 30, right: 56, zIndex: 1000,
  padding: '4px 10px', borderRadius: 7, cursor: 'pointer',
  background: 'var(--surface-100)', color: 'var(--fg-2)',
  border: '1px solid var(--border-medium)',
  fontFamily: 'var(--font-display)', fontSize: 11, fontWeight: 600,
  letterSpacing: '0.03em',
}
