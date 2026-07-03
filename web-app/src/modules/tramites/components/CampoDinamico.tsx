import { useState, useEffect, useRef } from 'react'
import { Input } from '../../../ui'
import type { TipoTramiteCampo } from '../types'
import { EntitySelect } from './EntitySelect'
import { geoBuscar, geoReverse, type GeoBuscarResult } from '../../../lib/geoNominatim'
import { MapaPicker } from '../../reclamos/components/MapaPicker'

interface CampoDinamicoProps {
  campo: TipoTramiteCampo
  value: unknown
  onChange: (nombre: string, valor: unknown) => void
  error?: string
}

const ENDPOINTS: Record<string, { endpoint: string; idField: string; labelField: string; searchParam: string }> = {
  ciudadano: { endpoint: '/api/v1/buc/ciudadanos/buscar', idField: 'id_ciudadano', labelField: 'nombre_completo', searchParam: 'q' },
  empresa:   { endpoint: '/api/v1/buc/empresas/buscar',   idField: 'id_empresa',   labelField: 'nombre',          searchParam: 'q' },
  agente:    { endpoint: '/api/v1/agentes',               idField: 'id_agente',    labelField: 'nombre',          searchParam: 'q' },
  subarea:   { endpoint: '/api/v1/subareas',              idField: 'id_subarea',   labelField: 'nombre',          searchParam: 'q' },
  equipo:    { endpoint: '/api/v1/equipos',               idField: 'id_equipo',    labelField: 'nombre',          searchParam: 'q' },
}

/**
 * Normaliza `opciones_jsonb` a `{valor, etiqueta}[]` tolerando shapes legacy.
 * Tipos seedeados viejos guardaron `{ opciones: ["a","b"] }` o un array de strings,
 * mientras que el editor nuevo produce `[{valor, etiqueta}]`. Sin esto, `.map` revienta.
 */
function normalizarOpciones(raw: unknown): Array<{ valor: string; etiqueta: string }> {
  let arr: unknown = raw
  if (raw && !Array.isArray(raw) && typeof raw === 'object' && 'opciones' in (raw as object)) {
    arr = (raw as { opciones: unknown }).opciones
  }
  if (!Array.isArray(arr)) return []
  return arr
    .map((op) => {
      if (op && typeof op === 'object' && 'valor' in op) {
        const o = op as { valor: unknown; etiqueta?: unknown }
        return { valor: String(o.valor), etiqueta: String(o.etiqueta ?? o.valor) }
      }
      return { valor: String(op), etiqueta: String(op) }
    })
    .filter((o) => o.valor !== 'undefined' && o.valor !== '')
}

export function CampoDinamico({ campo, value, onChange, error }: CampoDinamicoProps) {
  const { nombre_interno: nombre, etiqueta, tipo_dato, obligatorio, opciones_jsonb, validacion_jsonb, ayuda } = campo
  const opciones = normalizarOpciones(opciones_jsonb)

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
          endpoint={cfg.endpoint}
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
          {opciones.map((op) => (
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
          {opciones.map((op) => (
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
          value={value}
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

// Shape nuevo del valor persistido para tipo_dato='direccion' (2026-07-02):
// {texto, lat, lon} — permite geoposicionar el trámite en el mapa del Dashboard.
// Retro-compat: los trámites viejos guardan string plano; este input lo acepta
// y emite string mientras NO haya pin, y el objeto completo cuando lo hay.
interface DireccionValor { texto: string; lat: number; lon: number }

function parseDireccion(value: unknown): { texto: string; coords: { lat: number; lon: number } | null } {
  if (typeof value === 'string') return { texto: value, coords: null }
  if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
    const v = value as Partial<DireccionValor>
    const texto = typeof v.texto === 'string' ? v.texto : ''
    const coords = typeof v.lat === 'number' && typeof v.lon === 'number'
      ? { lat: v.lat, lon: v.lon }
      : null
    return { texto, coords }
  }
  return { texto: '', coords: null }
}

function DireccionOSMInput({ value, onChange }: { value: unknown; onChange: (v: string | DireccionValor) => void }) {
  const inicial = parseDireccion(value)
  const [query, setQuery] = useState(inicial.texto)
  const [resultados, setResultados] = useState<GeoBuscarResult[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(inicial.coords)
  const skipRef = useRef(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // Con pin → objeto {texto, lat, lon}; sin pin → string plano (retro-compat).
  function emit(texto: string, c: { lat: number; lon: number } | null) {
    onChange(c ? { texto, lat: c.lat, lon: c.lon } : texto)
  }

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
    const c = r.lat != null && r.lon != null ? { lat: r.lat, lon: r.lon } : null
    if (c) setCoords(c)
    emit(r.display_name, c ?? coords)
  }

  // Geocodifica el texto actual y abre el mapa (para corregir el pin cuando la
  // dirección se tipeó a mano o vino precargada, sin elegir una sugerencia).
  async function verEnMapa() {
    if (query.trim().length < 3) return
    setLoading(true)
    try {
      const res = await geoBuscar(query, 1, true)
      if (res[0]?.lat != null && res[0]?.lon != null) {
        const c = { lat: res[0].lat, lon: res[0].lon }
        setCoords(c)
        emit(query, c)
      }
    } catch { /* sin resultado, no abre el mapa */ } finally { setLoading(false) }
  }

  // Al arrastrar/clickear el pin: geocoding inverso → reescribe el texto con la
  // dirección corregida. Best-effort: si falla, deja el pin movido y el texto previo.
  async function onPinChange(lat: number, lon: number) {
    const c = { lat, lon }
    setCoords(c)
    try {
      const rev = await geoReverse(lat, lon)
      if (rev.display_name) {
        skipRef.current = true
        setQuery(rev.display_name)
        emit(rev.display_name, c)
        return
      }
    } catch { /* sin reverse, conserva el texto actual */ }
    emit(query, c)
  }

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%' }}>
      <Input
        type="text"
        value={query}
        onChange={(e) => { setQuery(e.target.value); emit(e.target.value, coords) }}
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
      {!coords && query.trim().length >= 3 && (
        <button
          type="button"
          onClick={() => { void verEnMapa() }}
          style={verMapaBtnStyle}
        >
          Ver en el mapa para ajustar la ubicación
        </button>
      )}
      {coords && (
        <div style={{ marginTop: 8 }}>
          <MapaPicker
            lat={coords.lat}
            lon={coords.lon}
            onChange={(la, lo) => { void onPinChange(la, lo) }}
            height={240}
          />
          <p style={{ fontSize: 11, color: 'var(--fg-3)', margin: '6px 0 0', fontFamily: 'var(--font-display)' }}>
            Si la ubicación no es correcta, arrastrá el pin o hacé clic en el mapa para ajustarla.
          </p>
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

const verMapaBtnStyle: React.CSSProperties = {
  marginTop: 6,
  alignSelf: 'flex-start',
  background: 'transparent',
  border: 'none',
  padding: 0,
  color: 'var(--zaris-orange)',
  fontSize: 12,
  fontFamily: 'var(--font-display)',
  fontWeight: 500,
  cursor: 'pointer',
  textDecoration: 'underline',
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
