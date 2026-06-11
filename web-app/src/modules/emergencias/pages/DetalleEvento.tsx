// Detalle del evento (plan 5.3): cabecera con tiempos, tabs Datos / Denunciante /
// Historial, panel lateral de acciones segun estado actual.
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Button, EmptyState, Skeleton } from '../../../ui'
import { Modal } from '../../agenda/components/Modal'
import { useNotificationsStore } from '../../../stores/notifications'
import {
  useAgregarNota,
  useCambiarEstado,
  useCerrarEvento,
  useDerivarEvento,
  useEventoDetalle,
  useEventoLog,
  useMarcarEnSitio,
  usePromoverABuc,
} from '../hooks/useEmergencias'
import type { ContactoEventual } from '../types'
import { CanalAppVecinoBadge, EstadoBadge, PrioridadPill, formatFechaHora, transcurridoDesde, useAhora } from '../lib/ui'
import { CambiarEstadoModal, CerrarModal, DerivarModal } from '../components/EventoAccionModals'

type TabId = 'datos' | 'denunciante' | 'historial'
type ModalId = 'estado' | 'derivar' | 'cerrar' | 'nota' | 'promover' | null

export function DetalleEvento() {
  const { id } = useParams()
  const idEvento = Number(id)
  const navigate = useNavigate()
  const push = useNotificationsStore((s) => s.push)
  const ahora = useAhora()

  const detalle = useEventoDetalle(Number.isFinite(idEvento) ? idEvento : null)
  const log = useEventoLog(Number.isFinite(idEvento) ? idEvento : null)

  const [tab, setTab] = useState<TabId>('datos')
  const [modal, setModal] = useState<ModalId>(null)
  const [destinoEstado, setDestinoEstado] = useState('')
  const [nota, setNota] = useState('')
  const [prom, setProm] = useState({ apellido: '', nombre: '', email: '' })

  const cambiar = useCambiarEstado()
  const derivar = useDerivarEvento()
  const cerrar = useCerrarEvento()
  const enSitio = useMarcarEnSitio()
  const agregarNota = useAgregarNota()
  const promover = usePromoverABuc()
  const busy = cambiar.isPending || derivar.isPending || cerrar.isPending || enSitio.isPending || agregarNota.isPending || promover.isPending

  if (detalle.isLoading) return <Skeleton height={300} />
  if (detalle.isError || !detalle.data) {
    return <EmptyState title="Evento no encontrado" description={String(detalle.error ?? '')} action={<Button onClick={() => navigate('/emergencias')}>Volver al tablero</Button>} />
  }
  const ev = detalle.data
  const estado = ev.estado_codigo

  const onError = (e: unknown) =>
    push({ kind: 'error', title: 'No se pudo aplicar la acción', body: e instanceof Error ? e.message : String(e) })
  const ok = (titulo: string) => () => {
    push({ kind: 'success', title: titulo, body: ev.numero_operativo })
    setModal(null)
  }

  const abrirEstado = (destino: string) => { setDestinoEstado(destino); setModal('estado') }

  const contactoEventual = !ev.denunciante_anonimo && ev.id_contacto_eventual && ev.denunciante
    ? (ev.denunciante as ContactoEventual)
    : null

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 280px', gap: 16, alignItems: 'start' }}>
      <div>
        {/* cabecera */}
        <div style={cabecera}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <PrioridadPill codigo={ev.prioridad_codigo} colorToken={ev.prioridad_color_token} />
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 18, fontWeight: 700, color: 'var(--fg-1)' }}>
              {ev.numero_operativo}
            </span>
            <EstadoBadge codigo={ev.estado_codigo} nombre={ev.estado_nombre} />
            <CanalAppVecinoBadge canalCodigo={ev.canal_codigo} />
            <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>
              hace {transcurridoDesde(ev.fecha_hora_recepcion, ahora)}
            </span>
          </div>
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 15, color: 'var(--fg-1)', marginTop: 6 }}>
            {ev.tipo_nombre}{ev.subtipo_nombre ? ` · ${ev.subtipo_nombre}` : ''} — {ev.subarea_nombre}
          </div>
          <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', marginTop: 10 }}>
            <Tiempo label="Recepción" valor={ev.fecha_hora_recepcion} />
            <Tiempo label="Despacho" valor={ev.fecha_hora_despacho} />
            <Tiempo label="Arribo (EN SITIO)" valor={ev.fecha_hora_arribo} />
            <Tiempo label="Cierre" valor={ev.fecha_hora_cierre} />
            <div>
              <div style={tLabel}>SLA arribo</div>
              <div style={tValor}>{ev.sla_minutos_arribo} min</div>
            </div>
          </div>
        </div>

        {/* tabs */}
        <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--border-primary)', marginTop: 16 }}>
          <TabBtn label="Datos del evento" active={tab === 'datos'} onClick={() => setTab('datos')} />
          <TabBtn label="Denunciante" active={tab === 'denunciante'} onClick={() => setTab('denunciante')} />
          <TabBtn label="Historial" active={tab === 'historial'} onClick={() => setTab('historial')} />
        </div>

        <div style={{ paddingTop: 14 }}>
          {tab === 'datos' && (
            <div style={panel}>
              <Dato label="Dirección" valor={ev.direccion_evento} />
              <Dato label="Referencia" valor={ev.referencia_ubicacion} />
              <Dato label="Canal de ingreso" valor={ev.canal_codigo === 'APP_VECINO' ? 'App Vecinos' : 'Llamada telefónica'} />
              <Dato label="Organismo de derivación" valor={ev.organismo_nombre} />
              <Dato label="Observaciones de recepción" valor={ev.observaciones_recepcion} ancho />
              <Dato label="Observaciones de cierre" valor={ev.observaciones_cierre} ancho />
              <Dato label="Veracidad" valor={ev.veracidad?.replace(/_/g, ' ')} />
              <Dato label="Lat / Lon" valor={ev.latitud != null ? `${ev.latitud}, ${ev.longitud}` : null} />
            </div>
          )}

          {tab === 'denunciante' && (
            <div style={panel}>
              {ev.denunciante_anonimo && <Dato label="Denunciante" valor="Anónimo" ancho />}
              {!ev.denunciante_anonimo && ev.denunciante && 'id_ciudadano' in ev.denunciante && (
                <>
                  <Dato label="Ciudadano BUC" valor={`${ev.denunciante.apellido}, ${ev.denunciante.nombre}`} />
                  <Dato label="DNI" valor={ev.denunciante.doc_nro} />
                  <Dato label="CUIL" valor={ev.denunciante.cuil} />
                  <Dato label="Teléfono" valor={ev.denunciante.telefono} />
                  <Dato label="Email" valor={ev.denunciante.email} />
                  <Dato label="Domicilio" valor={[ev.denunciante.calle, ev.denunciante.altura, ev.denunciante.localidad].filter(Boolean).join(' ')} ancho />
                </>
              )}
              {contactoEventual && (
                <>
                  <Dato label="Contacto eventual" valor={contactoEventual.nombre_apellido} />
                  <Dato label="DNI" valor={contactoEventual.dni} />
                  <Dato label="Teléfono" valor={contactoEventual.telefono} />
                  <Dato label="Dirección" valor={contactoEventual.direccion} ancho />
                  <Dato label="Contacto alternativo" valor={contactoEventual.contacto_alt_nombre ? `${contactoEventual.contacto_alt_nombre} (${contactoEventual.contacto_alt_telefono ?? 's/tel'})` : null} ancho />
                  <div style={{ gridColumn: '1 / -1' }}>
                    <Button variant="accent" onClick={() => setModal('promover')}>Promover a ciudadano BUC</Button>
                  </div>
                </>
              )}
            </div>
          )}

          {tab === 'historial' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {(log.data ?? []).map((l) => (
                <div key={l.id_emergencia_log} style={logItem}>
                  <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--fg-3)' }}>
                      {formatFechaHora(l.fecha_hora)}
                    </span>
                    <span style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 12, color: 'var(--zaris-orange)', letterSpacing: '0.04em' }}>
                      {l.tipo_accion.replace(/_/g, ' ')}
                    </span>
                    {l.estado_anterior && l.estado_nuevo && l.estado_anterior !== l.estado_nuevo && (
                      <span style={{ fontSize: 12, color: 'var(--fg-2)' }}>
                        {l.estado_anterior} → {l.estado_nuevo}
                      </span>
                    )}
                    <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--fg-3)' }}>
                      {l.usuario_nombre ?? 'sistema'}
                    </span>
                  </div>
                  {l.observaciones && <div style={{ fontSize: 13, color: 'var(--fg-1)', marginTop: 4 }}>{l.observaciones}</div>}
                </div>
              ))}
              {(log.data ?? []).length === 0 && <EmptyState title="Sin entradas" description="El historial está vacío." />}
            </div>
          )}
        </div>
      </div>

      {/* panel lateral de acciones (plan 5.3) */}
      <aside style={lateral}>
        <div style={{ ...bloqueTitulo, marginBottom: 10 }}>Acciones</div>
        {ev.es_terminal ? (
          <div style={{ fontSize: 13, color: 'var(--fg-3)' }}>
            Evento cerrado ({ev.estado_nombre}). Solo lectura.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {estado === 'PENDIENTE' && <Button onClick={() => abrirEstado('EN_PREPARACION')}>Pasar a EN PREPARACIÓN</Button>}
            {estado === 'EN_PREPARACION' && <Button onClick={() => abrirEstado('EN_CAMINO')}>Despachar (EN CAMINO)</Button>}
            {(estado === 'EN_CAMINO' || estado === 'DERIVADO') && (
              <Button disabled={busy} onClick={() => enSitio.mutate(idEvento, { onSuccess: ok('Arribo registrado'), onError })}>
                Marcar EN SITIO
              </Button>
            )}
            {estado !== 'DERIVADO' && <Button onClick={() => setModal('derivar')}>Derivar a organismo</Button>}
            {(estado === 'EN_SITIO' || estado === 'DERIVADO') && (
              <Button variant="accent" onClick={() => setModal('cerrar')}>Cerrar (RESUELTO)</Button>
            )}
            {(estado === 'PENDIENTE' || estado === 'EN_PREPARACION') && (
              <Button onClick={() => setModal('cerrar')}>Desestimar</Button>
            )}
            <Button variant="ghost" onClick={() => setModal('nota')}>Agregar nota</Button>
          </div>
        )}
        {ev.es_terminal && (
          <div style={{ marginTop: 10 }}>
            <Button variant="ghost" onClick={() => setModal('nota')}>Agregar nota</Button>
          </div>
        )}
      </aside>

      {/* modales */}
      <CambiarEstadoModal
        open={modal === 'estado'}
        destino={destinoEstado}
        titulo={`${ev.numero_operativo} → ${destinoEstado.replace(/_/g, ' ')}`}
        busy={busy}
        onConfirm={(obs) => cambiar.mutate({ id: idEvento, nuevo_estado: destinoEstado, observaciones: obs }, { onSuccess: ok('Estado actualizado'), onError })}
        onCancel={() => setModal(null)}
      />
      <DerivarModal
        open={modal === 'derivar'}
        busy={busy}
        onConfirm={(idOrg, obs) => derivar.mutate({ id: idEvento, id_organismo: idOrg, observaciones: obs }, { onSuccess: ok('Evento derivado'), onError })}
        onCancel={() => setModal(null)}
      />
      <CerrarModal
        open={modal === 'cerrar'}
        busy={busy}
        permiteResuelto={['EN_SITIO', 'DERIVADO'].includes(estado)}
        permiteDesestimado={['PENDIENTE', 'EN_PREPARACION'].includes(estado)}
        onConfirm={(body) => cerrar.mutate({ id: idEvento, ...body }, { onSuccess: ok('Evento cerrado'), onError })}
        onCancel={() => setModal(null)}
      />
      <Modal
        open={modal === 'nota'}
        onClose={() => setModal(null)}
        title="Agregar nota al historial"
        width={460}
        footer={
          <>
            <Button variant="ghost" onClick={() => setModal(null)}>Cancelar</Button>
            <Button variant="accent" disabled={busy || !nota.trim()} onClick={() =>
              agregarNota.mutate({ id: idEvento, observaciones: nota.trim() }, { onSuccess: () => { ok('Nota agregada')(); setNota('') }, onError })
            }>Guardar nota</Button>
          </>
        }
      >
        <textarea
          style={{ width: '100%', boxSizing: 'border-box', minHeight: 90, resize: 'vertical', padding: '8px 10px', border: '1px solid var(--border-medium)', borderRadius: 8, background: 'var(--surface-100)', color: 'var(--fg-1)', fontFamily: 'var(--font-display)', fontSize: 14 }}
          value={nota}
          onChange={(e) => setNota(e.target.value)}
          placeholder="Nota para el historial (no cambia el estado)..."
        />
      </Modal>
      <Modal
        open={modal === 'promover'}
        onClose={() => setModal(null)}
        title="Promover contacto eventual a BUC"
        width={460}
        footer={
          <>
            <Button variant="ghost" onClick={() => setModal(null)}>Cancelar</Button>
            <Button
              variant="accent"
              disabled={busy || !prom.apellido.trim() || !prom.nombre.trim() || !prom.email.trim()}
              onClick={() =>
                promover.mutate(
                  { id: ev.id_contacto_eventual as number, apellido: prom.apellido.trim(), nombre: prom.nombre.trim(), email: prom.email.trim() },
                  {
                    onSuccess: (r) => {
                      push({ kind: 'success', title: r.ciudadano_creado ? 'Ciudadano creado en la BUC' : 'Contacto vinculado a la BUC', body: `${r.eventos_reasignados} evento(s) reasignado(s)` })
                      setModal(null)
                    },
                    onError,
                  },
                )
              }
            >
              Promover
            </Button>
          </>
        }
      >
        <p style={{ margin: '0 0 10px', fontSize: 13, color: 'var(--fg-2)', lineHeight: 1.5 }}>
          Si ya existe un ciudadano con el mismo DNI se vincula automáticamente; si no, se crea uno nuevo en la BUC con estos datos. Todos los eventos del contacto pasan a apuntar al ciudadano.
        </p>
        <CampoModal label="Apellido *" value={prom.apellido} onChange={(v) => setProm({ ...prom, apellido: v })} />
        <CampoModal label="Nombre *" value={prom.nombre} onChange={(v) => setProm({ ...prom, nombre: v })} />
        <CampoModal label="Email *" value={prom.email} onChange={(v) => setProm({ ...prom, email: v })} />
      </Modal>
    </div>
  )
}

function CampoModal({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <label style={{ display: 'block', fontFamily: 'var(--font-display)', fontSize: 12, fontWeight: 600, color: 'var(--fg-2)', marginBottom: 4 }}>{label}</label>
      <input
        style={{ width: '100%', boxSizing: 'border-box', padding: '8px 10px', border: '1px solid var(--border-medium)', borderRadius: 8, background: 'var(--surface-100)', color: 'var(--fg-1)', fontFamily: 'var(--font-display)', fontSize: 14 }}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  )
}

function TabBtn({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} style={{
      fontFamily: 'var(--font-display)', fontSize: '0.85rem', cursor: 'pointer',
      background: 'transparent', border: 'none', padding: '8px 14px', marginBottom: -1,
      borderBottom: active ? '2px solid var(--zaris-orange)' : '2px solid transparent',
      color: active ? 'var(--fg-1)' : 'var(--fg-3)', fontWeight: active ? 600 : 400,
    }}>{label}</button>
  )
}

function Tiempo({ label, valor }: { label: string; valor?: string | null }) {
  return (
    <div>
      <div style={tLabel}>{label}</div>
      <div style={{ ...tValor, color: valor ? 'var(--fg-1)' : 'var(--fg-3)' }}>{formatFechaHora(valor)}</div>
    </div>
  )
}

function Dato({ label, valor, ancho }: { label: string; valor?: string | null; ancho?: boolean }) {
  return (
    <div style={{ gridColumn: ancho ? '1 / -1' : undefined }}>
      <div style={tLabel}>{label}</div>
      <div style={{ fontSize: 14, color: valor ? 'var(--fg-1)' : 'var(--fg-3)' }}>{valor || '—'}</div>
    </div>
  )
}

const cabecera: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 12, padding: '14px 18px',
}
const panel: React.CSSProperties = {
  display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12,
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 12, padding: '14px 18px',
}
const lateral: React.CSSProperties = {
  background: 'var(--surface-300)', border: '1px solid var(--border-primary)',
  borderRadius: 12, padding: '14px 16px', position: 'sticky', top: 8,
}
const bloqueTitulo: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: 13, fontWeight: 700,
  textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--fg-2)',
}
const logItem: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 10, padding: '8px 12px',
}
const tLabel: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: 11, fontWeight: 600,
  textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--fg-3)',
}
const tValor: React.CSSProperties = { fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--fg-1)' }
