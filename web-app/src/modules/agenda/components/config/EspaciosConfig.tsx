import { useState } from 'react'
import { Plus, Pencil, Trash2, Users } from 'lucide-react'
import { useEspacios, useEliminarEspacio } from '../../hooks/useEspacios'
import { Button, Badge, EmptyState, Skeleton, Table } from '../../../../ui'
import { EspacioFormModal } from './EspacioFormModal'
import { EspacioAgentesModal } from './EspacioAgentesModal'
import type { EspacioAgenda } from '../../types/agenda'

export function EspaciosConfig() {
  const lista = useEspacios()
  const eliminar = useEliminarEspacio()
  const [formOpen, setFormOpen] = useState<{ espacio: EspacioAgenda | null } | null>(null)
  const [agentesOpen, setAgentesOpen] = useState<number | null>(null)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <p style={{ margin: 0, color: 'var(--fg-3)', fontSize: 13, fontFamily: 'var(--font-display)' }}>
          Espacios fisicos donde se desarrollan eventos o turnos. Los atendidos requieren agentes vinculados.
        </p>
        <Button variant="accent" icon={<Plus size={14} strokeWidth={1.5} />} onClick={() => setFormOpen({ espacio: null })}>
          Nuevo espacio
        </Button>
      </div>

      {lista.isLoading && <Skeleton height={200} />}
      {lista.isError && (
        <div style={{ padding: 16, color: 'var(--color-error)', fontFamily: 'var(--font-mono)', fontSize: 13 }}>
          Error: {(lista.error as Error).message}
        </div>
      )}
      {lista.data && lista.data.length === 0 && (
        <EmptyState
          title="Sin espacios cargados"
          description="Crea tu primer espacio para asignarlo a eventos y disponibilidad."
        />
      )}
      {lista.data && lista.data.length > 0 && (
        <div style={{ background: 'var(--surface-100)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-primary)', overflow: 'hidden' }}>
          <Table
            keyField="id_espacio"
            rows={lista.data}
            columns={[
              { key: 'nombre', header: 'Nombre' },
              { key: 'subarea_nombre', header: 'Subarea', render: (r) => r.subarea_nombre ?? <span style={{ color: 'var(--fg-3)' }}>—</span> },
              { key: 'direccion', header: 'Direccion', render: (r) => r.direccion ?? <span style={{ color: 'var(--fg-3)' }}>—</span> },
              { key: 'capacidad_personas', header: 'Capacidad', render: (r) => r.capacidad_personas ?? <span style={{ color: 'var(--fg-3)' }}>—</span> },
              {
                key: 'atendido',
                header: 'Tipo',
                render: (r) => (
                  <div style={{ display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' }}>
                    <Badge kind={r.atendido ? 'success' : 'neutral'}>{r.atendido ? 'atendido' : 'desatendido'}</Badge>
                    {r.atendido && r.cant_agentes === 0 && (
                      <Badge kind="warn">⚠ falta vincular agentes</Badge>
                    )}
                  </div>
                ),
              },
              {
                key: '_acciones',
                header: '',
                width: 180,
                render: (r) => (
                  <div style={{ display: 'flex', gap: 4, justifyContent: 'flex-end' }}>
                    {r.atendido && (
                      <Button variant="ghost" icon={<Users size={13} strokeWidth={1.5} />} onClick={() => setAgentesOpen(r.id_espacio)}>
                        Agentes
                      </Button>
                    )}
                    <Button variant="ghost" icon={<Pencil size={13} strokeWidth={1.5} />} onClick={() => setFormOpen({ espacio: r })}>
                      Editar
                    </Button>
                    <Button
                      variant="ghost"
                      icon={<Trash2 size={13} strokeWidth={1.5} />}
                      onClick={() => {
                        if (confirm(`Eliminar el espacio "${r.nombre}"? Esta accion es reversible (baja logica).`)) {
                          eliminar.mutate(r.id_espacio)
                        }
                      }}
                    >
                      Eliminar
                    </Button>
                  </div>
                ),
              },
            ]}
          />
        </div>
      )}

      <EspacioFormModal
        open={formOpen != null}
        onClose={() => setFormOpen(null)}
        espacio={formOpen?.espacio ?? null}
      />
      <EspacioAgentesModal
        open={agentesOpen != null}
        onClose={() => setAgentesOpen(null)}
        idEspacio={agentesOpen}
      />
    </div>
  )
}
