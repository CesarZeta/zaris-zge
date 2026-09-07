/**
 * Panel de la GUARDIA (mig 106, F4 plan ATENCION) — la mesa de la ubicación
 * Guardia no trabaja con turnos: recibe las DERIVACIONES del COM (Emergencias)
 * y las cierra como atendidas (intervención obligatoria + recomendaciones) o
 * ausentes (el vecino no llegó). Decisión de César: sin turno de por medio.
 *
 * Refresca solo cada 30 s (las derivaciones las crea otro puesto). Las
 * pendientes se listan siempre, de cualquier día; las cerradas, las del día
 * de la mesa.
 */
import { useEffect, useState } from 'react'
import { Check, RefreshCw, Siren, UserX } from 'lucide-react'
import { useAtencionesGuardia, useAtenderGuardia, useAusenteGuardia } from '../hooks/useTurnos'
import { Modal } from '../../agenda/components/Modal'
import { CiudadanoSearch } from '../../agenda/components/CiudadanoSearch'
import { useNotificationsStore } from '../../../stores/notifications'
import type { CiudadanoMinimo } from '../../agenda/types/agenda'
import type { GuardiaAtencion, GuardiaAtenderBody } from '../types/turno'

const ESTADO_CHIP: Record<GuardiaAtencion['estado'], { bg: string; color: string; label: string }> = {
  pendiente: { bg: 'rgba(198,40,40,0.14)', color: '#c62828', label: 'Esperando' },
  atendida: { bg: 'rgba(31,138,101,0.16)', color: '#1f8a65', label: 'Atendida' },
  ausente: { bg: 'var(--surface-400)', color: 'var(--fg-3)', label: 'No se presentó' },
}

function haceCuanto(iso: string): string {
  const min = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000))
  if (min < 1) return 'recién'
  if (min < 60) return `hace ${min} min`
  const h = Math.floor(min / 60)
  return h < 24 ? `hace ${h} h ${min % 60} min` : `hace ${Math.floor(h / 24)} d`
}

function hora(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

export function PanelGuardia({ fecha, onCambio }: { fecha: string; onCambio?: () => void }) {
  const push = useNotificationsStore((s) => s.push)
  const { data, isLoading, isError, error, refetch, isFetching } = useAtencionesGuardia(fecha)
  const atender = useAtenderGuardia()
  const ausente = useAusenteGuardia()
  const [aAtender, setAAtender] = useState<GuardiaAtencion | null>(null)
  // Re-render por minuto para que "hace N min" no quede congelado.
  const [, setTick] = useState(0)
  useEffect(() => { const id = window.setInterval(() => setTick((t) => t + 1), 60000); return () => window.clearInterval(id) }, [])

  const pendientes = (data ?? []).filter((a) => a.estado === 'pendiente')
  const cerradas = (data ?? []).filter((a) => a.estado !== 'pendiente')

  async function accion(fn: () => Promise<unknown>, ok: string) {
    try {
      await fn()
      push({ kind: 'success', title: ok })
      onCambio?.()
    } catch (e) {
      push({ kind: 'error', title: 'No se pudo completar la acción', body: e instanceof Error ? e.message : undefined })
    }
  }

  return (
    <div style={card}>
      <div style={cabecera}>
        <div>
          <h2 style={titulo}><Siren size={16} strokeWidth={1.5} style={{ color: '#c62828', verticalAlign: '-3px' }} /> Guardia · derivaciones del COM</h2>
          <p style={sub}>
            Cada fila es un vecino que Emergencias mandó a la Guardia. Registrá la atención al verlo, o marcá que no se presentó.
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginLeft: 'auto' }}>
          <span style={{ ...chipBase, background: pendientes.length > 0 ? ESTADO_CHIP.pendiente.bg : 'var(--surface-400)', color: pendientes.length > 0 ? ESTADO_CHIP.pendiente.color : 'var(--fg-3)' }}>
            {pendientes.length} esperando
          </span>
          <button onClick={() => refetch()} style={btnGhost} title="Refrescar (se refresca solo cada 30 s)">
            <RefreshCw size={14} strokeWidth={1.5} style={{ animation: isFetching ? 'spin 1s linear infinite' : undefined }} />
          </button>
        </div>
      </div>

      {isError && <div style={errorBanner}>{(error as Error)?.message ?? 'Error al cargar la Guardia'}</div>}

      {isLoading ? (
        <p style={vacio}>Cargando derivaciones…</p>
      ) : pendientes.length === 0 ? (
        <p style={vacio}>No hay derivaciones esperando. Las nuevas aparecen solas cuando el COM deriva.</p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={tabla}>
            <thead>
              <tr>
                <th style={{ ...th, width: 130 }}>Evento</th>
                <th style={th}>Paciente</th>
                <th style={th}>Motivo</th>
                <th style={{ ...th, width: 150 }}>Derivado</th>
                <th style={{ ...th, width: 230, textAlign: 'right' }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {pendientes.map((a) => (
                <tr key={a.id_emergencia_atencion} style={{ borderBottom: '1px solid var(--border-primary)' }}>
                  <td style={td}>
                    <div style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{a.numero_operativo}</div>
                    <div style={meta}>{a.tipo_nombre}{a.subtipo_nombre ? ` · ${a.subtipo_nombre}` : ''}</div>
                    {a.direccion_evento && <div style={meta}>{a.direccion_evento}</div>}
                  </td>
                  <td style={td}>
                    {a.paciente_nombre ?? <span style={{ color: 'var(--fg-3)' }}>Sin identificar</span>}
                    {a.ciudadano_dni && <div style={meta}>DNI {a.ciudadano_dni}</div>}
                  </td>
                  <td style={{ ...td, color: 'var(--fg-2)', maxWidth: 320, whiteSpace: 'pre-wrap' }}>{a.motivo_derivacion}</td>
                  <td style={td}>
                    <div>{haceCuanto(a.derivado_en)}</div>
                    <div style={meta}>{hora(a.derivado_en)}{a.derivado_por ? ` · ${a.derivado_por}` : ''}</div>
                  </td>
                  <td style={{ ...td, textAlign: 'right', whiteSpace: 'nowrap' }}>
                    <button onClick={() => setAAtender(a)} style={btnAccion} title="Registrar la atención">
                      <Check size={13} strokeWidth={1.5} /> Atender
                    </button>
                    <button
                      onClick={() => accion(() => ausente.mutateAsync({ id_atencion: a.id_emergencia_atencion }), 'Marcado como no presentado')}
                      style={btnSec}
                      title="El vecino no llegó a la Guardia"
                    >
                      <UserX size={13} strokeWidth={1.5} /> No se presentó
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {cerradas.length > 0 && (
        <details style={{ marginTop: 4 }}>
          <summary style={resumen}>Cerradas en el día ({cerradas.length})</summary>
          <table style={{ ...tabla, marginTop: 8 }}>
            <thead>
              <tr>
                <th style={{ ...th, width: 64 }}>Hora</th>
                <th style={{ ...th, width: 130 }}>Evento</th>
                <th style={th}>Paciente</th>
                <th style={{ ...th, width: 120 }}>Resultado</th>
                <th style={th}>Atendió</th>
                <th style={th}>Intervención</th>
              </tr>
            </thead>
            <tbody>
              {cerradas.map((a) => {
                const chip = ESTADO_CHIP[a.estado]
                return (
                  <tr key={a.id_emergencia_atencion} style={{ borderBottom: '1px solid var(--border-primary)' }}>
                    <td style={{ ...td, fontFamily: 'var(--font-mono)' }}>{hora(a.atendido_en ?? a.fecha_modificacion)}</td>
                    <td style={{ ...td, fontFamily: 'var(--font-mono)' }}>{a.numero_operativo}</td>
                    <td style={td}>{a.paciente_nombre ?? '—'}</td>
                    <td style={td}><span style={{ ...chipBase, background: chip.bg, color: chip.color }}>{chip.label}</span></td>
                    <td style={{ ...td, color: 'var(--fg-2)' }}>{a.agente_atiende_nombre ?? '—'}</td>
                    <td style={{ ...td, color: 'var(--fg-2)', maxWidth: 360, whiteSpace: 'pre-wrap' }}>
                      {a.intervencion ?? '—'}
                      {a.recomendaciones && <div style={meta}>Recomendaciones: {a.recomendaciones}</div>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </details>
      )}

      <AtenderGuardiaModal
        atencion={aAtender}
        busy={atender.isPending}
        onCancel={() => setAAtender(null)}
        onConfirm={(body) => {
          const id = aAtender?.id_emergencia_atencion
          setAAtender(null)
          if (id != null) accion(() => atender.mutateAsync({ id_atencion: id, ...body }), 'Atención registrada')
        }}
      />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

/** Cierra la derivación como atendida. Intervención obligatoria (registro
 *  clínico mínimo, mismo criterio que la historia de atención de turnos). Si
 *  la derivación llegó sin ciudadano BUC, permite vincularlo acá. Cierra AL
 *  CONFIRMAR (§23); el resultado llega por toast. */
function AtenderGuardiaModal({ atencion, busy, onConfirm, onCancel }: {
  atencion: GuardiaAtencion | null
  busy?: boolean
  onConfirm: (body: GuardiaAtenderBody) => void
  onCancel: () => void
}) {
  const open = atencion != null
  const [intervencion, setIntervencion] = useState('')
  const [recomendaciones, setRecomendaciones] = useState('')
  const [ciudadano, setCiudadano] = useState<CiudadanoMinimo | null>(null)
  const [pacienteNombre, setPacienteNombre] = useState('')
  useEffect(() => {
    if (open) { setIntervencion(''); setRecomendaciones(''); setCiudadano(null); setPacienteNombre('') }
  }, [open, atencion?.id_emergencia_atencion])

  return (
    <Modal
      open={open}
      onClose={onCancel}
      title={atencion ? `Atención en la Guardia · ${atencion.numero_operativo}` : 'Atención en la Guardia'}
      width={560}
      footer={
        <>
          <button type="button" onClick={onCancel} style={btnSec}>Cancelar</button>
          <button
            type="button"
            disabled={busy || !intervencion.trim()}
            onClick={() => onConfirm({
              intervencion: intervencion.trim(),
              recomendaciones: recomendaciones.trim() || null,
              id_ciudadano: ciudadano?.id_ciudadano ?? null,
              paciente_nombre: pacienteNombre.trim() || null,
            })}
            style={{ ...btnAccion, opacity: busy || !intervencion.trim() ? 0.6 : 1 }}
          >
            <Check size={13} strokeWidth={1.5} /> Registrar atención
          </button>
        </>
      }
    >
      {atencion && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ fontSize: 13, color: 'var(--fg-2)', lineHeight: 1.5 }}>
            <b>{atencion.tipo_nombre}</b>{atencion.subtipo_nombre ? ` · ${atencion.subtipo_nombre}` : ''}
            {atencion.direccion_evento ? ` — ${atencion.direccion_evento}` : ''}
            <div style={{ marginTop: 4 }}>Motivo del COM: {atencion.motivo_derivacion}</div>
          </div>

          <label style={lbl}>Paciente</label>
          {atencion.id_ciudadano ? (
            <div style={{ fontSize: 14 }}>{atencion.paciente_nombre}{atencion.ciudadano_dni ? ` · DNI ${atencion.ciudadano_dni}` : ''}</div>
          ) : ciudadano ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 14 }}>
              <span>{ciudadano.apellido}, {ciudadano.nombre}</span>
              <button type="button" onClick={() => setCiudadano(null)} style={linkBtn}>Cambiar</button>
            </div>
          ) : (
            <>
              <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>
                {atencion.paciente_nombre ? `El COM lo registró como "${atencion.paciente_nombre}". ` : ''}
                Buscalo en la BUC para vincular la atención a su historia (opcional).
              </div>
              <CiudadanoSearch onSelect={setCiudadano} placeholder="DNI, apellido o teléfono…" permitirNuevo={false} />
              {!atencion.paciente_nombre && (
                <input
                  value={pacienteNombre}
                  onChange={(e) => setPacienteNombre(e.target.value.slice(0, 150))}
                  placeholder="Si no está en la BUC: nombre del paciente"
                  style={inp}
                />
              )}
            </>
          )}

          <label style={lbl}>Intervención *</label>
          <textarea
            value={intervencion}
            onChange={(e) => setIntervencion(e.target.value)}
            placeholder="Qué se hizo (evaluación, procedimiento, medicación)…"
            style={{ ...inp, minHeight: 90, resize: 'vertical' }}
          />
          <label style={lbl}>Recomendaciones</label>
          <textarea
            value={recomendaciones}
            onChange={(e) => setRecomendaciones(e.target.value)}
            placeholder="Indicaciones al paciente, controles, derivación posterior…"
            style={{ ...inp, minHeight: 60, resize: 'vertical' }}
          />
        </div>
      )}
    </Modal>
  )
}

const card: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 10, padding: 16, display: 'flex', flexDirection: 'column', gap: 12,
}
const cabecera: React.CSSProperties = { display: 'flex', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }
const titulo: React.CSSProperties = { margin: 0, fontSize: '1rem', fontWeight: 700, fontFamily: 'var(--font-display)' }
const sub: React.CSSProperties = { margin: '2px 0 0', fontSize: '0.82rem', color: 'var(--fg-3)' }
const tabla: React.CSSProperties = { width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem' }
const th: React.CSSProperties = {
  textAlign: 'left', padding: '6px 8px', fontSize: '0.72rem', textTransform: 'uppercase',
  letterSpacing: '0.04em', color: 'var(--fg-3)', borderBottom: '1px solid var(--border-medium)',
}
const td: React.CSSProperties = { padding: '8px', color: 'var(--fg-1)', verticalAlign: 'top' }
const meta: React.CSSProperties = { fontSize: '0.74rem', color: 'var(--fg-3)', marginTop: 2 }
const chipBase: React.CSSProperties = {
  display: 'inline-block', padding: '2px 8px', borderRadius: 999, fontSize: '0.74rem', fontWeight: 600,
}
const resumen: React.CSSProperties = {
  cursor: 'pointer', fontSize: '0.82rem', fontWeight: 600, color: 'var(--fg-2)',
  fontFamily: 'var(--font-display)',
}
const btnBase: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 4, padding: '5px 10px',
  fontSize: '0.8rem', fontFamily: 'inherit', fontWeight: 600, borderRadius: 6, cursor: 'pointer', marginLeft: 6,
}
const btnAccion: React.CSSProperties = {
  ...btnBase, background: 'var(--zaris-orange)', color: '#fff', border: '1px solid var(--zaris-orange)',
}
const btnSec: React.CSSProperties = {
  ...btnBase, background: 'var(--surface-100)', color: 'var(--fg-1)', border: '1px solid var(--border-medium)',
}
const btnGhost: React.CSSProperties = {
  ...btnBase, marginLeft: 0, background: 'var(--surface-300)', color: 'var(--fg-1)', border: '1px solid var(--border-medium)',
}
const linkBtn: React.CSSProperties = {
  background: 'none', border: 'none', color: 'var(--zaris-orange)', cursor: 'pointer',
  fontFamily: 'inherit', fontSize: 12, fontWeight: 600, padding: 0,
}
const lbl: React.CSSProperties = {
  fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--fg-3)',
  fontFamily: 'var(--font-display)',
}
const inp: React.CSSProperties = {
  width: '100%', boxSizing: 'border-box', fontFamily: 'var(--font-display)', fontSize: 14, padding: '8px 10px',
  border: '1px solid var(--border-medium)', borderRadius: 8, background: 'var(--surface-100)', color: 'var(--fg-1)',
}
const vacio: React.CSSProperties = { padding: '18px 8px', textAlign: 'center', color: 'var(--fg-3)', fontSize: '0.88rem', margin: 0 }
const errorBanner: React.CSSProperties = {
  background: '#ffebee', border: '1px solid #ffcdd2', borderLeft: '4px solid var(--color-error)',
  borderRadius: 8, padding: '12px 16px', color: '#c62828', fontSize: '0.86rem',
}
