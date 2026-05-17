import { useRef, useState } from 'react'
import { Upload, X, CheckCircle, AlertCircle } from 'lucide-react'
import { adjuntarDocumento } from '../lib/api'

interface FileUploaderProps {
  numeroExpediente: string
  onExito: () => void
  onCerrar: () => void
}

interface FileItem {
  file: File
  status: 'pendiente' | 'subiendo' | 'ok' | 'error'
  progreso: number
  mensaje?: string
  idDocumento?: string
}

export function FileUploader({ numeroExpediente, onExito, onCerrar }: FileUploaderProps) {
  const [archivos, setArchivos] = useState<FileItem[]>([])
  const [subiendo, setSubiendo] = useState(false)
  const [comentarioGlobal, setComentarioGlobal] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const dropRef = useRef<HTMLDivElement>(null)

  function agregarArchivos(files: FileList | null) {
    if (!files) return
    const nuevos: FileItem[] = Array.from(files)
      .filter((f) => !archivos.some((a) => a.file.name === f.name && a.file.size === f.size))
      .map((f) => ({ file: f, status: 'pendiente', progreso: 0 }))
    setArchivos((prev) => [...prev, ...nuevos])
  }

  function quitar(idx: number) {
    setArchivos((prev) => prev.filter((_, i) => i !== idx))
  }

  function onDragOver(e: React.DragEvent) {
    e.preventDefault()
    if (dropRef.current) dropRef.current.style.borderColor = 'var(--zaris-orange)'
  }
  function onDragLeave() {
    if (dropRef.current) dropRef.current.style.borderColor = 'var(--border-medium)'
  }
  function onDrop(e: React.DragEvent) {
    e.preventDefault()
    onDragLeave()
    agregarArchivos(e.dataTransfer.files)
  }

  async function subirTodo() {
    const pendientes = archivos.filter((a) => a.status === 'pendiente')
    if (pendientes.length === 0) return
    setSubiendo(true)

    for (let i = 0; i < archivos.length; i++) {
      if (archivos[i].status !== 'pendiente') continue

      setArchivos((prev) => prev.map((a, j) => j === i ? { ...a, status: 'subiendo', progreso: 0 } : a))

      try {
        const doc = await adjuntarDocumento(
          numeroExpediente,
          archivos[i].file,
          {
            nombre: comentarioGlobal || undefined,
            onProgress: (p) => {
              setArchivos((prev) => prev.map((a, j) => j === i ? { ...a, progreso: p } : a))
            },
          }
        )
        setArchivos((prev) => prev.map((a, j) => j === i ? { ...a, status: 'ok', progreso: 100, idDocumento: String(doc.id_tramite_documento) } : a))
      } catch (e) {
        const msg = e instanceof Error ? e.message : 'Error al subir'
        setArchivos((prev) => prev.map((a, j) => j === i ? { ...a, status: 'error', mensaje: msg } : a))
      }
    }

    setSubiendo(false)
    const exitos = archivos.filter((_, i) => archivos[i]?.status === 'ok').length
    if (exitos > 0) onExito()
  }

  const hayPendientes = archivos.some((a) => a.status === 'pendiente')
  const todosOk = archivos.length > 0 && archivos.every((a) => a.status === 'ok')

  return (
    <div style={overlayStyle} onClick={(e) => { if (e.target === e.currentTarget && !subiendo) onCerrar() }}>
      <div style={modalStyle}>
        <div style={headerStyle}>
          <h2 style={titleStyle}>Adjuntar documentos — {numeroExpediente}</h2>
        </div>

        <div style={bodyStyle}>
          {/* Drop zone */}
          <div
            ref={dropRef}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
            style={dropZoneStyle}
          >
            <Upload size={28} color="var(--fg-3)" strokeWidth={1.5} />
            <p style={{ margin: '8px 0 2px', fontFamily: 'var(--font-display)', fontSize: 14, color: 'var(--fg-2)', fontWeight: 500 }}>
              Arrastrá archivos aquí o hacé click para seleccionar
            </p>
            <p style={{ margin: 0, fontSize: 12, color: 'var(--fg-3)', fontFamily: 'var(--font-display)' }}>
              PDF, imágenes, Word, Excel — máx. 10 MB por archivo
            </p>
          </div>
          <input
            ref={inputRef}
            type="file"
            multiple
            style={{ display: 'none' }}
            onChange={(e) => agregarArchivos(e.target.files)}
          />

          {/* Lista de archivos */}
          {archivos.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {archivos.map((a, i) => (
                <div key={i} style={fileRowStyle}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{ margin: 0, fontSize: 13, fontFamily: 'var(--font-display)', color: 'var(--fg-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {a.file.name}
                    </p>
                    <p style={{ margin: 0, fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--font-display)' }}>
                      {(a.file.size / 1024).toFixed(0)} KB
                    </p>
                    {a.status === 'subiendo' && (
                      <div style={{ marginTop: 4, height: 3, borderRadius: 2, background: 'var(--surface-400)', overflow: 'hidden' }}>
                        <div style={{ height: '100%', width: `${a.progreso}%`, background: 'var(--zaris-orange)', transition: 'width 200ms' }} />
                      </div>
                    )}
                    {a.status === 'error' && (
                      <p style={{ margin: 0, fontSize: 11, color: 'var(--color-error)', fontFamily: 'var(--font-display)' }}>{a.mensaje}</p>
                    )}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                    {a.status === 'ok' && <CheckCircle size={16} color="var(--color-success, #1f8a65)" strokeWidth={1.5} />}
                    {a.status === 'error' && <AlertCircle size={16} color="var(--color-error)" strokeWidth={1.5} />}
                    {(a.status === 'pendiente' || a.status === 'error') && !subiendo && (
                      <button type="button" onClick={() => quitar(i)} style={btnXStyle} title="Quitar">
                        <X size={14} />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Comentario global */}
          <div>
            <label style={labelStyle}>Observación para todos los documentos (opcional)</label>
            <textarea
              value={comentarioGlobal}
              onChange={(e) => setComentarioGlobal(e.target.value)}
              rows={2}
              disabled={subiendo}
              placeholder="Descripción o aclaración general sobre los adjuntos..."
              style={{ ...textareaStyle, opacity: subiendo ? 0.6 : 1 }}
            />
          </div>
        </div>

        <div style={footerStyle}>
          <button type="button" onClick={onCerrar} disabled={subiendo} style={{ ...btnSecStyle, opacity: subiendo ? 0.5 : 1 }}>
            {todosOk ? 'Cerrar' : 'Cancelar'}
          </button>
          {!todosOk && (
            <button
              type="button"
              onClick={() => { void subirTodo() }}
              disabled={subiendo || !hayPendientes}
              style={{
                ...btnPrimStyle,
                opacity: subiendo || !hayPendientes ? 0.45 : 1,
                cursor: subiendo || !hayPendientes ? 'not-allowed' : 'pointer',
              }}
            >
              {subiendo ? 'Subiendo...' : `Subir ${archivos.filter((a) => a.status === 'pendiente').length} archivo${archivos.filter((a) => a.status === 'pendiente').length !== 1 ? 's' : ''}`}
            </button>
          )}
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
  width: '100%', maxWidth: 520, boxShadow: 'var(--shadow-card)',
  display: 'flex', flexDirection: 'column', maxHeight: '90vh', overflow: 'hidden',
}
const headerStyle: React.CSSProperties = {
  padding: '16px 20px', borderBottom: '1px solid var(--border-primary)', flexShrink: 0,
}
const titleStyle: React.CSSProperties = {
  margin: 0, fontSize: 16, fontFamily: 'var(--font-display)', fontWeight: 600, color: 'var(--fg-1)',
}
const bodyStyle: React.CSSProperties = {
  padding: '20px', display: 'flex', flexDirection: 'column', gap: 16, overflowY: 'auto',
}
const footerStyle: React.CSSProperties = {
  display: 'flex', justifyContent: 'flex-end', gap: 8,
  padding: '14px 20px', borderTop: '1px solid var(--border-primary)', flexShrink: 0,
}
const dropZoneStyle: React.CSSProperties = {
  border: '2px dashed var(--border-medium)', borderRadius: 'var(--radius-lg)',
  padding: '32px 20px', textAlign: 'center', cursor: 'pointer',
  display: 'flex', flexDirection: 'column', alignItems: 'center',
  transition: 'border-color 150ms ease',
}
const fileRowStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'flex-start', gap: 10,
  padding: '8px 12px', background: 'var(--surface-300)', borderRadius: 'var(--radius-lg)',
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
const btnXStyle: React.CSSProperties = {
  background: 'none', border: 'none', cursor: 'pointer', padding: 4,
  color: 'var(--fg-3)', display: 'flex', alignItems: 'center',
}
