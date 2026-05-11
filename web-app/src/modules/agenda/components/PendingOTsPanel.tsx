import { useDraggable } from '@dnd-kit/core'
import { ChevronRight, ChevronLeft, AlertCircle } from 'lucide-react'
import { useOTsPendientes } from '../dnd/useOTsPendientes'
import type { OTPendiente } from '../dnd/types'
import { Skeleton } from '../../../ui'

interface Props {
  open: boolean
  onToggle: () => void
}

export function PendingOTsPanel({ open, onToggle }: Props) {
  const q = useOTsPendientes(true)

  return (
    <aside
      style={{
        width: open ? 280 : 36,
        flex: '0 0 auto',
        transition: 'width 160ms',
        background: 'var(--surface-100)',
        border: '1px solid var(--border-primary)',
        borderRadius: 'var(--radius-lg)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        minHeight: 360,
      }}
    >
      <button
        type="button"
        onClick={onToggle}
        title={open ? 'Colapsar panel' : 'Expandir panel'}
        style={{
          display: 'flex', alignItems: 'center', justifyContent: open ? 'space-between' : 'center',
          gap: 6, padding: '10px 12px',
          background: 'var(--surface-200)', border: 'none', borderBottom: '1px solid var(--border-medium)',
          cursor: 'pointer', fontFamily: 'var(--font-display)', fontSize: 13,
          color: 'var(--fg-1)', fontWeight: 500, textAlign: 'left',
        }}
      >
        {open && <span>OTs pendientes {q.data ? `(${q.data.length})` : ''}</span>}
        {open ? <ChevronRight size={14} strokeWidth={1.5} /> : <ChevronLeft size={14} strokeWidth={1.5} />}
      </button>

      {open && (
        <div style={{ flex: 1, overflowY: 'auto', padding: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
          {q.isLoading && <Skeleton height={80} />}
          {q.isError && (
            <div style={{ color: 'var(--color-error)', fontSize: 12, padding: 8 }}>
              Error: {(q.error as Error).message}
            </div>
          )}
          {q.data && q.data.length === 0 && (
            <div style={{ color: 'var(--fg-3)', fontSize: 12, padding: 16, textAlign: 'center' }}>
              No hay OTs pendientes sin asignar.
            </div>
          )}
          {q.data?.map((ot) => <PendingOTItem key={ot.id_ot} ot={ot} />)}
        </div>
      )}
    </aside>
  )
}

function PendingOTItem({ ot }: { ot: OTPendiente }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `ot-${ot.id_ot}`,
    data: { kind: 'pending-ot', ot },
  })
  const dragTransform = transform
    ? `translate3d(${transform.x}px, ${transform.y}px, 0)`
    : undefined

  const prioColor = ot.reclamo_prioridad === 'Alta'  ? 'var(--color-error)'
                  : ot.reclamo_prioridad === 'Media' ? 'var(--zaris-gold)'
                  : 'var(--fg-3)'

  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      style={{
        background: 'var(--surface-200)',
        border: '1px solid var(--border-primary)',
        borderLeft: `3px solid ${prioColor}`,
        borderRadius: 'var(--radius-md)',
        padding: '8px 10px',
        cursor: isDragging ? 'grabbing' : 'grab',
        opacity: isDragging ? 0.4 : 1,
        transform: dragTransform,
        touchAction: 'none',
      }}
      title={ot.reclamo_descripcion ?? ot.nro_ot ?? ''}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6, marginBottom: 2 }}>
        <span style={{
          fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--zaris-orange)', fontWeight: 600,
        }}>
          {ot.nro_ot ?? `OT-${ot.id_ot}`}
        </span>
        {ot.reclamo_prioridad && (
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 3,
            fontSize: 10, color: prioColor, fontFamily: 'var(--font-mono)', textTransform: 'uppercase',
          }}>
            <AlertCircle size={10} strokeWidth={1.5} /> {ot.reclamo_prioridad}
          </span>
        )}
      </div>
      <div style={{
        fontSize: 12, color: 'var(--fg-1)', fontFamily: 'var(--font-display)',
        display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
        overflow: 'hidden', textOverflow: 'ellipsis',
        lineHeight: 1.3,
      }}>
        {ot.reclamo_descripcion || 'Sin descripcion'}
      </div>
      {ot.sla_dias != null && (
        <div style={{ fontSize: 10, color: 'var(--fg-3)', marginTop: 3, fontFamily: 'var(--font-mono)' }}>
          SLA {ot.sla_dias}d
        </div>
      )}
    </div>
  )
}
