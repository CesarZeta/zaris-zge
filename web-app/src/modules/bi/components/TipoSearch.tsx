import { useEffect, useRef, useState } from 'react'
import { biApi } from '../lib/api'
import type { TipoReclamoCatalogo } from '../lib/types'

// Buscador con autocompletar del filtro "Tipo de reclamo" (hay 282 tipos: un
// <select> es inusable, §23). Patrón CiudadanoSearch: debounce + dropdown +
// skipNextRef para que el setQ del pick no reabra el dropdown (§29).
export function TipoSearch({
  idArea,
  seleccionado,
  onSelect,
  inputStyle,
}: {
  idArea?: number
  seleccionado?: { id: number; nombre: string }
  onSelect: (t: TipoReclamoCatalogo | null) => void
  inputStyle: React.CSSProperties
}) {
  const [q, setQ] = useState(seleccionado?.nombre ?? '')
  const [open, setOpen] = useState(false)
  const [results, setResults] = useState<TipoReclamoCatalogo[]>([])
  const [buscando, setBuscando] = useState(false)
  const skipNextRef = useRef(false)
  const wrapRef = useRef<HTMLDivElement>(null)

  // Si el padre limpia el filtro (botón Limpiar), vaciar el input.
  useEffect(() => {
    if (!seleccionado) {
      skipNextRef.current = true
      setQ('')
    }
  }, [seleccionado])

  useEffect(() => {
    if (skipNextRef.current) { skipNextRef.current = false; return }
    if (q.trim().length < 2) { setResults([]); setOpen(false); return }
    const h = setTimeout(async () => {
      setBuscando(true)
      try {
        const r = await biApi.buscarTipos(q.trim(), idArea)
        setResults(r)
        setOpen(true)
      } catch {
        setResults([])
      } finally {
        setBuscando(false)
      }
    }, 280)
    return () => clearTimeout(h)
  }, [q, idArea])

  // Click-outside cierra el dropdown.
  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  return (
    <div ref={wrapRef} style={{ position: 'relative', minWidth: 220 }}>
      <input
        value={q}
        placeholder="Todos · escribí para buscar"
        onChange={(e) => {
          setQ(e.target.value)
          if (seleccionado && e.target.value !== seleccionado.nombre) onSelect(null)
        }}
        onFocus={() => { if (results.length) setOpen(true) }}
        style={{ ...inputStyle, width: '100%', paddingRight: seleccionado ? 26 : undefined }}
      />
      {seleccionado && (
        <button
          type="button"
          aria-label="Quitar tipo"
          onClick={() => { skipNextRef.current = true; setQ(''); setResults([]); setOpen(false); onSelect(null) }}
          style={{
            position: 'absolute', right: 6, top: '50%', transform: 'translateY(-50%)',
            border: 'none', background: 'transparent', color: 'var(--fg-3)', cursor: 'pointer', fontSize: 14, lineHeight: 1,
          }}
        >
          ×
        </button>
      )}
      {open && (
        <div
          style={{
            position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 40, marginTop: 4,
            background: 'var(--surface-100)', border: '1px solid var(--border-medium)',
            borderRadius: 8, boxShadow: 'var(--shadow-card)', maxHeight: 260, overflowY: 'auto',
          }}
        >
          {buscando && <div style={itemStyle}>Buscando…</div>}
          {!buscando && !results.length && <div style={itemStyle}>Sin resultados</div>}
          {results.map((t) => (
            <button
              key={t.id_tipo_reclamo}
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => {
                skipNextRef.current = true
                onSelect(t)
                setOpen(false)
                setResults([])
                setQ(t.nombre)
              }}
              style={{ ...itemStyle, width: '100%', textAlign: 'left', border: 'none', background: 'transparent', cursor: 'pointer' }}
            >
              {t.nombre}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

const itemStyle: React.CSSProperties = {
  display: 'block', padding: '7px 10px', fontFamily: 'var(--font-display)', fontSize: '0.82rem', color: 'var(--fg-1)',
}
