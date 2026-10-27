import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { Modal } from '../../agenda/components/Modal'
import { ConfirmModal } from '../../agenda/components/ConfirmModal'
import { Badge, Button, EmptyState, Skeleton } from '../../../ui'
import { useNotificationsStore } from '../../../stores/notifications'
import {
  ESTADO_ETIQUETA, cambiarEstado, cambiarModulos, cambiarTope, fichaMunicipio, probarPuestaEnMarcha,
  reenviarInvitacion, verificarDominios, type Chequeo, type Dominio, type FichaMunicipio,
} from '../api'
import { Advertencias, Casilla, faltaDependencia } from './AltaMunicipioPage'
import { EditarMunicipioModal } from './MunicipiosPage'
import { Exportaciones, Vaciado } from './VaciadoSecciones'
import { Campo, input, seccion, subtitulo, tabla, td, th, titulo } from './_comun'

// Ficha de un municipio (IT-01 F4+F5, Tarea 15; spec §4.4): estado y sus transiciones, módulos,
// tope de cuentas, administradores e invitación, dominios, prueba de puesta en marcha, exportaciones
// y vaciado (Tarea 16).

const CONFIRMAR = 'Escribí el nombre del municipio para confirmar.'

export function MunicipioFichaPage() {
  const { id } = useParams()
  const idMun = Number(id)
  const navigate = useNavigate()
  const qc = useQueryClient()
  const push = useNotificationsStore((s) => s.push)
  const q = useQuery({ queryKey: ['super', 'ficha', idMun], queryFn: () => fichaMunicipio(idMun), enabled: idMun > 0 })
  const [editando, setEditando] = useState(false)

  const refrescar = () => {
    qc.invalidateQueries({ queryKey: ['super', 'ficha', idMun] })
    qc.invalidateQueries({ queryKey: ['super', 'municipios'] })
  }
  const aviso = (titulo: string) => ({
    onSuccess: () => { refrescar(); push({ kind: 'success' as const, title: titulo }) },
    onError: (e: Error) => push({ kind: 'error' as const, title: 'No se pudo', body: e.message }),
  })

  if (q.isLoading) return <div style={pagina}><Skeleton height={300} /></div>
  if (q.isError || !q.data) {
    return <div style={pagina}><EmptyState title="No se pudo cargar la ficha" description={q.error?.message} /></div>
  }
  const { municipio: m } = q.data

  return (
    <div style={pagina}>
      <header style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <h1 style={titulo}>{m.nombre}</h1>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--fg-2)' }}>
            <Badge kind={m.estado === 'produccion' ? 'success' : m.estado === 'baja' ? 'error' : 'warn'}>
              {ESTADO_ETIQUETA[m.estado]}
            </Badge>{' '}
            <span style={{ fontFamily: 'var(--font-mono)' }}>{m.codigo_corto ?? '—'} · {m.subdominio ?? 'sin subdominio'}</span>
            {' · '}{m.provincia_nombre ?? 'sin provincia'}{m.partido_nombre ? ` · ${m.partido_nombre}` : ''}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button variant="ghost" type="button" onClick={() => navigate('/municipios')}>← Municipios</Button>
          <Button type="button" onClick={() => setEditando(true)}>Editar datos</Button>
        </div>
      </header>

      {q.data.advertencias.length > 0 && <Advertencias lista={q.data.advertencias} />}

      <Estado ficha={q.data} aviso={aviso} />
      <Modulos ficha={q.data} aviso={aviso} />
      <Tope ficha={q.data} aviso={aviso} />
      <Administradores ficha={q.data} aviso={aviso} />
      <Dominios idMun={idMun} />
      <Prueba idMun={idMun} />
      <Exportaciones idMun={idMun} />
      <Vaciado municipio={m} onTermino={refrescar} />

      <EditarMunicipioModal municipio={editando ? m : null} onClose={() => { setEditando(false); refrescar() }} />
    </div>
  )
}

type Aviso = (titulo: string) => {
  onSuccess: () => void
  onError: (e: Error) => void
}

function Estado({ ficha, aviso }: { ficha: FichaMunicipio; aviso: Aviso }) {
  const m = ficha.municipio
  const [accion, setAccion] = useState<'produccion' | 'baja' | 'reactivar' | null>(null)
  const [confirmacion, setConfirmacion] = useState('')
  useEffect(() => { if (accion) setConfirmacion('') }, [accion])
  const mut = useMutation({
    mutationFn: ({ estado, conf }: { estado: 'produccion' | 'baja' | 'reactivar'; conf?: string }) =>
      cambiarEstado(m.id_municipio, estado, conf),
    ...aviso('Estado actualizado'),
  })
  const confirmar = () => {
    if (!accion) return
    mut.mutate({ estado: accion, conf: accion === 'produccion' ? confirmacion.trim() : undefined })
    setAccion(null)
  }
  return (
    <section style={seccion}>
      <h2 style={subtitulo}>Estado</h2>
      <p style={{ margin: 0, fontSize: 13, color: 'var(--fg-2)' }}>
        {m.estado === 'puesta_en_marcha' && 'En puesta en marcha: se puede vaciar. El paso a producción no tiene vuelta atrás.'}
        {m.estado === 'produccion' && 'En producción: sus datos ya no se pueden vaciar.'}
        {m.estado === 'demo' && 'Municipio de demostración: lo alimenta el generador de datos demo.'}
        {m.estado === 'modelo' && 'Municipio modelo: de acá se copian los catálogos de cada alta. Se edita eligiéndolo en «Operando en».'}
        {m.estado === 'baja' && 'De baja: nadie entra y sus páginas públicas no responden.'}
      </p>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {m.estado === 'puesta_en_marcha' && (
          <Button variant="primary" type="button" onClick={() => setAccion('produccion')}>Pasar a producción</Button>
        )}
        {m.estado !== 'baja' && m.estado !== 'modelo' && !m.direccion_base && (
          <Button type="button" onClick={() => setAccion('baja')}>Dar de baja</Button>
        )}
        {m.estado === 'baja' && <Button type="button" onClick={() => setAccion('reactivar')}>Reactivar</Button>}
      </div>
      <Modal open={accion === 'produccion'} onClose={() => setAccion(null)} title="Pasar a producción"
             footer={<>
               <Button variant="ghost" type="button" onClick={() => setAccion(null)}>Cancelar</Button>
               <Button variant="primary" type="button" disabled={confirmacion.trim() !== m.nombre} onClick={confirmar}>
                 Pasar a producción
               </Button>
             </>}>
        <Campo etiqueta={CONFIRMAR} ayuda="Después de este paso los datos del municipio no se pueden vaciar.">
          <input style={input} value={confirmacion} onChange={(e) => setConfirmacion(e.target.value)} placeholder={m.nombre} />
        </Campo>
      </Modal>
      <ConfirmModal open={accion === 'baja' || accion === 'reactivar'} danger={accion === 'baja'}
                    title={accion === 'baja' ? 'Dar de baja' : 'Reactivar'}
                    message={accion === 'baja'
                      ? `Nadie va a poder entrar a ${m.nombre} y sus páginas públicas van a dejar de responder.`
                      : `${m.nombre} vuelve al estado que tenía antes de la baja.`}
                    confirmLabel={accion === 'baja' ? 'Dar de baja' : 'Reactivar'}
                    onConfirm={confirmar} onCancel={() => setAccion(null)} />
    </section>
  )
}

function Modulos({ ficha, aviso }: { ficha: FichaMunicipio; aviso: Aviso }) {
  const [elegidos, setElegidos] = useState<Set<string>>(new Set())
  useEffect(() => {
    setElegidos(new Set(ficha.modulos.filter((x) => x.habilitado).map((x) => x.codigo)))
  }, [ficha.modulos])
  const cambios = ficha.modulos.filter((x) => x.habilitado !== elegidos.has(x.codigo))
  const errorDependencia = faltaDependencia([...elegidos, ...ficha.modulos.filter((x) => x.fijo).map((x) => x.codigo)],
    ficha.modulos)
  const mut = useMutation({
    mutationFn: () => cambiarModulos(ficha.municipio.id_municipio,
      cambios.map((x) => ({ codigo: x.codigo, habilitado: elegidos.has(x.codigo) }))),
    ...aviso('Módulos guardados'),
  })
  return (
    <section style={seccion}>
      <h2 style={subtitulo}>Módulos habilitados</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 6 }}>
        {ficha.modulos.map((x) => (
          <Casilla key={x.codigo} etiqueta={x.nombre} marcada={x.fijo || elegidos.has(x.codigo)} deshabilitada={x.fijo}
                   nota={x.fijo ? 'fijo' : undefined}
                   onChange={(v) => setElegidos((prev) => {
                     const n = new Set(prev)
                     if (v) n.add(x.codigo)
                     else n.delete(x.codigo)
                     return n
                   })} />
        ))}
      </div>
      {errorDependencia && <span style={{ fontSize: 13, color: 'var(--color-error)' }}>{errorDependencia}</span>}
      <div>
        <Button variant="primary" type="button" disabled={cambios.length === 0 || !!errorDependencia || mut.isPending}
                onClick={() => mut.mutate()}>
          Guardar módulos
        </Button>
      </div>
    </section>
  )
}

function Tope({ ficha, aviso }: { ficha: FichaMunicipio; aviso: Aviso }) {
  const [valor, setValor] = useState('')
  useEffect(() => { setValor(ficha.cupo.maximo == null ? '' : String(ficha.cupo.maximo)) }, [ficha.cupo.maximo])
  const nuevo = valor.trim() === '' ? null : Number(valor)
  const valido = nuevo === null || (Number.isInteger(nuevo) && nuevo >= 1)
  const mut = useMutation({
    mutationFn: () => cambiarTope(ficha.municipio.id_municipio, nuevo),
    ...aviso('Tope guardado'),
  })
  const { activas, maximo, aviso: cerca } = ficha.cupo
  return (
    <section style={seccion}>
      <h2 style={subtitulo}>Tope de cuentas</h2>
      <p data-cupo style={{ margin: 0, fontSize: 13, color: cerca ? 'var(--color-error)' : 'var(--fg-2)', fontWeight: cerca ? 600 : 400 }}>
        {maximo == null ? `${activas} cuentas activas, sin tope.` : `${activas} de ${maximo} cuentas activas.`}
      </p>
      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end', flexWrap: 'wrap' }}>
        <Campo etiqueta="Tope" ayuda="Vacío = sin tope. Bajarlo no desactiva a nadie.">
          <input style={{ ...input, width: 140 }} inputMode="numeric" value={valor}
                 onChange={(e) => setValor(e.target.value.replace(/[^0-9]/g, ''))} />
        </Campo>
        <Button type="button" disabled={!valido || nuevo === maximo || mut.isPending} onClick={() => mut.mutate()}>
          Guardar tope
        </Button>
      </div>
    </section>
  )
}

function Administradores({ ficha, aviso }: { ficha: FichaMunicipio; aviso: Aviso }) {
  const mut = useMutation({ mutationFn: reenviarInvitacion, ...aviso('Invitación reenviada') })
  return (
    <section style={seccion}>
      <h2 style={subtitulo}>Administradores</h2>
      {ficha.administradores.length === 0 ? (
        <p style={{ margin: 0, fontSize: 13, color: 'var(--fg-2)' }}>El municipio no tiene administradores.</p>
      ) : (
        <table style={tabla}>
          <thead><tr><th style={th}>Nombre</th><th style={th}>Email</th><th style={th}>Invitación</th><th style={th} /></tr></thead>
          <tbody>
            {ficha.administradores.map((a) => (
              <tr key={a.id_usuario}>
                <td style={td}>{a.nombre}{!a.activo && <> <Badge kind="error">inactivo</Badge></>}</td>
                <td style={td}>{a.email ?? '—'}</td>
                <td style={td}>{a.invitacion_pendiente ? 'pendiente' : '—'}</td>
                <td style={{ ...td, textAlign: 'right' }}>
                  {a.activo && (
                    <Button type="button" disabled={mut.isPending} onClick={() => mut.mutate(a.id_usuario)}>
                      Reenviar invitación
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}

function Dominios({ idMun }: { idMun: number }) {
  const push = useNotificationsStore((s) => s.push)
  const [lista, setLista] = useState<Dominio[] | null>(null)
  const mut = useMutation({
    mutationFn: () => verificarDominios(idMun),
    onSuccess: setLista,
    onError: (e: Error) => push({ kind: 'error', title: 'No se pudo verificar', body: e.message }),
  })
  return (
    <section style={seccion}>
      <h2 style={subtitulo}>Dominios</h2>
      <p style={{ margin: 0, fontSize: 13, color: 'var(--fg-2)' }}>
        Se crean con <code>tools/dominios_municipio.py</code>. «Verificar» chequea DNS y HTTPS de cada dirección.
      </p>
      <div><Button type="button" disabled={mut.isPending} onClick={() => mut.mutate()}>
        {mut.isPending ? 'Verificando…' : 'Verificar'}
      </Button></div>
      {lista && (
        <table style={tabla}>
          <thead><tr><th style={th}>Dirección</th><th style={th}>DNS</th><th style={th}>HTTPS</th></tr></thead>
          <tbody>
            {lista.map((d) => (
              <tr key={d.app}>
                <td style={{ ...td, fontFamily: 'var(--font-mono)' }}>{d.host || `(${d.app}: sin dirección)`}</td>
                <td style={td}><Badge kind={d.dns ? 'success' : 'error'}>{d.dns ? 'resuelve' : 'no resuelve'}</Badge></td>
                <td style={td}>
                  <Badge kind={d.https != null && d.https < 400 ? 'success' : 'error'}>{d.https ?? 'no responde'}</Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}

function Prueba({ idMun }: { idMun: number }) {
  const push = useNotificationsStore((s) => s.push)
  const [lista, setLista] = useState<Chequeo[] | null>(null)
  const mut = useMutation({
    mutationFn: () => probarPuestaEnMarcha(idMun),
    onSuccess: setLista,
    onError: (e: Error) => push({ kind: 'error', title: 'No se pudo probar', body: e.message }),
  })
  return (
    <section style={seccion}>
      <h2 style={subtitulo}>Prueba de puesta en marcha</h2>
      <div><Button type="button" disabled={mut.isPending} onClick={() => mut.mutate()}>
        {mut.isPending ? 'Probando…' : 'Probar puesta en marcha'}
      </Button></div>
      {lista && (
        <ul style={{ margin: 0, paddingLeft: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 4 }}>
          {lista.map((c) => (
            <li key={c.nombre} style={{ fontSize: 13 }}>
              <Badge kind={c.ok ? 'success' : 'error'}>{c.ok ? 'bien' : 'falla'}</Badge> {c.nombre}
              <span style={{ color: 'var(--fg-3)' }}> — {c.detalle}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

const pagina: React.CSSProperties = { padding: 24, display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 960 }
