import { useState } from 'react'
import { AlertTriangle, Search } from 'lucide-react'
import { useConflictos } from '../hooks/useConflictos'
import { Badge, Button, Card, EmptyState, Skeleton } from '../../../ui'
import { AvisoBuscar, useBusquedaDiferida } from '../../../ui/busqueda'
import { ConflictoModal } from '../modals/ConflictoModal'
import type { Conflicto } from '../types/agenda'

type FiltroResuelto = 'no' | 'si' | 'todos'

function aResuelto(f: FiltroResuelto): boolean | undefined {
  return f === 'todos' ? undefined : f === 'si'
}

export function ConflictsView() {
  // Búsqueda diferida (§23): las pills marcan el filtro (borrador) pero no
  // piden nada; "Ver conflictos" lo aplica y recién ahí sale el request.
  // Resolver un conflicto invalida ['agenda'] y la lista ya buscada se refresca.
  const busqueda = useBusquedaDiferida<{ resuelto: FiltroResuelto }>({ resuelto: 'no' })
  const filtroResuelto = busqueda.borrador.resuelto
  const aplicado = busqueda.aplicado?.resuelto ?? 'no'
  const { data, isLoading, isError, error } = useConflictos(
    aResuelto(aplicado),
    { enabled: busqueda.buscado, version: busqueda.version },
  )
  const [sel, setSel] = useState<Conflicto | null>(null)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
        <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 'var(--size-subhead)', fontWeight: 400, letterSpacing: 'var(--track-subhead)', color: 'var(--fg-1)' }}>
          conflictos
        </h2>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', gap: 4 }}>
            {(['no', 'si', 'todos'] as const).map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => busqueda.setBorrador({ resuelto: opt })}
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
          <Button
            type="button"
            variant="accent"
            icon={<Search size={14} strokeWidth={1.5} />}
            onClick={() => busqueda.buscar()}
            title="Traer los conflictos del filtro elegido"
          >
            Ver conflictos
          </Button>
        </div>
      </div>

      {!busqueda.buscado && (
        <AvisoBuscar texto="Elegí pendientes, resueltos o todos y presioná Ver conflictos." />
      )}
      {busqueda.buscado && isLoading && <Skeleton height={200} />}
      {isError && <div style={{ color: 'var(--color-error)', fontSize: 13 }}>Error: {(error as Error).message}</div>}
      {data && data.length === 0 && (
        <EmptyState title="No hay conflictos" description={aplicado === 'no' ? 'Genial, no hay solapes pendientes.' : ''} />
      )}
      {data && data.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {data.map((c) => {
            const oo = c.ocupacion_origen_detalle as { fecha?: string; hora_inicio?: string; hora_fin?: string } | null
            const oc = c.ocupacion_conflicto_detalle as { fecha?: string; hora_inicio?: string; hora_fin?: string } | null
            const ocupFecha = oo?.fecha ?? oc?.fecha
            const ocupRango = oo
              ? `${oo.hora_inicio?.slice(0, 5)}-${oo.hora_fin?.slice(0, 5)}`
              : oc
              ? `${oc.hora_inicio?.slice(0, 5)}-${oc.hora_fin?.slice(0, 5)}`
              : null
            return (
              <Card key={c.id_conflicto} variant="default" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <AlertTriangle size={20} strokeWidth={1.5} style={{ color: c.resuelto ? 'var(--color-success)' : 'var(--color-error)' }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, color: 'var(--fg-1)' }}>
                    conflicto #{c.id_conflicto} · {c.tipo_recurso} #{c.id_recurso}
                    {ocupFecha && (
                      <span style={{ marginLeft: 8, color: 'var(--fg-2)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                        · {ocupFecha}{ocupRango ? ` ${ocupRango}` : ''}
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>
                    ocupaciones #{c.id_ocupacion_origen ?? '?'} vs #{c.id_ocupacion_conflicto ?? '?'} ·
                    detectado {new Date(c.fecha_deteccion).toLocaleString('es-AR')}
                  </div>
                </div>
                <Badge kind={c.resuelto ? 'success' : 'error'}>{c.resuelto ? 'resuelto' : 'pendiente'}</Badge>
                <button
                  type="button"
                  onClick={() => setSel(c)}
                  style={{ background: 'var(--surface-300)', border: 'none', borderRadius: 'var(--radius-md)', padding: '6px 12px', cursor: 'pointer', fontFamily: 'var(--font-display)', fontSize: 13 }}
                >
                  ver
                </button>
              </Card>
            )
          })}
        </div>
      )}

      <ConflictoModal open={sel != null} onClose={() => setSel(null)} conflicto={sel} />
    </div>
  )
}
