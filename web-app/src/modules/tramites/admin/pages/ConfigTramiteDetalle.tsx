import { useState, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Plus, Edit2, Trash2, Send, Archive, FilePlus,
} from 'lucide-react'
import { Button, Card, Badge, Skeleton, EmptyState } from '../../../../ui'
import {
  useTipoAdmin,
  useVersionDetalle,
  useCrearBorrador,
  usePublicarVersion,
  useArchivarVersion,
  useEliminarTipo,
  useEliminarCampo,
  useEliminarEstado,
  useEliminarTransicion,
  useEliminarDocReq,
} from '../hooks'
import { EditarTipoModal } from '../modals/EditarTipoModal'
import { CampoModal } from '../modals/CampoModal'
import { EstadoModal } from '../modals/EstadoModal'
import { TransicionModal } from '../modals/TransicionModal'
import { DocReqModal } from '../modals/DocReqModal'
import type {
  TipoTramiteCampo,
  TipoTramiteEstado,
  TipoTramiteTransicion,
  TipoTramiteDocRequerido,
} from '../../types'

type TabKey = 'general' | 'campos' | 'estados' | 'transiciones' | 'documentos'

export function ConfigTramiteDetalle() {
  const { idTipo } = useParams<{ idTipo: string }>()
  const navigate = useNavigate()
  const id = idTipo ? Number(idTipo) : null

  const tipo = useTipoAdmin(id)
  const tipoData = tipo.data

  // Version activa para editar: por default la mas alta (puede ser borrador o publicada)
  const [idVerEdit, setIdVerEdit] = useState<number | null>(null)
  const versionElegida = useMemo(() => {
    if (!tipoData || tipoData.versiones.length === 0) return null
    if (idVerEdit && tipoData.versiones.some((v) => v.id_tipo_tramite_version === idVerEdit)) {
      return idVerEdit
    }
    // default: ultima version
    return tipoData.versiones[tipoData.versiones.length - 1].id_tipo_tramite_version
  }, [tipoData, idVerEdit])

  const version = useVersionDetalle(versionElegida)
  const versionData = version.data

  // tabs
  const [tab, setTab] = useState<TabKey>('general')

  // modales
  const [editarTipoAbierto, setEditarTipoAbierto] = useState(false)
  const [campoEditando, setCampoEditando] = useState<TipoTramiteCampo | 'nuevo' | null>(null)
  const [estadoEditando, setEstadoEditando] = useState<TipoTramiteEstado | 'nuevo' | null>(null)
  const [transEditando, setTransEditando] = useState<TipoTramiteTransicion | 'nuevo' | null>(null)
  const [docEditando, setDocEditando] = useState<TipoTramiteDocRequerido | 'nuevo' | null>(null)

  const crearBorrador = useCrearBorrador()
  const publicar = usePublicarVersion()
  const archivar = useArchivarVersion()
  const eliminarTipoM = useEliminarTipo()
  const eliminarCampoM = useEliminarCampo()
  const eliminarEstadoM = useEliminarEstado()
  const eliminarTransM = useEliminarTransicion()
  const eliminarDocM = useEliminarDocReq()

  if (tipo.isLoading) {
    return <Skeleton height={300} />
  }
  if (tipo.error || !tipoData) {
    return (
      <Card>
        <p style={{ color: 'var(--color-error)' }}>
          No se pudo cargar el tipo de trámite. {tipo.error instanceof Error ? tipo.error.message : ''}
        </p>
        <Button onClick={() => navigate('/tramites/config')}>Volver</Button>
      </Card>
    )
  }

  const versionActiva = tipoData.versiones.find((v) => v.id_tipo_tramite_version === versionElegida)
  const editable = versionActiva?.estado === 'borrador' || (versionActiva?.estado === 'publicado' && (versionData?.cant_tramites ?? 0) === 0)
  const tieneBorradorAbierto = tipoData.versiones.some((v) => v.estado === 'borrador')

  async function handleEliminarTipo() {
    if (!confirm(`¿Desactivar el tipo "${tipoData!.nombre}"? Sólo se permite si no hay trámites activos.`)) return
    try {
      await eliminarTipoM.mutateAsync(tipoData!.id_tipo_tramite)
      navigate('/tramites/config')
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Error al eliminar')
    }
  }

  async function handlePublicar() {
    if (!versionElegida) return
    if (!confirm('¿Publicar esta versión? Quedará disponible para nuevos trámites y se archivará la anterior (si la hay).')) return
    try {
      await publicar.mutateAsync(versionElegida)
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Error al publicar')
    }
  }

  async function handleArchivar() {
    if (!versionElegida) return
    if (!confirm('¿Archivar esta versión?')) return
    try {
      await archivar.mutateAsync(versionElegida)
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Error al archivar')
    }
  }

  async function handleNuevoBorrador() {
    if (tieneBorradorAbierto) {
      alert('Ya hay un borrador abierto. Publicalo o archivalo antes de crear otro.')
      return
    }
    try {
      const nueva = await crearBorrador.mutateAsync(tipoData!.id_tipo_tramite)
      setIdVerEdit(nueva.id_tipo_tramite_version)
      alert(`Nueva versión v${nueva.version_num} (borrador) creada. La estructura fue copiada de la publicada.`)
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Error al crear borrador')
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Header */}
      <header style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button onClick={() => navigate('/tramites/config')} style={btnBack} title="Volver">
          <ArrowLeft size={18} />
        </button>
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: '1.4rem', margin: 0, color: 'var(--fg-1)' }}>
            {tipoData.nombre}{' '}
            <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--fg-3)', fontSize: 14 }}>
              ({tipoData.codigo})
            </span>
          </h1>
          <p style={{ margin: '4px 0 0', color: 'var(--fg-2)', fontSize: 13 }}>
            Prefijo de numeración: <strong>{tipoData.prefijo}</strong>
            {tipoData.descripcion ? ` · ${tipoData.descripcion}` : ''}
          </p>
        </div>
        <Button icon={<Edit2 size={14} />} onClick={() => setEditarTipoAbierto(true)}>
          Editar tipo
        </Button>
        <Button variant="ghost" icon={<Trash2 size={14} />} onClick={handleEliminarTipo}>
          Desactivar
        </Button>
      </header>

      {/* Selector de versión */}
      <Card>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 13, color: 'var(--fg-2)' }}>Versiones:</span>
          {tipoData.versiones.map((v) => {
            const esActiva = v.id_tipo_tramite_version === versionElegida
            return (
              <button
                key={v.id_tipo_tramite_version}
                onClick={() => setIdVerEdit(v.id_tipo_tramite_version)}
                style={{
                  ...pillVer,
                  background: esActiva ? 'var(--zaris-dark)' : 'var(--surface-300)',
                  color: esActiva ? 'var(--zaris-cream)' : 'var(--fg-1)',
                }}
              >
                v{v.version_num}{' '}
                <Badge kind={v.estado === 'publicado' ? 'success' : v.estado === 'borrador' ? 'warn' : 'neutral'}>
                  {v.estado}
                </Badge>
              </button>
            )
          })}
          <div style={{ flex: 1 }} />
          <Button icon={<FilePlus size={14} />} onClick={handleNuevoBorrador} disabled={tieneBorradorAbierto}>
            Nuevo borrador
          </Button>
          {versionActiva?.estado === 'borrador' && (
            <Button variant="accent" icon={<Send size={14} />} onClick={handlePublicar}>
              Publicar
            </Button>
          )}
          {(versionActiva?.estado === 'publicado' || versionActiva?.estado === 'borrador') && (
            <Button variant="ghost" icon={<Archive size={14} />} onClick={handleArchivar}>
              Archivar
            </Button>
          )}
        </div>
        {versionActiva && versionData && (
          <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--fg-3)' }}>
            {versionActiva.estado === 'publicado' && (versionData.cant_tramites ?? 0) > 0
              ? `Esta versión tiene ${versionData.cant_tramites} trámite(s) instanciado(s). Es inmutable. Crea un nuevo borrador para cambios.`
              : versionActiva.estado === 'publicado'
                ? 'Publicada sin trámites instanciados. Editable.'
                : versionActiva.estado === 'borrador'
                  ? 'Borrador editable. Publicalo cuando esté listo.'
                  : 'Archivada. Solo lectura.'}
          </p>
        )}
      </Card>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 8, borderBottom: '1px solid var(--border-primary)' }}>
        {([
          ['general', 'General'],
          ['campos', 'Campos'],
          ['estados', 'Estados'],
          ['transiciones', 'Transiciones'],
          ['documentos', 'Docs requeridos'],
        ] as Array<[TabKey, string]>).map(([k, label]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            style={{
              ...tabBtn,
              borderBottom: tab === k ? '2px solid var(--zaris-orange)' : '2px solid transparent',
              color: tab === k ? 'var(--fg-1)' : 'var(--fg-3)',
              fontWeight: tab === k ? 600 : 400,
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'general' && (
        <Card>
          <table style={{ width: '100%', fontSize: 14 }}>
            <tbody>
              <FilaInfo label="Código" valor={tipoData.codigo} mono />
              <FilaInfo label="Prefijo numerador" valor={tipoData.prefijo} mono />
              <FilaInfo label="Largo correlativo" valor={String(tipoData.largo_correlativo)} />
              <FilaInfo label="Separador" valor={tipoData.separador} mono />
              <FilaInfo label="Incluye municipio en N°" valor={tipoData.incluye_municipio ? 'Sí' : 'No'} />
              <FilaInfo label="Incluye año en N°" valor={tipoData.incluye_anio ? 'Sí' : 'No'} />
              <FilaInfo label="Correlativo reinicia anual" valor={tipoData.correlativo_reinicia_anual ? 'Sí' : 'No'} />
              <FilaInfo label="Iniciadores permitidos" valor={tipoData.iniciadores_permitidos.join(', ')} />
              <FilaInfo label="Permite representante" valor={tipoData.permite_representante ? 'Sí' : 'No'} />
              <FilaInfo label="Descripción" valor={tipoData.descripcion ?? '(sin descripción)'} />
            </tbody>
          </table>
        </Card>
      )}

      {tab !== 'general' && !versionData && <Skeleton height={200} />}

      {tab === 'campos' && versionData && (
        <SeccionLista
          titulo="Campos del formulario inicial"
          editable={editable}
          onNuevo={() => setCampoEditando('nuevo')}
          vacio={versionData.campos.length === 0}
          vacioMsg="No hay campos. Agregá los que el iniciador debe completar al crear un trámite."
        >
          <table style={{ width: '100%', fontSize: 14 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-primary)' }}>
                <th style={th}>Orden</th>
                <th style={th}>Nombre interno</th>
                <th style={th}>Etiqueta</th>
                <th style={th}>Tipo</th>
                <th style={th}>Obligatorio</th>
                <th style={th}></th>
              </tr>
            </thead>
            <tbody>
              {versionData.campos.map((c) => (
                <tr key={c.id_tipo_tramite_campo} style={{ borderBottom: '1px solid var(--border-primary)' }}>
                  <td style={td}>{c.orden}</td>
                  <td style={tdMono}>{c.nombre_interno}</td>
                  <td style={td}>{c.etiqueta}</td>
                  <td style={td}>{c.tipo_dato}</td>
                  <td style={td}>{c.obligatorio ? 'Sí' : 'No'}</td>
                  <td style={{ ...td, textAlign: 'right' }}>
                    <Accion
                      editable={editable}
                      onEdit={() => setCampoEditando(c)}
                      onDel={async () => {
                        if (!confirm(`Eliminar campo "${c.etiqueta}"?`)) return
                        try { await eliminarCampoM.mutateAsync(c.id_tipo_tramite_campo) }
                        catch (e) { alert(e instanceof Error ? e.message : 'Error') }
                      }}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </SeccionLista>
      )}

      {tab === 'estados' && versionData && (
        <SeccionLista
          titulo="Estados del circuito (FSM)"
          editable={editable}
          onNuevo={() => setEstadoEditando('nuevo')}
          vacio={versionData.estados.length === 0}
          vacioMsg="No hay estados. Mínimo 1 inicial y 1 final para poder publicar."
        >
          <table style={{ width: '100%', fontSize: 14 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-primary)' }}>
                <th style={th}>Orden</th>
                <th style={th}>Código</th>
                <th style={th}>Etiqueta</th>
                <th style={th}>Color</th>
                <th style={th}>Tipo</th>
                <th style={th}></th>
              </tr>
            </thead>
            <tbody>
              {versionData.estados.map((e) => (
                <tr key={e.id_tipo_tramite_estado} style={{ borderBottom: '1px solid var(--border-primary)' }}>
                  <td style={td}>{e.orden}</td>
                  <td style={tdMono}>{e.codigo}</td>
                  <td style={td}>{e.etiqueta}</td>
                  <td style={td}>
                    {e.color && <span style={{ display: 'inline-block', width: 16, height: 16, background: e.color, borderRadius: 4, verticalAlign: 'middle' }} />}
                    {' '}{e.color}
                  </td>
                  <td style={td}>
                    {e.es_inicial && <Badge kind="neutral">inicial</Badge>}{' '}
                    {e.es_final && <Badge kind="success">final</Badge>}
                  </td>
                  <td style={{ ...td, textAlign: 'right' }}>
                    <Accion
                      editable={editable}
                      onEdit={() => setEstadoEditando(e)}
                      onDel={async () => {
                        if (!confirm(`Eliminar estado "${e.etiqueta}"?`)) return
                        try { await eliminarEstadoM.mutateAsync(e.id_tipo_tramite_estado) }
                        catch (er) { alert(er instanceof Error ? er.message : 'Error') }
                      }}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </SeccionLista>
      )}

      {tab === 'transiciones' && versionData && (
        <SeccionLista
          titulo="Transiciones del FSM"
          editable={editable && versionData.estados.length >= 2}
          onNuevo={() => setTransEditando('nuevo')}
          vacio={versionData.transiciones.length === 0}
          vacioMsg="No hay transiciones. Necesitás al menos 2 estados para poder agregar una."
        >
          <table style={{ width: '100%', fontSize: 14 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-primary)' }}>
                <th style={th}>Origen</th>
                <th style={th}>→ Destino</th>
                <th style={th}>Etiqueta acción</th>
                <th style={th}>Requiere</th>
                <th style={th}></th>
              </tr>
            </thead>
            <tbody>
              {versionData.transiciones.map((t) => {
                const ori = versionData.estados.find((e) => e.id_tipo_tramite_estado === t.id_estado_origen)
                const dst = versionData.estados.find((e) => e.id_tipo_tramite_estado === t.id_estado_destino)
                return (
                  <tr key={t.id_tipo_tramite_transicion} style={{ borderBottom: '1px solid var(--border-primary)' }}>
                    <td style={td}>{ori?.etiqueta ?? `#${t.id_estado_origen}`}</td>
                    <td style={td}>→ {dst?.etiqueta ?? `#${t.id_estado_destino}`}</td>
                    <td style={td}>{t.etiqueta_accion}</td>
                    <td style={td}>
                      {t.requiere_comentario && <Badge kind="neutral">comentario</Badge>}{' '}
                      {t.requiere_adjunto && <Badge kind="neutral">adjunto</Badge>}
                    </td>
                    <td style={{ ...td, textAlign: 'right' }}>
                      <Accion
                        editable={editable}
                        onEdit={() => setTransEditando(t)}
                        onDel={async () => {
                          if (!confirm(`Eliminar transición "${t.etiqueta_accion}"?`)) return
                          try { await eliminarTransM.mutateAsync(t.id_tipo_tramite_transicion) }
                          catch (er) { alert(er instanceof Error ? er.message : 'Error') }
                        }}
                      />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </SeccionLista>
      )}

      {tab === 'documentos' && versionData && (
        <SeccionLista
          titulo="Documentos requeridos"
          editable={editable}
          onNuevo={() => setDocEditando('nuevo')}
          vacio={versionData.documentos_requeridos.length === 0}
          vacioMsg="No hay documentos requeridos definidos. Podés agregarlos opcionalmente."
        >
          <table style={{ width: '100%', fontSize: 14 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-primary)' }}>
                <th style={th}>Nombre</th>
                <th style={th}>Estado</th>
                <th style={th}>Aporta</th>
                <th style={th}>Obligatorio</th>
                <th style={th}>Firma</th>
                <th style={th}></th>
              </tr>
            </thead>
            <tbody>
              {versionData.documentos_requeridos.map((d) => {
                const estadoVinc = d.id_tipo_tramite_estado
                  ? versionData.estados.find((e) => e.id_tipo_tramite_estado === d.id_tipo_tramite_estado)
                  : null
                return (
                  <tr key={d.id_tipo_tramite_documento_requerido} style={{ borderBottom: '1px solid var(--border-primary)' }}>
                    <td style={td}>{d.nombre}</td>
                    <td style={td}>{estadoVinc?.etiqueta ?? '(al iniciar)'}</td>
                    <td style={td}>{d.quien_debe_adjuntar}</td>
                    <td style={td}>{d.obligatorio ? 'Sí' : 'No'}</td>
                    <td style={td}>{d.requiere_firma ? 'Sí' : 'No'}</td>
                    <td style={{ ...td, textAlign: 'right' }}>
                      <Accion
                        editable={editable}
                        onEdit={() => setDocEditando(d)}
                        onDel={async () => {
                          if (!confirm(`Eliminar "${d.nombre}"?`)) return
                          try { await eliminarDocM.mutateAsync(d.id_tipo_tramite_documento_requerido) }
                          catch (er) { alert(er instanceof Error ? er.message : 'Error') }
                        }}
                      />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </SeccionLista>
      )}

      {/* Modales */}
      {editarTipoAbierto && (
        <EditarTipoModal tipo={tipoData} onCerrar={() => setEditarTipoAbierto(false)} />
      )}
      {campoEditando && versionData && (
        <CampoModal
          idVersion={versionData.id_tipo_tramite_version}
          campo={campoEditando === 'nuevo' ? null : campoEditando}
          onCerrar={() => setCampoEditando(null)}
        />
      )}
      {estadoEditando && versionData && (
        <EstadoModal
          idVersion={versionData.id_tipo_tramite_version}
          estado={estadoEditando === 'nuevo' ? null : estadoEditando}
          onCerrar={() => setEstadoEditando(null)}
        />
      )}
      {transEditando && versionData && (
        <TransicionModal
          idVersion={versionData.id_tipo_tramite_version}
          transicion={transEditando === 'nuevo' ? null : transEditando}
          estados={versionData.estados}
          onCerrar={() => setTransEditando(null)}
        />
      )}
      {docEditando && versionData && (
        <DocReqModal
          idVersion={versionData.id_tipo_tramite_version}
          doc={docEditando === 'nuevo' ? null : docEditando}
          estados={versionData.estados}
          onCerrar={() => setDocEditando(null)}
        />
      )}
    </div>
  )
}

function FilaInfo({ label, valor, mono = false }: { label: string; valor: string; mono?: boolean }) {
  return (
    <tr style={{ borderBottom: '1px solid var(--border-primary)' }}>
      <td style={{ padding: '8px 12px', color: 'var(--fg-3)', width: 220, fontSize: 13 }}>{label}</td>
      <td style={{ padding: '8px 12px', fontFamily: mono ? 'var(--font-mono)' : undefined, fontSize: mono ? 13 : 14 }}>
        {valor}
      </td>
    </tr>
  )
}

function SeccionLista({
  titulo, editable, onNuevo, vacio, vacioMsg, children,
}: {
  titulo: string
  editable: boolean
  onNuevo: () => void
  vacio: boolean
  vacioMsg: string
  children: React.ReactNode
}) {
  return (
    <Card>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <h2 style={{ margin: 0, fontSize: '1.05rem', color: 'var(--fg-1)' }}>{titulo}</h2>
        <Button variant="accent" icon={<Plus size={14} />} onClick={onNuevo} disabled={!editable}>
          Nuevo
        </Button>
      </div>
      {!editable && (
        <p style={{ margin: '0 0 12px', fontSize: 12, color: 'var(--fg-3)' }}>
          Esta versión no es editable. Creá un nuevo borrador para hacer cambios.
        </p>
      )}
      {vacio ? <EmptyState title="Sin elementos" description={vacioMsg} /> : children}
    </Card>
  )
}

function Accion({ editable, onEdit, onDel }: { editable: boolean; onEdit: () => void; onDel: () => void }) {
  return (
    <div style={{ display: 'inline-flex', gap: 4 }}>
      <button onClick={onEdit} disabled={!editable} title="Editar" style={btnIconoMini}>
        <Edit2 size={14} />
      </button>
      <button onClick={onDel} disabled={!editable} title="Eliminar" style={btnIconoMini}>
        <Trash2 size={14} />
      </button>
    </div>
  )
}

const btnBack: React.CSSProperties = {
  background: 'transparent', border: 'none', cursor: 'pointer',
  color: 'var(--fg-2)', padding: 6, borderRadius: 4,
}
const pillVer: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6,
  padding: '4px 10px', borderRadius: 'var(--radius-pill)',
  border: 'none', cursor: 'pointer',
  fontSize: 13, fontFamily: 'var(--font-display)',
}
const tabBtn: React.CSSProperties = {
  background: 'transparent', border: 'none', cursor: 'pointer',
  padding: '8px 12px', fontFamily: 'var(--font-display)', fontSize: 14,
}
const th: React.CSSProperties = {
  padding: '8px 10px', textAlign: 'left',
  fontFamily: 'var(--font-display)', fontSize: 11,
  textTransform: 'uppercase', color: 'var(--fg-3)', fontWeight: 600,
}
const td: React.CSSProperties = { padding: '8px 10px', color: 'var(--fg-1)' }
const tdMono: React.CSSProperties = { ...td, fontFamily: 'var(--font-mono)', fontSize: 13 }
const btnIconoMini: React.CSSProperties = {
  background: 'transparent', border: 'none', cursor: 'pointer',
  color: 'var(--fg-2)', padding: 4, borderRadius: 4,
}
