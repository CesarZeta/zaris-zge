import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { Search } from 'lucide-react'
import { buscarPartidos, type Partido } from '../api'

// Partido / municipio con autocompletar (CLAUDE.md §23): el catálogo de gobiernos locales tiene
// cientos por provincia. Patrón de CiudadanoSearch (debounce), pero en vez de un skipNextRef (§29) se
// compara el texto con el último elegido: el doble efecto de StrictMode consumía el salto y reabría la lista.
interface Props {
  idProvincia: number | null
  value: number | null
  /** Nombre del elegido cuando el form arranca con uno (edición). */
  etiqueta?: string | null
  disabled?: boolean
  inputStyle?: CSSProperties
  onChange: (p: Partido | null) => void
}

export function PartidoSearch({ idProvincia, value, etiqueta, disabled, inputStyle, onChange }: Props) {
  const [q, setQ] = useState(etiqueta ?? '')
  const [results, setResults] = useState<Partido[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const reqIdRef = useRef(0)
  // Texto del último elegido: mientras el input lo muestre, no se busca.
  const elegidoRef = useRef(etiqueta ?? '')
  const provinciaRef = useRef(idProvincia)

  // El valor se borró desde afuera (marcar «ficticio», por ejemplo): el nombre que mostraba ya no corresponde.
  useEffect(() => {
    if (value == null && elegidoRef.current && q === elegidoRef.current) {
      elegidoRef.current = ''
      setQ('')
    }
  }, [value]) // eslint-disable-line react-hooks/exhaustive-deps

  // Otra provincia: el texto anterior ya no corresponde.
  useEffect(() => {
    if (provinciaRef.current === idProvincia) return
    provinciaRef.current = idProvincia
    elegidoRef.current = ''
    setQ(''); setResults([]); setOpen(false)
  }, [idProvincia])

  useEffect(() => {
    if (idProvincia == null || q.trim().length < 2 || q === elegidoRef.current) {
      setResults([]); setOpen(false); return
    }
    const myId = ++reqIdRef.current
    setLoading(true); setOpen(true)
    const t = setTimeout(async () => {
      try {
        const rows = await buscarPartidos(idProvincia, q.trim())
        if (myId === reqIdRef.current) setResults(rows)
      } catch {
        if (myId === reqIdRef.current) setResults([])
      } finally {
        if (myId === reqIdRef.current) setLoading(false)
      }
    }, 250)
    return () => clearTimeout(t)
  }, [q, idProvincia])

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%' }} data-partido-search>
      <Search size={14} strokeWidth={1.5}
              style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--fg-3)' }} />
      <input
        value={q}
        disabled={disabled || idProvincia == null}
        placeholder={idProvincia == null ? 'Elegí la provincia primero' : 'Escribí el nombre…'}
        onChange={(e) => {
          setQ(e.target.value)
          elegidoRef.current = ''
          if (value != null) onChange(null)   // tocar el texto deshace la elección
        }}
        onFocus={() => q.trim().length >= 2 && value == null && setOpen(true)}
        style={{ ...inputStyle, paddingLeft: 32, width: '100%', boxSizing: 'border-box' }}
      />
      {open && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0, zIndex: 50,
          background: 'var(--surface-100)', borderRadius: 'var(--radius-lg)',
          boxShadow: 'var(--shadow-card)', maxHeight: 280, overflowY: 'auto',
        }}>
          {loading && <div style={{ padding: 12, color: 'var(--fg-3)', fontSize: 13 }}>Buscando…</div>}
          {!loading && results.length === 0 && (
            <div style={{ padding: 12, color: 'var(--fg-3)', fontSize: 13 }}>Sin resultados en esta provincia.</div>
          )}
          {results.map((p) => (
            <button
              key={p.id_partido}
              type="button"
              onClick={() => {
                elegidoRef.current = p.nombre
                onChange(p)
                setOpen(false)
                setResults([])
                setQ(p.nombre)
              }}
              style={{
                display: 'block', width: '100%', textAlign: 'left', padding: '8px 12px',
                background: 'transparent', border: 'none', cursor: 'pointer',
                borderBottom: '1px solid var(--border-primary)', fontFamily: 'var(--font-display)',
                fontSize: 13, color: 'var(--fg-1)',
              }}
            >
              <strong>{p.nombre}</strong>
              {p.categoria && <span style={{ color: 'var(--fg-3)' }}> — {p.categoria}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
