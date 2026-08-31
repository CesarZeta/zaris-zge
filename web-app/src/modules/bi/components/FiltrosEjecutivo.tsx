import { useMemo } from 'react'
import type { AreaCatalogo, BiFiltros, EjLocalidadCatalogo, EjSubareaCatalogo } from '../lib/types'
import { labelPeriodo } from './FiltrosGlobales'

// Panel "Filtrado de análisis" del EJECUTIVO (2026-08-30). Decisión de César:
// el tablero de conducción filtra por PERÍODO + ÁREA (+ localidad, como los
// tableros VL de referencia); la composición (estado/canal/tipo) se ve en las
// visualizaciones, no se filtra. Mismo look que FiltrosGlobales del Operativo
// (panel naranja, chips de año, tildes de meses, contraíble).
const TODOS_LOS_MESES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

export function FiltrosEjecutivo({
  filtros,
  onChange,
  areas,
  subareas,
  localidades,
  areaDefault,
  permiteTodas,
  colapsado,
  onColapsar,
}: {
  filtros: BiFiltros
  onChange: (f: BiFiltros) => void
  areas: AreaCatalogo[]
  /** Subáreas con reclamos del área elegida (catálogo del Ejecutivo). */
  subareas: EjSubareaCatalogo[]
  /** Localidades con reclamos (catálogo del Ejecutivo). */
  localidades: EjLocalidadCatalogo[]
  /** Área que se restaura al "Limpiar". */
  areaDefault?: number
  /** Admin: puede elegir "Todas las áreas". */
  permiteTodas: boolean
  colapsado: boolean
  onColapsar: (v: boolean) => void
}) {
  const set = (patch: Partial<BiFiltros>) => onChange({ ...filtros, ...patch })

  const anioActual = new Date().getFullYear()
  const anios = useMemo(() => [anioActual - 2, anioActual - 1, anioActual], [anioActual])
  const meses = filtros.meses ?? []
  const anioCompleto = meses.length === 12

  // Chips → limpian el rango manual. Rango manual → limpia los chips (igual Operativo).
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

  const hayFiltros = !!(filtros.desde || filtros.hasta || filtros.anio || meses.length
    || filtros.id_localidad || filtros.id_subarea
    || (filtros.id_area ?? undefined) !== (areaDefault ?? undefined))

  const nombreArea = filtros.id_area ? areas.find((a) => a.id_area === filtros.id_area)?.nombre : 'Todas las áreas'
  const nombreSub = filtros.id_subarea
    ? subareas.find((s) => s.id_subarea === filtros.id_subarea)?.nombre
    : undefined
  const nombreLoc = filtros.id_localidad
    ? localidades.find((l) => l.id_localidad === filtros.id_localidad)?.nombre
    : undefined
  const resumen = [
    nombreArea ?? '—',
    nombreSub,
    labelPeriodo(filtros) ?? 'todo el período',
    nombreLoc,
  ].filter(Boolean).join(' · ')

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
            <button type="button" onClick={() => onChange({ id_area: areaDefault })} style={btnOutlineStyle}>
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
            <label style={labelStyle}>Área de servicio</label>
            <select
              value={filtros.id_area ?? ''}
              onChange={(e) => set({ id_area: e.target.value ? Number(e.target.value) : undefined, id_subarea: undefined })}
              style={{ ...inputStyle, minWidth: 250, fontWeight: 600, borderColor: 'var(--zaris-orange)', borderWidth: 2 }}
            >
              {permiteTodas && <option value="">Todas las áreas</option>}
              {areas.map((a) => (
                <option key={a.id_area} value={a.id_area}>{a.nombre}</option>
              ))}
            </select>
          </div>
          <div>
            <label style={labelStyle}>Subárea</label>
            <select
              value={filtros.id_subarea ?? ''}
              onChange={(e) => set({ id_subarea: e.target.value ? Number(e.target.value) : undefined })}
              style={{ ...inputStyle, minWidth: 180 }}
            >
              <option value="">Todas</option>
              {subareas.map((s) => (
                <option key={s.id_subarea} value={s.id_subarea}>{s.nombre}</option>
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
          <div>
            <label style={labelStyle}>Localidad</label>
            <select
              value={filtros.id_localidad ?? ''}
              onChange={(e) => set({ id_localidad: e.target.value ? Number(e.target.value) : undefined })}
              style={inputStyle}
            >
              <option value="">Todas</option>
              {localidades.map((l) => (
                <option key={l.id_localidad} value={l.id_localidad}>{l.nombre}</option>
              ))}
            </select>
          </div>
        </div>
      )}
    </div>
  )
}

// Mismos estilos del panel del Operativo (§ modulo-bi: panel naranja del brand).
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
