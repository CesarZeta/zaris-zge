import { useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { crearUploadUrl, confirmarAdjunto } from '../api/reclamosApi'
import { useNotificationsStore } from '../../../stores/notifications'

const MIME_PERMITIDOS = new Set([
  'image/jpeg', 'image/png', 'image/webp',
  'image/gif', 'image/heic', 'image/heif',
])
const MAX_BYTES = 10 * 1024 * 1024 // 10 MB

type ItemEstado = 'pendiente' | 'subiendo' | 'ok' | 'error'

interface Item {
  id: string
  file: File
  preview: string
  estado: ItemEstado
  mensaje?: string
}

interface Props {
  idReclamo: number
}

export function UploadAdjuntosPanel({ idReclamo }: Props) {
  const qc = useQueryClient()
  const push = useNotificationsStore((s) => s.push)
  const [items, setItems] = useState<Item[]>([])
  const [dragOver, setDragOver] = useState(false)
  const [subiendo, setSubiendo] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  function pickFiles(files: FileList | File[]) {
    const next: Item[] = []
    for (const file of Array.from(files)) {
      if (!MIME_PERMITIDOS.has(file.type)) {
        push({ kind: 'error', title: 'Archivo rechazado', body: `${file.name}: tipo ${file.type || 'desconocido'} no permitido` })
        continue
      }
      if (file.size > MAX_BYTES) {
        push({ kind: 'error', title: 'Archivo rechazado', body: `${file.name}: supera 10 MB` })
        continue
      }
      next.push({
        id: `${file.name}-${file.size}-${Date.now()}-${Math.random()}`,
        file,
        preview: URL.createObjectURL(file),
        estado: 'pendiente',
      })
    }
    if (next.length > 0) setItems((prev) => [...prev, ...next])
  }

  function quitarItem(id: string) {
    setItems((prev) => {
      const found = prev.find((p) => p.id === id)
      if (found) URL.revokeObjectURL(found.preview)
      return prev.filter((p) => p.id !== id)
    })
  }

  async function subirItem(item: Item): Promise<boolean> {
    setItems((prev) => prev.map((p) => p.id === item.id ? { ...p, estado: 'subiendo', mensaje: undefined } : p))
    try {
      const signed = await crearUploadUrl(idReclamo, {
        nombre_archivo: item.file.name,
        mime_type: item.file.type,
        tamano_bytes: item.file.size,
      })

      const putRes = await fetch(signed.upload_url, {
        method: 'PUT',
        headers: {
          'Content-Type': item.file.type,
          'x-upsert': 'true',
        },
        body: item.file,
      })
      if (!putRes.ok) {
        throw new Error(`Storage HTTP ${putRes.status}`)
      }

      await confirmarAdjunto(idReclamo, signed.id_adjunto)
      setItems((prev) => prev.map((p) => p.id === item.id ? { ...p, estado: 'ok' } : p))
      return true
    } catch (err) {
      const msg = (err as Error).message ?? 'Error desconocido'
      setItems((prev) => prev.map((p) => p.id === item.id ? { ...p, estado: 'error', mensaje: msg } : p))
      return false
    }
  }

  async function subirTodos() {
    const pendientes = items.filter((i) => i.estado === 'pendiente' || i.estado === 'error')
    if (pendientes.length === 0) return
    setSubiendo(true)
    let ok = 0
    let fail = 0
    for (const it of pendientes) {
      // eslint-disable-next-line no-await-in-loop
      const success = await subirItem(it)
      if (success) ok += 1
      else fail += 1
    }
    setSubiendo(false)
    if (ok > 0) {
      push({ kind: 'success', title: `${ok} adjunto${ok === 1 ? '' : 's'} subido${ok === 1 ? '' : 's'}` })
      qc.invalidateQueries({ queryKey: ['reclamos', 'adjuntos', idReclamo] })
    }
    if (fail > 0) {
      push({ kind: 'error', title: `${fail} falla${fail === 1 ? '' : 's'} al subir`, body: 'Tocá "Reintentar" en cada item con error.' })
    }
  }

  function limpiarSubidos() {
    setItems((prev) => {
      prev.filter((p) => p.estado === 'ok').forEach((p) => URL.revokeObjectURL(p.preview))
      return prev.filter((p) => p.estado !== 'ok')
    })
  }

  // Drag & drop
  function onDragOver(e: React.DragEvent) {
    e.preventDefault()
    setDragOver(true)
  }
  function onDragLeave(e: React.DragEvent) {
    e.preventDefault()
    setDragOver(false)
  }
  function onDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragOver(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      pickFiles(e.dataTransfer.files)
    }
  }

  const tieneItems = items.length > 0
  const pendientes = items.filter((i) => i.estado === 'pendiente' || i.estado === 'error').length

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        style={{
          border: `1.5px dashed ${dragOver ? 'var(--zaris-orange)' : 'var(--border-medium)'}`,
          background: dragOver ? 'rgba(245,78,0,0.05)' : 'var(--surface-200)',
          borderRadius: 'var(--radius-lg)',
          padding: '16px 20px',
          cursor: 'pointer',
          textAlign: 'center',
          fontSize: 'var(--size-ui)',
          color: 'var(--fg-2)',
          transition: 'background 120ms, border-color 120ms',
        }}
      >
        <strong style={{ color: 'var(--fg-1)' }}>Subir adjuntos</strong>
        <div style={{ fontSize: 'var(--size-caption)', color: 'var(--fg-3)', marginTop: 4 }}>
          Arrastrá imágenes acá o tocá para elegir. Formatos: JPG, PNG, WEBP, GIF, HEIC. Máx 10 MB cada uno.
        </div>
        <input
          ref={inputRef}
          type="file"
          accept={Array.from(MIME_PERMITIDOS).join(',')}
          multiple
          onChange={(e) => { if (e.target.files) { pickFiles(e.target.files); e.target.value = '' } }}
          style={{ display: 'none' }}
        />
      </div>

      {tieneItems && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 10 }}>
            {items.map((it) => (
              <div key={it.id} style={{
                position: 'relative',
                background: 'var(--surface-100)',
                border: '1px solid var(--border-primary)',
                borderRadius: 'var(--radius-md)',
                overflow: 'hidden',
                display: 'flex', flexDirection: 'column',
              }}>
                <div style={{ aspectRatio: '1 / 1', overflow: 'hidden', background: 'var(--surface-300)' }}>
                  <img src={it.preview} alt={it.file.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                </div>
                <div style={{ padding: '6px 8px', fontSize: 'var(--size-caption)' }}>
                  <div style={{ color: 'var(--fg-1)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={it.file.name}>
                    {it.file.name}
                  </div>
                  <div style={{ color: badgeColor(it.estado), fontWeight: 600, marginTop: 2 }}>
                    {labelEstado(it.estado)}
                    {it.mensaje && <span style={{ color: 'var(--fg-3)', fontWeight: 400 }}> — {it.mensaje}</span>}
                  </div>
                </div>
                {it.estado !== 'subiendo' && (
                  <button
                    type="button"
                    onClick={() => quitarItem(it.id)}
                    aria-label="Quitar"
                    style={{
                      position: 'absolute', top: 6, right: 6,
                      width: 22, height: 22, borderRadius: '50%',
                      background: 'rgba(0,0,0,0.55)', color: 'white',
                      border: 'none', cursor: 'pointer', fontSize: 14, lineHeight: '20px',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}
                  >
                    ×
                  </button>
                )}
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            {items.some((i) => i.estado === 'ok') && (
              <button type="button" onClick={limpiarSubidos} style={btnGhost}>
                Quitar subidos
              </button>
            )}
            <button
              type="button"
              onClick={subirTodos}
              disabled={subiendo || pendientes === 0}
              style={pendientes > 0 && !subiendo ? btnPrimary : btnDisabled}
            >
              {subiendo ? 'Subiendo…' : `Subir ${pendientes} adjunto${pendientes === 1 ? '' : 's'}`}
            </button>
          </div>
        </>
      )}
    </div>
  )
}

function labelEstado(e: ItemEstado): string {
  switch (e) {
    case 'pendiente': return 'Listo para subir'
    case 'subiendo':  return 'Subiendo…'
    case 'ok':        return 'Subido ✓'
    case 'error':     return 'Error'
  }
}

function badgeColor(e: ItemEstado): string {
  switch (e) {
    case 'pendiente': return 'var(--fg-2)'
    case 'subiendo':  return 'var(--zaris-orange)'
    case 'ok':        return 'var(--color-success)'
    case 'error':     return 'var(--color-error)'
  }
}

const btnPrimary: React.CSSProperties = {
  padding: '8px 14px', background: 'var(--zaris-dark)', color: 'var(--zaris-cream)',
  border: 'none', borderRadius: 'var(--radius-md)', fontFamily: 'var(--font-display)',
  fontSize: 'var(--size-btn)', cursor: 'pointer',
}
const btnGhost: React.CSSProperties = {
  padding: '8px 14px', background: 'transparent', color: 'var(--fg-2)',
  border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-md)',
  fontFamily: 'var(--font-display)', fontSize: 'var(--size-btn)', cursor: 'pointer',
}
const btnDisabled: React.CSSProperties = {
  ...btnPrimary, background: 'var(--surface-300)', color: 'var(--fg-3)', cursor: 'not-allowed',
}
