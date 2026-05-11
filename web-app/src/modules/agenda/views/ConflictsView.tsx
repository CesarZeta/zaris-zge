import { useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import { useConflictos } from '../hooks/useConflictos'
import { Badge, Card, EmptyState, Skeleton } from '../../../ui'
import { ConflictoModal } from '../modals/ConflictoModal'
import type { Conflicto } from '../types/agenda'

export function ConflictsView() {
  const [filtroResuelto, setFiltroResuelto] = useState<'no' | 'si' | 'todos'>('no')
  const resuelto = filtroResuelto === 'todos' ? undefined : filtroResuelto === 'si'
  const { data, isLoading, isError, error } = useConflictos(resuelto)
  const [sel, setSel] = useState<Conflicto | null>(null)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 'var(--size-subhead)', fontWeight: 400, letterSpacing: 'var(--track-subhead)', color: 'var(--fg-1)' }}>
          conflictos
        </h2>
        <div style={{ display: 'flex', gap: 4 }}>
          {(['no', 'si', 'todos'] as const).map((opt) => (
            <button
              key={opt}
              onClick={() => setFiltroResuelto(opt)}
              style={{
                padding: '6px 12px', borderRadius: 'var(--radius-pill)',
                border: 'none', cursor: 'pointer',
                background: filtroResuelto === opt ? 'var(--zaris-dark)' : 'var(--surface-400)',
                color: filtroResuelto === opt ? 'var(--zaris-cream)' : 'var(--fg-2)',
                fontFamily: 'var(--font-display)', fontSize: 12,
              }}
            >
              {opt === 'no' ? 'pendientes' : opt === 'si' ? 'resueltos' : 'todos'}
            </button>
          ))}
        </div>
      </div>

      {isLoading && <Skeleton height={200} />}
      {isError && <div style={{ color: 'var(--color-error)', fontSize: 13 }}>Error: {(error as Error).message}</div>}
      {data && data.length === 0 && (
        <EmptyState title="No hay conflictos" description={filtroResuelto === 'no' ? 'Genial, no hay solapes pendientes.' : ''} />
      )}
      {data && data.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {data.map((c) => (
            <Card key={c.id_conflicto} variant="default" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <AlertTriangle size={20} strokeWidth={1.5} style={{ color: c.resuelto ? 'var(--color-success)' : 'var(--color-error)' }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, color: 'var(--fg-1)' }}>
                  conflicto #{c.id_conflicto} · {c.tipo_recurso} #{c.id_recurso}
                </div>
                <div style={{ fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>
                  ocupaciones #{c.id_ocupacion_origen ?? '?'} vs #{c.id_ocupacion_conflicto ?? '?'} ·
                  detectado {new Date(c.fecha_deteccion).toLocaleString('es-AR')}
                </div>
              </div>
              <Badge kind={c.resuelto ? 'success' : 'error'}>{c.resuelto ? 'resuelto' : 'pendiente'}</Badge>
              <button
                onClick={() => setSel(c)}
                style={{ background: 'var(--surface-300)', border: 'none', borderRadius: 'var(--radius-md)', padding: '6px 12px', cursor: 'pointer', fontFamily: 'var(--font-display)', fontSize: 13 }}
              >
                ver
              </button>
            </Card>
          ))}
        </div>
      )}

      <ConflictoModal open={sel != null} onClose={() => setSel(null)} conflicto={sel} />
    </div>
  )
}
