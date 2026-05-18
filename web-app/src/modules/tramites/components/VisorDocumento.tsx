import { useEffect, useMemo, useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import { X, Download, ChevronLeft, ChevronRight, ZoomIn, ZoomOut, RotateCcw } from 'lucide-react'
import pdfWorkerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import { descargarDocumentoBlob } from '../lib/api'
import type { TramiteDocumento } from '../types'

pdfjs.GlobalWorkerOptions.workerSrc = pdfWorkerSrc

interface VisorDocumentoProps {
  tramiteNumero: string
  doc: TramiteDocumento
  onCerrar: () => void
}

const PDF_OPTIONS = { cMapUrl: '/cmaps/', cMapPacked: true }

export function VisorDocumento({ tramiteNumero, doc, onCerrar }: VisorDocumentoProps) {
  const [estado, setEstado] = useState<'cargando' | 'listo' | 'error'>('cargando')
  const [error, setError] = useState<string | null>(null)
  const [objectUrl, setObjectUrl] = useState<string | null>(null)
  const [mime, setMime] = useState<string>(doc.mime_type)
  const [totalPaginas, setTotalPaginas] = useState(0)
  const [paginaActual, setPaginaActual] = useState(1)
  const [zoom, setZoom] = useState(1)

  useEffect(() => {
    let cancelado = false
    let urlLocal: string | null = null
    setEstado('cargando')
    setError(null)
    descargarDocumentoBlob(tramiteNumero, doc.id_tramite_documento)
      .then(({ objectUrl, mime }) => {
        if (cancelado) {
          URL.revokeObjectURL(objectUrl)
          return
        }
        urlLocal = objectUrl
        setObjectUrl(objectUrl)
        setMime(mime)
        setEstado('listo')
      })
      .catch((err: Error) => {
        if (cancelado) return
        setError(err.message)
        setEstado('error')
      })
    return () => {
      cancelado = true
      if (urlLocal) URL.revokeObjectURL(urlLocal)
    }
  }, [tramiteNumero, doc.id_tramite_documento])

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onCerrar()
      if (esPdf(mime)) {
        if (e.key === 'ArrowRight') setPaginaActual((p) => Math.min(p + 1, totalPaginas || p))
        if (e.key === 'ArrowLeft') setPaginaActual((p) => Math.max(p - 1, 1))
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onCerrar, mime, totalPaginas])

  function handleDescargar() {
    if (!objectUrl) return
    const a = document.createElement('a')
    a.href = objectUrl
    a.download = doc.nombre
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  const tipo = useMemo<'pdf' | 'imagen' | 'otro'>(() => {
    if (esPdf(mime)) return 'pdf'
    if (esImagen(mime)) return 'imagen'
    return 'otro'
  }, [mime])

  return (
    <div style={overlayStyle} onClick={onCerrar}>
      <div style={modalStyle} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div style={headerStyle}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <p style={tituloStyle}>{doc.nombre}</p>
            <p style={metaStyle}>
              {mime} · {formatBytes(doc.tamano_bytes)}
            </p>
          </div>
          {tipo === 'pdf' && estado === 'listo' && totalPaginas > 0 && (
            <div style={controlGroupStyle}>
              <button type="button" onClick={() => setPaginaActual((p) => Math.max(p - 1, 1))} disabled={paginaActual <= 1} style={iconBtnStyle} title="Página anterior (←)">
                <ChevronLeft size={16} strokeWidth={1.5} />
              </button>
              <span style={paginaTextoStyle}>{paginaActual} / {totalPaginas}</span>
              <button type="button" onClick={() => setPaginaActual((p) => Math.min(p + 1, totalPaginas))} disabled={paginaActual >= totalPaginas} style={iconBtnStyle} title="Página siguiente (→)">
                <ChevronRight size={16} strokeWidth={1.5} />
              </button>
            </div>
          )}
          {(tipo === 'pdf' || tipo === 'imagen') && estado === 'listo' && (
            <div style={controlGroupStyle}>
              <button type="button" onClick={() => setZoom((z) => Math.max(0.5, z - 0.25))} style={iconBtnStyle} title="Alejar">
                <ZoomOut size={16} strokeWidth={1.5} />
              </button>
              <span style={paginaTextoStyle}>{Math.round(zoom * 100)}%</span>
              <button type="button" onClick={() => setZoom((z) => Math.min(3, z + 0.25))} style={iconBtnStyle} title="Acercar">
                <ZoomIn size={16} strokeWidth={1.5} />
              </button>
              <button type="button" onClick={() => setZoom(1)} style={iconBtnStyle} title="Restablecer zoom">
                <RotateCcw size={16} strokeWidth={1.5} />
              </button>
            </div>
          )}
          <button type="button" onClick={handleDescargar} disabled={!objectUrl} style={iconBtnStyle} title="Descargar">
            <Download size={16} strokeWidth={1.5} />
          </button>
          <button type="button" onClick={onCerrar} style={iconBtnStyle} title="Cerrar (Esc)">
            <X size={18} strokeWidth={1.5} />
          </button>
        </div>

        {/* Body */}
        <div style={bodyStyle}>
          {estado === 'cargando' && <Loader />}
          {estado === 'error' && (
            <div style={errorStyle}>
              <p style={{ margin: 0, fontWeight: 500 }}>No se pudo abrir el documento</p>
              <p style={{ margin: '6px 0 0', fontSize: 12, color: 'var(--fg-3)' }}>{error}</p>
            </div>
          )}
          {estado === 'listo' && objectUrl && tipo === 'pdf' && (
            <Document
              file={objectUrl}
              options={PDF_OPTIONS}
              onLoadSuccess={({ numPages }) => setTotalPaginas(numPages)}
              onLoadError={(e) => { setError(e.message); setEstado('error') }}
              loading={<Loader />}
            >
              <Page pageNumber={paginaActual} scale={zoom} renderAnnotationLayer renderTextLayer />
            </Document>
          )}
          {estado === 'listo' && objectUrl && tipo === 'imagen' && (
            <img
              src={objectUrl}
              alt={doc.nombre}
              style={{ transform: `scale(${zoom})`, transformOrigin: 'center top', maxWidth: '100%', maxHeight: '100%' }}
            />
          )}
          {estado === 'listo' && objectUrl && tipo === 'otro' && (
            <div style={{ textAlign: 'center', padding: 32 }}>
              <p style={{ margin: 0, fontSize: 14, color: 'var(--fg-2)' }}>
                Vista previa no disponible para <strong>{mime}</strong>.
              </p>
              <p style={{ margin: '8px 0 16px', fontSize: 12, color: 'var(--fg-3)' }}>
                Descargá el archivo para abrirlo localmente.
              </p>
              <button type="button" onClick={handleDescargar} style={btnPrimaryStyle}>
                <Download size={14} strokeWidth={1.5} style={{ marginRight: 6 }} />
                Descargar
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function Loader() {
  return (
    <p style={{ fontSize: 13, color: 'var(--fg-3)', fontFamily: 'var(--font-display)' }}>
      Cargando documento…
    </p>
  )
}

function esPdf(mime: string): boolean {
  return mime.toLowerCase().includes('pdf')
}

function esImagen(mime: string): boolean {
  return mime.toLowerCase().startsWith('image/')
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

const overlayStyle: React.CSSProperties = {
  position: 'fixed', inset: 0, background: 'rgba(0,0,0,.7)',
  zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center',
  padding: 24,
}
const modalStyle: React.CSSProperties = {
  background: 'var(--surface-100)', borderRadius: 'var(--radius-lg)',
  width: '100%', maxWidth: 1100, height: '92vh',
  display: 'flex', flexDirection: 'column', boxShadow: '0 24px 64px rgba(0,0,0,.4)',
  overflow: 'hidden',
}
const headerStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 12,
  padding: '12px 16px', borderBottom: '1px solid var(--border-primary)',
  background: 'var(--surface-200)',
}
const tituloStyle: React.CSSProperties = {
  margin: 0, fontSize: 14, fontWeight: 600,
  fontFamily: 'var(--font-display)', color: 'var(--fg-1)',
  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
}
const metaStyle: React.CSSProperties = {
  margin: '2px 0 0', fontSize: 11,
  color: 'var(--fg-3)', fontFamily: 'var(--font-display)',
}
const controlGroupStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 4,
  padding: '4px 8px', borderLeft: '1px solid var(--border-primary)',
}
const paginaTextoStyle: React.CSSProperties = {
  fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--fg-2)', minWidth: 56, textAlign: 'center',
}
const iconBtnStyle: React.CSSProperties = {
  background: 'none', border: 'none', cursor: 'pointer',
  color: 'var(--fg-2)', padding: 4, display: 'inline-flex',
  alignItems: 'center', borderRadius: 'var(--radius-md)',
}
const bodyStyle: React.CSSProperties = {
  flex: 1, overflow: 'auto', display: 'flex', alignItems: 'flex-start',
  justifyContent: 'center', padding: 16, background: 'var(--surface-300)',
}
const errorStyle: React.CSSProperties = {
  padding: 24, color: 'var(--color-error)',
  fontFamily: 'var(--font-display)', textAlign: 'center',
}
const btnPrimaryStyle: React.CSSProperties = {
  background: 'var(--zaris-orange)', color: '#fff',
  border: 'none', padding: '8px 16px', borderRadius: 'var(--radius-md)',
  fontFamily: 'var(--font-display)', fontSize: 13, fontWeight: 500,
  cursor: 'pointer', display: 'inline-flex', alignItems: 'center',
}
