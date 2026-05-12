import { useEffect, useRef, useState } from 'react'
import { geoBuscar, type GeoBuscarResult } from '../api/reclamosApi'

interface Props {
  onPick: (result: GeoBuscarResult) => void
  placeholder?: string
}

export function GeocodingSearch({ onPick, placeholder }: Props) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<GeoBuscarResult[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const skipNextRef = useRef(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // Debounce 500ms (Nominatim acepta 1 req/seg, backend ya tiene rate limit).
  useEffect(() => {
    if (skipNextRef.current) { skipNextRef.current = false; return }
    if (q.trim().length < 3) {
      setResults([])
      setOpen(false)
      return
    }
    const t = setTimeout(async () => {
      setLoading(true)
      setErr(null)
      try {
        const data = await geoBuscar(q.trim(), 5)
        setResults(data.filter((r) => r.lat != null && r.lon != null))
        setOpen(true)
      } catch (e) {
        setErr((e as Error).message)
        setResults([])
        setOpen(true)
      } finally {
        setLoading(false)
      }
    }, 500)
    return () => clearTimeout(t)
  }, [q])

  // Click fuera cierra
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (!containerRef.current) return
      if (!containerRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  function handlePick(r: GeoBuscarResult) {
    skipNextRef.current = true
    onPick(r)
    setOpen(false)
    setResults([])
    setQ(r.display_name ?? '')
  }

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%' }}>
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => { if (results.length > 0) setOpen(true) }}
        placeholder={placeholder ?? 'Buscar dirección (ej. Av. Maipú 1500 Vicente López)'}
        style={inputStyle}
      />
      {open && (
        <div style={dropdownStyle}>
          {loading && <div style={lineMutedStyle}>Buscando…</div>}
          {err && <div style={{ ...lineMutedStyle, color: 'var(--color-error)' }}>Error: {err}</div>}
          {!loading && !err && results.length === 0 && (
            <div style={lineMutedStyle}>Sin resultados</div>
          )}
          {results.map((r, i) => (
            <button
              key={`${r.lat}-${r.lon}-${i}`}
              type="button"
              onClick={() => handlePick(r)}
              style={resultBtnStyle}
            >
              <div style={{ fontSize: 'var(--size-ui)', color: 'var(--fg-1)' }}>
                {r.display_name}
              </div>
              {r.type && (
                <div style={{ fontSize: 'var(--size-caption)', color: 'var(--fg-3)' }}>
                  {r.type}
                </div>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '9px 12px',
  fontFamily: 'var(--font-display)',
  fontSize: 'var(--size-ui)',
  color: 'var(--fg-1)',
  background: 'var(--surface-100)',
  border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-lg)',
  outline: 'none',
}

const dropdownStyle: React.CSSProperties = {
  position: 'absolute',
  top: 'calc(100% + 4px)',
  left: 0,
  right: 0,
  background: 'var(--surface-100)',
  border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-lg)',
  boxShadow: 'var(--shadow-ambient)',
  zIndex: 1000,
  maxHeight: 280,
  overflowY: 'auto',
}

const lineMutedStyle: React.CSSProperties = {
  padding: '10px 12px',
  fontSize: 'var(--size-caption)',
  color: 'var(--fg-3)',
}

const resultBtnStyle: React.CSSProperties = {
  display: 'block',
  width: '100%',
  textAlign: 'left',
  padding: '8px 12px',
  background: 'transparent',
  border: 'none',
  borderBottom: '1px solid var(--border-primary)',
  cursor: 'pointer',
  fontFamily: 'var(--font-display)',
}
