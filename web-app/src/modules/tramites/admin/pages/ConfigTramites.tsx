import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Settings, ExternalLink } from 'lucide-react'
import { Button, Card, Badge, EmptyState, Skeleton } from '../../../../ui'
import { useTiposCatalogo } from '../hooks'
import { NuevoTipoModal } from '../modals/NuevoTipoModal'

export function ConfigTramites() {
  const navigate = useNavigate()
  const { data, isLoading, error } = useTiposCatalogo()
  const [modalAbierto, setModalAbierto] = useState(false)

  const tipos = data?.items ?? []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: '1.4rem', margin: 0, color: 'var(--fg-1)' }}>
            Configuración de trámites
          </h1>
          <p style={{ margin: '4px 0 0', color: 'var(--fg-2)', fontSize: 14 }}>
            Tipos de trámite y versiones de circuitos. Solo Admin/Supervisor.
          </p>
        </div>
        <Button variant="accent" icon={<Plus size={16} />} onClick={() => setModalAbierto(true)}>
          Nuevo tipo
        </Button>
      </header>

      {isLoading && (
        <Card>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} height={48} />
            ))}
          </div>
        </Card>
      )}

      {error && (
        <Card>
          <p style={{ color: 'var(--color-error)' }}>
            Error al cargar los tipos: {error instanceof Error ? error.message : String(error)}
          </p>
        </Card>
      )}

      {!isLoading && tipos.length === 0 && (
        <EmptyState
          title="No hay tipos de trámite"
          description="Crea el primer tipo para empezar a configurar el catálogo."
          action={
            <Button variant="accent" icon={<Plus size={16} />} onClick={() => setModalAbierto(true)}>
              Nuevo tipo
            </Button>
          }
        />
      )}

      {!isLoading && tipos.length > 0 && (
        <Card>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
            <thead>
              <tr style={{ textAlign: 'left', borderBottom: '1px solid var(--border-primary)' }}>
                <th style={cellHead}>Código</th>
                <th style={cellHead}>Nombre</th>
                <th style={cellHead}>Prefijo</th>
                <th style={cellHead}>Iniciadores</th>
                <th style={cellHead}>Versión publicada</th>
                <th style={{ ...cellHead, width: 100, textAlign: 'right' }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {tipos.map((t) => (
                <tr key={t.id_tipo_tramite} style={{ borderBottom: '1px solid var(--border-primary)' }}>
                  <td style={cellMono}>{t.codigo}</td>
                  <td style={cell}>{t.nombre}</td>
                  <td style={cellMono}>{t.prefijo}</td>
                  <td style={cell}>
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {t.iniciadores_permitidos.map((i) => (
                        <Badge key={i} kind="neutral">{i}</Badge>
                      ))}
                    </div>
                  </td>
                  <td style={cell}>
                    {t.id_version_publicada ? (
                      <Badge kind="success">publicada</Badge>
                    ) : (
                      <Badge kind="warn">sin publicar</Badge>
                    )}
                  </td>
                  <td style={{ ...cell, textAlign: 'right' }}>
                    <button
                      onClick={() => navigate(`/tramites/config/${t.id_tipo_tramite}`)}
                      title="Editar"
                      style={btnIcono}
                    >
                      <Settings size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      <Card variant="default">
        <p style={{ margin: 0, fontSize: 13, color: 'var(--fg-3)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <ExternalLink size={14} />
          Para gestionar permisos de quien puede crear/editar tipos, ver módulo Usuarios.
        </p>
      </Card>

      {modalAbierto && (
        <NuevoTipoModal
          onCerrar={() => setModalAbierto(false)}
          onCreado={(idTipo) => {
            setModalAbierto(false)
            navigate(`/tramites/config/${idTipo}`)
          }}
        />
      )}
    </div>
  )
}

const cellHead: React.CSSProperties = {
  padding: '10px 12px',
  fontFamily: 'var(--font-display)',
  fontSize: 12,
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
  color: 'var(--fg-3)',
  fontWeight: 600,
}
const cell: React.CSSProperties = { padding: '10px 12px', color: 'var(--fg-1)' }
const cellMono: React.CSSProperties = { ...cell, fontFamily: 'var(--font-mono)', fontSize: 13 }
const btnIcono: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  cursor: 'pointer',
  color: 'var(--fg-2)',
  padding: 6,
  borderRadius: 4,
}
