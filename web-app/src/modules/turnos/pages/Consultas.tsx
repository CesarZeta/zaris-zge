import { useMemo, useState } from 'react'
import { Download, X } from 'lucide-react'
import { useTurnos, useAtencionesCiudadano } from '../hooks/useTurnos'
import { CiudadanoSearch } from '../../agenda/components/CiudadanoSearch'
import { TurnoDetalleModal } from '../components/TurnoDetalleModal'
import { AtencionItem } from '../components/HistorialAtenciones'
import { useNotificationsStore } from '../../../stores/notifications'
import { exportarTurnosPdf, type TurnoPdfRow } from '../lib/exportPdf'
import type { CiudadanoMinimo } from '../../agenda/types/agenda'
import type { EstadoTurno, Turno } from '../types/turno'

const ESTADO_COLOR: Record<EstadoTurno, { bg: string; fg: string }> = {
  reservado: { bg: 'rgba(245,127,23,0.14)', fg: '#b35900' },
  llamado: { bg: 'rgba(245,78,0,0.16)', fg: '#f54e00' },
  cumplido: { bg: 'rgba(31,138,101,0.16)', fg: '#1f8a65' },
  ausente: { bg: 'rgba(198,40,40,0.14)', fg: '#c62828' },
  cancelado: { bg: 'rgba(198,40,40,0.12)', fg: '#c62828' },
}

type Solapa = 'turnos' | 'realizadas'

/**
 * Consulta por ciudadano: todos sus turnos (cualquier estado) y las
 * prestaciones realizadas (turnos cumplidos + su atención registrada, mig 86).
 * El alcance lo limita el backend con el scope por nivel de turnos (§33).
 */
export function Consultas() {
  const push = useNotificationsStore((s) => s.push)
  const [ciudadano, setCiudadano] = useState<CiudadanoMinimo | null>(null)
  const [solapa, setSolapa] = useState<Solapa>('turnos')
  const [detalle, setDetalle] = useState<Turno | null>(null)

  const turnosQ = useTurnos(
    { id_ciudadano: ciudadano?.id_ciudadano ?? -1 },
    { enabled: ciudadano != null },
  )
  const turnos = useMemo(
    () => (ciudadano ? (turnosQ.data ?? []) : []),
    [ciudadano, turnosQ.data],
  )
  const realizados = useMemo(() => turnos.filter((t) => t.estado === 'cumplido'), [turnos])
  const atenciones = useAtencionesCiudadano(ciudadano?.id_ciudadano ?? null)

  const nombreCiudadano = ciudadano
    ? `${ciudadano.apellido ?? ''}${ciudadano.apellido && ciudadano.nombre ? ', ' : ''}${ciudadano.nombre ?? ''}`
    : ''

  function doExport() {
    const fuente = solapa === 'turnos' ? turnos : realizados
    if (!ciudadano || fuente.length === 0) {
      push({ kind: 'error', title: 'No hay datos para exportar' })
      return
    }
    const rows: TurnoPdfRow[] = fuente.map((t) => {
      const at = (atenciones.data ?? []).find((a) => a.id_turno === t.id_turno)
      return {
        fecha: t.fecha,
        hora: `${t.hora_inicio.slice(0, 5)}-${t.hora_fin.slice(0, 5)}`,
        ciudadano: t.ciudadano_nombre ?? '',
        dni: t.ciudadano_dni ?? '',
        atiende: t.recurso_nombre ?? t.agente_nombre ?? '',
        prestacion: t.prestacion_nombre ?? '',
        estado: t.estado,
        observaciones: solapa === 'realizadas'
          ? (at ? `${at.intervencion}${at.recomendaciones ? ` | Recomendaciones: ${at.recomendaciones}` : ''}` : (t.observaciones ?? ''))
          : (t.observaciones ?? ''),
      }
    })
    exportarTurnosPdf(rows, {
      titulo: solapa === 'turnos' ? `Turnos de ${nombreCiudadano}` : `Prestaciones realizadas de ${nombreCiudadano}`,
      conEstado: solapa === 'turnos',
    })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <h1 style={titulo}>consultas</h1>
        <p style={{ margin: '6px 0 0', color: 'var(--fg-3)', fontSize: 'var(--size-btn)' }}>
          buscá un ciudadano para consultar sus turnos y las prestaciones realizadas, con su historia de atenciones.
        </p>
      </div>

      {/* Buscador de ciudadano */}
      <div style={panel}>
        {ciudadano ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--fg-3)' }}>
              Ciudadano
            </span>
            <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-1)' }}>{nombreCiudadano}</span>
            {ciudadano.doc_nro && <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>DNI {ciudadano.doc_nro}</span>}
            <button onClick={() => setCiudadano(null)} style={btnGhostSm} title="Buscar otro ciudadano">
              <X size={12} strokeWidth={1.5} /> Cambiar
            </button>
            <div style={{ marginLeft: 'auto' }}>
              <button onClick={doExport} style={btnPrimary}>
                <Download size={14} strokeWidth={1.5} /> Exportar PDF
              </button>
            </div>
          </div>
        ) : (
          <div style={{ maxWidth: 480 }}>
            <label style={lbl}>Buscar ciudadano</label>
            <CiudadanoSearch onSelect={setCiudadano} permitirNuevo={false} />
          </div>
        )}
      </div>

      {ciudadano && (
        <>
          {/* Sub-solapas */}
          <div style={{ display: 'flex', gap: 6 }}>
            <button onClick={() => setSolapa('turnos')} style={tabBtn(solapa === 'turnos')}>
              Consulta de turnos ({turnos.length})
            </button>
            <button onClick={() => setSolapa('realizadas')} style={tabBtn(solapa === 'realizadas')}>
              Consulta de prestaciones realizadas ({realizados.length})
            </button>
          </div>

          {turnosQ.isError && (
            <div style={errorBanner}>{(turnosQ.error as Error)?.message ?? 'Error al consultar turnos'}</div>
          )}

          {solapa === 'turnos' ? (
            <div style={card}>
              <table style={table}>
                <thead>
                  <tr>
                    <th style={th}>Fecha / Hora</th>
                    <th style={th}>Atiende</th>
                    <th style={th}>Prestación</th>
                    <th style={th}>Estado</th>
                    <th style={th}>Observaciones</th>
                  </tr>
                </thead>
                <tbody>
                  {turnosQ.isLoading && <tr><td colSpan={5} style={empty}>Cargando…</td></tr>}
                  {!turnosQ.isLoading && turnos.length === 0 && (
                    <tr><td colSpan={5} style={empty}>El ciudadano no tiene turnos registrados (o están fuera de tu alcance de consulta).</td></tr>
                  )}
                  {turnos.map((t) => (
                    <tr key={t.id_turno} onClick={() => setDetalle(t)} style={{ cursor: 'pointer' }} title="Ver detalle del turno">
                      <td style={td}>
                        <div style={mono}>{t.fecha}</div>
                        <div style={{ ...mono, fontSize: '0.74rem', color: 'var(--fg-3)' }}>
                          {t.hora_inicio.slice(0, 5)}–{t.hora_fin.slice(0, 5)}
                        </div>
                      </td>
                      <td style={td}>
                        {t.recurso_nombre ?? t.agente_nombre ?? '—'}
                        <div style={{ fontSize: '0.7rem', color: 'var(--fg-3)' }}>
                          {t.id_espacio != null ? 'Lugar de atención' : 'Agente'}
                        </div>
                      </td>
                      <td style={td}>{t.prestacion_nombre ?? '—'}</td>
                      <td style={td}><EstadoBadge estado={t.estado} /></td>
                      <td style={{ ...td, maxWidth: 240, color: 'var(--fg-3)', whiteSpace: 'pre-wrap' }}>{t.observaciones ?? ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {turnosQ.isLoading && <div style={empty}>Cargando…</div>}
              {!turnosQ.isLoading && realizados.length === 0 && (
                <div style={{ ...panel, ...empty }}>
                  El ciudadano no tiene prestaciones realizadas (turnos cumplidos) registradas, o están fuera de tu alcance de consulta.
                </div>
              )}
              {realizados.map((t) => {
                const at = (atenciones.data ?? []).find((a) => a.id_turno === t.id_turno)
                return (
                  <div key={t.id_turno} style={{ ...panel, cursor: 'pointer' }} onClick={() => setDetalle(t)} title="Ver detalle del turno">
                    <div style={{ display: 'flex', gap: 10, alignItems: 'baseline', flexWrap: 'wrap', marginBottom: at ? 8 : 0 }}>
                      <span style={mono}>{t.fecha} · {t.hora_inicio.slice(0, 5)}–{t.hora_fin.slice(0, 5)}</span>
                      <span style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--fg-1)' }}>{t.prestacion_nombre ?? '—'}</span>
                      <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>
                        {t.recurso_nombre ?? t.agente_nombre ?? '—'} · {t.id_espacio != null ? 'Lugar de atención' : 'Agente'}
                      </span>
                      <span style={{ marginLeft: 'auto' }}><EstadoBadge estado={t.estado} /></span>
                    </div>
                    {at ? (
                      <AtencionItem a={at} />
                    ) : (
                      <div style={{ fontSize: 12, color: 'var(--fg-3)', fontStyle: 'italic' }}>
                        Sin registro de atención (la prestación no registra historia, o el registro está fuera de tu alcance).
                        {t.observaciones ? ` Observación del turno: ${t.observaciones}` : ''}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </>
      )}

      <TurnoDetalleModal turno={detalle} onClose={() => setDetalle(null)} />
    </div>
  )
}

function EstadoBadge({ estado }: { estado: EstadoTurno }) {
  const c = ESTADO_COLOR[estado]
  return (
    <span style={{ background: c.bg, color: c.fg, fontSize: '0.72rem', fontWeight: 600, padding: '2px 9px', borderRadius: 999, textTransform: 'capitalize' }}>
      {estado}
    </span>
  )
}

const titulo: React.CSSProperties = {
  margin: 0, fontFamily: 'var(--font-display)', fontSize: 'var(--size-section)',
  fontWeight: 400, letterSpacing: 'var(--track-section)', color: 'var(--fg-1)',
}
const panel: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 12, padding: 14,
}
const lbl: React.CSSProperties = {
  display: 'block', fontSize: 11, fontWeight: 600, textTransform: 'uppercase',
  letterSpacing: '0.04em', color: 'var(--fg-3)', marginBottom: 6,
}
function tabBtn(active: boolean): React.CSSProperties {
  return {
    fontFamily: 'var(--font-display)', fontSize: 12.5, cursor: 'pointer',
    padding: '7px 16px', borderRadius: 8, fontWeight: active ? 600 : 400,
    border: '1px solid ' + (active ? 'var(--zaris-orange)' : 'var(--border-medium)'),
    background: active ? 'rgba(245,78,0,0.08)' : 'transparent',
    color: active ? 'var(--zaris-orange)' : 'var(--fg-2)',
  }
}
const btnBase: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.82rem', cursor: 'pointer',
  borderRadius: 8, padding: '7px 12px', border: '1px solid transparent', fontWeight: 500,
  display: 'inline-flex', alignItems: 'center', gap: 6,
}
const btnPrimary: React.CSSProperties = {
  ...btnBase, background: 'var(--zaris-orange)', color: 'white', borderColor: 'var(--zaris-orange)',
}
const btnGhostSm: React.CSSProperties = {
  ...btnBase, fontSize: '0.76rem', padding: '4px 9px',
  background: 'transparent', color: 'var(--fg-2)', border: '1px solid var(--border-medium)',
}
const card: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 12, overflowX: 'auto',
}
const table: React.CSSProperties = {
  width: '100%', borderCollapse: 'separate', borderSpacing: 0, fontSize: '0.84rem', minWidth: 720,
}
const th: React.CSSProperties = {
  textAlign: 'left', fontWeight: 600, fontSize: '0.72rem', textTransform: 'uppercase',
  letterSpacing: '0.04em', color: 'var(--fg-3)', padding: '9px 12px',
  borderBottom: '1px solid var(--border-primary)', background: 'var(--surface-300)', whiteSpace: 'nowrap',
}
const td: React.CSSProperties = {
  padding: '10px 12px', borderBottom: '1px solid var(--border-primary)',
  verticalAlign: 'middle', background: 'var(--surface-100)',
}
const mono: React.CSSProperties = {
  fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--fg-2)', whiteSpace: 'nowrap',
}
const empty: React.CSSProperties = {
  padding: 24, textAlign: 'center', color: 'var(--fg-3)', fontSize: '0.88rem',
}
const errorBanner: React.CSSProperties = {
  background: '#ffebee', border: '1px solid #ffcdd2', borderLeft: '4px solid var(--color-error)',
  borderRadius: 8, padding: '12px 16px', color: '#c62828', fontSize: '0.86rem',
}
