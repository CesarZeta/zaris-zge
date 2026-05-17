import { useState, useEffect, useRef, useCallback } from 'react'
import { api } from '../../../lib/api'
import { Input } from '../../../ui'

interface EntityOption {
  id: number
  label: string
}

interface EntitySelectProps {
  endpoint: string
  searchParam?: string
  idField?: string
  labelField?: string
  value: number | null
  onChange: (id: number | null, label: string) => void
  placeholder?: string
  disabled?: boolean
}

export function EntitySelect({
  endpoint,
  searchParam = 'q',
  idField = 'id',
  labelField = 'nombre',
  value,
  onChange,
  placeholder = 'Buscar...',
  disabled = false,
}: EntitySelectProps) {
  const [query, setQuery] = useState('')
  const [resultados, setResultados] = useState<EntityOption[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [degradado, setDegradado] = useState(false)
  const skipRef = useRef(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const buscar = useCallback(
    async (q: string) => {
      if (q.trim().length < 2) { setResultados([]); setOpen(false); return }
      setLoading(true)
      try {
        const res = await api.get<unknown[]>(endpoint, { params: { [searchParam]: q, limit: 20 } })
        setResultados(
          res.map((item) => {
            const r = item as Record<string, unknown>
            return { id: r[idField] as number, label: r[labelField] as string }
          }),
        )
        setOpen(true)
        setDegradado(false)
      } catch (err) {
        const e = err as Error
        if (e.message.includes('404') || e.message.includes('Not Found')) {
          setDegradado(true)
        }
        setResultados([])
        setOpen(false)
      } finally {
        setLoading(false)
      }
    },
    [endpoint, searchParam, idField, labelField],
  )

  useEffect(() => {
    if (skipRef.current) { skipRef.current = false; return }
    if (!query) { setResultados([]); setOpen(false); return }
    const t = setTimeout(() => { void buscar(query) }, 300)
    return () => clearTimeout(t)
  }, [query, buscar])

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  function seleccionar(opt: EntityOption) {
    skipRef.current = true
    setQuery(opt.label)
    setOpen(false)
    setResultados([])
    onChange(opt.id, opt.label)
  }

  function limpiar() {
    setQuery('')
    onChange(null, '')
    setOpen(false)
  }

  if (degradado) {
    return (
      <input
        placeholder="Ingrese el ID (endpoint no disponible)"
        style={inputStyle}
        type="number"
        disabled={disabled}
        onChange={(e) => {
          const v = parseInt(e.target.value)
          if (!isNaN(v)) onChange(v, `ID: ${v}`)
        }}
      />
    )
  }

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%' }}>
      <div style={{ display: 'flex', gap: 6 }}>
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder}
          disabled={disabled}
          style={{ flex: 1 }}
        />
        {value != null && (
          <button onClick={limpiar} style={clearBtnStyle} type="button" title="Limpiar selección">
            ×
          </button>
        )}
      </div>
      {loading && (
        <div style={dropdownStyle}>
          <div style={dropdownItemStyle}>Buscando...</div>
        </div>
      )}
      {open && resultados.length > 0 && (
        <div style={dropdownStyle}>
          {resultados.map((opt) => (
            <button
              key={opt.id}
              type="button"
              style={{ ...dropdownItemStyle, ...dropdownBtnStyle }}
              onMouseDown={() => seleccionar(opt)}
            >
              {opt.label}
              <span style={{ color: 'var(--fg-3)', fontSize: 11, marginLeft: 'auto' }}>
                #{opt.id}
              </span>
            </button>
          ))}
        </div>
      )}
      {open && !loading && resultados.length === 0 && query.length >= 2 && (
        <div style={dropdownStyle}>
          <div style={dropdownItemStyle}>Sin resultados</div>
        </div>
      )}
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  fontFamily: 'var(--font-display)',
  fontSize: 'var(--size-ui)',
  color: 'var(--fg-1)',
  background: 'transparent',
  padding: '9px 12px',
  border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-lg)',
  outline: 'none',
  width: '100%',
}

const dropdownStyle: React.CSSProperties = {
  position: 'absolute',
  top: '100%',
  left: 0,
  right: 0,
  marginTop: 4,
  background: 'var(--surface-100)',
  border: '1px solid var(--border-medium)',
  borderRadius: 'var(--radius-lg)',
  boxShadow: 'var(--shadow-card)',
  zIndex: 100,
  maxHeight: 240,
  overflowY: 'auto',
}

const dropdownItemStyle: React.CSSProperties = {
  padding: '8px 12px',
  fontSize: 13,
  fontFamily: 'var(--font-display)',
  color: 'var(--fg-2)',
}

const dropdownBtnStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  width: '100%',
  border: 'none',
  background: 'transparent',
  cursor: 'pointer',
  textAlign: 'left',
}

const clearBtnStyle: React.CSSProperties = {
  background: 'var(--surface-400)',
  border: 'none',
  borderRadius: 'var(--radius-lg)',
  width: 36,
  fontSize: 18,
  color: 'var(--fg-3)',
  cursor: 'pointer',
  flexShrink: 0,
}
