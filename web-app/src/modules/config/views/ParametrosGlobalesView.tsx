import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, EmptyState, Skeleton } from '../../../ui'
import { useNotificationsStore } from '../../../stores/notifications'
import { actualizarConfigGlobal, listarConfigGlobal, type ConfigGlobal } from '../api/configApi'

// Parámetros globales (IT-01 F3): las filas de configuracion_general sin municipio. Valen para
// todos los municipios y ningún municipio las sobrescribe (p. ej. la renovación de claves).
// Solo el super administrador. Las claves vapid_* no se listan (el backend las excluye).

const ETIQUETAS: Record<string, string> = {
  password_renovacion_dias: 'Renovación de claves (días; 0 = desactivada)',
}

export function ParametrosGlobalesView() {
  const q = useQuery({ queryKey: ['super', 'config-global'], queryFn: listarConfigGlobal })
  if (q.isLoading) return <Skeleton height={120} />
  if (q.isError) return <EmptyState title="No se pudieron cargar los parámetros globales" description={q.error.message} />
  const filas = q.data ?? []
  if (filas.length === 0) return <EmptyState title="No hay parámetros globales" />
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--fg-3)' }}>
        Valen para todos los municipios y ningún municipio los sobrescribe. Cada cambio queda en el registro del super
        administrador.
      </p>
      {filas.map((p) => <FilaGlobal key={p.id_config} p={p} />)}
    </div>
  )
}

function FilaGlobal({ p }: { p: ConfigGlobal }) {
  const qc = useQueryClient()
  const push = useNotificationsStore((s) => s.push)
  const [valor, setValor] = useState(p.valor ?? '')
  useEffect(() => { setValor(p.valor ?? '') }, [p.valor])
  const mut = useMutation({
    mutationFn: (v: string) => actualizarConfigGlobal(p.id_config, v),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['super', 'config-global'] })
      push({ kind: 'success', title: 'Parámetro global guardado' })
    },
    onError: (e: Error) => push({ kind: 'error', title: 'No se pudo guardar', body: e.message }),
  })
  const cambiado = valor.trim() !== (p.valor ?? '')
  const valido = p.tipo !== 'integer' || /^-?[0-9]{1,9}$/.test(valor.trim())
  return (
    <div style={fila}>
      <div style={{ flex: 1, minWidth: 220 }}>
        <div style={{ fontWeight: 600, fontSize: 13.5, color: 'var(--fg-1)' }}>{ETIQUETAS[p.clave] ?? p.clave}</div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5, color: 'var(--fg-3)' }}>{p.clave}</div>
        {p.descripcion && <div style={{ fontSize: 12, color: 'var(--fg-3)', marginTop: 2 }}>{p.descripcion}</div>}
      </div>
      {p.tipo === 'boolean' ? (
        <select value={valor} onChange={(e) => setValor(e.target.value)} style={input}>
          <option value="true">Sí</option>
          <option value="false">No</option>
        </select>
      ) : (
        <input value={valor} onChange={(e) => setValor(e.target.value)} style={input}
               inputMode={p.tipo === 'integer' ? 'numeric' : undefined} />
      )}
      <Button variant="primary" type="button" disabled={!cambiado || !valido || mut.isPending}
              onClick={() => mut.mutate(valor.trim())}>
        Guardar
      </Button>
    </div>
  )
}

const fila: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', padding: 12,
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)', borderRadius: 12,
}
const input: React.CSSProperties = {
  fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--fg-1)', background: 'var(--surface-100)',
  border: '1px solid var(--border-medium)', borderRadius: 'var(--radius-md)', padding: '6px 10px', width: 140,
}
