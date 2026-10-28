import { Fragment, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Modal } from '../../agenda/components/Modal'
import { ConfirmModal } from '../../agenda/components/ConfirmModal'
import { ApiError } from '../../../lib/api'
import { Badge, Button, EmptyState, Skeleton } from '../../../ui'
import { ThOrden, ordenarFilas, useOrden } from '../../../ui/orden'
import { useNotificationsStore } from '../../../stores/notifications'
import {
  ESTADO_ETIQUETA, editarMunicipio, etiquetaZona, listarMunicipios, listarPaises, listarProvincias,
  opcionesAlta, type EstadoMunicipio, type MunicipioSuper, type MunicipioSuperUpdate,
} from '../api'
import { Campo, grupo, input, labelCampo, tabla, td, th, titulo } from './_comun'
import { PartidoSearch } from '../components/PartidoSearch'

// Módulo «Municipios» del super administrador (IT-01 F3; país, provincia y estado de F4,
// PLAN_MULTI_MUNICIPIO_F4_F5.md, Tarea 6). La lista es corta y se carga entera: los filtros por
// país, provincia y estado se aplican en pantalla (§23). Sin un orden elegido, va agrupada por
// país y provincia, como la devuelve el backend. La identidad (logo, colores) se edita en
// Configuración → Identidad con el municipio elegido en el selector.

type Campo = 'nombre' | 'codigo' | 'subdominio' | 'provincia' | 'estado' | 'cuentas'

const VALORES: Record<Campo, (m: MunicipioSuper) => string | number | null> = {
  nombre: (m) => m.nombre,
  codigo: (m) => m.codigo_corto,
  subdominio: (m) => m.subdominio,
  provincia: (m) => m.provincia_nombre,
  estado: (m) => ESTADO_ETIQUETA[m.estado],
  cuentas: (m) => m.cuentas_activas,
}

const KIND_ESTADO: Record<EstadoMunicipio, 'success' | 'warn' | 'neutral' | 'error'> = {
  produccion: 'success', puesta_en_marcha: 'warn', demo: 'neutral', modelo: 'neutral', baja: 'error',
}

const grupoDe = (m: MunicipioSuper) =>
  m.estado === 'modelo' ? 'Modelo' : `${m.pais_nombre ?? m.codigo_pais} · ${m.provincia_nombre ?? 'sin provincia'}`

export function MunicipiosPage() {
  const q = useQuery({ queryKey: ['super', 'municipios'], queryFn: () => listarMunicipios() })
  const { orden, alternar } = useOrden<Campo>()
  const navigate = useNavigate()
  const [pais, setPais] = useState('')
  const [provincia, setProvincia] = useState('')
  const [estado, setEstado] = useState('')

  const todos = q.data ?? []
  const paises = useMemo(() => [...new Map(todos.map((m) => [m.codigo_pais, m.pais_nombre ?? m.codigo_pais])).entries()], [todos])
  const provincias = useMemo(() => [...new Map(todos
    .filter((m) => m.id_provincia != null && (!pais || m.codigo_pais === pais))
    .map((m) => [String(m.id_provincia), m.provincia_nombre ?? ''])).entries()], [todos, pais])
  const filtrados = todos.filter((m) => (!pais || m.codigo_pais === pais)
    && (!provincia || String(m.id_provincia) === provincia) && (!estado || m.estado === estado))
  const filas = ordenarFilas(filtrados, orden, VALORES)
  const agrupar = !orden

  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <header>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
          <h1 style={titulo}>Municipios</h1>
          <div style={{ display: 'flex', gap: 8 }}>
            <Button variant="ghost" type="button" onClick={() => navigate('/municipios/super-administradores')}>
              Super administradores
            </Button>
            <Button variant="primary" type="button" onClick={() => navigate('/municipios/alta')}>
              + Dar de alta un municipio
            </Button>
          </div>
        </div>
        <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--fg-2)' }}>
          Datos de cada municipio, agrupados por país y provincia. La identidad (logo y colores) se edita en
          Configuración → Identidad, con el municipio elegido arriba en «Operando en».
        </p>
      </header>

      {todos.length > 0 && (
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <Filtro etiqueta="País" valor={pais} onChange={(v) => { setPais(v); setProvincia('') }}
                  opciones={paises.map(([v, t]) => [v, t])} />
          <Filtro etiqueta="Provincia" valor={provincia} onChange={setProvincia} opciones={provincias} />
          <Filtro etiqueta="Estado" valor={estado} onChange={setEstado}
                  opciones={Object.entries(ESTADO_ETIQUETA)} />
        </div>
      )}

      {q.isLoading && <Skeleton height={160} />}
      {q.isError && <EmptyState title="No se pudo cargar la lista" description={q.error.message} />}
      {q.data && filas.length === 0 && <EmptyState title="No hay municipios con esos filtros" />}
      {filas.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={tabla}>
            <thead>
              <tr>
                <ThOrden campo="nombre" orden={orden} onOrdenar={alternar} style={th}>Nombre</ThOrden>
                <ThOrden campo="codigo" orden={orden} onOrdenar={alternar} style={th}>Código</ThOrden>
                <ThOrden campo="subdominio" orden={orden} onOrdenar={alternar} style={th}>Subdominio</ThOrden>
                <ThOrden campo="provincia" orden={orden} onOrdenar={alternar} style={th}>Provincia</ThOrden>
                <ThOrden campo="estado" orden={orden} onOrdenar={alternar} style={th}>Estado</ThOrden>
                <ThOrden campo="cuentas" orden={orden} onOrdenar={alternar} style={th}>Cuentas activas</ThOrden>
              </tr>
            </thead>
            <tbody>
              {filas.map((m, i) => (
                <Fragment key={m.id_municipio}>
                  {agrupar && (i === 0 || grupoDe(filas[i - 1]) !== grupoDe(m)) && (
                    <tr><td colSpan={6} style={grupo}>{grupoDe(m)}</td></tr>
                  )}
                  <tr onClick={() => navigate(`/municipios/${m.id_municipio}`)} style={{ cursor: 'pointer' }}
                      title="Abrir la ficha del municipio">
                    <td style={td}>
                      {m.nombre}{' '}
                      {m.direccion_base && <Badge kind="neutral">dirección base</Badge>}
                    </td>
                    <td style={{ ...td, fontFamily: 'var(--font-mono)' }}>{m.codigo_corto ?? '—'}</td>
                    <td style={{ ...td, fontFamily: 'var(--font-mono)' }}>{m.subdominio ?? '—'}</td>
                    <td style={td}>{m.provincia_nombre ?? '—'}{m.partido_nombre ? ` · ${m.partido_nombre}` : ''}</td>
                    <td style={td}><Badge kind={KIND_ESTADO[m.estado]}>{ESTADO_ETIQUETA[m.estado]}</Badge></td>
                    <td style={{ ...td, fontFamily: 'var(--font-mono)' }}>
                      {m.max_usuarios_activos ? `${m.cuentas_activas} de ${m.max_usuarios_activos}` : m.cuentas_activas}
                    </td>
                  </tr>
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function Filtro({ etiqueta, valor, onChange, opciones }: {
  etiqueta: string; valor: string; onChange: (v: string) => void; opciones: [string, string][]
}) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <span style={labelCampo}>{etiqueta}</span>
      <select style={input} value={valor} onChange={(e) => onChange(e.target.value)}>
        <option value="">Todos</option>
        {opciones.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
      </select>
    </label>
  )
}

export function EditarMunicipioModal({ municipio, onClose }: { municipio: MunicipioSuper | null; onClose: () => void }) {
  const qc = useQueryClient()
  const push = useNotificationsStore((s) => s.push)
  const [form, setForm] = useState<MunicipioSuperUpdate | null>(null)

  // El modal vive montado: se reinicia al abrir con el municipio elegido (§23/§29).
  useEffect(() => {
    if (!municipio) { setForm(null); return }
    setForm({
      nombre: municipio.nombre, subdominio: municipio.subdominio, codigo_pais: municipio.codigo_pais,
      id_provincia: municipio.id_provincia, id_partido: municipio.id_partido, zona_horaria: municipio.zona_horaria,
    })
  }, [municipio])

  const paises = useQuery({ queryKey: ['geo', 'paises'], queryFn: () => listarPaises(), enabled: municipio != null })
  const provincias = useQuery({
    queryKey: ['geo', 'provincias', form?.codigo_pais], queryFn: () => listarProvincias(form!.codigo_pais),
    enabled: !!form?.codigo_pais,
  })
  const opciones = useQuery({ queryKey: ['super', 'alta', 'opciones'], queryFn: opcionesAlta, enabled: municipio != null })
  const zonas = opciones.data?.zonas ?? []
  const paisSel = paises.data?.find((p) => p.codigo_pais === form?.codigo_pais)
  const nivel1 = paisSel?.etiqueta_nivel_1 ?? 'Provincia'
  const nivel2 = paisSel?.etiqueta_nivel_2 ?? 'Partido'

  // Cambiar el partido con el contorno oficial del anterior: el backend responde 409 y se confirma acá.
  const [quitarContorno, setQuitarContorno] = useState<{ id: number; body: MunicipioSuperUpdate; mensaje: string } | null>(null)
  const mut = useMutation({
    mutationFn: ({ id, body }: { id: number; body: MunicipioSuperUpdate }) => editarMunicipio(id, body),
    onSuccess: (m) => {
      qc.invalidateQueries({ queryKey: ['super'] })
      qc.invalidateQueries({ queryKey: ['contorno'] })
      push({ kind: 'success', title: `Municipio «${m.nombre}» guardado` })
      if (m.aviso_contorno) push({ kind: 'info', title: 'Revisá el contorno', body: m.aviso_contorno, ttl: 10000 })
    },
    onError: (e: Error, vars) => {
      if (e instanceof ApiError && e.status === 409
          && (e.body as { contorno_partido_anterior?: boolean } | undefined)?.contorno_partido_anterior) {
        setQuitarContorno({ ...vars, mensaje: e.message })
        return
      }
      push({ kind: 'error', title: 'No se pudo guardar', body: e.message })
    },
  })

  const sinProvinciaOk = municipio?.estado === 'baja' || municipio?.estado === 'modelo'
  const subdominioOk = !form?.subdominio || /^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$/.test(form.subdominio)
  const valido = !!form && form.nombre.trim().length >= 3 && subdominioOk && !!form.codigo_pais
    && (form.id_provincia != null || sinProvinciaOk) && form.zona_horaria.trim() !== ''

  const guardar = () => {
    if (!municipio || !form || !valido) return
    // Cerrar AL CONFIRMAR (§23): el resultado llega por aviso.
    mut.mutate({ id: municipio.id_municipio, body: {
      ...form, nombre: form.nombre.trim(), subdominio: form.subdominio?.trim() || null,
      zona_horaria: form.zona_horaria.trim(),
    } })
    onClose()
  }

  return (
    <>
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
          <Campo etiqueta="País">
            <select style={input} value={form.codigo_pais}
                    onChange={(e) => setForm({ ...form, codigo_pais: e.target.value, id_provincia: null, id_partido: null })}>
              {(paises.data ?? [{ codigo_pais: form.codigo_pais, nombre: form.codigo_pais }]).map((p) => (
                <option key={p.codigo_pais} value={p.codigo_pais}>{p.nombre}</option>
              ))}
            </select>
          </Campo>
          <Campo etiqueta={nivel1}
                 error={form.id_provincia == null && !sinProvinciaOk ? `Elegí la ${nivel1.toLowerCase()}` : undefined}>
            <select style={input} value={form.id_provincia ?? ''}
                    onChange={(e) => setForm({ ...form, id_provincia: e.target.value ? Number(e.target.value) : null, id_partido: null })}>
              <option value="">—</option>
              {(provincias.data ?? []).map((p) => <option key={p.id_provincia} value={p.id_provincia}>{p.nombre}</option>)}
            </select>
          </Campo>
          <Campo etiqueta={nivel2}
                 ayuda={form.id_partido == null ? 'Sin partido = municipio ficticio (demo o prueba): no pasa a producción.'
                   : 'El municipio es el partido: uno por partido.'}>
            <PartidoSearch key={municipio?.id_municipio} idProvincia={form.id_provincia} value={form.id_partido}
                           etiqueta={municipio?.partido_nombre} inputStyle={input}
                           onChange={(p) => setForm({ ...form, id_partido: p?.id_partido ?? null })} />
          </Campo>
          <Campo etiqueta="Zona horaria" ayuda="Ordenadas por su diferencia con Greenwich.">
            <select style={{ ...input, fontFamily: 'var(--font-mono)' }} value={form.zona_horaria}
                    onChange={(e) => setForm({ ...form, zona_horaria: e.target.value })}>
              {!zonas.some((z) => z.nombre === form.zona_horaria) && <option value={form.zona_horaria}>{form.zona_horaria}</option>}
              {zonas.map((z) => <option key={z.nombre} value={z.nombre}>{etiquetaZona(z)}</option>)}
            </select>
          </Campo>
        </div>
      )}
    </Modal>
    <ConfirmModal open={quitarContorno != null} title="Cambiar el partido"
                  message={`${quitarContorno?.mensaje ?? ''} El contorno se quita y el partido se cambia.`}
                  confirmLabel="Quitar el contorno y cambiar el partido" danger
                  onConfirm={() => {
                    const p = quitarContorno
                    setQuitarContorno(null)
                    if (p) mut.mutate({ id: p.id, body: { ...p.body, quitar_contorno: true } })
                  }}
                  onCancel={() => setQuitarContorno(null)} />
    </>
  )
}
