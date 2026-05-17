import { useState } from 'react'
import { Search } from 'lucide-react'
import { Input } from '../../../ui'
import { listarBandeja } from '../lib/api'

interface ModalRelacionarProps {
  numeroExpediente: string
  onConfirmar: (body: { id_tramite_b: number; comentario?: string }) => Promise<void>
  onCerrar: () => void
}

export function ModalRelacionar({ numeroExpediente, onConfirmar, onCerrar }: ModalRelacionarProps) {
  const [numeroB, setNumeroB] = useState('')
  const [comentario, setComentario] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleConfirmar() {
    const num = numeroB.trim().toUpperCase()
    if (!num) { setError('Ingresá el número de expediente'); return }
    if (num === numeroExpediente.toUpperCase()) { setError('No podés relacionar un trámite consigo mismo'); return }
    setError('')
    setLoading(true)
    try {
      // Resolver número → id
      const res = await listarBandeja({ numero: num, limit: 1 })
      const tramiteB = res.items[0]
      if (!tramiteB || tramiteB.numero_expediente.toUpperCase() !== num) {
        setError(`No se encontró el trámite ${num}`)
        setLoading(false)
        return
      }
      await onConfirmar({
        id_tramite_b: tramiteB.id_tramite,
        comentario: comentario.trim() || undefined,
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al relacionar')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={overlayStyle} onClick={(e) => { if (e.target === e.currentTarget) onCerrar() }}>
      <div style={modalStyle}>
        <div style={headerStyle}>
          <h2 style={titleStyle}>Relacionar trámite — {numeroExpediente}</h2>
        </div>
        <div style={bodyStyle}>
          <div>
            <label style={labelStyle}>
              N° de expediente a relacionar <span style={{ color: 'var(--color-error)' }}>*</span>
            </label>
            <Input
              icon={<Search size={14} />}
              value={numeroB}
              onChange={(e) => { setNumeroB(e.target.value); setError('') }}
              placeholder="POD-LPL-2026-0001"
              style={{ textTransform: 'uppercase' }}
            />
            {error && (
              <p style={{ margin: '4px 0 0', fontSize: 11, color: 'var(--color-error)', fontFamily: 'var(--font-display)' }}>
                {error}
              </p>
            )}
          </div>

          <div>
            <label style={labelStyle}>Comentario (opcional)</label>
            <textarea
              value={comentario}
              onChange={(e) => setComentario(e.target.value)}
              rows={2}
              placeholder="Aclaración sobre la relación entre los expedientes..."
              style={textareaStyle}
            />
          </div>
        </div>

        <div style={footerStyle}>
          <button type="button" onClick={onCerrar} style={btnSecStyle}>Cancelar</button>
          <button
            type="button"
            onClick={() => { void handleConfirmar() }}
            disabled={loading || !numeroB.trim()}
            style={{
              ...btnPrimStyle,
              opacity: loading || !numeroB.trim() ? 0.45 : 1,
              cursor: loading || !numeroB.trim() ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Relacionando...' : 'Confirmar relación'}
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
  width: '100%', maxWidth: 460, boxShadow: 'var(--shadow-card)',
  display: 'flex', flexDirection: 'column',
}
const headerStyle: React.CSSProperties = {
  padding: '16px 20px', borderBottom: '1px solid var(--border-primary)',
}
const titleStyle: React.CSSProperties = {
  margin: 0, fontSize: 16, fontFamily: 'var(--font-display)', fontWeight: 600, color: 'var(--fg-1)',
}
const bodyStyle: React.CSSProperties = {
  padding: '20px', display: 'flex', flexDirection: 'column', gap: 16,
}
const footerStyle: React.CSSProperties = {
  display: 'flex', justifyContent: 'flex-end', gap: 8,
  padding: '14px 20px', borderTop: '1px solid var(--border-primary)',
}
const labelStyle: React.CSSProperties = {
  display: 'block', fontSize: 12, fontWeight: 500, color: 'var(--fg-3)',
  marginBottom: 6, fontFamily: 'var(--font-display)', textTransform: 'uppercase', letterSpacing: '0.04em',
}
const textareaStyle: React.CSSProperties = {
  width: '100%', padding: '8px 12px', border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-lg)', background: 'transparent', resize: 'vertical',
  fontFamily: 'var(--font-display)', fontSize: 13, color: 'var(--fg-1)', outline: 'none',
  boxSizing: 'border-box',
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
