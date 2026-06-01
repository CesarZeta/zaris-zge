import { useState } from 'react'
import { CheckCircle2, XCircle, Clock, ShieldCheck, Lock } from 'lucide-react'
import { useResolverAprobacion } from '../hooks/useTramites'
import type { TramiteAprobacion } from '../types'

/**
 * Panel de aprobaciones por etapa (visados) en el detalle del trámite.
 * Muestra cada marca en verde (aprobada) / rojo (rechazada) / gris (pendiente)
 * y permite resolverla. Avisa si hay bloqueantes pendientes que traban el avance.
 */
export function PanelAprobaciones({
  numero,
  aprobaciones,
  onActualizar,
}: {
  numero: string
  aprobaciones: TramiteAprobacion[]
  onActualizar?: () => void
}) {
  if (!aprobaciones || aprobaciones.length === 0) return null

  const bloqueantesPendientes = aprobaciones.filter(
    (a) => a.bloqueante && a.estado === 'pendiente',
  ).length

  return (
    <section style={cardStyle}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <ShieldCheck size={16} strokeWidth={1.5} color="var(--fg-2)" />
        <h2 style={cardTitleStyle}>Aprobaciones de etapa</h2>
      </div>

      {bloqueantesPendientes > 0 && (
        <div style={avisoBloqueoStyle}>
          <Lock size={13} strokeWidth={1.5} />
          {bloqueantesPendientes === 1
            ? 'Hay 1 aprobación bloqueante pendiente. El trámite no puede avanzar hasta resolverla.'
            : `Hay ${bloqueantesPendientes} aprobaciones bloqueantes pendientes. El trámite no puede avanzar hasta resolverlas.`}
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {aprobaciones.map((a) => (
          <AprobacionRow key={a.id_tramite_aprobacion} numero={numero} aprob={a} onActualizar={onActualizar} />
        ))}
      </div>
    </section>
  )
}

function AprobacionRow({
  numero,
  aprob,
  onActualizar,
}: {
  numero: string
  aprob: TramiteAprobacion
  onActualizar?: () => void
}) {
  const [abierto, setAbierto] = useState(false)
  const [decision, setDecision] = useState<'aprobada' | 'rechazada' | null>(null)
  const [comentario, setComentario] = useState('')
  const resolver = useResolverAprobacion(numero)

  const v = visualPorEstado(aprob.estado)
  const resuelta = aprob.estado !== 'pendiente'

  function elegir(d: 'aprobada' | 'rechazada') {
    setDecision(d)
    setAbierto(true)
  }

  async function confirmar() {
    if (!decision) return
    // El rechazo exige motivo (el área debe explicar por qué traba la etapa).
    if (decision === 'rechazada' && comentario.trim().length === 0) return
    try {
      await resolver.mutateAsync({
        idAprob: aprob.id_tramite_aprobacion,
        decision,
        comentario: comentario.trim() || undefined,
      })
      setAbierto(false)
      setDecision(null)
      setComentario('')
      onActualizar?.()
    } catch {
      /* el error se muestra abajo via resolver.error */
    }
  }

  return (
    <div style={{ ...rowStyle, borderLeft: `3px solid ${v.color}` }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
        <span style={{ marginTop: 1, color: v.color, flexShrink: 0 }}>{v.icon}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 13, fontWeight: 600, fontFamily: 'var(--font-display)', color: 'var(--fg-1)' }}>
              {aprob.etiqueta}
            </span>
            {aprob.bloqueante && (
              <span style={badgeBloqStyle}>bloqueante</span>
            )}
          </div>
          <p style={metaStyle}>
            {aprob.estado_etiqueta && <>Etapa: {aprob.estado_etiqueta} · </>}
            Aprueba: {aprob.aprobador_nombre ?? aprob.aprobador_tipo}
          </p>
          {resuelta && (
            <p style={{ ...metaStyle, color: v.color, fontWeight: 600 }}>
              {aprob.estado === 'aprobada' ? 'Aprobada' : 'Rechazada'}
              {aprob.resuelto_por_nombre && <> por {aprob.resuelto_por_nombre}</>}
              {aprob.resuelto_en && <> · {new Date(aprob.resuelto_en).toLocaleDateString('es-AR', { day: '2-digit', month: 'short', year: 'numeric' })}</>}
            </p>
          )}
          {resuelta && aprob.comentario && (
            <p style={comentarioStyle}>"{aprob.comentario}"</p>
          )}
        </div>
      </div>

      {!resuelta && !abierto && (
        <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
          <button type="button" onClick={() => elegir('aprobada')} style={btnAprobarStyle}>
            <CheckCircle2 size={13} strokeWidth={1.5} /> Aprobar
          </button>
          <button type="button" onClick={() => elegir('rechazada')} style={btnRechazarStyle}>
            <XCircle size={13} strokeWidth={1.5} /> Rechazar
          </button>
        </div>
      )}

      {!resuelta && abierto && (
        <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <textarea
            value={comentario}
            onChange={(e) => setComentario(e.target.value)}
            placeholder={decision === 'rechazada' ? 'Motivo del rechazo (obligatorio)' : 'Comentario (opcional)'}
            rows={2}
            style={textareaStyle}
          />
          {resolver.error && (
            <p style={{ margin: 0, fontSize: 12, color: 'var(--color-error)', fontFamily: 'var(--font-display)' }}>
              {resolver.error instanceof Error ? resolver.error.message : 'No se pudo resolver.'}
            </p>
          )}
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              type="button"
              onClick={() => { void confirmar() }}
              disabled={resolver.isPending || (decision === 'rechazada' && comentario.trim().length === 0)}
              style={{
                ...(decision === 'rechazada' ? btnRechazarStyle : btnAprobarStyle),
                opacity: resolver.isPending || (decision === 'rechazada' && comentario.trim().length === 0) ? 0.5 : 1,
                cursor: resolver.isPending || (decision === 'rechazada' && comentario.trim().length === 0) ? 'default' : 'pointer',
              }}
            >
              {resolver.isPending ? 'Guardando…' : decision === 'rechazada' ? 'Confirmar rechazo' : 'Confirmar aprobación'}
            </button>
            <button
              type="button"
              onClick={() => { setAbierto(false); setDecision(null); setComentario('') }}
              style={btnCancelarStyle}
            >
              Cancelar
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function visualPorEstado(estado: TramiteAprobacion['estado']): { color: string; icon: React.ReactNode } {
  if (estado === 'aprobada') return { color: '#1f8a65', icon: <CheckCircle2 size={16} strokeWidth={1.5} /> }
  if (estado === 'rechazada') return { color: 'var(--color-error)', icon: <XCircle size={16} strokeWidth={1.5} /> }
  return { color: 'var(--fg-3)', icon: <Clock size={16} strokeWidth={1.5} /> }
}

const cardStyle: React.CSSProperties = {
  background: 'var(--surface-100)', borderRadius: 'var(--radius-xl)',
  border: '1px solid var(--border-primary)', padding: '18px',
  display: 'flex', flexDirection: 'column', gap: 12,
}
const cardTitleStyle: React.CSSProperties = {
  margin: 0, fontSize: 14, fontWeight: 600,
  fontFamily: 'var(--font-display)', color: 'var(--fg-1)',
}
const rowStyle: React.CSSProperties = {
  padding: '10px 12px', background: 'var(--surface-300)',
  borderRadius: 'var(--radius-lg)',
}
const metaStyle: React.CSSProperties = {
  margin: '3px 0 0', fontSize: 12, color: 'var(--fg-3)', fontFamily: 'var(--font-display)',
}
const comentarioStyle: React.CSSProperties = {
  margin: '4px 0 0', fontSize: 12, color: 'var(--fg-2)',
  fontFamily: 'var(--font-display)', fontStyle: 'italic',
}
const avisoBloqueoStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 6,
  padding: '8px 10px', borderRadius: 'var(--radius-lg)',
  background: 'rgba(207, 45, 86, 0.08)', border: '1px solid rgba(207, 45, 86, 0.25)',
  color: 'var(--color-error)', fontSize: 12, fontFamily: 'var(--font-display)', fontWeight: 500,
}
const badgeBloqStyle: React.CSSProperties = {
  fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.04em',
  fontWeight: 600, fontFamily: 'var(--font-display)',
  padding: '1px 6px', borderRadius: 999,
  background: 'rgba(207, 45, 86, 0.12)', color: 'var(--color-error)',
}
const btnBaseChip: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 4,
  padding: '5px 10px', borderRadius: 'var(--radius-lg)',
  fontFamily: 'var(--font-display)', fontSize: 12, fontWeight: 500,
  border: '1px solid transparent', cursor: 'pointer',
}
const btnAprobarStyle: React.CSSProperties = {
  ...btnBaseChip, background: 'rgba(31, 138, 101, 0.12)',
  borderColor: 'rgba(31, 138, 101, 0.3)', color: '#1f8a65',
}
const btnRechazarStyle: React.CSSProperties = {
  ...btnBaseChip, background: 'rgba(207, 45, 86, 0.1)',
  borderColor: 'rgba(207, 45, 86, 0.3)', color: 'var(--color-error)',
}
const btnCancelarStyle: React.CSSProperties = {
  ...btnBaseChip, background: 'transparent',
  borderColor: 'var(--border-primary)', color: 'var(--fg-3)',
}
const textareaStyle: React.CSSProperties = {
  width: '100%', boxSizing: 'border-box', resize: 'vertical',
  padding: '8px 10px', borderRadius: 'var(--radius-lg)',
  border: '1px solid var(--border-primary)', background: 'var(--surface-100)',
  fontFamily: 'var(--font-display)', fontSize: 13, color: 'var(--fg-1)',
}
