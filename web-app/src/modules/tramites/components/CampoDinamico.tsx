import { useState, useEffect, useRef } from 'react'
import { Input } from '../../../ui'
import type { TipoTramiteCampo } from '../types'
import { EntitySelect } from './EntitySelect'
import { geoBuscar, type GeoBuscarResult } from '../../../lib/geoNominatim'

interface CampoDinamicoProps {
  campo: TipoTramiteCampo
  value: unknown
  onChange: (nombre: string, valor: unknown) => void
  error?: string
}

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? 'http://127.0.0.1:8000'

const ENDPOINTS: Record<string, { endpoint: string; idField: string; labelField: string; searchParam: string }> = {
  ciudadano: { endpoint: '/api/v1/buc/ciudadanos/buscar', idField: 'id_ciudadano', labelField: 'nombre_completo', searchParam: 'q' },
  empresa:   { endpoint: '/api/v1/buc/empresas/buscar',   idField: 'id_empresa',   labelField: 'nombre',          searchParam: 'q' },
  agente:    { endpoint: '/api/v1/agentes',               idField: 'id_agente',    labelField: 'nombre',          searchParam: 'q' },
  subarea:   { endpoint: '/api/v1/subareas',              idField: 'id_subarea',   labelField: 'nombre',          searchParam: 'q' },
  equipo:    { endpoint: '/api/v1/equipos',               idField: 'id_equipo',    labelField: 'nombre',          searchParam: 'q' },
}

export function CampoDinamico({ campo, value, onChange, error }: CampoDinamicoProps) {
  const { nombre_interno: nombre, etiqueta, tipo_dato, obligatorio, opciones_jsonb, validacion_jsonb, ayuda } = campo

  function set(v: unknown) { onChange(nombre, v) }

  const labelEl = (
    <label style={labelStyle}>
      {etiqueta}
      {obligatorio && <span style={{ color: 'var(--color-error)', marginLeft: 3 }}>*</span>}
    </label>
  )
  const hintEl = ayuda && !error ? <p style={hintStyle}>{ayuda}</p> : null
  const errorEl = error ? <p style={errorStyle}>{error}</p> : null

  let input: React.ReactNode

  /* ── Tipos de entidad con EntitySelect ────────── */
  if (tipo_dato === 'ciudadano' || tipo_dato === 'empresa' || tipo_dato === 'agente' || tipo_dato === 'subarea' || tipo_dato === 'equipo') {
    const cfg = ENDPOINTS[tipo_dato]
    return (
      <div style={fieldWrapStyle}>
        {labelEl}
        <EntitySelect
          endpoint={`${BASE}${cfg.endpoint}`}
          idField={cfg.idField}
          labelField={cfg.labelField}
          searchParam={cfg.searchParam}
          value={typeof value === 'number' ? value : null}
          onChange={(id) => set(id)}
          placeholder={`Buscar ${etiqueta.toLowerCase()}...`}
        />
        {hintEl}
        {errorEl}
      </div>
    )
  }

  /* ── Archivo: diferido a la sección Documentos ─ */
  if (tipo_dato === 'archivo') {
    return (
      <div style={fieldWrapStyle}>
        {labelEl}
        <p style={{ fontSize: 12, color: 'var(--fg-3)', fontFamily: 'var(--font-display)', fontStyle: 'italic', margin: 0 }}>
          Se adjunta tras crear el trámite, en la sección Documentos.
        </p>
      </div>
    )
  }

  /* ── Booleano ──────────────────────────────────── */
  if (tipo_dato === 'booleano') {
    return (
      <div style={fieldWrapStyle}>
        <label style={{ display: 'flex', gap: 10, alignItems: 'center', cursor: 'pointer', fontFamily: 'var(--font-display)', fontSize: 13, color: 'var(--fg-1)' }}>
          <input
            type="checkbox"
            checked={Boolean(value)}
            onChange={(e) => set(e.target.checked)}
            style={{ width: 16, height: 16, cursor: 'pointer' }}
          />
          {etiqueta}
          {obligatorio && <span style={{ color: 'var(--color-error)' }}>*</span>}
        </label>
        {errorEl}
      </div>
    )
  }

  /* ── Selección simple ─────────────────────────── */
  if (tipo_dato === 'seleccion') {
    return (
      <div style={fieldWrapStyle}>
        {labelEl}
        <select
          value={typeof value === 'string' ? value : ''}
          onChange={(e) => set(e.target.value || null)}
          style={selectStyle}
        >
          <option value="">— Seleccionar —</option>
          {(opciones_jsonb ?? []).map((op) => (
            <option key={op.valor} value={op.valor}>{op.etiqueta}</option>
          ))}
        </select>
        {errorEl}
      </div>
    )
  }

  /* ── Selección múltiple ───────────────────────── */
  if (tipo_dato === 'seleccion_multiple') {
    const sel: string[] = Array.isArray(value) ? (value as string[]) : []
    function toggleOp(op: string) {
      if (sel.includes(op)) { set(sel.filter((x) => x !== op)) }
      else { set([...sel, op]) }
    }
    return (
      <div style={fieldWrapStyle}>
        {labelEl}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {(opciones_jsonb ?? []).map((op) => (
            <label key={op.valor} style={{ display: 'flex', gap: 8, alignItems: 'center', cursor: 'pointer', fontSize: 13, fontFamily: 'var(--font-display)', color: 'var(--fg-1)' }}>
              <input
                type="checkbox"
                checked={sel.includes(op.valor)}
                onChange={() => toggleOp(op.valor)}
                style={{ width: 15, height: 15, cursor: 'pointer' }}
              />
              {op.etiqueta}
            </label>
          ))}
        </div>
        {errorEl}
      </div>
    )
  }

  /* ── Texto largo ──────────────────────────────── */
  if (tipo_dato === 'texto_largo') {
    const rows = (validacion_jsonb?.rows as number | undefined) ?? 4
    return (
      <div style={fieldWrapStyle}>
        {labelEl}
        <textarea
          value={typeof value === 'string' ? value : ''}
          onChange={(e) => set(e.target.value)}
          rows={rows}
          maxLength={(validacion_jsonb?.max as number | undefined) ?? undefined}
          style={textareaStyle}
        />
        {hintEl}
        {errorEl}
      </div>
    )
  }

  /* ── Moneda ───────────────────────────────────── */
  if (tipo_dato === 'moneda') {
    return (
      <div style={fieldWrapStyle}>
        {labelEl}
        <div style={{ position: 'relative', width: '100%' }}>
          <span style={{
            position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)',
            color: 'var(--fg-3)', fontFamily: 'var(--font-display)', fontSize: 13, userSelect: 'none',
          }}>$</span>
          <Input
            type="number"
            step="0.01"
            value={typeof value === 'number' ? value : ''}
            onChange={(e) => set(e.target.value ? Number(e.target.value) : null)}
            style={{ paddingLeft: 24 }}
          />
        </div>
        {hintEl}
        {errorEl}
      </div>
    )
  }

  /* ── Fecha y fecha_hora ───────────────────────── */
  if (tipo_dato === 'fecha') {
    input = (
      <Input
        type="date"
        value={typeof value === 'string' ? value : ''}
        onChange={(e) => set(e.target.value || null)}
      />
    )
  } else if (tipo_dato === 'fecha_hora') {
    input = (
      <Input
        type="datetime-local"
        value={typeof value === 'string' ? value : ''}
        onChange={(e) => set(e.target.value || null)}
      />
    )
  } else if (tipo_dato === 'numero') {
    input = (
      <Input
        type="number"
        step="1"
        value={typeof value === 'number' ? value : ''}
        maxLength={(validacion_jsonb?.max as number | undefined) ?? undefined}
        onChange={(e) => set(e.target.value ? Number(e.target.value) : null)}
      />
    )
  } else if (tipo_dato === 'decimal') {
    input = (
      <Input
        type="number"
        step="0.01"
        value={typeof value === 'number' ? value : ''}
        onChange={(e) => set(e.target.value ? Number(e.target.value) : null)}
      />
    )
  } else if (tipo_dato === 'direccion') {
    return (
      <div style={fieldWrapStyle}>
        {labelEl}
        <DireccionOSMInput
          value={typeof value === 'string' ? value : ''}
          onChange={set}
        />
        {hintEl}
        {errorEl}
      </div>
    )
  } else {
    // texto (default)
    input = (
      <Input
        type="text"
        value={typeof value === 'string' ? value : ''}
        maxLength={(validacion_jsonb?.max as number | undefined) ?? 500}
        onChange={(e) => set(e.target.value)}
      />
    )
  }

  return (
    <div style={fieldWrapStyle}>
      {labelEl}
      {input}
      {hintEl}
      {errorEl}
    </div>
  )
}

/* ── Buscador de dirección OSM ────────────────────────────────────────────── */

function DireccionOSMInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [query, setQuery] = useState(value)
  const [resultados, setResultados] = useState<GeoBuscarResult[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const skipRef = useRef(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (skipRef.current) { skipRef.current = false; return }
    if (query.trim().length < 3) { setResultados([]); setOpen(false); return }
    const t = setTimeout(async () => {
      setLoading(true)
      try {
        const res = await geoBuscar(query, 7, true)
        setResultados(res)
        setOpen(res.length > 0)
      } catch { setResultados([]) } finally { setLoading(false) }
    }, 350)
    return () => clearTimeout(t)
  }, [query])

  useEffect(() => {
    function handleOut(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleOut)
    return () => document.removeEventListener('mousedown', handleOut)
  }, [])

  function seleccionar(r: GeoBuscarResult) {
    skipRef.current = true
    setQuery(r.display_name)
    setOpen(false)
    setResultados([])
    onChange(r.display_name)
  }

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%' }}>
      <Input
        type="text"
        value={query}
        onChange={(e) => { setQuery(e.target.value); onChange(e.target.value) }}
        placeholder="Escribí la dirección..."
      />
      {loading && (
        <div style={osmDropdownStyle}>
          <div style={{ padding: '8px 12px', fontSize: 12, color: 'var(--fg-3)', fontFamily: 'var(--font-display)' }}>Buscando…</div>
        </div>
      )}
      {open && resultados.length > 0 && (
        <div style={osmDropdownStyle}>
          {resultados.map((r, i) => (
            <button
              key={i}
              type="button"
              onMouseDown={() => seleccionar(r)}
              style={osmOptionStyle}
            >
              {r.display_name}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

const osmDropdownStyle: React.CSSProperties = {
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

const osmOptionStyle: React.CSSProperties = {
  display: 'block',
  width: '100%',
  padding: '8px 12px',
  fontSize: 12,
  fontFamily: 'var(--font-display)',
  color: 'var(--fg-2)',
  textAlign: 'left',
  border: 'none',
  background: 'transparent',
  cursor: 'pointer',
  lineHeight: 1.4,
}

const fieldWrapStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
}

const labelStyle: React.CSSProperties = {
  fontSize: 12,
  fontWeight: 500,
  color: 'var(--fg-3)',
  fontFamily: 'var(--font-display)',
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
}

const hintStyle: React.CSSProperties = {
  fontSize: 11,
  color: 'var(--fg-3)',
  margin: 0,
  fontFamily: 'var(--font-display)',
}

const errorStyle: React.CSSProperties = {
  fontSize: 11,
  color: 'var(--color-error)',
  margin: 0,
  fontFamily: 'var(--font-display)',
}

const selectStyle: React.CSSProperties = {
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

const textareaStyle: React.CSSProperties = {
  width: '100%',
  padding: '9px 12px',
  border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-lg)',
  background: 'transparent',
  resize: 'vertical',
  fontFamily: 'var(--font-display)',
  fontSize: 13,
  color: 'var(--fg-1)',
  outline: 'none',
  boxSizing: 'border-box',
}
