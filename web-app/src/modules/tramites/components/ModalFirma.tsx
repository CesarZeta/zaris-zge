import { useState } from 'react'
import { AlertTriangle, FileText } from 'lucide-react'
import type { TramiteDocumento, TramiteFirma } from '../types'
import { firmarDocumento } from '../lib/api'
import { useNotificationsStore } from '../../../stores/notifications'

interface ModalFirmaProps {
  tramiteNumero: string
  doc: TramiteDocumento
  firma: TramiteFirma
  onFirmado: () => void
  onCerrar: () => void
}

export function ModalFirma({ tramiteNumero, doc, firma, onFirmado, onCerrar }: ModalFirmaProps) {
  const push = useNotificationsStore((s) => s.push)
  const [aceptado, setAceptado] = useState(false)
  const [comentario, setComentario] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleFirmar() {
    if (!aceptado || loading) return
    setLoading(true)
    try {
      await firmarDocumento(tramiteNumero, doc.id_tramite_documento, {
        id_tramite_firma: firma.id_tramite_firma,
        comentario: comentario.trim() || undefined,
      })
      onFirmado()
    } catch (err) {
      const msg = (err as Error).message
      if (msg.includes('corrupto') || msg.includes('hash')) {
        push({ kind: 'error', title: 'Documento modificado', body: 'El hash del documento no coincide. No se puede firmar.' })
      } else {
        push({ kind: 'error', title: 'Error al firmar', body: msg })
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={overlayStyle} onClick={(e) => { if (e.target === e.currentTarget) onCerrar() }}>
      <div style={modalStyle}>
        <div style={headerStyle}>
          <AlertTriangle size={20} color="#f57f17" strokeWidth={1.5} />
          <h2 style={{ margin: 0, fontSize: 16, fontFamily: 'var(--font-display)', fontWeight: 600, color: 'var(--fg-1)' }}>
            Firmar electrónicamente
          </h2>
        </div>

        <div style={bodyStyle}>
          {/* Documento */}
          <div
            style={{
              background: 'var(--surface-300)',
              borderRadius: 'var(--radius-lg)',
              padding: '12px 14px',
              display: 'flex',
              gap: 10,
              alignItems: 'flex-start',
            }}
          >
            <FileText size={24} strokeWidth={1.5} color="var(--fg-3)" style={{ flexShrink: 0, marginTop: 2 }} />
            <div>
              <p style={{ margin: 0, fontWeight: 600, fontSize: 14, fontFamily: 'var(--font-display)', color: 'var(--fg-1)' }}>
                {doc.nombre}
              </p>
              {doc.hash_sha256 && (
                <p style={{ margin: '4px 0 0', fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--font-display)' }}>
                  Hash SHA256:{' '}
                  <span
                    title={doc.hash_sha256}
                    style={{ fontFamily: 'var(--font-mono)', cursor: 'help' }}
                  >
                    {doc.hash_sha256.slice(0, 16)}…
                  </span>
                </p>
              )}
              <p style={{ margin: '2px 0 0', fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--font-display)' }}>
                Tamaño: {formatBytes(doc.tamano_bytes)}
              </p>
            </div>
          </div>

          {/* Firmante */}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', fontSize: 13, fontFamily: 'var(--font-display)', color: 'var(--fg-2)' }}>
            <span>Firmás como: <strong>{firma.asignado_a?.nombre ?? firma.asignado_nombre ?? '—'}</strong></span>
            <span>·</span>
            <span>Rol: <strong>{ROLES[firma.rol_intervencion]}</strong></span>
          </div>

          {/* Aviso legal */}
          <div
            style={{
              background: 'rgba(245,127,23,.08)',
              border: '1px solid rgba(245,127,23,.3)',
              borderRadius: 'var(--radius-lg)',
              padding: '10px 14px',
              fontSize: 12,
              fontFamily: 'var(--font-display)',
              color: 'var(--fg-2)',
              lineHeight: 1.6,
            }}
          >
            <p style={{ margin: '0 0 6px', fontWeight: 600 }}>
              Esta firma quedará registrada con tu identidad, IP, fecha y hora, y el hash del documento al momento de firmar.
            </p>
            <p style={{ margin: 0, color: 'var(--fg-3)' }}>
              Esta es una <strong>constancia electrónica auditable de uso interno</strong>. No constituye firma digital con valor legal según Ley 25.506.
            </p>
          </div>

          {/* Comentario opcional */}
          <div>
            <label style={labelStyle}>Comentario (opcional)</label>
            <textarea
              value={comentario}
              onChange={(e) => setComentario(e.target.value)}
              rows={2}
              placeholder="Observaciones sobre esta firma..."
              style={textareaStyle}
            />
          </div>

          {/* Checkbox de consentimiento */}
          <label style={{ display: 'flex', gap: 10, alignItems: 'flex-start', cursor: 'pointer', fontSize: 13, fontFamily: 'var(--font-display)', color: 'var(--fg-1)' }}>
            <input
              type="checkbox"
              checked={aceptado}
              onChange={(e) => setAceptado(e.target.checked)}
              style={{ marginTop: 2, flexShrink: 0, width: 16, height: 16, cursor: 'pointer' }}
            />
            <span>He leído y comprendo que estoy firmando electrónicamente este documento con las implicancias indicadas arriba.</span>
          </label>
        </div>

        <div style={footerStyle}>
          <button onClick={onCerrar} style={btnSecStyle} type="button">
            Cancelar
          </button>
          <button
            onClick={() => { void handleFirmar() }}
            disabled={!aceptado || loading}
            type="button"
            style={{ ...btnPrimStyle, opacity: aceptado && !loading ? 1 : 0.45, cursor: aceptado && !loading ? 'pointer' : 'not-allowed' }}
          >
            {loading ? 'Firmando...' : 'Firmar electrónicamente'}
          </button>
        </div>
      </div>
    </div>
  )
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

const ROLES: Record<string, string> = {
  firma: 'Firma',
  visado: 'Visado',
  notificacion: 'Notificación',
}

const overlayStyle: React.CSSProperties = {
  position: 'fixed', inset: 0, background: 'rgba(38,37,30,.5)',
  display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
}
const modalStyle: React.CSSProperties = {
  background: 'var(--surface-100)', borderRadius: 'var(--radius-xl)',
  width: '100%', maxWidth: 500, boxShadow: 'var(--shadow-card)',
  display: 'flex', flexDirection: 'column', maxHeight: '90vh', overflow: 'hidden',
}
const headerStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 10,
  padding: '16px 20px', borderBottom: '1px solid var(--border-primary)',
}
const bodyStyle: React.CSSProperties = {
  padding: '20px', display: 'flex', flexDirection: 'column', gap: 14, overflowY: 'auto',
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
const btnSecStyle: React.CSSProperties = {
  padding: '9px 16px', borderRadius: 'var(--radius-lg)', border: 'none',
  background: 'var(--surface-300)', color: 'var(--fg-2)', cursor: 'pointer',
  fontFamily: 'var(--font-display)', fontSize: 13,
}
const btnPrimStyle: React.CSSProperties = {
  padding: '9px 16px', borderRadius: 'var(--radius-lg)', border: 'none',
  background: 'var(--zaris-dark)', color: 'var(--zaris-cream)', cursor: 'pointer',
  fontFamily: 'var(--font-display)', fontSize: 13, fontWeight: 500,
}
