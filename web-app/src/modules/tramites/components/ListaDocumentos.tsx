import { useState } from 'react'
import { FileText, Download, PenSquare, XCircle, ChevronDown, ChevronUp } from 'lucide-react'
import type { TramiteDocumento, TramiteFirma } from '../types'
import { descargarDocumentoUrl, rechazarFirma } from '../lib/api'
import { EstadoFirmaBadge } from './EstadoFirmaBadge'
import { ModalFirma } from './ModalFirma'
import { useNotificationsStore } from '../../../stores/notifications'

interface ListaDocumentosProps {
  tramiteNumero: string
  documentos: TramiteDocumento[]
  onCambio: () => void
}

export function ListaDocumentos({ tramiteNumero, documentos, onCambio }: ListaDocumentosProps) {
  const push = useNotificationsStore((s) => s.push)
  const [firmaAbierta, setFirmaAbierta] = useState<{ doc: TramiteDocumento; firma: TramiteFirma } | null>(null)
  const [expandidos, setExpandidos] = useState<Set<number>>(new Set())

  function toggleExpandido(id: number) {
    setExpandidos((prev) => {
      const next = new Set(prev)
      if (next.has(id)) { next.delete(id) } else { next.add(id) }
      return next
    })
  }

  async function handleRechazarFirma(doc: TramiteDocumento, firma: TramiteFirma) {
    const motivo = window.prompt('Motivo del rechazo:')
    if (!motivo?.trim()) return
    try {
      await rechazarFirma(tramiteNumero, doc.id_tramite_documento, {
        id_tramite_firma: firma.id_tramite_firma,
        motivo: motivo.trim(),
      })
      push({ kind: 'success', title: 'Firma rechazada' })
      onCambio()
    } catch (err) {
      push({ kind: 'error', title: 'Error al rechazar', body: (err as Error).message })
    }
  }

  async function handleFirmado() {
    setFirmaAbierta(null)
    push({ kind: 'success', title: 'Firma registrada correctamente' })
    onCambio()
  }

  if (documentos.length === 0) {
    return (
      <p style={{ fontSize: 13, color: 'var(--fg-3)', fontFamily: 'var(--font-display)' }}>
        Sin documentos adjuntos.
      </p>
    )
  }

  return (
    <>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {documentos.map((doc) => {
          const expandido = expandidos.has(doc.id_tramite_documento)
          return (
            <div
              key={doc.id_tramite_documento}
              style={{
                background: 'var(--surface-300)',
                borderRadius: 'var(--radius-lg)',
                border: '1px solid var(--border-primary)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px' }}>
                <FileText size={18} strokeWidth={1.5} color="var(--fg-3)" style={{ flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p
                    style={{
                      margin: 0,
                      fontSize: 13,
                      fontWeight: 500,
                      fontFamily: 'var(--font-display)',
                      color: 'var(--fg-1)',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {doc.nombre}
                  </p>
                  <p style={{ margin: '2px 0 0', fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--font-display)' }}>
                    {formatBytes(doc.tamano_bytes)} · {doc.mime_type} ·{' '}
                    <span
                      title={doc.hash_sha256}
                      style={{ fontFamily: 'var(--font-mono)', cursor: 'help' }}
                    >
                      {doc.hash_sha256.slice(0, 8)}…
                    </span>
                  </p>
                </div>
                <EstadoFirmaBadge estado={doc.estado_firma} />
                <a
                  href={descargarDocumentoUrl(tramiteNumero, doc.id_tramite_documento)}
                  target="_blank"
                  rel="noreferrer"
                  title="Descargar / ver"
                  style={{ color: 'var(--fg-3)', display: 'inline-flex' }}
                >
                  <Download size={16} strokeWidth={1.5} />
                </a>
                {doc.firmas.length > 0 && (
                  <button
                    type="button"
                    onClick={() => toggleExpandido(doc.id_tramite_documento)}
                    style={iconBtnStyle}
                    title="Ver firmas"
                  >
                    {expandido ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  </button>
                )}
              </div>

              {/* Panel de firmas */}
              {expandido && doc.firmas.length > 0 && (
                <div
                  style={{
                    borderTop: '1px solid var(--border-primary)',
                    padding: '8px 12px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 6,
                  }}
                >
                  <p style={{ fontSize: 11, color: 'var(--fg-3)', margin: 0, fontFamily: 'var(--font-display)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Firmas
                  </p>
                  {doc.firmas.map((firma) => (
                    <div
                      key={firma.id_tramite_firma}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        fontSize: 12,
                        fontFamily: 'var(--font-display)',
                        color: 'var(--fg-2)',
                      }}
                    >
                      <span style={{ flex: 1 }}>
                        {firma.asignado_a.nombre} ·{' '}
                        <span style={{ color: 'var(--fg-3)' }}>
                          {ROLES[firma.rol_intervencion]}
                        </span>
                      </span>
                      <FirmaBadge estado={firma.estado} firmado_en={firma.firmado_en} />
                      {firma.estado === 'pendiente' && (
                        <div style={{ display: 'flex', gap: 4 }}>
                          <button
                            type="button"
                            onClick={() => setFirmaAbierta({ doc, firma })}
                            style={{ ...iconBtnStyle, color: '#1f8a65' }}
                            title="Firmar electrónicamente"
                          >
                            <PenSquare size={14} strokeWidth={1.5} />
                          </button>
                          <button
                            type="button"
                            onClick={() => { void handleRechazarFirma(doc, firma) }}
                            style={{ ...iconBtnStyle, color: 'var(--color-error)' }}
                            title="Rechazar firma"
                          >
                            <XCircle size={14} strokeWidth={1.5} />
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {firmaAbierta && (
        <ModalFirma
          tramiteNumero={tramiteNumero}
          doc={firmaAbierta.doc}
          firma={firmaAbierta.firma}
          onFirmado={handleFirmado}
          onCerrar={() => setFirmaAbierta(null)}
        />
      )}
    </>
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

function FirmaBadge({ estado, firmado_en }: { estado: string; firmado_en: string | null }) {
  const colors: Record<string, { bg: string; fg: string; label: string }> = {
    pendiente: { bg: 'rgba(192,133,50,.18)', fg: 'var(--zaris-gold)', label: 'Pendiente' },
    firmado:   { bg: 'rgba(31,138,101,.14)', fg: '#1f8a65', label: firmado_en ? `Firmado ${new Date(firmado_en).toLocaleDateString('es-AR')}` : 'Firmado' },
    rechazado: { bg: 'rgba(207,45,86,.14)', fg: 'var(--color-error)', label: 'Rechazado' },
  }
  const c = colors[estado] ?? colors.pendiente
  return (
    <span style={{ background: c.bg, color: c.fg, fontSize: 10, padding: '2px 8px', borderRadius: 'var(--radius-pill)', fontWeight: 500 }}>
      {c.label}
    </span>
  )
}

const iconBtnStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  color: 'var(--fg-3)',
  padding: 2,
  display: 'inline-flex',
  alignItems: 'center',
}
