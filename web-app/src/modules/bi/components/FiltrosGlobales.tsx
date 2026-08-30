import { useMemo } from 'react'
import { TipoSearch } from './TipoSearch'
import type { AreaCatalogo, BiFiltros } from '../lib/types'
import { LABEL_CANAL } from '../lib/theme'

// Panel "Filtrado de análisis" del Operativo (2026-08-30). UNA barra gobierna
// todas las secciones y las exportaciones. Decisiones de César:
//  - el ÁREA DE SERVICIO es el selector principal (estas vistas son "para cada
//    área"): va primero, resaltado, con una por defecto; "Todas las áreas" solo admin.
//  - AÑO en chips (uno a la vez) y MESES como tildes independientes (se marcan y
//    desmarcan, solo por color) + casilla "Seleccionar año completo" que
//    marca/desmarca los 12. Los chips viajan como `anio` + `meses`; el rango
//    manual (desde/hasta) es la otra vía: usar una limpia la otra.
//  - Estado, prioridad, canal y tipo de reclamo (buscador).
//  - El panel se puede CONTRAER: contraído muestra un resumen de lo aplicado.
export const ESTADOS = ['Sin asignar', 'En gestión', 'En espera', 'En auditoría', 'Resuelto', 'Cancelado'] as const
const CANALES = ['web', 'app_movil', 'whatsapp', 'telefono', 'presencial', 'oficio', 'otro', 'sin_dato'] as const
const TODOS_LOS_MESES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

// "2026 · año completo" / "2026 · mes 5" / "2026 · meses 5, 6" (mismo criterio que el backend).
export function labelPeriodo(f: BiFiltros): string | undefined {
  const m = f.meses ?? []
  if (f.anio || m.length) {
    const anio = f.anio ?? new Date().getFullYear()
    if (!m.length) return String(anio)
    if (m.length === 12) return `${anio} · año completo`
    return `${anio} · ${m.length === 1 ? 'mes' : 'meses'} ${m.join(', ')}`
  }
  if (f.desde || f.hasta) return `${f.desde ?? '…'} a ${f.hasta ?? '…'}`
  return undefined
}

export function FiltrosGlobales({
  filtros,
  onChange,
  areas,
  areaDefault,
  permiteTodas,
  colapsado,
  onColapsar,
}: {
  filtros: BiFiltros
  onChange: (f: BiFiltros) => void
  areas: AreaCatalogo[]
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

  // Chips → limpian el rango manual. Rango manual → limpia los chips.
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

  const hayFiltros = !!(filtros.desde || filtros.hasta || filtros.anio || meses.length || filtros.prioridad
    || filtros.estado || filtros.id_tipo_reclamo || filtros.canal
    || (filtros.id_area ?? undefined) !== (areaDefault ?? undefined))

  // Resumen de lo aplicado (se muestra contraído).
  const nombreArea = filtros.id_area ? areas.find((a) => a.id_area === filtros.id_area)?.nombre : 'Todas las áreas'
  const resumen = [
    nombreArea ?? '—',
    labelPeriodo(filtros) ?? 'todo el período',
    filtros.estado, filtros.prioridad && `prioridad ${filtros.prioridad}`,
    filtros.canal && (LABEL_CANAL[filtros.canal] ?? filtros.canal),
    filtros.tipo_nombre,
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
        <>
          {/* Fila 1: área (principal) + año + meses */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, alignItems: 'flex-end' }}>
            <div>
              <label style={labelStyle}>Área de servicio</label>
              <select
                value={filtros.id_area ?? ''}
                onChange={(e) => set({ id_area: e.target.value ? Number(e.target.value) : undefined, id_tipo_reclamo: undefined, tipo_nombre: undefined })}
                style={{ ...inputStyle, minWidth: 250, fontWeight: 600, borderColor: 'var(--zaris-orange)', borderWidth: 2 }}
              >
                {permiteTodas && <option value="">Todas las áreas</option>}
                {areas.map((a) => (
                  <option key={a.id_area} value={a.id_area}>{a.nombre}</option>
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
          </div>

          {/* Fila 2: rango manual + estado + prioridad + canal + tipo */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, alignItems: 'flex-end' }}>
            <div>
              <label style={labelStyle}>Desde</label>
              <input type="date" value={filtros.desde ?? ''} onChange={(e) => setRango({ desde: e.target.value || undefined, hasta: filtros.hasta })} style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>Hasta</label>
              <input type="date" value={filtros.hasta ?? ''} onChange={(e) => setRango({ desde: filtros.desde, hasta: e.target.value || undefined })} style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>Estado</label>
              <select value={filtros.estado ?? ''} onChange={(e) => set({ estado: e.target.value || undefined })} style={inputStyle}>
                <option value="">Todos</option>
                {ESTADOS.map((e) => <option key={e} value={e}>{e}</option>)}
              </select>
            </div>
            <div>
              <label style={labelStyle}>Prioridad</label>
              <select value={filtros.prioridad ?? ''} onChange={(e) => set({ prioridad: e.target.value || undefined })} style={inputStyle}>
                <option value="">Todas</option>
                <option value="Alta">Alta</option>
                <option value="Media">Media</option>
                <option value="Baja">Baja</option>
              </select>
            </div>
            <div>
              <label style={labelStyle}>Canal de origen</label>
              <select value={filtros.canal ?? ''} onChange={(e) => set({ canal: e.target.value || undefined })} style={inputStyle}>
                <option value="">Todos</option>
                {CANALES.map((c) => <option key={c} value={c}>{LABEL_CANAL[c] ?? c}</option>)}
              </select>
            </div>
            <div>
              <label style={labelStyle}>Tipo de reclamo</label>
              <TipoSearch
                idArea={filtros.id_area}
                seleccionado={filtros.id_tipo_reclamo ? { id: filtros.id_tipo_reclamo, nombre: filtros.tipo_nombre ?? '' } : undefined}
                onSelect={(t) => set({ id_tipo_reclamo: t?.id_tipo_reclamo, tipo_nombre: t?.nombre })}
                inputStyle={inputStyle}
              />
            </div>
          </div>
        </>
      )}
    </div>
  )
}

// Panel naranja (pedido de César): tinte del brand con borde naranja; los
// controles mantienen su fondo claro para leerse.
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
