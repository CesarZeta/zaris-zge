import { useEffect, useMemo, useRef, useState } from 'react'
import { Search } from 'lucide-react'
import { useTiposCatalogo } from '../hooks/useReclamos'
import type { TipoCatalogo } from '../types/reclamo'

interface Props {
  value: number | null
  onChange: (id: number | null, tipo: TipoCatalogo | null) => void
  disabled?: boolean
  placeholder?: string
}

// Picker con input + filtro local. tipo_reclamo tiene ~282 filas en prod
// asi que no hay paginacion ni debounce remoto. El catalogo se cachea HORA.
export function TipoReclamoPicker({ value, onChange, disabled, placeholder = 'Tipear nombre del reclamo...' }: Props) {
  const tipos = useTiposCatalogo()
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // Sincronizar texto cuando value cambia desde afuera (ej. hidratacion en edit)
  useEffect(() => {
    if (!value) { setQ(''); return }
    const t = tipos.data?.find((x) => x.id_tipo_reclamo === value)
    if (t) setQ(t.nombre)
  }, [value, tipos.data])

  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])

  const filtrados = useMemo<TipoCatalogo[]>(() => {
    if (!tipos.data) return []
    const term = q.trim().toLowerCase()
    if (!term) return tipos.data.slice(0, 30)
    return tipos.data.filter((t) =>
      t.nombre.toLowerCase().includes(term) ||
      (t.area_nombre ?? '').toLowerCase().includes(term),
    ).slice(0, 50)
  }, [tipos.data, q])

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%' }}>
      <div style={{ position: 'relative' }}>
        <Search size={14} strokeWidth={1.5} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--fg-3)' }} />
        <input
          value={q}
          onChange={(e) => { setQ(e.target.value); setOpen(true); if (!e.target.value) onChange(null, null) }}
          onFocus={() => setOpen(true)}
          disabled={disabled}
          placeholder={placeholder}
          style={{
            fontFamily: 'var(--font-display)', fontSize: 'var(--size-ui)', width: '100%',
            padding: '9px 12px 9px 32px', borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--border-primary)',
            background: disabled ? 'var(--surface-300)' : 'var(--surface-100)',
            outline: 'none', color: disabled ? 'var(--fg-2)' : 'var(--fg-1)',
            cursor: disabled ? 'not-allowed' : 'text',
          }}
        />
      </div>
      {open && !disabled && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0,
          background: 'var(--surface-100)', borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--border-primary)',
          boxShadow: 'var(--shadow-card, 0 6px 24px rgba(0,0,0,.08))',
          maxHeight: 300, overflowY: 'auto', zIndex: 50,
        }}>
          {tipos.isLoading && (
            <div style={{ padding: 12, color: 'var(--fg-3)', fontSize: 13 }}>Cargando catálogo...</div>
          )}
          {!tipos.isLoading && filtrados.length === 0 && (
            <div style={{ padding: 12, color: 'var(--fg-3)', fontSize: 13 }}>Sin coincidencias.</div>
          )}
          {filtrados.map((t) => (
            <button
              key={t.id_tipo_reclamo}
              onClick={() => {
                onChange(t.id_tipo_reclamo, t)
                setQ(t.nombre)
                setOpen(false)
              }}
              style={{
                display: 'block', width: '100%', textAlign: 'left', padding: '8px 12px',
                background: 'transparent', border: 'none', cursor: 'pointer',
                borderBottom: '1px solid var(--border-primary)',
                fontFamily: 'var(--font-display)',
              }}
            >
              <div style={{ fontSize: 13, color: 'var(--fg-1)', fontWeight: 500 }}>{t.nombre}</div>
              <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
                {t.area_nombre ?? '—'}{t.sla_dias ? ` · SLA ${t.sla_dias}d` : ''}{t.audit ? ' · auditable' : ''}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
