import { useMemo } from 'react'
import type { AreaCatalogo, AtPrestacionCatalogo, AtUbicacionCatalogo, BiFiltros } from '../lib/types'
import { periodoEjecutivoDefault } from '../lib/periodo'
import { labelPeriodo } from './FiltrosGlobales'

// Panel "Filtrado de análisis" del tablero de ATENCIÓN (F6, 2026-09-19).
// Jerarquía del plan: GESTIÓN (área) → UBICACIÓN (espacio) → PRESTACIÓN, más el
// período (chips de año, tildes de meses, rango manual). La composición (estado,
// origen) se VE en las visualizaciones, no se filtra (mismo criterio que el
// Ejecutivo). Mismo look que FiltrosGlobales (panel naranja, contraíble).
const TODOS_LOS_MESES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

export function FiltrosAtencion({
  filtros,
  onChange,
  gestiones,
  ubicaciones,
  prestaciones,
  areaDefault,
  permiteTodas,
  colapsado,
  onColapsar,
}: {
  filtros: BiFiltros
  onChange: (f: BiFiltros) => void
  gestiones: AreaCatalogo[]
  /** Ubicaciones (espacios) de la gestión elegida, o todas con su gestión. */
  ubicaciones: AtUbicacionCatalogo[]
  /** Prestaciones de la gestión / ubicación elegida. */
  prestaciones: AtPrestacionCatalogo[]
  /** Gestión que se restaura al "Limpiar". */
  areaDefault?: number
  /** Admin: puede elegir "Todas las gestiones". */
  permiteTodas: boolean
  colapsado: boolean
  onColapsar: (v: boolean) => void
}) {
  const set = (patch: Partial<BiFiltros>) => onChange({ ...filtros, ...patch })

  const anioActual = new Date().getFullYear()
  const anios = useMemo(() => [anioActual - 2, anioActual - 1, anioActual], [anioActual])
  const meses = filtros.meses ?? []
  const anioCompleto = meses.length === 12

  const elegirAnio = (y: number) => {
    if (filtros.anio === y) set({ anio: undefined, desde: undefined, hasta: undefined })
    else set({ anio: y, desde: undefined, hasta: undefined })
  }
  const toggleMes = (m: number) => {
    const nuevo = meses.includes(m) ? meses.filter((x) => x !== m) : [...meses, m].sort((a, b) => a - b)
    set({ meses: nuevo.length ? nuevo : undefined, anio: filtros.anio ?? anioActual, desde: undefined, hasta: undefined })
  }
  const toggleAnioCompleto = () => {
    if (anioCompleto) set({ meses: undefined })
    else set({ meses: TODOS_LOS_MESES, anio: filtros.anio ?? anioActual, desde: undefined, hasta: undefined })
  }
  const setRango = (patch: { desde?: string; hasta?: string }) =>
    set({ ...patch, anio: undefined, meses: undefined })

  // Default (mismo que el Ejecutivo): gestión default + año en curso con el mes
  // anterior tildado. "Limpiar" vuelve a ESO.
  const def: BiFiltros = useMemo(() => ({ id_area: areaDefault, ...periodoEjecutivoDefault() }), [areaDefault])
  const hayFiltros = !!(filtros.desde || filtros.hasta
    || (filtros.anio ?? undefined) !== def.anio
    || meses.join(',') !== (def.meses ?? []).join(',')
    || filtros.id_espacio_ubicacion || filtros.id_tipo_prestacion
    || (filtros.id_area ?? undefined) !== (def.id_area ?? undefined))

  const nombreGestion = filtros.id_area ? gestiones.find((a) => a.id_area === filtros.id_area)?.nombre : 'Todas las gestiones'
  const nombreUbic = filtros.id_espacio_ubicacion
    ? ubicaciones.find((u) => u.id_espacio === filtros.id_espacio_ubicacion)?.nombre
    : undefined
  const nombrePrest = filtros.id_tipo_prestacion
    ? prestaciones.find((p) => p.id_tipo_prestacion === filtros.id_tipo_prestacion)?.nombre
    : undefined
  const resumen = [nombreGestion ?? '—', nombreUbic, nombrePrest, labelPeriodo(filtros) ?? 'todo el período']
    .filter(Boolean).join(' · ')

  // Ubicaciones agrupadas por gestión cuando se ven todas.
  const grupos = useMemo(() => {
    const m = new Map<string, AtUbicacionCatalogo[]>()
    for (const u of ubicaciones) m.set(u.gestion, [...(m.get(u.gestion) ?? []), u])
    return [...m.entries()]
  }, [ubicaciones])

  return (
    <div style={wrapStyle}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <h2 style={tituloStyle}>Filtrado de análisis</h2>
        {colapsado && (
          <span style={{ fontFamily: 'var(--font-display)', fontSize: '0.8rem', color: 'var(--fg-1)', flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={resumen}>
            {resumen}
          </span>
        )}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          {hayFiltros && (
            <button type="button" onClick={() => onChange(def)} style={btnOutlineStyle}>
              Limpiar filtros
            </button>
          )}
          <button type="button" onClick={() => onColapsar(!colapsado)} style={btnOutlineStyle} aria-expanded={!colapsado}>
            {colapsado ? '▾ Mostrar filtros' : '▴ Ocultar filtros'}
          </button>
        </div>
      </div>

      {!colapsado && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, alignItems: 'flex-end' }}>
          <div>
            <label style={labelStyle}>Gestión</label>
            <select
              value={filtros.id_area ?? ''}
              onChange={(e) => set({ id_area: e.target.value ? Number(e.target.value) : undefined, id_espacio_ubicacion: undefined, id_tipo_prestacion: undefined })}
              style={{ ...inputStyle, minWidth: 250, fontWeight: 600, borderColor: 'var(--zaris-orange)', borderWidth: 2 }}
            >
              {permiteTodas && <option value="">Todas las gestiones</option>}
              {gestiones.map((a) => (
                <option key={a.id_area} value={a.id_area}>{a.nombre}</option>
              ))}
            </select>
          </div>
          <div>
            <label style={labelStyle}>Ubicación</label>
            <select
              value={filtros.id_espacio_ubicacion ?? ''}
              onChange={(e) => set({ id_espacio_ubicacion: e.target.value ? Number(e.target.value) : undefined, id_tipo_prestacion: undefined })}
              style={{ ...inputStyle, minWidth: 220 }}
            >
              <option value="">Todas</option>
              {filtros.id_area
                ? ubicaciones.map((u) => <option key={u.id_espacio} value={u.id_espacio}>{u.nombre}</option>)
                : grupos.map(([g, us]) => (
                    <optgroup key={g} label={g}>
                      {us.map((u) => <option key={u.id_espacio} value={u.id_espacio}>{u.nombre}</option>)}
                    </optgroup>
                  ))}
            </select>
          </div>
          <div>
            <label style={labelStyle}>Prestación</label>
            <select
              value={filtros.id_tipo_prestacion ?? ''}
              onChange={(e) => set({ id_tipo_prestacion: e.target.value ? Number(e.target.value) : undefined })}
              style={{ ...inputStyle, minWidth: 220 }}
            >
              <option value="">Todas</option>
              {prestaciones.map((p) => (
                <option key={p.id_tipo_prestacion} value={p.id_tipo_prestacion}>{p.nombre}{p.activo ? '' : ' (baja)'}</option>
              ))}
            </select>
          </div>
          <div>
            <label style={labelStyle}>Año</label>
            <div style={chipsStyle}>
              {anios.map((y) => (
                <button key={y} type="button" onClick={() => elegirAnio(y)} style={chipStyle(filtros.anio === y)}>{y}</button>
              ))}
            </div>
          </div>
          <div>
            <label style={labelStyle}>Meses {filtros.anio ? `de ${filtros.anio}` : `(${anioActual})`}</label>
            <div style={{ ...chipsStyle, alignItems: 'center' }}>
              {TODOS_LOS_MESES.map((m) => (
                <button
                  key={m}
                  type="button"
                  role="checkbox"
                  aria-checked={meses.includes(m)}
                  onClick={() => toggleMes(m)}
                  style={chipStyle(meses.includes(m))}
                  title={meses.includes(m) ? 'Desmarcar mes' : 'Marcar mes'}
                >
                  {m}
                </button>
              ))}
              <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginLeft: 6, fontFamily: 'var(--font-display)', fontSize: '0.78rem', color: 'var(--fg-1)', cursor: 'pointer', fontWeight: 600 }}>
                <input type="checkbox" checked={anioCompleto} onChange={toggleAnioCompleto} />
                Seleccionar año completo
              </label>
            </div>
          </div>
          <div>
            <label style={labelStyle}>Desde</label>
            <input type="date" value={filtros.desde ?? ''} onChange={(e) => setRango({ desde: e.target.value || undefined, hasta: filtros.hasta })} style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>Hasta</label>
            <input type="date" value={filtros.hasta ?? ''} onChange={(e) => setRango({ desde: filtros.desde, hasta: e.target.value || undefined })} style={inputStyle} />
          </div>
        </div>
      )}
    </div>
  )
}

// Mismos estilos del panel del Operativo / Ejecutivo (panel naranja del brand).
const wrapStyle: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 10,
  background: 'rgba(245, 78, 0, 0.10)', border: '2px solid var(--zaris-orange)',
  borderRadius: 12, padding: '8px 16px 12px',
}
const tituloStyle: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.98rem', fontWeight: 700,
  color: 'var(--zaris-orange)', margin: 0, letterSpacing: '0.02em', textTransform: 'uppercase',
}
const inputStyle: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.82rem', padding: '6px 10px',
  border: '1px solid var(--border-medium)', borderRadius: 8,
  background: 'var(--surface-100)', color: 'var(--fg-1)',
}
const btnOutlineStyle: React.CSSProperties = {
  ...inputStyle, cursor: 'pointer', color: 'var(--zaris-orange)', borderColor: 'var(--zaris-orange)',
  background: 'var(--surface-100)', fontWeight: 600,
}
const labelStyle: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.7rem', textTransform: 'uppercase',
  letterSpacing: '0.04em', color: 'var(--fg-2)', fontWeight: 700, marginBottom: 3, display: 'block',
}
const chipsStyle: React.CSSProperties = { display: 'flex', gap: 4, flexWrap: 'wrap' }
function chipStyle(active: boolean): React.CSSProperties {
  return {
    fontFamily: 'var(--font-display)', fontSize: '0.76rem', fontWeight: 600,
    padding: '5px 9px', borderRadius: 6, cursor: 'pointer', minWidth: 30,
    border: `1px solid ${active ? 'var(--zaris-orange)' : 'var(--border-medium)'}`,
    background: active ? 'var(--zaris-orange)' : 'var(--surface-100)',
    color: active ? '#fff' : 'var(--fg-2)',
  }
}
