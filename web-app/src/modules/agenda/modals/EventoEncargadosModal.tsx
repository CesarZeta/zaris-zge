import { useState } from 'react'
import { Trash2, UserPlus } from 'lucide-react'
import { Modal } from '../components/Modal'
import { Button } from '../../../ui'
import { useEventoDetalle } from '../hooks/useEventos'
import { useAsignarEncargado, useDesasignarEncargado } from '../hooks/useOcupaciones'
import { useNotificationsStore } from '../../../stores/notifications'
import type { TipoRecurso } from '../types/agenda'

interface Props {
  open: boolean
  onClose: () => void
  idEvento: number | null
}

export function EventoEncargadosModal({ open, onClose, idEvento }: Props) {
  const push = useNotificationsStore((s) => s.push)
  const detalle = useEventoDetalle(open ? idEvento : null)
  const asignar = useAsignarEncargado()
  const desasignar = useDesasignarEncargado()
  const [tipo, setTipo] = useState<TipoRecurso>('agente')
  const [idRec, setIdRec] = useState<number | ''>('')

  async function onAdd() {
    if (!idEvento || !idRec) return
    try {
      const r = await asignar.mutateAsync({ idEvento, tipo_recurso: tipo, id_recurso: Number(idRec) })
      const conConflicto = (r.conflictos?.length ?? 0) > 0
      push({
        kind: conConflicto ? 'error' : 'success',
        title: conConflicto ? 'Encargado asignado con conflicto' : 'Encargado asignado',
        body: conConflicto ? `${r.conflictos.length} solape - ver Conflictos` : r.mensaje ?? undefined,
        ttl: conConflicto ? 7000 : 4000,
      })
      setIdRec('')
    } catch (e) {
      push({ kind: 'error', title: 'No se pudo asignar', body: (e as Error).message })
    }
  }

  async function onRemove(idEnc: number) {
    if (!idEvento) return
    if (!confirm('Quitar este encargado y dar de baja su ocupacion?')) return
    try {
      await desasignar.mutateAsync({ idEvento, idEncargado: idEnc })
      push({ kind: 'success', title: 'Encargado quitado' })
    } catch (e) {
      push({ kind: 'error', title: 'No se pudo quitar', body: (e as Error).message })
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Encargados · evento #${idEvento ?? ''}`}
      footer={<Button variant="ghost" onClick={onClose}>Cerrar</Button>}
    >
      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end', marginBottom: 14 }}>
        <div>
          <label style={{ fontSize: 11, color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '.04em' }}>Tipo</label>
          <select value={tipo} onChange={(e) => setTipo(e.target.value as TipoRecurso)} style={inp}>
            <option value="agente">agente</option>
            <option value="equipo">equipo</option>
          </select>
        </div>
        <div style={{ flex: 1 }}>
          <label style={{ fontSize: 11, color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '.04em' }}>ID {tipo}</label>
          <input
            type="number"
            value={idRec}
            min={1}
            onChange={(e) => setIdRec(e.target.value ? Number(e.target.value) : '')}
            placeholder="ej: 1"
            style={inp}
          />
        </div>
        <Button variant="accent" onClick={onAdd} icon={<UserPlus size={14} strokeWidth={1.5} />}>
          Agregar
        </Button>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {detalle.data?.encargados.length === 0 && (
          <div style={{ padding: 16, textAlign: 'center', color: 'var(--fg-3)' }}>Sin encargados asignados</div>
        )}
        {detalle.data?.encargados.map((enc) => (
          <div key={enc.id_evento_encargado} style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '8px 10px', background: 'var(--surface-200)', borderRadius: 'var(--radius-md)',
          }}>
            <div>
              <div style={{ fontSize: 13, color: 'var(--fg-1)' }}>
                <strong>{enc.recurso_nombre ?? `${enc.tipo_recurso} ${enc.id_recurso}`}</strong>
              </div>
              <div style={{ fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>
                {enc.tipo_recurso} #{enc.id_recurso}
              </div>
            </div>
            <button
              onClick={() => onRemove(enc.id_evento_encargado)}
              aria-label="Quitar encargado"
              style={{
                background: 'transparent', border: 'none', cursor: 'pointer',
                color: 'var(--fg-3)', padding: 6, borderRadius: 'var(--radius-md)',
              }}
            >
              <Trash2 size={14} strokeWidth={1.5} />
            </button>
          </div>
        ))}
      </div>
    </Modal>
  )
}

const inp: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: 'var(--size-ui)',
  padding: '8px 10px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-primary)',
  background: 'var(--surface-100)', outline: 'none', width: '100%',
}
