import { useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { Modal } from '../Modal'
import { Button, EmptyState, Skeleton } from '../../../../ui'
import { useEspacio, useVincularAgente, useDesvincularAgente } from '../../hooks/useEspacios'
import { RecursoPicker } from '../RecursoPicker'

interface Props {
  open: boolean
  onClose: () => void
  idEspacio: number | null
}

export function EspacioAgentesModal({ open, onClose, idEspacio }: Props) {
  const det = useEspacio(idEspacio)
  const vincular   = useVincularAgente()
  const desvincular = useDesvincularAgente()
  const [agenteSel, setAgenteSel] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function agregar() {
    if (!idEspacio || !agenteSel) return
    setError(null)
    try {
      await vincular.mutateAsync({ idEspacio, id_agente: agenteSel })
      setAgenteSel(null)
    } catch (e) {
      setError((e as Error).message || 'No se pudo vincular.')
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={det.data ? `Agentes vinculados - ${det.data.nombre}` : 'Agentes vinculados'}
      footer={<Button variant="ghost" onClick={onClose}>Cerrar</Button>}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {det.isLoading && <Skeleton height={120} />}
        {det.data && (
          <>
            <p style={{ margin: 0, color: 'var(--fg-3)', fontSize: 13, fontFamily: 'var(--font-display)' }}>
              Solo los agentes vinculados aportan disponibilidad horaria a un espacio atendido. La interseccion del horario del espacio con la union de horarios de sus agentes define cuando el espacio esta disponible.
            </p>
            <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
              <div style={{ flex: 1 }}>
                <label style={{ fontFamily: 'var(--font-display)', fontSize: 11, color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '.04em' }}>
                  Agregar agente
                </label>
                <RecursoPicker tipo="agente" value={agenteSel} onChange={setAgenteSel} placeholder="Seleccionar..." />
              </div>
              <Button variant="accent" icon={<Plus size={14} strokeWidth={1.5} />} onClick={agregar} disabled={!agenteSel || vincular.isPending}>
                Vincular
              </Button>
            </div>
            {error && <div style={{ color: 'var(--color-error)', fontSize: 13, fontFamily: 'var(--font-mono)' }}>{error}</div>}

            {det.data.agentes_vinculados.length === 0 ? (
              <EmptyState title="Sin agentes vinculados" description="Sin agentes este espacio no tendra disponibilidad efectiva." />
            ) : (
              <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
                {det.data.agentes_vinculados.map((a) => (
                  <li
                    key={a.id_espacio_agente}
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '8px 12px', background: 'var(--surface-200)',
                      borderRadius: 'var(--radius-md)', border: '1px solid var(--border-primary)',
                    }}
                  >
                    <span style={{ fontFamily: 'var(--font-display)', fontSize: 13, color: 'var(--fg-1)' }}>
                      {a.agente_nombre ?? `Agente ${a.id_agente}`}
                    </span>
                    <Button
                      variant="ghost"
                      icon={<Trash2 size={13} strokeWidth={1.5} />}
                      onClick={() => {
                        if (idEspacio && confirm(`Desvincular a "${a.agente_nombre ?? 'el agente'}" del espacio?`)) {
                          desvincular.mutate({ idEspacio, idEspacioAgente: a.id_espacio_agente })
                        }
                      }}
                    >
                      Quitar
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </div>
    </Modal>
  )
}
