import { useState } from 'react'
import { Modal } from '../../agenda/components/Modal'
import { useReclamoAdjuntos, useReclamoDetalle } from '../../reclamos/hooks/useReclamos'
import type {
  Adjunto,
  HistorialItem,
  OTAsociada,
  Subreclamo,
} from '../../reclamos/types/reclamo'
import { BadgeEstadoOT, BadgeEstadoReclamo, BadgePrioridad } from '../lib/format'

interface Props {
  open: boolean
  idReclamo: number | null
  idOTResaltada?: number | null
  onClose: () => void
}

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

export function OTDetalleDrawer({ open, idReclamo, idOTResaltada, onClose }: Props) {
  const detalle = useReclamoDetalle(open ? idReclamo : null)

  const r = detalle.data

  const title = r
    ? `${r.nro_reclamo ?? `Reclamo #${r.id_reclamo}`} · ${r.tipo_nombre ?? '—'}`
    : 'Detalle del reclamo'

  return (
    <Modal open={open} onClose={onClose} title={title} width={920}>
      {detalle.isLoading && (
        <div style={{ color: 'var(--fg-3)', padding: 20 }}>Cargando reclamo…</div>
      )}
      {detalle.isError && (
        <div style={{ color: 'var(--color-error)', padding: 20 }}>
          Error: {(detalle.error as Error)?.message ?? 'desconocido'}
        </div>
      )}
      {r && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Section title="Estado">
            <Grid cols="repeat(4, 1fr)">
              <Cell label="Estado"><BadgeEstadoReclamo estado={r.estado} /></Cell>
              <Cell label="Prioridad"><BadgePrioridad prioridad={r.prioridad} /></Cell>
              <Cell label="Área">{r.area_nombre ?? '—'}</Cell>
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
          </Section>

          <Section title="Ciudadano">
            <Grid cols="repeat(4, 1fr)">
              <Cell label="Nombre">{r.ciudadano_apellido ?? '—'}, {r.ciudadano_nombre ?? '—'}</Cell>
              <Cell label="DNI / CUIL" mono>{r.doc_nro ?? '—'}{r.cuil ? ` · ${r.cuil}` : ''}</Cell>
              <Cell label="Teléfono" mono>{r.telefono ?? '—'}</Cell>
              <Cell label="Email">{r.ciudadano_email ?? '—'}</Cell>
            </Grid>
            {r.id_empresa != null && (
              <Grid cols="1fr">
                <Cell label="A nombre de empresa">
                  <strong>{r.empresa_nombre ?? `#${r.id_empresa}`}</strong>
                  {r.empresa_cuit && (
                    <span style={{ color: 'var(--fg-3)', marginLeft: 8, fontFamily: 'var(--font-mono)' }}>
                      CUIT {r.empresa_cuit}
                    </span>
                  )}
                </Cell>
              </Grid>
            )}
          </Section>

          <Section title="Descripción">
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
          </Section>

          <UbicacionSection r={r} />

          <AdjuntosSection idReclamo={r.id_reclamo} />

          {r.subreclamos.length > 0 && <SubreclamosSection items={r.subreclamos} />}

          {r.ordenes_trabajo.length > 0 && (
            <OTsSection items={r.ordenes_trabajo} idResaltada={idOTResaltada ?? null} />
          )}

          <HistorialSection items={r.historial} />
        </div>
      )}
    </Modal>
  )
}

// ── Sub-secciones ──

function UbicacionSection({ r }: { r: NonNullable<ReturnType<typeof useReclamoDetalle>['data']> }) {
  const direccion = r.direccion || r.domicilio_reclamo || ''
  const ubicacion = [r.localidad_nombre, r.partido_nombre, r.provincia_nombre].filter(Boolean).join(' · ')
  const tieneCoords = r.latitud != null && r.longitud != null
  const coordsTxt = tieneCoords ? `${(+r.latitud!).toFixed(6)}, ${(+r.longitud!).toFixed(6)}` : '—'
  const osmHref = tieneCoords
    ? `https://www.openstreetmap.org/?mlat=${r.latitud}&mlon=${r.longitud}#map=18/${r.latitud}/${r.longitud}`
    : null
  const activoTxt = r.id_activo
    ? `${r.activo_codigo ?? `#${r.id_activo}`}${r.activo_tipo_nombre ? ' · ' + r.activo_tipo_nombre : ''}`
    : null
  return (
    <Section title="Ubicación">
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
    </Section>
  )
}

function AdjuntosSection({ idReclamo }: { idReclamo: number }) {
  const adjuntos = useReclamoAdjuntos(idReclamo)
  const [lightbox, setLightbox] = useState<Adjunto | null>(null)

  return (
    <Section title="Adjuntos">
      {adjuntos.isLoading && (
        <div style={{ color: 'var(--fg-3)', fontSize: '0.82rem' }}>Cargando adjuntos…</div>
      )}
      {adjuntos.isError && (
        <div style={{ color: 'var(--color-error)', fontSize: '0.82rem' }}>Error al cargar adjuntos</div>
      )}
      {adjuntos.data && adjuntos.data.length === 0 && (
        <div style={{ color: 'var(--fg-3)', fontSize: '0.82rem' }}>Sin adjuntos</div>
      )}
      {adjuntos.data && adjuntos.data.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 10 }}>
          {adjuntos.data.map((a) => (
            <button
              key={a.id_adjunto}
              onClick={() => setLightbox(a)}
              title={a.nombre_archivo}
              style={{
                position: 'relative', aspectRatio: '1 / 1', overflow: 'hidden',
                background: 'var(--surface-200)', border: '1px solid var(--border-primary)',
                borderRadius: 'var(--radius-md)', padding: 0, cursor: 'zoom-in',
              }}
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
    </Section>
  )
}

function SubreclamosSection({ items }: { items: Subreclamo[] }) {
  return (
    <Section title={`Subreclamos (${items.length})`}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {items.map((s) => (
          <div
            key={s.id_reclamo}
            style={{
              display: 'flex', alignItems: 'center', gap: 12,
              padding: '10px 14px', background: 'var(--surface-100)',
              border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-md)',
            }}
          >
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--fg-3)' }}>
              {s.nro_reclamo ?? `#${s.id_reclamo}`}
            </span>
            <span style={{ flex: 1, fontSize: '0.85rem', color: 'var(--fg-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {s.descripcion}
            </span>
            <BadgeEstadoReclamo estado={s.estado} />
          </div>
        ))}
      </div>
    </Section>
  )
}

function OTsSection({ items, idResaltada }: { items: OTAsociada[]; idResaltada: number | null }) {
  return (
    <Section title={`Órdenes de trabajo (${items.length})`}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {items.map((ot) => {
          const isActual = ot.id_ot === idResaltada
          return (
            <div
              key={ot.id_ot}
              style={{
                display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
                padding: '10px 14px',
                background: isActual ? '#fff1ea' : 'var(--surface-100)',
                border: `1px solid ${isActual ? 'var(--zaris-orange)' : 'var(--border-primary)'}`,
                borderRadius: 'var(--radius-md)',
              }}
            >
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--fg-2)' }}>
                {ot.nro_ot ?? `#${ot.id_ot}`}
              </span>
              {isActual && <span style={badgeActual}>Esta OT</span>}
              {ot.es_auditoria && <span style={badgeAudit}>Auditoría</span>}
              <BadgeEstadoOT estado={ot.estado_nombre as never} />
              <span style={{ flex: 1, fontSize: '0.85rem', color: 'var(--fg-1)', minWidth: 120 }}>
                {ot.equipo_nombre
                  ? `Equipo: ${ot.equipo_nombre}`
                  : ot.agente_apellido
                    ? `${ot.agente_apellido}, ${ot.agente_nombre ?? ''}`.trim()
                    : '—'}
              </span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--fg-3)' }}>
                {formatFecha(ot.fecha_creacion)}
              </span>
              {ot.observaciones && (
                <div style={{ flexBasis: '100%', fontSize: '0.8rem', color: 'var(--fg-2)', whiteSpace: 'pre-wrap', borderTop: '1px dashed var(--border-primary)', paddingTop: 8, marginTop: 2 }}>
                  {ot.observaciones}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </Section>
  )
}

function HistorialSection({ items }: { items: HistorialItem[] }) {
  if (items.length === 0) {
    return (
      <Section title="Historial">
        <div style={{ color: 'var(--fg-3)', fontSize: '0.82rem' }}>Sin historial registrado</div>
      </Section>
    )
  }
  const ultimoIdx = items.length - 1
  return (
    <Section title="Historial">
      <div style={{ display: 'flex', flexDirection: 'column' }}>
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
                {formatFecha(h.fecha_alta)} · {h.usuario_nombre ?? 'Sistema'}
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
    </Section>
  )
}

// ── Primitivos UI ──

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{
      background: 'var(--surface-100)',
      border: '1px solid var(--border-primary)',
      borderRadius: 'var(--radius-lg)',
      padding: '14px 18px',
      display: 'flex', flexDirection: 'column', gap: 12,
    }}>
      <h3 style={{
        margin: 0, fontFamily: 'var(--font-display)',
        fontSize: '0.72rem', fontWeight: 700,
        textTransform: 'uppercase', letterSpacing: '0.07em',
        color: 'var(--fg-3)',
      }}>{title}</h3>
      {children}
    </section>
  )
}

function Grid({ cols, children }: { cols: string; children: React.ReactNode }) {
  return <div style={{ display: 'grid', gridTemplateColumns: cols, gap: 12 }}>{children}</div>
}

const cellLabel: React.CSSProperties = {
  fontSize: '0.7rem', fontWeight: 600,
  textTransform: 'uppercase', letterSpacing: '0.05em',
  color: 'var(--fg-3)', marginTop: 6, marginBottom: 2,
}

function Cell({ label, mono, children }: { label: string; mono?: boolean; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
      <span style={cellLabel}>{label}</span>
      <span style={{
        color: 'var(--fg-1)', fontSize: '0.88rem',
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
  borderRadius: 999,
  background: 'rgba(96,165,200,.14)', color: '#3b82a8',
  textTransform: 'uppercase', letterSpacing: '0.04em',
}

const badgeActual: React.CSSProperties = {
  fontSize: 10, fontWeight: 700, padding: '2px 8px',
  borderRadius: 999,
  background: 'var(--zaris-orange)', color: 'white',
  textTransform: 'uppercase', letterSpacing: '0.04em',
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
