import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, RefreshCw, Paperclip } from 'lucide-react'
import { Skeleton } from '../../../ui'
import { useAuthStore } from '../../../stores/auth'
import { useTramite } from '../hooks/useTramites'
import { EstadoBadge } from '../components/EstadoBadge'
import { Timeline } from '../components/Timeline'
import { ListaDocumentos } from '../components/ListaDocumentos'
import { PanelAcciones } from '../components/PanelAcciones'
import { FileUploader } from '../components/FileUploader'

export function DetalleTramite() {
  const { numero } = useParams<{ numero: string }>()
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const [showUploader, setShowUploader] = useState(false)

  const { detalle, movimientos, transiciones, refetch } = useTramite(numero ?? '')

  const isLoading = detalle.isLoading
  const error = detalle.error
  const data = detalle.data
  const movData = movimientos.data?.movimientos ?? []
  const transData = transiciones.data

  if (isLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} height={40} />)}
      </div>
    )
  }

  if (error || !data) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, alignItems: 'flex-start' }}>
        <button type="button" onClick={() => navigate('/tramites')} style={btnBackStyle}>
          <ArrowLeft size={14} strokeWidth={1.5} /> Volver a bandeja
        </button>
        <p style={{ color: 'var(--color-error)', fontFamily: 'var(--font-display)', fontSize: 13 }}>
          {error instanceof Error ? error.message : 'No se encontró el trámite.'}
        </p>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <button type="button" onClick={() => navigate('/tramites')} style={btnBackStyle}>
            <ArrowLeft size={14} strokeWidth={1.5} /> Bandeja
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <h1 style={h1Style}>{data.numero_expediente}</h1>
            <EstadoBadge etiqueta={data.estado_etiqueta} color={data.estado_color} />
          </div>
          <p style={{ margin: 0, fontSize: 13, fontFamily: 'var(--font-display)', color: 'var(--fg-2)' }}>
            {data.tipo_nombre}
            {data.asunto && <> · {data.asunto}</>}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button
            type="button"
            onClick={() => setShowUploader(true)}
            style={btnOutlineStyle}
          >
            <Paperclip size={14} strokeWidth={1.5} />
            Adjuntar
          </button>
          <button
            type="button"
            onClick={() => { void refetch() }}
            title="Actualizar"
            style={iconBtnStyle}
          >
            <RefreshCw size={15} strokeWidth={1.5} />
          </button>
        </div>
      </div>

      {/* Layout 2 columnas */}
      <div style={layoutStyle}>
        {/* Columna izquierda */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Metadatos */}
          <section style={cardStyle}>
            <h2 style={cardTitleStyle}>Datos del trámite</h2>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px 24px' }}>
              <MetaDato
                label="Iniciador"
                valor={`${data.iniciador_tipo === 'area_interna' ? 'Área interna' : data.iniciador_tipo}${data.iniciador_nombre ? ` — ${data.iniciador_nombre}` : ''}`}
              />
              <MetaDato
                label="Fecha de alta"
                valor={new Date(data.fecha_alta).toLocaleDateString('es-AR', { day: '2-digit', month: 'long', year: 'numeric' })}
              />
              {data.destinatario_actual_nombre && (
                <MetaDato label="Ubicación actual" valor={`${data.destinatario_actual_tipo ?? ''} — ${data.destinatario_actual_nombre}`} />
              )}
              {data.tomado_por_nombre && (
                <MetaDato label="Tomado por" valor={data.tomado_por_nombre} />
              )}
              {data.representante_nombre && (
                <MetaDato label="Representante" valor={data.representante_nombre} />
              )}
              <MetaDato label="Tipo" valor={`${data.tipo_nombre} (v${data.version_num})`} />
            </div>
          </section>

          {/* Documentos */}
          <section style={cardStyle}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <h2 style={{ ...cardTitleStyle, margin: 0 }}>
                Documentos ({data.cant_documentos})
              </h2>
              <button type="button" onClick={() => setShowUploader(true)} style={btnSmallStyle}>
                <Paperclip size={13} strokeWidth={1.5} /> Adjuntar
              </button>
            </div>
            <ListaDocumentos
              tramiteNumero={data.numero_expediente}
              documentos={[]}
              onCambio={() => { void refetch() }}
            />
          </section>

          {/* Timeline */}
          <section style={cardStyle}>
            <h2 style={cardTitleStyle}>Historial</h2>
            <Timeline movimientos={movData} />
          </section>

          {/* Relaciones */}
          {data.relaciones && data.relaciones.length > 0 && (
            <section style={cardStyle}>
              <h2 style={cardTitleStyle}>Expedientes relacionados</h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {data.relaciones.map((r) => (
                  <div key={r.id_tramite_relacion} style={relacionRowStyle}>
                    <div>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--zaris-orange)', fontWeight: 600 }}>
                        {r.numero_expediente_relacionado}
                      </span>
                      <span style={{ fontSize: 12, color: 'var(--fg-3)', fontFamily: 'var(--font-display)', marginLeft: 8 }}>
                        {r.tipo_relacion.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => navigate(`/tramites/${r.numero_expediente_relacionado}`)}
                      style={btnSmallStyle}
                    >
                      Ver
                    </button>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>

        {/* Columna derecha */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, position: 'sticky', top: 20, alignSelf: 'flex-start' }}>
          <PanelAcciones
            tramite={data}
            transicionesPermitidas={transData?.transiciones ?? []}
            documentosDesdeEstado={[]}
            idUsuarioActual={user?.id_usuario}
            onActualizar={() => { void refetch() }}
          />
        </div>
      </div>

      {showUploader && (
        <FileUploader
          numeroExpediente={data.numero_expediente}
          onExito={() => { void refetch() }}
          onCerrar={() => setShowUploader(false)}
        />
      )}
    </div>
  )
}

function MetaDato({ label, valor, destacar }: { label: string; valor: string; destacar?: boolean }) {
  return (
    <div>
      <p style={{ margin: 0, fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--font-display)', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 500 }}>
        {label}
      </p>
      <p style={{ margin: '2px 0 0', fontSize: 13, color: destacar ? 'var(--color-error)' : 'var(--fg-1)', fontFamily: 'var(--font-display)', fontWeight: destacar ? 600 : 400 }}>
        {valor}
      </p>
    </div>
  )
}

const h1Style: React.CSSProperties = {
  fontSize: '1.35rem', fontWeight: 600, letterSpacing: '-0.5px',
  color: 'var(--fg-1)', margin: 0, fontFamily: 'var(--font-display)',
}
const layoutStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'minmax(0, 1fr) 300px',
  gap: 20,
  alignItems: 'flex-start',
}
const cardStyle: React.CSSProperties = {
  background: 'var(--surface-100)', borderRadius: 'var(--radius-xl)',
  border: '1px solid var(--border-primary)', padding: '20px',
}
const cardTitleStyle: React.CSSProperties = {
  margin: '0 0 14px', fontSize: 14, fontWeight: 600,
  fontFamily: 'var(--font-display)', color: 'var(--fg-1)',
}
const relacionRowStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  padding: '8px 12px', background: 'var(--surface-300)', borderRadius: 'var(--radius-lg)',
}
const btnBackStyle: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 5,
  background: 'none', border: 'none', cursor: 'pointer',
  fontFamily: 'var(--font-display)', fontSize: 12, color: 'var(--fg-3)',
  padding: 0,
}
const btnOutlineStyle: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6,
  padding: '8px 14px', borderRadius: 'var(--radius-lg)',
  border: '1px solid var(--border-primary)',
  background: 'transparent', color: 'var(--fg-2)', cursor: 'pointer',
  fontFamily: 'var(--font-display)', fontSize: 13,
}
const btnSmallStyle: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 4,
  padding: '5px 10px', borderRadius: 'var(--radius-lg)',
  border: '1px solid var(--border-primary)',
  background: 'transparent', color: 'var(--fg-2)', cursor: 'pointer',
  fontFamily: 'var(--font-display)', fontSize: 12,
}
const iconBtnStyle: React.CSSProperties = {
  background: 'var(--surface-300)', border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-lg)', padding: '8px 9px',
  color: 'var(--fg-3)', cursor: 'pointer', display: 'inline-flex', alignItems: 'center',
}
