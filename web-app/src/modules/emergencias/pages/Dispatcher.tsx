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
  useEventosAbiertos,
  useTiposEmergencia,
} from '../hooks/useEmergencias'
import type { EmergenciaEvento } from '../types'
import { CanalAppVecinoBadge, EstadoBadge, PrioridadPill, formatFechaHora, transcurridoDesde, useAhora } from '../lib/ui'
import { CambiarEstadoModal, CerrarModal, DerivarModal } from '../components/EventoAccionModals'
import { RANGOS, StatsEmergenciasBar } from '../components/StatsEmergenciasBar'
import { EmergenciasMap } from '../components/EmergenciasMap'

type Accion =
  | { tipo: 'estado'; destino: string; evento: EmergenciaEvento }
  | { tipo: 'derivar'; evento: EmergenciaEvento }
  | { tipo: 'cerrar'; evento: EmergenciaEvento }

export function Dispatcher() {
  const navigate = useNavigate()
  const push = useNotificationsStore((s) => s.push)
  const ahora = useAhora()

  const [fSubarea, setFSubarea] = useState<number | ''>('')
  const [fPrioridad, setFPrioridad] = useState<string>('')
  const [fEstado, setFEstado] = useState<string>('')
  const [fNro, setFNro] = useState<string>('')
  const [horasKpi, setHorasKpi] = useState<number | undefined>(24)
  const [fullscreen, setFullscreen] = useState(false)
  const fsRef = useRef<HTMLDivElement>(null)
  const [accion, setAccion] = useState<Accion | null>(null)

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

  const abiertos = useEventosAbiertos({ id_subarea: fSubarea === '' ? undefined : fSubarea })
  const tipos = useTiposEmergencia()
  const estados = useEstadosEmergencia()

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
    let lista = abiertos.data ?? []
    if (fPrioridad) lista = lista.filter((e) => e.prioridad_codigo === fPrioridad)
    if (fEstado) lista = lista.filter((e) => e.estado_codigo === fEstado)
    if (fNro.trim()) {
      const q = fNro.trim().toLowerCase()
      lista = lista.filter((e) => e.numero_operativo.toLowerCase().includes(q))
    }
    return lista
  }, [abiertos.data, fPrioridad, fEstado, fNro])

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
          <option value="">Todo estado abierto</option>
          {(estados.data ?? []).filter((s) => !s.es_terminal).map((s) => (
            <option key={s.codigo} value={s.codigo}>{s.nombre}</option>
          ))}
        </select>
        <Button variant="accent" style={{ marginLeft: 'auto' }} onClick={() => navigate('/emergencias/recepcion')}>
          + Recibir llamado
        </Button>
      </div>

      {abiertos.isLoading && <Skeleton height={220} />}
      {abiertos.isError && (
        <EmptyState title="No se pudo cargar el tablero" description={String(abiertos.error)} />
      )}
      {!abiertos.isLoading && !abiertos.isError && eventos.length === 0 && (
        <EmptyState
          title="Sin eventos abiertos"
          description="Cuando se reciba un llamado o un reporte de la App Vecinos, aparece acá."
          action={<Button variant="accent" onClick={() => navigate('/emergencias/recepcion')}>Recibir llamado</Button>}
        />
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {eventos.map((ev) => (
          <div key={ev.id_emergencia_evento} style={cardStyle}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
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
const cardStyle: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 12, padding: '12px 16px',
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
