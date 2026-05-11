import { useEffect, useRef, useState } from 'react'
import { Search } from 'lucide-react'
import { buscarCiudadanos } from '../api/agendaApi'
import type { CiudadanoMinimo } from '../types/agenda'

interface Props {
  onSelect: (c: CiudadanoMinimo) => void
  placeholder?: string
}

export function CiudadanoSearch({ onSelect, placeholder = 'DNI, CUIL, telefono o nombre...' }: Props) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<CiudadanoMinimo[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const reqIdRef = useRef(0)
  // Tras un pick, setQ() rellena el input con el nombre, lo cual reabriria
  // el dropdown ("Sin resultados") por el effect debounced. Este flag salta
  // un ciclo del effect para que la linea "Seleccionado: ..." quede visible.
  const skipNextRef = useRef(false)

  useEffect(() => {
    if (skipNextRef.current) {
      skipNextRef.current = false
      return
    }
    if (q.trim().length < 2) {
      setResults([]); setOpen(false); return
    }
    const myId = ++reqIdRef.current
    setLoading(true); setOpen(true)
    const t = setTimeout(async () => {
      try {
        const rows = await buscarCiudadanos(q.trim(), 10)
        if (myId === reqIdRef.current) setResults(rows)
      } catch {
        if (myId === reqIdRef.current) setResults([])
      } finally {
        if (myId === reqIdRef.current) setLoading(false)
      }
    }, 280)
    return () => clearTimeout(t)
  }, [q])

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%' }}>
      <div style={{ position: 'relative' }}>
        <Search size={14} strokeWidth={1.5} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--fg-3)' }} />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={placeholder}
          onFocus={() => q.length >= 2 && setOpen(true)}
          style={{
            fontFamily: 'var(--font-display)', fontSize: 'var(--size-ui)', width: '100%',
            padding: '9px 12px 9px 32px', borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--border-primary)', background: 'transparent',
            outline: 'none', color: 'var(--fg-1)',
          }}
        />
      </div>
      {open && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0,
          background: 'var(--surface-100)', borderRadius: 'var(--radius-lg)',
          boxShadow: 'var(--shadow-card)', maxHeight: 280, overflowY: 'auto',
          zIndex: 50,
        }}>
          {loading && (
            <div style={{ padding: 12, color: 'var(--fg-3)', fontSize: 13 }}>Buscando...</div>
          )}
          {!loading && results.length === 0 && (
            <div style={{ padding: 12, color: 'var(--fg-3)', fontSize: 13 }}>Sin resultados.</div>
          )}
          {results.map((c) => (
            <button
              key={c.id_ciudadano}
              onClick={() => {
                skipNextRef.current = true
                onSelect(c)
                setOpen(false)
                setResults([])
                setQ(`${c.apellido ?? ''}, ${c.nombre ?? ''}`.trim())
              }}
              style={{
                display: 'block', width: '100%', textAlign: 'left', padding: '8px 12px',
                background: 'transparent', border: 'none', cursor: 'pointer',
                borderBottom: '1px solid var(--border-primary)', fontFamily: 'var(--font-display)',
              }}
            >
              <div style={{ fontSize: 13, color: 'var(--fg-1)' }}>
                <strong>{c.apellido}, {c.nombre}</strong>
                {c.doc_nro && <span style={{ color: 'var(--fg-3)' }}> · DNI {c.doc_nro}</span>}
              </div>
              <div style={{ fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>
                {[c.telefono, c.email].filter(Boolean).join(' · ')}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
