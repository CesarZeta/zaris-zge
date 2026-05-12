import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useReclamoAdjuntos, useReclamoDetalle } from '../hooks/useReclamos'
import { useAuthStore } from '../../../stores/auth'
import { Badge } from '../components/Badge'
import { CambiarEstadoModal } from '../components/CambiarEstadoModal'
import { CancelarReclamoModal } from '../components/CancelarReclamoModal'
import type { Adjunto, ReclamoDetalle, HistorialItem, OTAsociada, Subreclamo } from '../types/reclamo'

const FUENTE_LABEL: Record<string, string> = {
  pin_manual: 'Pin manual en mapa',
  geocoding_osm: 'Sugerencia OpenStreetMap',
  gps_dispositivo: 'GPS del dispositivo',
  activo_referenciado: 'Activo referenciado',
}

const CANAL_LABEL: Record<string, string> = {
  web: 'Web', whatsapp: 'WhatsApp', telefono: 'Teléfono',
  presencial: 'Presencial', oficio: 'Oficio', app_movil: 'App móvil', otro: 'Otro',
}

export function DetailView() {
  const navigate = useNavigate()
  const params = useParams<{ id?: string }>()
  const id = params.id ? Number(params.id) : null
  const detalle = useReclamoDetalle(id)
  const user = useAuthStore((s) => s.user)
  const [openEstado, setOpenEstado] = useState(false)
  const [openCancelar, setOpenCancelar] = useState(false)

  if (detalle.isLoading) {
    return <div style={{ color: 'var(--fg-3)', padding: 20 }}>Cargando reclamo...</div>
  }
  if (detalle.isError) {
    return <div style={{ color: 'var(--color-error)', padding: 20 }}>Error: {(detalle.error as Error).message}</div>
  }
  if (!detalle.data) return null

  const r = detalle.data
  const esFinal = r.estado === 'Resuelto' || r.estado === 'Cancelado'
  // Gestion solo nivel 1/2/3 (admin/supervisor/operador). Nivel 4 (consultor) solo lee.
  const puedeGestionar = !!user && user.nivel_acceso <= 3
  const accionesVisibles = !esFinal && puedeGestionar

  return (
    <>
      {/* Header con botón volver */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
        <div>
          <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: '1.2rem', color: 'var(--fg-1)', fontWeight: 600 }}>
            {r.tipo_nombre || 'Reclamo'}
          </h2>
          <div style={{ fontSize: '0.82rem', color: 'var(--fg-3)', marginTop: 2, fontFamily: 'var(--font-mono)' }}>
            {r.nro_reclamo || `#${r.id_reclamo}`} · {r.area_nombre || '—'}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          {accionesVisibles && (
            <>
              <button onClick={() => setOpenEstado(true)} style={btnPrimary}>Cambiar estado</button>
              <button onClick={() => navigate(`/reclamos/${r.id_reclamo}/editar`)} style={btnGhost}>Editar</button>
              <button onClick={() => setOpenCancelar(true)} style={btnDanger}>Cancelar reclamo</button>
            </>
          )}
          <button onClick={() => navigate('/reclamos')} style={btnGhost}>← Volver</button>
        </div>
      </div>

      {/* Modales B3 */}
      <CambiarEstadoModal
        open={openEstado}
        idReclamo={r.id_reclamo}
        estadoActual={r.estado}
        onClose={() => setOpenEstado(false)}
        onSuccess={() => { setOpenEstado(false); detalle.refetch() }}
      />
      <CancelarReclamoModal
        open={openCancelar}
        idReclamo={r.id_reclamo}
        nroReclamo={r.nro_reclamo}
        onClose={() => setOpenCancelar(false)}
        onSuccess={() => { setOpenCancelar(false); detalle.refetch() }}
      />

      <ReclamoSection title="Estado" icon="●">
        <Grid cols="repeat(4, 1fr)">
          <Cell label="Estado">
            <Badge kind="estado" value={r.estado} />
          </Cell>
          <Cell label="Prioridad">
            <Badge kind="prioridad" value={r.prioridad ?? 'Media'} />
          </Cell>
          <Cell label="Responsable">{r.agente_nombre || '—'}</Cell>
          <Cell label="Canal">{CANAL_LABEL[r.canal_origen ?? ''] ?? r.canal_origen ?? '—'}</Cell>
        </Grid>
        <Grid cols="repeat(3, 1fr)">
          <Cell label="Fecha ingreso" mono>{formatFecha(r.fecha_alta)}</Cell>
          <Cell label="Vencimiento SLA" mono>{r.sla_vencimiento ? formatFecha(r.sla_vencimiento) : '—'}</Cell>
          {r.fecha_cierre
            ? <Cell label="Cierre" mono>{formatFecha(r.fecha_cierre)}</Cell>
            : r.fecha_primer_asignacion
              ? <Cell label="Primera asignación" mono>{formatFecha(r.fecha_primer_asignacion)}</Cell>
              : <span />}
        </Grid>
      </ReclamoSection>

      <ReclamoSection title="Ciudadano">
        <Grid cols="repeat(4, 1fr)">
          <Cell label="Nombre">{r.ciudadano_apellido || '—'}, {r.ciudadano_nombre || '—'}</Cell>
          <Cell label="DNI / CUIL" mono>{r.doc_nro || '—'}{r.cuil ? ` · ${r.cuil}` : ''}</Cell>
          <Cell label="Teléfono" mono>{r.telefono || '—'}</Cell>
          <Cell label="Email">{r.ciudadano_email || '—'}</Cell>
        </Grid>
        {r.id_empresa && (
          <Grid cols="1fr">
            <Cell label="A nombre de empresa">
              <strong>{r.empresa_nombre || `#${r.id_empresa}`}</strong>
              {r.empresa_cuit ? <span style={{ color: 'var(--fg-3)', marginLeft: 8, fontFamily: 'var(--font-mono)' }}>CUIT {r.empresa_cuit}</span> : null}
            </Cell>
          </Grid>
        )}
      </ReclamoSection>

      <ReclamoSection title="Descripción">
        <p style={{ margin: 0, color: 'var(--fg-1)', fontSize: '0.92rem', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>
          {r.descripcion}
        </p>
        {r.observaciones && (
          <>
            <div style={cellLabel}>Observaciones</div>
            <p style={{ margin: 0, color: 'var(--fg-2)', fontSize: '0.88rem', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>
              {r.observaciones}
            </p>
          </>
        )}
      </ReclamoSection>

      <UbicacionSection r={r} />

      <AdjuntosSection idReclamo={r.id_reclamo} />

      {r.subreclamos.length > 0 && <SubreclamosSection items={r.subreclamos} />}

      {r.ordenes_trabajo.length > 0 && <OTsSection items={r.ordenes_trabajo} />}

      <HistorialSection items={r.historial} />
    </>
  )
}

// ── Sub-secciones ──

function UbicacionSection({ r }: { r: ReclamoDetalle }) {
  const direccion = r.direccion || r.domicilio_reclamo || ''
  const ubicacion = [r.localidad_nombre, r.partido_nombre, r.provincia_nombre].filter(Boolean).join(' · ')
  const tieneCoords = r.latitud != null && r.longitud != null
  const coordsTxt = tieneCoords ? `${(+r.latitud!).toFixed(6)}, ${(+r.longitud!).toFixed(6)}` : '—'
  const osmHref = tieneCoords ? `https://www.openstreetmap.org/?mlat=${r.latitud}&mlon=${r.longitud}#map=18/${r.latitud}/${r.longitud}` : null
  const activoTxt = r.id_activo
    ? `${r.activo_codigo || `#${r.id_activo}`}${r.activo_tipo_nombre ? ' · ' + r.activo_tipo_nombre : ''}`
    : null
  return (
    <ReclamoSection title="Ubicación">
      <Grid cols="1fr">
        <Cell label="Dirección">{direccion || '—'}</Cell>
        <Cell label="Localidad">{ubicacion || '—'}</Cell>
      </Grid>
      <Grid cols="repeat(2, 1fr)">
        <Cell label="Coordenadas" mono>
          {osmHref
            ? <a href={osmHref} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--zaris-orange)', textDecoration: 'none' }}>{coordsTxt}</a>
            : coordsTxt}
        </Cell>
        <Cell label="Fuente">{FUENTE_LABEL[r.fuente_geolocalizacion ?? ''] ?? r.fuente_geolocalizacion ?? '—'}</Cell>
      </Grid>
      {activoTxt && (
        <Grid cols="1fr">
          <Cell label="Activo referenciado" mono>{activoTxt}</Cell>
        </Grid>
      )}
    </ReclamoSection>
  )
}

function AdjuntosSection({ idReclamo }: { idReclamo: number }) {
  const adjuntos = useReclamoAdjuntos(idReclamo)
  const [lightbox, setLightbox] = useState<Adjunto | null>(null)

  return (
    <ReclamoSection title="Adjuntos">
      {adjuntos.isLoading && <div style={{ color: 'var(--fg-3)', fontSize: '0.82rem' }}>Cargando adjuntos...</div>}
      {adjuntos.isError && <div style={{ color: 'var(--color-error)', fontSize: '0.82rem' }}>Error al cargar adjuntos</div>}
      {adjuntos.data && adjuntos.data.length === 0 && (
        <div style={{ color: 'var(--fg-3)', fontSize: '0.82rem' }}>Sin adjuntos</div>
      )}
      {adjuntos.data && adjuntos.data.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 10 }}>
          {adjuntos.data.map((a) => (
            <button
              key={a.id_adjunto}
              onClick={() => setLightbox(a)}
              style={{
                position: 'relative', aspectRatio: '1 / 1', overflow: 'hidden',
                background: 'var(--surface-200)', border: '1px solid var(--border-primary)',
                borderRadius: 'var(--radius-md)', cursor: 'zoom-in', padding: 0,
              }}
              title={a.nombre_archivo}
            >
              <img
                src={a.url}
                alt={a.nombre_archivo}
                style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                loading="lazy"
              />
            </button>
          ))}
        </div>
      )}
      {lightbox && (
        <div
          onClick={() => setLightbox(null)}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 9999, cursor: 'zoom-out', padding: 40,
          }}
        >
          <img
            src={lightbox.url}
            alt={lightbox.nombre_archivo}
            style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
          />
        </div>
      )}
    </ReclamoSection>
  )
}

function SubreclamosSection({ items }: { items: Subreclamo[] }) {
  const navigate = useNavigate()
  return (
    <ReclamoSection title={`Subreclamos (${items.length})`}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {items.map((s) => (
          <button
            key={s.id_reclamo}
            onClick={() => navigate(`/reclamos/${s.id_reclamo}`)}
            style={{
              display: 'flex', alignItems: 'center', gap: 12,
              padding: '10px 14px', background: 'var(--surface-100)',
              border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-md)',
              cursor: 'pointer', textAlign: 'left', fontFamily: 'var(--font-display)',
              width: '100%',
            }}
          >
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--fg-3)' }}>
              {s.nro_reclamo || `#${s.id_reclamo}`}
            </span>
            <span style={{ flex: 1, fontSize: '0.85rem', color: 'var(--fg-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {s.descripcion}
            </span>
            <Badge kind="estado" value={s.estado} />
          </button>
        ))}
      </div>
    </ReclamoSection>
  )
}

function OTsSection({ items }: { items: OTAsociada[] }) {
  return (
    <ReclamoSection title={`Órdenes de trabajo (${items.length})`}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {items.map((ot) => (
          <div
            key={ot.id_ot}
            style={{
              display: 'flex', alignItems: 'center', gap: 12,
              padding: '10px 14px', background: 'var(--surface-100)',
              border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-md)',
            }}
          >
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--fg-2)' }}>
              {ot.nro_ot || `#${ot.id_ot}`}
            </span>
            {ot.es_auditoria && <span style={badgeAudit}>Auditoría</span>}
            <span style={{
              fontSize: '0.78rem', fontWeight: 600,
              padding: '2px 10px', borderRadius: 'var(--radius-pill)',
              background: ot.estado_color ? `${ot.estado_color}22` : 'rgba(38,37,30,.08)',
              color: ot.estado_color ?? 'var(--fg-2)',
              textTransform: 'uppercase', letterSpacing: '0.04em',
            }}>
              {ot.estado_nombre}
            </span>
            <span style={{ flex: 1, fontSize: '0.85rem', color: 'var(--fg-1)' }}>
              {ot.equipo_nombre
                ? `Equipo: ${ot.equipo_nombre}`
                : ot.agente_apellido
                  ? `${ot.agente_apellido}, ${ot.agente_nombre}`
                  : '—'}
            </span>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--fg-3)' }}>
              {formatFecha(ot.fecha_creacion)}
            </span>
          </div>
        ))}
      </div>
    </ReclamoSection>
  )
}

function HistorialSection({ items }: { items: HistorialItem[] }) {
  if (items.length === 0) {
    return (
      <ReclamoSection title="Historial">
        <div style={{ color: 'var(--fg-3)', fontSize: '0.82rem' }}>Sin historial registrado</div>
      </ReclamoSection>
    )
  }
  const ultimoIdx = items.length - 1
  return (
    <ReclamoSection title="Historial">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        {items.map((h, i) => (
          <div key={h.id_historial} style={{ display: 'flex', gap: 12, position: 'relative', paddingBottom: i === ultimoIdx ? 0 : 16 }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 14 }}>
              <span style={{
                width: 10, height: 10, borderRadius: '50%',
                background: i === ultimoIdx ? 'var(--zaris-orange)' : 'var(--border-medium)',
                marginTop: 4,
              }} />
              {i !== ultimoIdx && (
                <span style={{ flex: 1, width: 1, background: 'var(--border-primary)', marginTop: 4 }} />
              )}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--fg-1)' }}>
                {h.accion}
                {h.estado_anterior && h.estado_nuevo && h.estado_anterior !== h.estado_nuevo && (
                  <span style={{ fontWeight: 400, color: 'var(--fg-3)', marginLeft: 6, fontSize: '0.8rem' }}>
                    {h.estado_anterior} → {h.estado_nuevo}
                  </span>
                )}
              </div>
              <div style={{ fontSize: '0.76rem', color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                {formatFecha(h.fecha_alta)} · {h.usuario_nombre || 'Sistema'}
              </div>
              {h.nota && (
                <div style={{ fontSize: '0.82rem', color: 'var(--fg-2)', marginTop: 4, lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>
                  {h.nota}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </ReclamoSection>
  )
}

// ── Primitivos UI ──

function ReclamoSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{
      background: 'var(--surface-100)',
      border: '1px solid var(--border-primary)',
      borderRadius: 'var(--radius-xl)',
      boxShadow: 'var(--shadow-ambient)',
      padding: '18px 22px',
      display: 'flex', flexDirection: 'column', gap: 14,
    }}>
      <h3 style={{
        margin: 0, fontFamily: 'var(--font-display)',
        fontSize: 'var(--size-caption)', fontWeight: 700,
        textTransform: 'uppercase', letterSpacing: '0.07em',
        color: 'var(--fg-3)',
      }}>{title}</h3>
      {children}
    </section>
  )
}

function Grid({ cols, children }: { cols: string; children: React.ReactNode }) {
  return <div style={{ display: 'grid', gridTemplateColumns: cols, gap: 14 }}>{children}</div>
}

const cellLabel: React.CSSProperties = {
  fontSize: 'var(--size-caption)',
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  color: 'var(--fg-3)',
  marginTop: 8,
  marginBottom: 4,
}

function Cell({ label, mono, children }: { label: string; mono?: boolean; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
      <span style={cellLabel}>{label}</span>
      <span style={{
        color: 'var(--fg-1)',
        fontSize: '0.88rem',
        fontFamily: mono ? 'var(--font-mono)' : 'var(--font-display)',
        overflow: 'hidden', textOverflow: 'ellipsis',
      }}>
        {children}
      </span>
    </div>
  )
}

const badgeAudit: React.CSSProperties = {
  fontSize: 10, fontWeight: 600, padding: '2px 8px',
  borderRadius: 'var(--radius-pill)',
  background: 'rgba(96,165,200,.14)', color: '#3b82a8',
  textTransform: 'uppercase', letterSpacing: '0.04em',
}

const btnGhost: React.CSSProperties = {
  padding: '7px 14px', background: 'transparent', color: 'var(--fg-2)',
  border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)',
  fontFamily: 'var(--font-display)', fontSize: 'var(--size-btn)', cursor: 'pointer',
}
const btnPrimary: React.CSSProperties = {
  padding: '7px 14px', background: 'var(--zaris-dark)', color: 'var(--zaris-cream)',
  border: 'none', borderRadius: 'var(--radius-lg)', fontFamily: 'var(--font-display)',
  fontSize: 'var(--size-btn)', fontWeight: 500, cursor: 'pointer',
}
const btnDanger: React.CSSProperties = {
  padding: '7px 14px', background: 'var(--color-error)', color: '#fff',
  border: 'none', borderRadius: 'var(--radius-lg)', fontFamily: 'var(--font-display)',
  fontSize: 'var(--size-btn)', fontWeight: 500, cursor: 'pointer',
}

function formatFecha(iso: string): string {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleString('es-AR', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return iso
  }
}
