import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { api } from '../../../lib/api'
import { AvisoBuscar, useBusquedaDiferida } from '../../../ui/busqueda'
import { ThOrden, useOrden } from '../../../ui/orden'
import { Button, EmptyState, Skeleton } from '../../../ui'

// «Registro del super administrador» (IT-01 F3, spec §4): lo que hizo el super administrador en
// ESTE municipio. Solo lectura. El backend filtra por el municipio de la request.

const LIMITE = 200

const ACCIONES: Record<string, string> = {
  request: 'Consulta u operación',
  seleccion: 'Entró al municipio',
  historia_clinica: 'Historia clínica',
  municipio_editar: 'Editó el municipio',
  segundo_factor: 'Segundo factor',
}

interface AccesoSuper {
  id_super_admin_acceso: number
  fecha_hora: string
  id_municipio: number
  usuario: string | null
  accion: string
  metodo: string | null
  ruta: string | null
  detalle: string | null
}

type Campo = 'fecha' | 'accion' | 'usuario'
interface Filtros { desde: string; hasta: string; accion: string }

export function AccesosSuperView() {
  const { borrador, setBorrador, aplicado, buscar, buscado, version } = useBusquedaDiferida<Filtros>({
    desde: '', hasta: '', accion: '',
  })
  const { orden, alternar } = useOrden<Campo>()
  const q = useQuery({
    queryKey: ['auditoria', 'accesos-super', aplicado, orden, version],
    queryFn: () => api.getWithHeaders<AccesoSuper[]>('/api/v1/auditoria/accesos-super', {
      params: {
        desde: aplicado?.desde || null, hasta: aplicado?.hasta || null, accion: aplicado?.accion || null,
        orden: orden?.campo ?? null, dir: orden?.dir ?? null, limit: LIMITE,
      },
    }),
    enabled: buscado,
    placeholderData: keepPreviousData,
  })
  const filas = q.data?.data ?? []
  const total = Number(q.data?.headers.get('X-Total-Count') ?? filas.length)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <p style={{ margin: 0, fontSize: 13, color: 'var(--fg-2)' }}>
        Todo lo que hizo el super administrador en este municipio: cada consulta, cada operación y cada historia clínica
        que abrió, con el motivo que declaró.
      </p>
      <form onSubmit={(e) => { e.preventDefault(); buscar() }} style={barra}>
        <label style={campo}>Desde
          <input type="date" value={borrador.desde} onChange={(e) => setBorrador({ ...borrador, desde: e.target.value })} style={input} />
        </label>
        <label style={campo}>Hasta
          <input type="date" value={borrador.hasta} onChange={(e) => setBorrador({ ...borrador, hasta: e.target.value })} style={input} />
        </label>
        <label style={campo}>Acción
          <select value={borrador.accion} onChange={(e) => setBorrador({ ...borrador, accion: e.target.value })} style={input}>
            <option value="">Todas</option>
            {Object.entries(ACCIONES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <Button variant="primary" type="submit">Buscar</Button>
      </form>

      {!buscado ? <AvisoBuscar /> : q.isLoading ? <Skeleton height={140} /> : q.isError ? (
        <EmptyState title="No se pudo cargar el registro" description={q.error.message} />
      ) : filas.length === 0 ? (
        <EmptyState title="Sin accesos del super administrador" description="No hay registros con esos filtros." />
      ) : (
        <>
          {total > filas.length && (
            <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>
              Se muestran los primeros {filas.length} de {total}: acotá por fecha o por acción.
            </div>
          )}
          <div style={{ overflowX: 'auto' }}>
            <table style={tabla}>
              <thead>
                <tr>
                  <ThOrden campo="fecha" orden={orden} onOrdenar={alternar} style={th}>Fecha y hora</ThOrden>
                  <ThOrden campo="usuario" orden={orden} onOrdenar={alternar} style={th}>Usuario</ThOrden>
                  <ThOrden campo="accion" orden={orden} onOrdenar={alternar} style={th}>Acción</ThOrden>
                  <th style={th}>Método y ruta</th>
                  <th style={th}>Detalle</th>
                </tr>
              </thead>
              <tbody>
                {filas.map((a) => (
                  <tr key={a.id_super_admin_acceso}>
                    <td style={{ ...td, fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap' }}>
                      {new Date(a.fecha_hora).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'medium' })}
                    </td>
                    <td style={td}>{a.usuario ?? '—'}</td>
                    <td style={td}>{ACCIONES[a.accion] ?? a.accion}</td>
                    <td style={{ ...td, fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                      {[a.metodo, a.ruta].filter(Boolean).join(' ')}
                    </td>
                    <td style={{ ...td, whiteSpace: 'pre-wrap' }}>{a.detalle ?? ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}

const barra: React.CSSProperties = { display: 'flex', alignItems: 'flex-end', gap: 12, flexWrap: 'wrap' }
const campo: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 4, fontSize: 11, fontWeight: 600, textTransform: 'uppercase',
  letterSpacing: '0.04em', color: 'var(--fg-3)',
}
const input: React.CSSProperties = {
  fontFamily: 'inherit', fontSize: 13, color: 'var(--fg-1)', background: 'var(--surface-100)',
  border: '1px solid var(--border-medium)', borderRadius: 'var(--radius-md)', padding: '6px 10px',
  textTransform: 'none', letterSpacing: 'normal', fontWeight: 400,
}
const tabla: React.CSSProperties = { width: '100%', borderCollapse: 'collapse', fontSize: 13 }
const th: React.CSSProperties = {
  textAlign: 'left', padding: '8px 10px', borderBottom: '1px solid var(--border-medium)', color: 'var(--fg-3)',
  fontFamily: 'var(--font-display)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.04em',
}
const td: React.CSSProperties = {
  padding: '8px 10px', borderBottom: '1px solid var(--border-primary)', color: 'var(--fg-1)', verticalAlign: 'top',
}
