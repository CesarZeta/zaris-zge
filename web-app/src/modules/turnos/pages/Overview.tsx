import { useMemo, useState } from 'react'
import { Plus, RefreshCw } from 'lucide-react'
import { useTurnos, useCumplirTurno, useCancelarTurno } from '../hooks/useTurnos'
import { TurnoFormModal } from '../components/TurnoFormModal'
import { ConfirmModal } from '../../agenda/components/ConfirmModal'
import { useNotificationsStore } from '../../../stores/notifications'
import type { EstadoTurno, Turno } from '../types/turno'

type FiltroEstado = EstadoTurno | ''

const ESTADO_COLOR: Record<EstadoTurno, { bg: string; fg: string }> = {
  reservado: { bg: 'rgba(245,127,23,0.14)', fg: '#b35900' },
  cumplido: { bg: 'rgba(31,138,101,0.16)', fg: '#1f8a65' },
  cancelado: { bg: 'rgba(198,40,40,0.12)', fg: '#c62828' },
}

export function Overview() {
  const push = useNotificationsStore((s) => s.push)
  const [fEstado, setFEstado] = useState<FiltroEstado>('')
  const [fTexto, setFTexto] = useState('')
  const [fDesde, setFDesde] = useState('')
  const [fHasta, setFHasta] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editTurno, setEditTurno] = useState<Turno | null>(null)
  const [confirmCumplir, setConfirmCumplir] = useState<Turno | null>(null)
  const [confirmCancelar, setConfirmCancelar] = useState<Turno | null>(null)

  const { data, isLoading, isError, error, refetch, isFetching } = useTurnos({
    estado: fEstado || undefined,
    fecha_desde: fDesde || undefined,
    fecha_hasta: fHasta || undefined,
  })
  const cumplir = useCumplirTurno()
  const cancelar = useCancelarTurno()

  const turnos = data ?? []

  const filtrados = useMemo(() => {
    const txt = fTexto.trim().toLowerCase()
    if (!txt) return turnos
    return turnos.filter((t) =>
      [t.ciudadano_nombre, t.ciudadano_dni, t.agente_nombre, t.tipo_servicio_nombre, t.observaciones]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
        .includes(txt),
    )
  }, [turnos, fTexto])

  const counts = useMemo(() => {
    const c = { reservado: 0, cumplido: 0, cancelado: 0 }
    turnos.forEach((t) => { c[t.estado] += 1 })
    return c
  }, [turnos])

  async function doCumplir(t: Turno) {
    setConfirmCumplir(null)
    try {
      await cumplir.mutateAsync(t.id_turno)
      push({ kind: 'success', title: 'Turno marcado como cumplido' })
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
        <h1 style={titulo}>turnos</h1>
        <p style={{ margin: '6px 0 0', color: 'var(--fg-3)', fontSize: 'var(--size-btn)' }}>
          gestión de turnos de atención sobre la disponibilidad de agentes.
        </p>
      </div>

      {/* Toolbar */}
      <div style={toolbar}>
        <div style={field}>
          <label style={lbl}>Buscar</label>
          <input
            type="text"
            value={fTexto}
            onChange={(e) => setFTexto(e.target.value)}
            placeholder="Ciudadano, DNI, agente o servicio"
            style={{ ...inp, minWidth: 220 }}
          />
        </div>
        <div style={field}>
          <label style={lbl}>Estado</label>
          <select value={fEstado} onChange={(e) => setFEstado(e.target.value as FiltroEstado)} style={inp}>
            <option value="">Todos</option>
            <option value="reservado">Reservado</option>
            <option value="cumplido">Cumplido</option>
            <option value="cancelado">Cancelado</option>
          </select>
        </div>
        <div style={field}>
          <label style={lbl}>Desde</label>
          <input type="date" value={fDesde} onChange={(e) => setFDesde(e.target.value)} style={inp} />
        </div>
        <div style={field}>
          <label style={lbl}>Hasta</label>
          <input type="date" value={fHasta} onChange={(e) => setFHasta(e.target.value)} style={inp} />
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'flex-end' }}>
          <button onClick={() => refetch()} style={btnGhost} title="Refrescar">
            <RefreshCw size={14} strokeWidth={1.5} style={{ animation: isFetching ? 'spin 1s linear infinite' : undefined }} />
          </button>
          <button onClick={() => { setEditTurno(null); setModalOpen(true) }} style={btnPrimary}>
            <Plus size={14} strokeWidth={1.5} /> Nuevo turno
          </button>
        </div>
      </div>

      {/* Chips de conteo */}
      <div style={{ display: 'flex', gap: 8 }}>
        <Chip label="Reservados" value={counts.reservado} color={ESTADO_COLOR.reservado} />
        <Chip label="Cumplidos" value={counts.cumplido} color={ESTADO_COLOR.cumplido} />
        <Chip label="Cancelados" value={counts.cancelado} color={ESTADO_COLOR.cancelado} />
      </div>

      {/* Link publico de autoservicio */}
      <LinkAutoservicio />

      {isError && <div style={errorBanner}>{(error as Error)?.message ?? 'Error al cargar turnos'}</div>}

      {/* Tabla */}
      <div style={card}>
        <table style={table}>
          <thead>
            <tr>
              <th style={th}>Fecha / Hora</th>
              <th style={th}>Ciudadano</th>
              <th style={th}>Agente</th>
              <th style={th}>Servicio</th>
              <th style={th}>Estado</th>
              <th style={th}>Observaciones</th>
              <th style={{ ...th, textAlign: 'right' }}>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={7} style={empty}>Cargando…</td></tr>}
            {!isLoading && !isError && filtrados.length === 0 && (
              <tr><td colSpan={7} style={empty}>No hay turnos para los filtros seleccionados.</td></tr>
            )}
            {filtrados.map((t) => (
              <tr key={t.id_turno}>
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
                <td style={td}>{t.agente_nombre ?? '—'}</td>
                <td style={td}>{t.tipo_servicio_nombre ?? '—'}</td>
                <td style={td}><EstadoBadge estado={t.estado} /></td>
                <td style={{ ...td, maxWidth: 200, color: 'var(--fg-3)' }}>{t.observaciones ?? ''}</td>
                <td style={{ ...td, textAlign: 'right', whiteSpace: 'nowrap' }}>
                  {t.estado === 'reservado' ? (
                    <>
                      <button onClick={() => { setEditTurno(t); setModalOpen(true) }} style={btnGhostSm}>Reprogramar</button>
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

      <TurnoFormModal open={modalOpen} onClose={() => setModalOpen(false)} turno={editTurno} />
      <ConfirmModal
        open={confirmCumplir != null}
        title="Marcar turno como cumplido"
        message={`Confirmás que el turno de ${confirmCumplir?.ciudadano_nombre ?? ''} fue atendido?`}
        confirmLabel="Marcar cumplido"
        onConfirm={() => confirmCumplir && doCumplir(confirmCumplir)}
        onCancel={() => setConfirmCumplir(null)}
      />
      <ConfirmModal
        open={confirmCancelar != null}
        title="Cancelar turno"
        message={`Cancelar el turno de ${confirmCancelar?.ciudadano_nombre ?? ''}? Libera el bloque en la agenda del agente.`}
        confirmLabel="Cancelar turno"
        danger
        onConfirm={() => confirmCancelar && doCancelar(confirmCancelar)}
        onCancel={() => setConfirmCancelar(null)}
      />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

function LinkAutoservicio() {
  const push = useNotificationsStore((s) => s.push)
  // Turnos autoservicio no tiene token de entrada (el ciudadano arranca
  // eligiendo el tramite). El link es fijo: la pagina publica de turnos.
  const url = `${window.location.origin}${window.location.pathname}#/turnos-autoservicio`
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
      background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
      borderRadius: 12, padding: '12px 16px',
    }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <span style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--fg-2)' }}>
          Autoservicio para ciudadanos
        </span>
        <span style={{ fontSize: '0.74rem', color: 'var(--fg-3)' }}>
          Compartí este link para que reserven turnos sin pasar por mesa.
        </span>
      </div>
      <code style={{
        marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: '0.74rem',
        color: 'var(--fg-2)', background: 'var(--surface-300)',
        padding: '4px 8px', borderRadius: 6, maxWidth: 360,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }}>{url}</code>
      <button
        style={btnGhostSm}
        onClick={() => {
          navigator.clipboard?.writeText(url)
            .then(() => push({ kind: 'success', title: 'Link copiado' }))
            .catch(() => push({ kind: 'error', title: 'No se pudo copiar' }))
        }}
      >
        Copiar link
      </button>
    </div>
  )
}

function EstadoBadge({ estado }: { estado: EstadoTurno }) {
  const c = ESTADO_COLOR[estado]
  return (
    <span style={{
      background: c.bg, color: c.fg, fontSize: '0.72rem', fontWeight: 600,
      padding: '2px 9px', borderRadius: 999, textTransform: 'capitalize',
    }}>{estado}</span>
  )
}

function Chip({ label, value, color }: { label: string; value: number; color: { bg: string; fg: string } }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 6,
      background: color.bg, color: color.fg,
      padding: '5px 12px', borderRadius: 8, fontSize: '0.78rem', fontWeight: 500,
    }}>
      {label}<strong style={{ fontSize: '0.86rem' }}>{value}</strong>
    </div>
  )
}

const titulo: React.CSSProperties = {
  margin: 0, fontFamily: 'var(--font-display)', fontSize: 'var(--size-section)',
  fontWeight: 400, letterSpacing: 'var(--track-section)', color: 'var(--fg-1)',
}

const toolbar: React.CSSProperties = {
  display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end',
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 12, padding: 14,
}

const field: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: 4 }

const lbl: React.CSSProperties = {
  fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--fg-3)',
}

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

const btnPrimary: React.CSSProperties = {
  ...btnBase, background: 'var(--zaris-orange)', color: 'white', borderColor: 'var(--zaris-orange)',
}

const btnGhost: React.CSSProperties = {
  ...btnBase, background: 'transparent', color: 'var(--fg-2)', border: '1px solid var(--border-medium)',
}

const btnSmBase: React.CSSProperties = {
  ...btnBase, fontSize: '0.76rem', padding: '4px 9px',
}

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
  width: '100%', borderCollapse: 'separate', borderSpacing: 0,
  fontSize: '0.84rem', minWidth: 880,
}

const th: React.CSSProperties = {
  textAlign: 'left', fontWeight: 600, fontSize: '0.72rem',
  textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--fg-3)',
  padding: '9px 12px', borderBottom: '1px solid var(--border-primary)',
  background: 'var(--surface-300)', whiteSpace: 'nowrap',
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
