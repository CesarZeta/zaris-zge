import { useState } from 'react'
import { Plus, Users, Calendar } from 'lucide-react'
import { useEventos } from '../hooks/useEventos'
import { Badge, Button, Card, EmptyState, Skeleton, Table } from '../../../ui'
import { EventoModal } from '../modals/EventoModal'
import { ReservaModal } from '../modals/ReservaModal'
import { EventoEncargadosModal } from '../modals/EventoEncargadosModal'
import type { Evento } from '../types/agenda'

export function EventListView() {
  const [fechaDesde, setFechaDesde] = useState('')
  const [fechaHasta, setFechaHasta] = useState('')
  const [limit] = useState(50)
  const [offset, setOffset] = useState(0)
  const { data, isLoading, isError, error } = useEventos({
    fecha_desde: fechaDesde || undefined,
    fecha_hasta: fechaHasta || undefined,
    limit, offset,
  })
  const [editId, setEditId] = useState<number | null>(null)
  const [nuevo, setNuevo] = useState(false)
  const [reservasId, setReservasId] = useState<number | null>(null)
  const [encargadosId, setEncargadosId] = useState<number | null>(null)

  const rows = (data?.data ?? []) as unknown as Record<string, unknown>[]
  const total = Number(data?.headers.get('X-Total-Count') ?? rows.length)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
        <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 'var(--size-subhead)', fontWeight: 400, letterSpacing: 'var(--track-subhead)', color: 'var(--fg-1)' }}>
          eventos
        </h2>
        <Button variant="accent" icon={<Plus size={14} strokeWidth={1.5} />} onClick={() => setNuevo(true)}>
          Nuevo evento
        </Button>
      </div>

      <Card variant="default">
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <label style={lbl}>desde</label>
          <input type="date" value={fechaDesde} onChange={(e) => setFechaDesde(e.target.value)} style={inp} />
          <label style={lbl}>hasta</label>
          <input type="date" value={fechaHasta} onChange={(e) => setFechaHasta(e.target.value)} style={inp} />
          <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>
            total: {total}
          </span>
        </div>
      </Card>

      {isLoading && <Skeleton height={200} />}
      {isError && (
        <div style={{ padding: 16, color: 'var(--color-error)', fontFamily: 'var(--font-mono)', fontSize: 13 }}>
          Error: {(error as Error).message}
        </div>
      )}
      {data && rows.length === 0 && <EmptyState title="No hay eventos en el rango" />}
      {data && rows.length > 0 && (
        <Card variant="default">
          <Table
            keyField="id_evento"
            columns={[
              { key: 'fecha',       header: 'fecha',    render: (r) => <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{r.fecha as string}</span> },
              { key: 'hora_inicio', header: 'horario',  render: (r) => <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{String(r.hora_inicio).slice(0, 5)} - {String(r.hora_fin).slice(0, 5)}</span> },
              { key: 'nombre',      header: 'nombre' },
              { key: 'capacidad_ciudadanos', header: 'cupo' },
              { key: 'estado_codigo',        header: 'estado',
                render: (r) => <Badge kind={r.estado_codigo === 'activo' ? 'success' : r.estado_codigo === 'cancelado' ? 'error' : 'neutral'}>{String(r.estado_codigo ?? '?')}</Badge>,
              },
              { key: 'acciones',    header: 'acciones',
                render: (r) => {
                  const ev = r as unknown as Evento
                  return (
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button aria-label="Editar"      onClick={() => setEditId(ev.id_evento)}       style={iconBtn}><Calendar size={13} strokeWidth={1.5} /></button>
                      <button aria-label="Encargados"  onClick={() => setEncargadosId(ev.id_evento)} style={iconBtn}><Users size={13} strokeWidth={1.5} /></button>
                      <button aria-label="Reservas"    onClick={() => setReservasId(ev.id_evento)}   style={iconBtn}>+R</button>
                    </div>
                  )
                },
              },
            ]}
            rows={rows}
          />
          <div style={{ marginTop: 10, display: 'flex', gap: 8, alignItems: 'center', justifyContent: 'flex-end' }}>
            <Button variant="ghost" onClick={() => setOffset(Math.max(0, offset - limit))}>Anterior</Button>
            <span style={{ fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>
              {offset + 1} - {Math.min(offset + limit, total)} de {total}
            </span>
            <Button variant="ghost" onClick={() => offset + limit < total && setOffset(offset + limit)}>Siguiente</Button>
          </div>
        </Card>
      )}

      <EventoModal open={nuevo || editId != null} onClose={() => { setNuevo(false); setEditId(null) }} idEvento={editId} />
      <ReservaModal open={reservasId != null} onClose={() => setReservasId(null)} idEvento={reservasId} />
      <EventoEncargadosModal open={encargadosId != null} onClose={() => setEncargadosId(null)} idEvento={encargadosId} />
    </div>
  )
}

const inp: React.CSSProperties = {
  fontFamily: 'var(--font-mono)', fontSize: 12, padding: '4px 8px',
  border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-md)',
  background: 'var(--surface-100)', outline: 'none',
}
const lbl: React.CSSProperties = { fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--font-display)', textTransform: 'uppercase' }
const iconBtn: React.CSSProperties = {
  background: 'transparent', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-md)',
  padding: '4px 8px', cursor: 'pointer', color: 'var(--fg-2)', fontSize: 11, fontFamily: 'var(--font-mono)',
  display: 'inline-flex', alignItems: 'center', gap: 3,
}
