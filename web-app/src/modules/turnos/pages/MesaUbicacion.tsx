import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronLeft, ChevronRight, MapPin, Plus, RefreshCw } from 'lucide-react'
import { useMesaUbicacion } from '../hooks/useTurnos'
import { obtenerTurno } from '../api/turnosApi'
import { useUbicacionTurnosStore } from '../stores/ubicacionTurnos'
import { TurnoDetalleModal } from '../components/TurnoDetalleModal'
import { TurnoFormModal } from '../components/TurnoFormModal'
import { PanelAtencion } from '../components/PanelAtencion'
import { useNotificationsStore } from '../../../stores/notifications'
import { toIsoDate, hoy, sumarDias, etiquetaFechaLarga, mismaFecha, timeToMinutes } from '../../../lib/dates'
import type { MesaOcupacion, MesaRecurso, Turno } from '../types/turno'

// Mesa del día de una ubicación (F2 plan ATENCION): para la ubicación elegida
// muestra, columna por columna, la disponibilidad efectiva y la ocupación de
// cada recurso que atiende ahí (el lugar mismo + sus agentes). Es LA vista
// para responder "¿cómo está la disponibilidad/ocupación de esta ubicación
// (o de tal agente acá) para tal día?".

const HORA_INI = 7
const HORA_FIN = 21
const PX_POR_HORA = 56
const ALTO_GRILLA = (HORA_FIN - HORA_INI) * PX_POR_HORA

const TURNO_COLOR: Record<string, { bg: string; border: string; fg: string }> = {
  reservado: { bg: 'rgba(245,127,23,0.18)', border: '#f57f17', fg: '#8a5800' },
  cumplido:  { bg: 'rgba(31,138,101,0.18)', border: '#1f8a65', fg: '#15614a' },
  cancelado: { bg: 'rgba(38,37,30,0.07)',   border: 'var(--border-medium)', fg: 'var(--fg-3)' },
}
const OTRA_OCUPACION = { bg: 'rgba(38,37,30,0.10)', border: 'var(--border-medium)', fg: 'var(--fg-2)' }
const DISPONIBLE_BG = 'rgba(31,138,101,0.07)'

export function MesaUbicacion() {
  const navigate = useNavigate()
  const push = useNotificationsStore((s) => s.push)
  const ubicacion = useUbicacionTurnosStore((s) => s.ubicacion)
  const [ancla, setAncla] = useState<Date>(hoy())
  const [detalle, setDetalle] = useState<Turno | null>(null)
  const [modalNuevo, setModalNuevo] = useState(false)

  const fecha = toIsoDate(ancla)
  const { data, isLoading, isError, error, refetch, isFetching } =
    useMesaUbicacion(ubicacion?.id_espacio ?? null, fecha)

  const resumen = useMemo(() => {
    let reservados = 0
    let llamados = 0
    let cumplidos = 0
    let ausentes = 0
    for (const r of data?.recursos ?? []) {
      for (const o of r.ocupaciones) {
        if (o.turno_estado === 'reservado') reservados += 1
        if (o.turno_estado === 'llamado') llamados += 1
        if (o.turno_estado === 'cumplido') cumplidos += 1
        if (o.turno_estado === 'ausente') ausentes += 1
      }
    }
    return { reservados, llamados, cumplidos, ausentes }
  }, [data])

  async function abrirTurno(o: MesaOcupacion) {
    if (o.id_turno == null) return
    try {
      setDetalle(await obtenerTurno(o.id_turno))
    } catch (e) {
      push({ kind: 'error', title: 'No se pudo abrir el turno', body: (e as Error).message })
    }
  }

  if (!ubicacion) {
    return (
      <div style={vacioCta}>
        <MapPin size={22} strokeWidth={1.5} style={{ color: 'var(--zaris-orange)' }} />
        <p style={{ margin: 0, color: 'var(--fg-2)' }}>
          La mesa del día trabaja sobre una ubicación de atención.
        </p>
        <button onClick={() => navigate('/turnos')} style={btnPrimary}>Elegir ubicación</button>
      </div>
    )
  }

  const horas = Array.from({ length: HORA_FIN - HORA_INI }, (_, i) => HORA_INI + i)
  const esHoy = mismaFecha(ancla, hoy())

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div>
        <h1 style={titulo}>{data?.nombre ?? ubicacion.nombre}</h1>
        <p style={{ margin: '6px 0 0', color: 'var(--fg-3)', fontSize: 'var(--size-btn)' }}>
          {data?.direccion ? `${data.direccion} · ` : ''}mesa del día: disponibilidad y ocupación de
          cada recurso de la ubicación. Clic en un turno para verlo.
        </p>
      </div>

      <div style={toolbar}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button onClick={() => setAncla((a) => sumarDias(a, -1))} style={navBtn} aria-label="Día anterior"><ChevronLeft size={16} /></button>
          <button onClick={() => setAncla(hoy())} style={navBtn}>Hoy</button>
          <button onClick={() => setAncla((a) => sumarDias(a, 1))} style={navBtn} aria-label="Día siguiente"><ChevronRight size={16} /></button>
          <span style={{ fontWeight: 600, color: esHoy ? 'var(--zaris-orange)' : 'var(--fg-1)', fontSize: '0.92rem', textTransform: 'capitalize' }}>
            {etiquetaFechaLarga(ancla)}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 8, marginLeft: 'auto', alignItems: 'center' }}>
          <span style={{ ...chip, background: 'rgba(245,127,23,0.14)', color: '#b35900' }}>{resumen.reservados} en espera</span>
          {resumen.llamados > 0 && (
            <span style={{ ...chip, background: 'rgba(245,78,0,0.16)', color: '#f54e00' }}>{resumen.llamados} llamados</span>
          )}
          <span style={{ ...chip, background: 'rgba(31,138,101,0.16)', color: '#1f8a65' }}>{resumen.cumplidos} atendidos</span>
          {resumen.ausentes > 0 && (
            <span style={{ ...chip, background: 'rgba(198,40,40,0.14)', color: '#c62828' }}>{resumen.ausentes} ausentes</span>
          )}
          <button onClick={() => refetch()} style={navBtn} title="Refrescar">
            <RefreshCw size={14} strokeWidth={1.5} style={{ animation: isFetching ? 'spin 1s linear infinite' : undefined }} />
          </button>
          <button onClick={() => setModalNuevo(true)} style={btnPrimary}>
            <Plus size={14} strokeWidth={1.5} /> Nuevo turno
          </button>
        </div>
      </div>

      <div style={leyendaBar}>
        <Leyenda color={DISPONIBLE_BG} borde="rgba(31,138,101,0.4)" label="Franja disponible" />
        <Leyenda color={TURNO_COLOR.reservado.bg} borde={TURNO_COLOR.reservado.border} label="Turno reservado" />
        <Leyenda color={TURNO_COLOR.cumplido.bg} borde={TURNO_COLOR.cumplido.border} label="Turno cumplido" />
        <Leyenda color={OTRA_OCUPACION.bg} borde={OTRA_OCUPACION.border} label="Otra ocupación (evento / OT / bloqueo / turno en otra ubicación)" />
      </div>

      {isError && <div style={errorBanner}>{(error as Error)?.message ?? 'Error al cargar la mesa'}</div>}

      {/* Colero (mig 105): el panel va ARRIBA de la grilla porque es lo que el
          operador toca todo el día; la grilla queda como vista del día. */}
      {ubicacion?.id_espacio != null && (
        <PanelAtencion
          idEspacioUbicacion={ubicacion.id_espacio}
          fecha={fecha}
          tokenPantalla={data?.token_pantalla ?? null}
          onCambio={() => refetch()}
        />
      )}

      <div style={card}>
        {isLoading ? (
          <p style={vacio}>Cargando…</p>
        ) : (
          <div style={{ display: 'flex', overflowX: 'auto' }}>
            <div style={{ flexShrink: 0, width: 52, paddingTop: 44 }}>
              {horas.map((h) => (
                <div key={h} style={{ height: PX_POR_HORA, position: 'relative' }}>
                  <span style={horaLabel}>{String(h).padStart(2, '0')}:00</span>
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', flex: 1, minWidth: Math.max(320, (data?.recursos.length ?? 1) * 180) }}>
              {(data?.recursos ?? []).map((r) => (
                <ColumnaRecurso key={`${r.tipo}:${r.id_recurso}`} recurso={r} horas={horas} onOcupacionClick={abrirTurno} />
              ))}
              {(data?.recursos.length ?? 0) === 0 && (
                <p style={vacio}>La ubicación no tiene recursos con agenda (ni agentes vinculados ni prestaciones).</p>
              )}
            </div>
          </div>
        )}
      </div>

      <TurnoDetalleModal turno={detalle} onClose={() => setDetalle(null)} />
      <TurnoFormModal open={modalNuevo} onClose={() => { setModalNuevo(false); refetch() }} turno={null} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

function ColumnaRecurso({ recurso, horas, onOcupacionClick }: {
  recurso: MesaRecurso
  horas: number[]
  onOcupacionClick: (o: MesaOcupacion) => void
}) {
  return (
    <div style={{ flex: 1, minWidth: 160, borderLeft: '1px solid var(--border-primary)' }}>
      <div style={colHeader}>
        <span style={{ fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {recurso.nombre}
        </span>
        <span style={{ fontSize: '0.66rem', color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          {recurso.tipo === 'espacio' ? 'Lugar' : 'Agente'}
        </span>
      </div>
      <div style={{ position: 'relative', height: ALTO_GRILLA }}>
        {/* franjas de disponibilidad efectiva (fondo) */}
        {recurso.disponibilidad.map((d, i) => {
          const pos = posicion(d.hora_inicio, d.hora_fin)
          if (!pos) return null
          return (
            <div
              key={`d${i}`}
              title={`Disponible ${d.hora_inicio.slice(0, 5)}–${d.hora_fin.slice(0, 5)}`}
              style={{ position: 'absolute', top: pos.top, height: pos.alto, left: 0, right: 0, background: DISPONIBLE_BG }}
            />
          )
        })}
        {/* líneas de hora */}
        {horas.map((h, i) => (
          <div key={h} style={{ position: 'absolute', top: i * PX_POR_HORA, left: 0, right: 0, borderTop: '1px solid var(--border-primary)', opacity: 0.5 }} />
        ))}
        {/* ocupaciones */}
        {recurso.ocupaciones.map((o) => {
          const pos = posicion(o.hora_inicio, o.hora_fin)
          if (!pos) return null
          const esTurno = o.id_turno != null
          const c = esTurno ? (TURNO_COLOR[o.turno_estado ?? 'reservado'] ?? TURNO_COLOR.reservado) : OTRA_OCUPACION
          const horaTxt = `${o.hora_inicio.slice(0, 5)}–${o.hora_fin.slice(0, 5)}`
          const linea2 = esTurno ? (o.ciudadano_nombre ?? '—') : (o.motivo ?? o.tipo)
          return (
            <div
              key={o.id_ocupacion}
              onClick={esTurno ? () => onOcupacionClick(o) : undefined}
              title={esTurno
                ? `${horaTxt} · ${o.prestacion_nombre ?? ''} · ${o.ciudadano_nombre ?? ''} — clic para ver detalle`
                : `${horaTxt} · ${o.motivo ?? o.tipo}`}
              style={{
                position: 'absolute', top: pos.top, height: Math.max(22, pos.alto - 2), left: 3, right: 3,
                background: c.bg, borderLeft: `3px solid ${c.border}`, borderRadius: 5,
                padding: '3px 7px', overflow: 'hidden', fontSize: '0.72rem', lineHeight: 1.25,
                color: c.fg, cursor: esTurno ? 'pointer' : 'default',
              }}
            >
              <div style={{ fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{horaTxt}</div>
              <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: 'var(--fg-1)' }}>{linea2}</div>
              {esTurno && o.prestacion_nombre && (
                <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{o.prestacion_nombre}</div>
              )}
            </div>
          )
        })}
        {recurso.disponibilidad.length === 0 && recurso.ocupaciones.length === 0 && (
          <div style={sinDatos}>Sin disponibilidad cargada</div>
        )}
      </div>
    </div>
  )
}

function posicion(horaInicio: string, horaFin: string): { top: number; alto: number } | null {
  const ini = timeToMinutes(horaInicio)
  const fin = timeToMinutes(horaFin || horaInicio)
  const visIni = Math.max(ini, HORA_INI * 60)
  const visFin = Math.min(fin, HORA_FIN * 60)
  if (visFin <= visIni) return null
  return {
    top: ((visIni - HORA_INI * 60) / 60) * PX_POR_HORA,
    alto: ((visFin - visIni) / 60) * PX_POR_HORA,
  }
}

function Leyenda({ color, borde, label }: { color: string; borde: string; label: string }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <span style={{ width: 12, height: 12, borderRadius: 3, background: color, border: `1px solid ${borde}`, display: 'inline-block' }} />
      {label}
    </span>
  )
}

const titulo: React.CSSProperties = {
  margin: 0, fontFamily: 'var(--font-display)', fontSize: 'var(--size-section)',
  fontWeight: 400, letterSpacing: 'var(--track-section)', color: 'var(--fg-1)',
}
const toolbar: React.CSSProperties = {
  display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center',
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)', borderRadius: 12, padding: 12,
}
const leyendaBar: React.CSSProperties = {
  display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center',
  fontSize: '0.78rem', color: 'var(--fg-2)',
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 12, padding: '8px 14px',
}
const navBtn: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: 13, cursor: 'pointer', borderRadius: 8, padding: '6px 10px',
  background: 'transparent', color: 'var(--fg-2)', border: '1px solid var(--border-medium)',
  display: 'inline-flex', alignItems: 'center',
}
const btnPrimary: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.82rem', cursor: 'pointer',
  borderRadius: 8, padding: '7px 12px', fontWeight: 500, border: '1px solid var(--zaris-orange)',
  background: 'var(--zaris-orange)', color: 'white', display: 'inline-flex', alignItems: 'center', gap: 6,
}
const chip: React.CSSProperties = {
  fontSize: '0.76rem', fontWeight: 600, padding: '4px 10px', borderRadius: 999,
}
const card: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)', borderRadius: 12, overflow: 'hidden',
}
const colHeader: React.CSSProperties = {
  height: 44, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
  fontSize: '0.8rem', borderBottom: '1px solid var(--border-primary)', background: 'var(--surface-300)',
  padding: '0 8px', textAlign: 'center',
}
const horaLabel: React.CSSProperties = {
  position: 'absolute', top: -7, right: 8, fontSize: '0.68rem', color: 'var(--fg-3)', fontFamily: 'var(--font-mono)',
}
const sinDatos: React.CSSProperties = {
  position: 'absolute', top: 12, left: 8, right: 8, textAlign: 'center', color: 'var(--fg-3)', fontSize: '0.74rem',
}
const vacio: React.CSSProperties = { color: 'var(--fg-3)', fontSize: 13, textAlign: 'center', padding: 40, width: '100%' }
const vacioCta: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12,
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 12, padding: 48, textAlign: 'center',
}
const errorBanner: React.CSSProperties = {
  background: '#ffebee', border: '1px solid #ffcdd2', borderLeft: '4px solid var(--color-error)',
  borderRadius: 8, padding: '12px 16px', color: '#c62828', fontSize: '0.86rem',
}
