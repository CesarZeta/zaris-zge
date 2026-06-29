import { useMemo, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { useTurnos, useCumplirTurno, useCancelarTurno } from '../hooks/useTurnos'
import { TurnoFormModal } from '../components/TurnoFormModal'
import { CumplirTurnoModal } from '../components/CumplirTurnoModal'
import { TurnoDetalleModal } from '../components/TurnoDetalleModal'
import { ConfirmModal } from '../../agenda/components/ConfirmModal'
import { useNotificationsStore } from '../../../stores/notifications'
import type { CumplirTurnoBody, Turno } from '../types/turno'

// Fecha "hoy" en hora local del municipio (AR = UTC-3, sin DST). El
// .toISOString() del navegador da UTC: entre las 21:00 y 00:00 locales adelanta
// un día y "Hoy" mostraría los turnos de mañana. Espeja app/utils/fechas.py del
// backend (offset fijo -3). Devuelve 'YYYY-MM-DD' para comparar con turno.fecha.
function hoy_local(): string {
  const ahora = new Date()
  const localMs = ahora.getTime() + (ahora.getTimezoneOffset() - 180) * 60_000
  return new Date(localMs).toISOString().slice(0, 10)
}

// "Mis turnos" — vista de GESTIÓN del agente (sidebar: "Gestión de Turnos").
// El backend ya scopea GET /turnos por nivel: el operador (nivel 3) recibe solo
// los turnos donde es el agente involucrado o de un espacio de su subárea
// (_scope_turnos_para_usuario). Por eso acá NO se filtra por agente en el cliente:
// lo que llega YA es "lo suyo". El supervisor (nivel ≤2) ve todo su alcance, lo
// que también es útil como vista de gestión centrada en cumplir.
//
// A diferencia del tab "Turnos" (alta/mesa), esta vista se enfoca en TRABAJAR los
// turnos: ver los reservados pendientes primero, cumplirlos (registrando la
// atención si la prestación lo pide) o reprogramar/cancelar. No tiene "Nuevo
// turno" (eso es de la mesa de atención) ni el link de autoservicio.

const ESTADO_COLOR = {
  reservado: { bg: 'rgba(245,127,23,0.14)', fg: '#b35900' },
  cumplido: { bg: 'rgba(31,138,101,0.16)', fg: '#1f8a65' },
  cancelado: { bg: 'rgba(198,40,40,0.12)', fg: '#c62828' },
} as const

type FiltroTiempo = 'pendientes' | 'hoy' | 'todos'

export function MisTurnos() {
  const push = useNotificationsStore((s) => s.push)
  const [tiempo, setTiempo] = useState<FiltroTiempo>('pendientes')
  const [fTexto, setFTexto] = useState('')
  const [editTurno, setEditTurno] = useState<Turno | null>(null)
  const [confirmCumplir, setConfirmCumplir] = useState<Turno | null>(null)
  const [confirmCancelar, setConfirmCancelar] = useState<Turno | null>(null)
  const [detalle, setDetalle] = useState<Turno | null>(null)

  const { data, isLoading, isError, error, refetch, isFetching } = useTurnos({})
  const cumplir = useCumplirTurno()
  const cancelar = useCancelarTurno()

  const turnos = data ?? []
  const hoy = hoy_local()

  const filtrados = useMemo(() => {
    let res = [...turnos]
    if (tiempo === 'pendientes') res = res.filter((t) => t.estado === 'reservado')
    else if (tiempo === 'hoy') res = res.filter((t) => t.fecha === hoy)
    const txt = fTexto.trim().toLowerCase()
    if (txt) {
      res = res.filter((t) =>
        [t.ciudadano_nombre, t.ciudadano_dni, t.recurso_nombre, t.agente_nombre, t.prestacion_nombre, t.observaciones]
          .filter(Boolean)
          .join(' ')
          .toLowerCase()
          .includes(txt),
      )
    }
    // Próximos primero (fecha + hora ascendente): lo que hay que atender antes.
    res.sort((a, b) => (a.fecha + a.hora_inicio).localeCompare(b.fecha + b.hora_inicio))
    return res
  }, [turnos, tiempo, fTexto, hoy])

  const counts = useMemo(() => {
    const pendientes = turnos.filter((t) => t.estado === 'reservado').length
    const hoyCount = turnos.filter((t) => t.fecha === hoy && t.estado === 'reservado').length
    return { pendientes, hoy: hoyCount }
  }, [turnos, hoy])

  async function doCumplir(t: Turno, body: CumplirTurnoBody) {
    setConfirmCumplir(null)
    try {
      await cumplir.mutateAsync({ id_turno: t.id_turno, ...body })
      push({
        kind: 'success',
        title: body.intervencion ? 'Atención registrada y turno cumplido' : 'Turno marcado como cumplido',
      })
    } catch (e) {
      push({ kind: 'error', title: 'No se pudo cumplir', body: (e as Error).message })
    }
  }

  async function doCancelar(t: Turno) {
    setConfirmCancelar(null)
    try {
      await cancelar.mutateAsync(t.id_turno)
      push({ kind: 'success', title: 'Turno cancelado' })
    } catch (e) {
      push({ kind: 'error', title: 'No se pudo cancelar', body: (e as Error).message })
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <h1 style={titulo}>mis turnos</h1>
        <p style={{ margin: '6px 0 0', color: 'var(--fg-3)', fontSize: 'var(--size-btn)' }}>
          los turnos a tu cargo. Cumplilos al atender (registrando la atención si la prestación lo requiere),
          reprogramalos o cancelalos.
        </p>
      </div>

      {/* Toolbar simple: foco temporal + búsqueda */}
      <div style={toolbar}>
        <div style={{ display: 'flex', gap: 6 }}>
          <TabBtn active={tiempo === 'pendientes'} onClick={() => setTiempo('pendientes')}>
            Pendientes {counts.pendientes > 0 && <Pill>{counts.pendientes}</Pill>}
          </TabBtn>
          <TabBtn active={tiempo === 'hoy'} onClick={() => setTiempo('hoy')}>
            Hoy {counts.hoy > 0 && <Pill>{counts.hoy}</Pill>}
          </TabBtn>
          <TabBtn active={tiempo === 'todos'} onClick={() => setTiempo('todos')}>
            Todos
          </TabBtn>
        </div>
        <div style={field}>
          <input
            type="text"
            value={fTexto}
            onChange={(e) => setFTexto(e.target.value)}
            placeholder="Buscar ciudadano, DNI o prestación"
            style={{ ...inp, minWidth: 240 }}
          />
        </div>
        <button onClick={() => refetch()} style={{ ...btnGhost, marginLeft: 'auto' }} title="Refrescar">
          <RefreshCw size={14} strokeWidth={1.5} style={{ animation: isFetching ? 'spin 1s linear infinite' : undefined }} />
        </button>
      </div>

      {isError && <div style={errorBanner}>{(error as Error)?.message ?? 'Error al cargar turnos'}</div>}

      <div style={card}>
        <table style={table}>
          <thead>
            <tr>
              <th style={th}>Fecha / Hora</th>
              <th style={th}>Ciudadano</th>
              <th style={th}>Atiende</th>
              <th style={th}>Prestación</th>
              <th style={th}>Estado</th>
              <th style={{ ...th, textAlign: 'right' }}>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={6} style={empty}>Cargando…</td></tr>}
            {!isLoading && !isError && filtrados.length === 0 && (
              <tr><td colSpan={6} style={empty}>
                {tiempo === 'pendientes' ? 'No tenés turnos pendientes. ¡Al día!' : 'No hay turnos para este filtro.'}
              </td></tr>
            )}
            {filtrados.map((t) => (
              <tr key={t.id_turno} onClick={() => setDetalle(t)} style={{ cursor: 'pointer' }} title="Ver detalle del turno">
                <td style={td}>
                  <div style={mono}>{t.fecha}</div>
                  <div style={{ ...mono, fontSize: '0.74rem', color: 'var(--fg-3)' }}>
                    {t.hora_inicio.slice(0, 5)}–{t.hora_fin.slice(0, 5)}
                  </div>
                </td>
                <td style={td}>
                  {t.ciudadano_nombre ?? '—'}
                  {t.ciudadano_dni && <div style={{ fontSize: '0.72rem', color: 'var(--fg-3)' }}>DNI {t.ciudadano_dni}</div>}
                </td>
                <td style={td}>
                  {t.recurso_nombre ?? t.agente_nombre ?? '—'}
                  <div style={{ fontSize: '0.7rem', color: 'var(--fg-3)' }}>
                    {t.id_espacio != null ? 'Lugar de atención' : 'Agente'}
                  </div>
                </td>
                <td style={td}>{t.prestacion_nombre ?? '—'}</td>
                <td style={td}><EstadoBadge estado={t.estado} /></td>
                <td style={{ ...td, textAlign: 'right', whiteSpace: 'nowrap' }} onClick={(e) => e.stopPropagation()}>
                  {t.estado === 'reservado' ? (
                    <>
                      <button onClick={() => { setEditTurno(t) }} style={btnGhostSm}>Reprogramar</button>
                      <button onClick={() => setConfirmCumplir(t)} style={{ ...btnSuccessSm, marginLeft: 4 }}>Cumplir</button>
                      <button onClick={() => setConfirmCancelar(t)} style={{ ...btnDangerSm, marginLeft: 4 }}>Cancelar</button>
                    </>
                  ) : (
                    <span style={{ color: 'var(--fg-3)', fontSize: '0.78rem' }}>—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <TurnoFormModal open={editTurno != null} onClose={() => setEditTurno(null)} turno={editTurno} />
      <TurnoDetalleModal turno={detalle} onClose={() => setDetalle(null)} />
      <CumplirTurnoModal
        turno={confirmCumplir}
        onConfirm={(body) => confirmCumplir && doCumplir(confirmCumplir, body)}
        onCancel={() => setConfirmCumplir(null)}
      />
      <ConfirmModal
        open={confirmCancelar != null}
        title="Cancelar turno"
        message={`Cancelar el turno de ${confirmCancelar?.ciudadano_nombre ?? ''}? Libera el bloque en la agenda.`}
        confirmLabel="Cancelar turno"
        danger
        onConfirm={() => confirmCancelar && doCancelar(confirmCancelar)}
        onCancel={() => setConfirmCancelar(null)}
      />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

function TabBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      style={{
        ...btnBase, fontSize: '0.82rem', padding: '7px 14px',
        background: active ? 'var(--surface-400)' : 'transparent',
        color: active ? 'var(--fg-1)' : 'var(--fg-2)',
        border: '1px solid', borderColor: active ? 'var(--border-medium)' : 'var(--border-primary)',
        fontWeight: active ? 600 : 500,
      }}
    >
      {children}
    </button>
  )
}

function Pill({ children }: { children: React.ReactNode }) {
  return (
    <span style={{
      marginLeft: 6, background: 'var(--zaris-orange)', color: 'white',
      fontSize: '0.7rem', fontWeight: 700, padding: '1px 7px', borderRadius: 999,
    }}>{children}</span>
  )
}

function EstadoBadge({ estado }: { estado: keyof typeof ESTADO_COLOR }) {
  const c = ESTADO_COLOR[estado]
  return (
    <span style={{
      background: c.bg, color: c.fg, fontSize: '0.72rem', fontWeight: 600,
      padding: '2px 9px', borderRadius: 999, textTransform: 'capitalize',
    }}>{estado}</span>
  )
}

const titulo: React.CSSProperties = {
  margin: 0, fontFamily: 'var(--font-display)', fontSize: 'var(--size-section)',
  fontWeight: 400, letterSpacing: 'var(--track-section)', color: 'var(--fg-1)',
}

const toolbar: React.CSSProperties = {
  display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center',
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 12, padding: 14,
}

const field: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: 4 }

const inp: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: 13, padding: '6px 10px',
  borderRadius: 'var(--radius-md)', border: '1px solid var(--border-primary)',
  background: 'var(--surface-100)', outline: 'none',
}

const btnBase: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.82rem', cursor: 'pointer',
  borderRadius: 8, padding: '7px 12px', border: '1px solid transparent', fontWeight: 500,
  display: 'inline-flex', alignItems: 'center', gap: 6,
}

const btnGhost: React.CSSProperties = {
  ...btnBase, background: 'transparent', color: 'var(--fg-2)', border: '1px solid var(--border-medium)',
}

const btnSmBase: React.CSSProperties = { ...btnBase, fontSize: '0.76rem', padding: '4px 9px' }

const btnGhostSm: React.CSSProperties = {
  ...btnSmBase, background: 'transparent', color: 'var(--fg-2)', border: '1px solid var(--border-medium)',
}

const btnSuccessSm: React.CSSProperties = {
  ...btnSmBase, background: '#1f8a65', color: 'white', borderColor: '#1f8a65',
}

const btnDangerSm: React.CSSProperties = {
  ...btnSmBase, background: 'transparent', color: 'var(--color-error)', borderColor: 'var(--color-error)',
}

const card: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 12, overflowX: 'auto',
}

const table: React.CSSProperties = {
  width: '100%', borderCollapse: 'separate', borderSpacing: 0, fontSize: '0.84rem', minWidth: 760,
}

const th: React.CSSProperties = {
  textAlign: 'left', fontWeight: 600, fontSize: '0.72rem', textTransform: 'uppercase',
  letterSpacing: '0.04em', color: 'var(--fg-3)', padding: '9px 12px',
  borderBottom: '1px solid var(--border-primary)', background: 'var(--surface-300)', whiteSpace: 'nowrap',
}

const td: React.CSSProperties = {
  padding: '10px 12px', borderBottom: '1px solid var(--border-primary)',
  verticalAlign: 'middle', background: 'var(--surface-100)',
}

const mono: React.CSSProperties = {
  fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--fg-2)', whiteSpace: 'nowrap',
}

const empty: React.CSSProperties = {
  padding: 36, textAlign: 'center', color: 'var(--fg-3)', fontSize: '0.88rem',
}

const errorBanner: React.CSSProperties = {
  background: '#ffebee', border: '1px solid #ffcdd2', borderLeft: '4px solid var(--color-error)',
  borderRadius: 8, padding: '12px 16px', color: '#c62828', fontSize: '0.86rem',
}
