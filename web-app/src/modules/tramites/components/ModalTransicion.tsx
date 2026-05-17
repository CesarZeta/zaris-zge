import { useState } from 'react'
import type { TransicionPermitida, TramiteDocumento } from '../types'

interface ModalTransicionProps {
  transicion: TransicionPermitida
  documentosDesdeEstado: TramiteDocumento[]
  onConfirmar: (body: { id_tipo_tramite_transicion: number; comentario?: string }) => Promise<void>
  onCerrar: () => void
}

export function ModalTransicion({ transicion, documentosDesdeEstado, onConfirmar, onCerrar }: ModalTransicionProps) {
  const [comentario, setComentario] = useState('')
  const [loading, setLoading] = useState(false)

  const faltaAdjunto = transicion.requiere_adjunto && documentosDesdeEstado.length === 0

  async function handleConfirmar() {
    if (loading || faltaAdjunto) return
    if (transicion.requiere_comentario && !comentario.trim()) return
    setLoading(true)
    try {
      await onConfirmar({
        id_tipo_tramite_transicion: transicion.id_tipo_tramite_transicion,
        comentario: comentario.trim() || undefined,
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={overlayStyle} onClick={(e) => { if (e.target === e.currentTarget) onCerrar() }}>
      <div style={modalStyle}>
        <div style={headerStyle}>
          <h2 style={titleStyle}>Ejecutar: {transicion.etiqueta_accion}</h2>
        </div>
        <div style={bodyStyle}>
          <p style={{ fontSize: 13, fontFamily: 'var(--font-display)', color: 'var(--fg-2)', margin: 0 }}>
            Estado destino: <strong>{transicion.etiqueta_destino}</strong>
          </p>

          {faltaAdjunto && (
            <div style={alertStyle}>
              <p style={{ margin: 0, fontSize: 13, fontFamily: 'var(--font-display)' }}>
                Esta transición requiere al menos un documento adjunto desde el estado actual.
                Adjuntá un documento antes de continuar.
              </p>
            </div>
          )}

          {transicion.requiere_comentario && (
            <div>
              <label style={labelStyle}>
                Comentario <span style={{ color: 'var(--color-error)' }}>*</span>
              </label>
              <textarea
                value={comentario}
                onChange={(e) => setComentario(e.target.value)}
                rows={3}
                placeholder="Describí el motivo o resultado de esta acción..."
                style={textareaStyle}
              />
            </div>
          )}

          {!transicion.requiere_comentario && (
            <div>
              <label style={labelStyle}>Comentario (opcional)</label>
              <textarea
                value={comentario}
                onChange={(e) => setComentario(e.target.value)}
                rows={2}
                placeholder="Observaciones adicionales..."
                style={textareaStyle}
              />
            </div>
          )}
        </div>

        <div style={footerStyle}>
          <button type="button" onClick={onCerrar} style={btnSecStyle}>Cancelar</button>
          <button
            type="button"
            onClick={() => { void handleConfirmar() }}
            disabled={loading || faltaAdjunto || (transicion.requiere_comentario && !comentario.trim())}
            style={{
              ...btnPrimStyle,
              opacity: !loading && !faltaAdjunto && (!transicion.requiere_comentario || comentario.trim()) ? 1 : 0.45,
              cursor: loading || faltaAdjunto ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Ejecutando...' : `Ejecutar: ${transicion.etiqueta_accion}`}
          </button>
        </div>
      </div>
    </div>
  )
}

const overlayStyle: React.CSSProperties = {
  position: 'fixed', inset: 0, background: 'rgba(38,37,30,.5)',
  display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
}
const modalStyle: React.CSSProperties = {
  background: 'var(--surface-100)', borderRadius: 'var(--radius-xl)',
  width: '100%', maxWidth: 480, boxShadow: 'var(--shadow-card)',
  display: 'flex', flexDirection: 'column',
}
const headerStyle: React.CSSProperties = {
  padding: '16px 20px', borderBottom: '1px solid var(--border-primary)',
}
const titleStyle: React.CSSProperties = {
  margin: 0, fontSize: 16, fontFamily: 'var(--font-display)', fontWeight: 600, color: 'var(--fg-1)',
}
const bodyStyle: React.CSSProperties = {
  padding: '20px', display: 'flex', flexDirection: 'column', gap: 14,
}
const footerStyle: React.CSSProperties = {
  display: 'flex', justifyContent: 'flex-end', gap: 8,
  padding: '14px 20px', borderTop: '1px solid var(--border-primary)',
}
const labelStyle: React.CSSProperties = {
  display: 'block', fontSize: 12, fontWeight: 500, color: 'var(--fg-3)',
  marginBottom: 4, fontFamily: 'var(--font-display)', textTransform: 'uppercase', letterSpacing: '0.04em',
}
const textareaStyle: React.CSSProperties = {
  width: '100%', padding: '8px 12px', border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-lg)', background: 'transparent', resize: 'vertical',
  fontFamily: 'var(--font-display)', fontSize: 13, color: 'var(--fg-1)', outline: 'none',
  boxSizing: 'border-box',
}
const alertStyle: React.CSSProperties = {
  padding: '10px 14px', background: 'rgba(207,45,86,.08)',
  border: '1px solid rgba(207,45,86,.3)', borderRadius: 'var(--radius-lg)',
}
const btnSecStyle: React.CSSProperties = {
  padding: '9px 16px', borderRadius: 'var(--radius-lg)', border: 'none',
  background: 'var(--surface-300)', color: 'var(--fg-2)', cursor: 'pointer',
  fontFamily: 'var(--font-display)', fontSize: 13,
}
const btnPrimStyle: React.CSSProperties = {
  padding: '9px 16px', borderRadius: 'var(--radius-lg)', border: 'none',
  background: 'var(--zaris-orange)', color: 'white', cursor: 'pointer',
  fontFamily: 'var(--font-display)', fontSize: 13, fontWeight: 500,
}
