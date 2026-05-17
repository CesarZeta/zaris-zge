import { useState } from 'react'
import { EntitySelect } from './EntitySelect'

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? 'http://127.0.0.1:8000'

interface ModalPaseProps {
  numeroExpediente: string
  onConfirmar: (body: { destinatario_tipo: 'subarea' | 'equipo'; destinatario_id: number; comentario?: string }) => Promise<void>
  onCerrar: () => void
}

export function ModalPase({ numeroExpediente, onConfirmar, onCerrar }: ModalPaseProps) {
  const [tipo, setTipo] = useState<'subarea' | 'equipo'>('subarea')
  const [idDest, setIdDest] = useState<number | null>(null)
  const [comentario, setComentario] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleConfirmar() {
    if (loading || !idDest) return
    setLoading(true)
    try {
      await onConfirmar({
        destinatario_tipo: tipo,
        destinatario_id: idDest,
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
          <h2 style={titleStyle}>Pase manual — {numeroExpediente}</h2>
        </div>
        <div style={bodyStyle}>
          <div>
            <label style={labelStyle}>Tipo de destinatario</label>
            <div style={{ display: 'flex', gap: 8 }}>
              {(['subarea', 'equipo'] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => { setTipo(t); setIdDest(null) }}
                  style={{
                    padding: '7px 16px', borderRadius: 'var(--radius-lg)', border: 'none',
                    cursor: 'pointer', fontFamily: 'var(--font-display)', fontSize: 13,
                    background: tipo === t ? 'var(--zaris-orange)' : 'var(--surface-300)',
                    color: tipo === t ? 'white' : 'var(--fg-2)',
                    fontWeight: tipo === t ? 600 : 400,
                  }}
                >
                  {t === 'subarea' ? 'Subárea' : 'Equipo'}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label style={labelStyle}>
              {tipo === 'subarea' ? 'Subárea destino' : 'Equipo destino'} <span style={{ color: 'var(--color-error)' }}>*</span>
            </label>
            <EntitySelect
              key={tipo}
              endpoint={tipo === 'subarea' ? `${BASE}/api/v1/subareas` : `${BASE}/api/v1/equipos`}
              idField={tipo === 'subarea' ? 'id_subarea' : 'id_equipo'}
              labelField="nombre"
              searchParam="q"
              value={idDest}
              onChange={setIdDest}
              placeholder={`Buscar ${tipo === 'subarea' ? 'subárea' : 'equipo'}...`}
            />
          </div>

          <div>
            <label style={labelStyle}>Motivo del pase (opcional)</label>
            <textarea
              value={comentario}
              onChange={(e) => setComentario(e.target.value)}
              rows={2}
              placeholder="Indicá el motivo o instrucciones para el área receptora..."
              style={textareaStyle}
            />
          </div>
        </div>

        <div style={footerStyle}>
          <button type="button" onClick={onCerrar} style={btnSecStyle}>Cancelar</button>
          <button
            type="button"
            onClick={() => { void handleConfirmar() }}
            disabled={loading || !idDest}
            style={{
              ...btnPrimStyle,
              opacity: loading || !idDest ? 0.45 : 1,
              cursor: loading || !idDest ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Enviando...' : 'Confirmar pase'}
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
