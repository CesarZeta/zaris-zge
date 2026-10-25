import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Modal } from '../../agenda/components/Modal'
import { Badge, Button, EmptyState, Skeleton } from '../../../ui'
import { ThOrden, ordenarFilas, useOrden } from '../../../ui/orden'
import { useNotificationsStore } from '../../../stores/notifications'
import { editarMunicipio, listarMunicipios, type MunicipioSuper, type MunicipioSuperUpdate } from '../api'

// Módulo «Municipios» del super administrador (IT-01 F3, PLAN_MULTI_MUNICIPIO_F3.md, Tarea 8).
// En F3 solo se editan los datos del municipio: el alta, la baja, el código corto (prefijo de los
// números) y la dirección base son de F4. La identidad (logo, colores) se edita en
// Configuración → Identidad con el municipio elegido en el selector.

type Campo = 'nombre' | 'codigo' | 'subdominio' | 'pais' | 'zona' | 'estado'

const VALORES: Record<Campo, (m: MunicipioSuper) => string | null> = {
  nombre: (m) => m.nombre,
  codigo: (m) => m.codigo_corto,
  subdominio: (m) => m.subdominio,
  pais: (m) => m.pais ?? m.codigo_pais,
  zona: (m) => m.zona_horaria,
  estado: (m) => (m.activo ? 'activo' : 'inactivo'),
}

export function MunicipiosPage() {
  const q = useQuery({ queryKey: ['super', 'municipios'], queryFn: listarMunicipios })
  const { orden, alternar } = useOrden<Campo>()
  const [editando, setEditando] = useState<MunicipioSuper | null>(null)
  const filas = ordenarFilas(q.data ?? [], orden, VALORES)

  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <header>
        <h1 style={titulo}>Municipios</h1>
        <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--fg-2)' }}>
          Datos de cada municipio. El alta y la baja llegan con la fase F4; la identidad (logo y colores) se edita
          en Configuración → Identidad, con el municipio elegido arriba en «Operando en».
        </p>
      </header>

      {q.isLoading && <Skeleton height={160} />}
      {q.isError && <EmptyState title="No se pudo cargar la lista" description={q.error.message} />}
      {q.data && filas.length === 0 && <EmptyState title="No hay municipios" />}
      {filas.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={tabla}>
            <thead>
              <tr>
                <ThOrden campo="nombre" orden={orden} onOrdenar={alternar} style={th}>Nombre</ThOrden>
                <ThOrden campo="codigo" orden={orden} onOrdenar={alternar} style={th}>Código</ThOrden>
                <ThOrden campo="subdominio" orden={orden} onOrdenar={alternar} style={th}>Subdominio</ThOrden>
                <ThOrden campo="pais" orden={orden} onOrdenar={alternar} style={th}>País</ThOrden>
                <ThOrden campo="zona" orden={orden} onOrdenar={alternar} style={th}>Zona horaria</ThOrden>
                <ThOrden campo="estado" orden={orden} onOrdenar={alternar} style={th}>Estado</ThOrden>
              </tr>
            </thead>
            <tbody>
              {filas.map((m) => (
                <tr key={m.id_municipio} onClick={() => setEditando(m)} style={{ cursor: 'pointer' }}
                    title="Editar los datos del municipio">
                  <td style={td}>
                    {m.nombre}{' '}
                    {m.direccion_base && <Badge kind="neutral">dirección base</Badge>}
                  </td>
                  <td style={{ ...td, fontFamily: 'var(--font-mono)' }}>{m.codigo_corto ?? '—'}</td>
                  <td style={{ ...td, fontFamily: 'var(--font-mono)' }}>{m.subdominio ?? '—'}</td>
                  <td style={td}>{m.pais ?? m.codigo_pais}</td>
                  <td style={{ ...td, fontFamily: 'var(--font-mono)' }}>{m.zona_horaria}</td>
                  <td style={td}>{m.activo ? <Badge kind="success">Activo</Badge> : <Badge kind="neutral">Inactivo</Badge>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <EditarMunicipioModal municipio={editando} onClose={() => setEditando(null)} />
    </div>
  )
}

function EditarMunicipioModal({ municipio, onClose }: { municipio: MunicipioSuper | null; onClose: () => void }) {
  const qc = useQueryClient()
  const push = useNotificationsStore((s) => s.push)
  const [form, setForm] = useState<MunicipioSuperUpdate | null>(null)

  // El modal vive montado: se reinicia al abrir con el municipio elegido (§23/§29).
  useEffect(() => {
    if (!municipio) { setForm(null); return }
    setForm({
      nombre: municipio.nombre, subdominio: municipio.subdominio, codigo_pais: municipio.codigo_pais,
      pais: municipio.pais, zona_horaria: municipio.zona_horaria,
    })
  }, [municipio])

  const mut = useMutation({
    mutationFn: ({ id, body }: { id: number; body: MunicipioSuperUpdate }) => editarMunicipio(id, body),
    onSuccess: (m) => {
      qc.invalidateQueries({ queryKey: ['super', 'municipios'] })
      push({ kind: 'success', title: `Municipio «${m.nombre}» guardado` })
    },
    onError: (e: Error) => push({ kind: 'error', title: 'No se pudo guardar', body: e.message }),
  })

  const subdominioOk = !form?.subdominio || /^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$/.test(form.subdominio)
  const paisOk = !!form && /^[A-Z]{2}$/.test(form.codigo_pais)
  const valido = !!form && form.nombre.trim().length >= 3 && subdominioOk && paisOk && form.zona_horaria.trim() !== ''

  const guardar = () => {
    if (!municipio || !form || !valido) return
    // Cerrar AL CONFIRMAR (§23): el resultado llega por aviso.
    mut.mutate({ id: municipio.id_municipio, body: {
      ...form, nombre: form.nombre.trim(), subdominio: form.subdominio?.trim() || null,
      pais: form.pais?.trim() || null, zona_horaria: form.zona_horaria.trim(),
    } })
    onClose()
  }

  return (
    <Modal
      open={municipio != null}
      onClose={onClose}
      title={municipio ? `Editar ${municipio.nombre}` : 'Editar municipio'}
      footer={
        <>
          <Button variant="ghost" type="button" onClick={onClose}>Cancelar</Button>
          <Button variant="primary" type="button" disabled={!valido} onClick={guardar}>Guardar</Button>
        </>
      }
    >
      {form && municipio && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Campo etiqueta="Nombre">
            <input style={input} value={form.nombre} maxLength={150}
                   onChange={(e) => setForm({ ...form, nombre: e.target.value })} />
          </Campo>
          <Campo etiqueta="Código corto" ayuda="Es el prefijo de los números (REC-SAN-…); se fija en el alta.">
            <input style={{ ...input, background: 'var(--surface-400)' }} value={municipio.codigo_corto ?? ''} readOnly />
          </Campo>
          <Campo etiqueta="Subdominio" ayuda="Minúsculas, números y guiones: <subdominio>.zge.zaris.com.ar"
                 error={subdominioOk ? undefined : 'Solo minúsculas, números y guiones, sin espacios'}>
            <input style={{ ...input, fontFamily: 'var(--font-mono)' }} value={form.subdominio ?? ''} maxLength={63}
                   onChange={(e) => setForm({ ...form, subdominio: e.target.value.toLowerCase() })} />
          </Campo>
          <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 12 }}>
            <Campo etiqueta="País (código)" error={paisOk ? undefined : 'Dos letras, p. ej. AR'}>
              <input style={{ ...input, fontFamily: 'var(--font-mono)' }} value={form.codigo_pais} maxLength={2}
                     onChange={(e) => setForm({ ...form, codigo_pais: e.target.value.toUpperCase() })} />
            </Campo>
            <Campo etiqueta="País (nombre)">
              <input style={input} value={form.pais ?? ''} maxLength={100}
                     onChange={(e) => setForm({ ...form, pais: e.target.value })} />
            </Campo>
          </div>
          <Campo etiqueta="Zona horaria" ayuda="Nombre IANA, p. ej. America/Argentina/Buenos_Aires">
            <input style={{ ...input, fontFamily: 'var(--font-mono)' }} value={form.zona_horaria} maxLength={64}
                   onChange={(e) => setForm({ ...form, zona_horaria: e.target.value })} />
          </Campo>
        </div>
      )}
    </Modal>
  )
}

function Campo({ etiqueta, ayuda, error, children }: {
  etiqueta: string; ayuda?: string; error?: string; children: React.ReactNode
}) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <span style={labelCampo}>{etiqueta}</span>
      {children}
      {error ? <span style={{ fontSize: 12, color: 'var(--color-error)' }}>{error}</span>
        : ayuda ? <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>{ayuda}</span> : null}
    </label>
  )
}

const titulo: React.CSSProperties = { margin: 0, fontFamily: 'var(--font-display)', fontSize: 22, color: 'var(--fg-1)' }
const tabla: React.CSSProperties = { width: '100%', borderCollapse: 'collapse', fontSize: 13 }
const th: React.CSSProperties = {
  textAlign: 'left', padding: '8px 10px', borderBottom: '1px solid var(--border-medium)', color: 'var(--fg-3)',
  fontFamily: 'var(--font-display)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.04em',
}
const td: React.CSSProperties = { padding: '8px 10px', borderBottom: '1px solid var(--border-primary)', color: 'var(--fg-1)' }
const labelCampo: React.CSSProperties = {
  fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--fg-3)',
}
const input: React.CSSProperties = {
  fontFamily: 'inherit', fontSize: 13, color: 'var(--fg-1)', background: 'var(--surface-100)',
  border: '1px solid var(--border-medium)', borderRadius: 'var(--radius-md)', padding: '7px 10px',
}
