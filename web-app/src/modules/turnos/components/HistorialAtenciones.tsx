import { useAtencionesCiudadano } from '../hooks/useTurnos'
import type { TurnoAtencion } from '../types/turno'

/**
 * Historia de atenciones de un ciudadano (turnos con registra_atencion, mig 86).
 * Scopeada por nivel en el backend (mismo alcance que los turnos §33).
 * Compartido por CumplirTurnoModal (atenciones previas) y TurnoDetalleModal
 * (solapa Historia).
 */
export function HistorialAtenciones({
  idCiudadano,
  titulo = 'Atenciones anteriores',
  resaltarTurno,
  maxAlto = 180,
}: {
  idCiudadano: number
  titulo?: string
  /** id_turno a resaltar (la atención del turno que se está consultando). */
  resaltarTurno?: number
  maxAlto?: number
}) {
  const { data, isLoading, isError } = useAtencionesCiudadano(idCiudadano)
  const atenciones = data ?? []
  return (
    <div style={{
      border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-md)',
      background: 'var(--surface-300)', padding: '10px 12px',
    }}>
      <div style={{
        fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em',
        color: 'var(--fg-3)', marginBottom: 8,
      }}>
        {titulo} {!isLoading && !isError ? `(${atenciones.length})` : ''}
      </div>
      {isLoading && <div style={metaTxt}>Cargando historial…</div>}
      {isError && <div style={{ ...metaTxt, color: 'var(--color-error)' }}>No se pudo cargar el historial.</div>}
      {!isLoading && !isError && atenciones.length === 0 && (
        <div style={metaTxt}>Sin atenciones registradas para este ciudadano.</div>
      )}
      {atenciones.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: maxAlto, overflowY: 'auto' }}>
          {atenciones.map((a) => (
            <AtencionItem key={a.id_turno_atencion} a={a} resaltada={resaltarTurno != null && a.id_turno === resaltarTurno} />
          ))}
        </div>
      )}
    </div>
  )
}

export function AtencionItem({ a, resaltada = false }: { a: TurnoAtencion; resaltada?: boolean }) {
  return (
    <div style={{
      background: 'var(--surface-100)',
      border: resaltada ? '1px solid var(--zaris-orange)' : '1px solid var(--border-primary)',
      borderRadius: 'var(--radius-md)', padding: '8px 10px',
    }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'baseline', flexWrap: 'wrap' }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5, color: 'var(--fg-2)' }}>{a.fecha}</span>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg-1)' }}>{a.prestacion_nombre ?? 'Atención'}</span>
        {resaltada && (
          <span style={{
            fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em',
            background: 'rgba(245,78,0,0.12)', color: 'var(--zaris-orange)', padding: '1px 7px', borderRadius: 999,
          }}>este turno</span>
        )}
        {a.atendido_por && <span style={{ ...metaTxt, marginLeft: 'auto' }}>atendió: {a.atendido_por}</span>}
      </div>
      <div style={{ fontSize: 12.5, color: 'var(--fg-1)', marginTop: 4, whiteSpace: 'pre-wrap' }}>{a.intervencion}</div>
      {a.recomendaciones && (
        <div style={{ fontSize: 12, color: 'var(--fg-2)', marginTop: 4, whiteSpace: 'pre-wrap' }}>
          <span style={{ fontWeight: 600 }}>Recomendaciones:</span> {a.recomendaciones}
        </div>
      )}
    </div>
  )
}

const metaTxt: React.CSSProperties = { fontSize: 11.5, color: 'var(--fg-3)' }
