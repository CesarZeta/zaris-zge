import { useMemo, useState } from 'react'
import { Plus, RefreshCw, Ticket, ExternalLink } from 'lucide-react'
import { useEventosEntrada, useCancelarEventoEntrada } from '../hooks/useEntradas'
import { EventoEntradaFormModal } from '../components/EventoEntradaFormModal'
import { ReservaModal } from '../../agenda/modals/ReservaModal'
import { ConfirmModal } from '../../agenda/components/ConfirmModal'
import { useEspacios } from '../../agenda/hooks/useEspacios'
import { useNotificationsStore } from '../../../stores/notifications'
import type { Evento } from '../../agenda/types/agenda'

export function Overview() {
  const push = useNotificationsStore((s) => s.push)
  const { data, isLoading, isError, error, refetch, isFetching } = useEventosEntrada()
  const espacios = useEspacios()
  const cancelar = useCancelarEventoEntrada()

  const [fTexto, setFTexto] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [reservaEvento, setReservaEvento] = useState<Evento | null>(null)
  const [confirmCancelar, setConfirmCancelar] = useState<Evento | null>(null)

  const eventos = data ?? []

  const espacioNombre = useMemo(() => {
    const m = new Map<number, string>()
    ;(espacios.data ?? []).forEach((e) => m.set(e.id_espacio, e.nombre))
    return m
  }, [espacios.data])

  const filtrados = useMemo(() => {
    const txt = fTexto.trim().toLowerCase()
    if (!txt) return eventos
    return eventos.filter((e) =>
      [e.nombre, e.descripcion, e.id_espacio != null ? espacioNombre.get(e.id_espacio) : '']
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
        .includes(txt),
    )
  }, [eventos, fTexto, espacioNombre])

  async function doCancelar(e: Evento) {
    setConfirmCancelar(null)
    try {
      await cancelar.mutateAsync(e.id_evento)
      push({ kind: 'success', title: 'Evento cancelado' })
    } catch (err) {
      push({ kind: 'error', title: 'No se pudo cancelar', body: (err as Error).message })
    }
  }

  function linkPublico(e: Evento): string | null {
    if (!e.admite_autoservicio || !e.token_publico) return null
    return `${window.location.origin}${window.location.pathname}#/autoservicio/${e.token_publico}`
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <h1 style={titulo}>entradas</h1>
        <p style={{ margin: '6px 0 0', color: 'var(--fg-3)', fontSize: 'var(--size-btn)' }}>
          eventos con cupo en espacios físicos — gestión de reservas de entradas.
        </p>
      </div>

      <div style={toolbar}>
        <div style={field}>
          <label style={lbl}>Buscar</label>
          <input
            type="text"
            value={fTexto}
            onChange={(e) => setFTexto(e.target.value)}
            placeholder="Nombre del evento o espacio"
            style={{ ...inp, minWidth: 260 }}
          />
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'flex-end' }}>
          <button onClick={() => refetch()} style={btnGhost} title="Refrescar">
            <RefreshCw size={14} strokeWidth={1.5} style={{ animation: isFetching ? 'spin 1s linear infinite' : undefined }} />
          </button>
          <button onClick={() => setModalOpen(true)} style={btnPrimary}>
            <Plus size={14} strokeWidth={1.5} /> Nuevo evento
          </button>
        </div>
      </div>

      {isError && <div style={errorBanner}>{(error as Error)?.message ?? 'Error al cargar eventos'}</div>}

      {!isLoading && !isError && filtrados.length === 0 && (
        <div style={emptyCard}>
          <Ticket size={28} strokeWidth={1.5} style={{ color: 'var(--fg-3)' }} />
          <p style={{ margin: '10px 0 4px', fontSize: '0.92rem', color: 'var(--fg-2)' }}>
            No hay eventos con entradas todavía.
          </p>
          <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--fg-3)' }}>
            Creá un evento y asignale un espacio físico para empezar a gestionar entradas.
          </p>
        </div>
      )}

      {filtrados.length > 0 && (
        <div style={grid}>
          {filtrados.map((e) => {
            const link = linkPublico(e)
            const cancelado = e.estado_codigo === 'cancelado'
            return (
              <div key={e.id_evento} style={{ ...cardEvento, opacity: cancelado ? 0.6 : 1 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                  <div>
                    <div style={{ fontSize: '0.96rem', fontWeight: 600, color: 'var(--fg-1)' }}>{e.nombre}</div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--fg-3)', marginTop: 2 }}>
                      {e.id_espacio != null ? (espacioNombre.get(e.id_espacio) ?? `espacio #${e.id_espacio}`) : 'sin espacio'}
                    </div>
                  </div>
                  {cancelado && <span style={badgeCancelado}>cancelado</span>}
                </div>

                <div style={{ display: 'flex', gap: 14, fontSize: '0.8rem', color: 'var(--fg-2)', fontFamily: 'var(--font-mono)' }}>
                  <span>{e.fecha}</span>
                  <span>{e.hora_inicio.slice(0, 5)}–{e.hora_fin.slice(0, 5)}</span>
                  <span>cap. {e.capacidad_ciudadanos}</span>
                </div>

                {e.descripcion && (
                  <div style={{ fontSize: '0.8rem', color: 'var(--fg-3)' }}>{e.descripcion}</div>
                )}

                {link && (
                  <a href={link} target="_blank" rel="noopener noreferrer" style={linkStyle}>
                    <ExternalLink size={12} strokeWidth={1.5} /> link público de reserva
                  </a>
                )}

                <div style={{ display: 'flex', gap: 8, marginTop: 'auto', paddingTop: 8 }}>
                  <button onClick={() => setReservaEvento(e)} style={btnAccentSm}>Gestionar entradas</button>
                  {!cancelado && (
                    <button onClick={() => setConfirmCancelar(e)} style={btnDangerSm}>Cancelar</button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      <EventoEntradaFormModal open={modalOpen} onClose={() => setModalOpen(false)} />
      <ReservaModal
        open={reservaEvento != null}
        idEvento={reservaEvento?.id_evento ?? null}
        onClose={() => setReservaEvento(null)}
      />
      <ConfirmModal
        open={confirmCancelar != null}
        title="Cancelar evento"
        message={`Cancelar el evento "${confirmCancelar?.nombre ?? ''}"? Las entradas reservadas quedan sin efecto.`}
        confirmLabel="Cancelar evento"
        danger
        onConfirm={() => confirmCancelar && doCancelar(confirmCancelar)}
        onCancel={() => setConfirmCancelar(null)}
      />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
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

const btnAccentSm: React.CSSProperties = {
  ...btnBase, fontSize: '0.76rem', padding: '5px 10px',
  background: 'var(--zaris-orange)', color: 'white', borderColor: 'var(--zaris-orange)',
}

const btnDangerSm: React.CSSProperties = {
  ...btnBase, fontSize: '0.76rem', padding: '5px 10px',
  background: 'transparent', color: 'var(--color-error)', borderColor: 'var(--color-error)',
}

const grid: React.CSSProperties = {
  display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 14,
}

const cardEvento: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 8,
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 12, padding: 16, minHeight: 160,
}

const badgeCancelado: React.CSSProperties = {
  background: 'rgba(198,40,40,0.12)', color: '#c62828', fontSize: '0.7rem',
  fontWeight: 600, padding: '2px 8px', borderRadius: 999, whiteSpace: 'nowrap',
}

const linkStyle: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 4,
  fontSize: '0.76rem', color: 'var(--zaris-orange)', textDecoration: 'none',
}

const emptyCard: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 12, padding: '48px 24px', textAlign: 'center',
}

const errorBanner: React.CSSProperties = {
  background: '#ffebee', border: '1px solid #ffcdd2', borderLeft: '4px solid var(--color-error)',
  borderRadius: 8, padding: '12px 16px', color: '#c62828', fontSize: '0.86rem',
}
