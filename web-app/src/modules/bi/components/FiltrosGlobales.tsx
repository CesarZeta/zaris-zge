import { useMemo } from 'react'
import { TipoSearch } from './TipoSearch'
import type { AreaCatalogo, BiFiltros } from '../lib/types'
import { LABEL_CANAL } from '../lib/theme'

// Barra de filtros GLOBALES del Operativo (2026-08-30). Una sola barra gobierna
// todas las secciones y las exportaciones. Decisiones de César:
//  - el ÁREA DE SERVICIO es el selector principal (estas vistas son "para cada
//    área"): va primero, resaltado, con una por defecto; "Todas las áreas" queda
//    como opción explícita.
//  - atajos de AÑO y MES como en Power BI (setean desde/hasta), además del rango
//    manual; y filtros de Estado, Tipo de reclamo (buscador) y Canal.
export const ESTADOS = ['Sin asignar', 'En gestión', 'En espera', 'En auditoría', 'Resuelto', 'Cancelado'] as const
const CANALES = ['web', 'app_movil', 'whatsapp', 'telefono', 'presencial', 'oficio', 'otro', 'sin_dato'] as const

const MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

const pad = (n: number) => String(n).padStart(2, '0')
const ultimoDia = (y: number, m: number) => new Date(y, m, 0).getDate() // m 1..12

export function FiltrosGlobales({
  filtros,
  onChange,
  areas,
  areaDefault,
  permiteTodas,
}: {
  filtros: BiFiltros
  onChange: (f: BiFiltros) => void
  areas: AreaCatalogo[]
  /** Área que se restaura al "Limpiar". */
  areaDefault?: number
  /** Admin: puede elegir "Todas las áreas". */
  permiteTodas: boolean
}) {
  const set = (patch: Partial<BiFiltros>) => onChange({ ...filtros, ...patch })

  const hoy = new Date()
  const anios = useMemo(() => [hoy.getFullYear() - 2, hoy.getFullYear() - 1, hoy.getFullYear()], [hoy])

  // Año/mes "activos" se derivan del rango: año = rango 01-01..12-31; mes = rango
  // completo de ese mes. Así los chips reflejan lo que el rango manual diga.
  const anioActivo = anios.find((y) => filtros.desde === `${y}-01-01` && filtros.hasta === `${y}-12-31`)
    ?? anios.find((y) => filtros.desde?.startsWith(`${y}-`) && filtros.hasta?.startsWith(`${y}-`))
  const mesActivo = (() => {
    if (!filtros.desde || !filtros.hasta) return undefined
    const [y, m, d] = filtros.desde.split('-').map(Number)
    const [y2, m2, d2] = filtros.hasta.split('-').map(Number)
    if (y === y2 && m === m2 && d === 1 && d2 === ultimoDia(y, m)) return m
    return undefined
  })()
  const anioBase = anioActivo ?? hoy.getFullYear()

  const elegirAnio = (y: number) => {
    if (anioActivo === y && !mesActivo) set({ desde: undefined, hasta: undefined })
    else set({ desde: `${y}-01-01`, hasta: `${y}-12-31` })
  }
  const elegirMes = (m: number) => {
    if (mesActivo === m && anioActivo === anioBase) { elegirAnio(anioBase); return }
    set({ desde: `${anioBase}-${pad(m)}-01`, hasta: `${anioBase}-${pad(m)}-${pad(ultimoDia(anioBase, m))}` })
  }

  const hayFiltros = !!(filtros.desde || filtros.hasta || filtros.prioridad || filtros.estado || filtros.id_tipo_reclamo || filtros.canal
    || (filtros.id_area ?? undefined) !== (areaDefault ?? undefined))

  return (
    <div style={wrapStyle}>
      {/* Fila 1: área (principal) + atajos de año/mes */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, alignItems: 'flex-end' }}>
        <div>
          <label style={labelStyle}>Área de servicio</label>
          <select
            value={filtros.id_area ?? ''}
            onChange={(e) => set({ id_area: e.target.value ? Number(e.target.value) : undefined, id_tipo_reclamo: undefined, tipo_nombre: undefined })}
            style={{ ...inputStyle, minWidth: 240, fontWeight: 600, borderColor: 'var(--zaris-orange)' }}
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
              <button key={y} type="button" onClick={() => elegirAnio(y)} style={chipStyle(anioActivo === y)}>{y}</button>
            ))}
          </div>
        </div>
        <div>
          <label style={labelStyle}>Mes {anioActivo ? `(${anioActivo})` : `(${anioBase})`}</label>
          <div style={chipsStyle}>
            {MESES.map((m, i) => (
              <button key={m} type="button" onClick={() => elegirMes(i + 1)} style={chipStyle(mesActivo === i + 1 && anioBase === (anioActivo ?? anioBase))}>{i + 1}</button>
            ))}
          </div>
        </div>
      </div>

      {/* Fila 2: rango manual + estado + prioridad + canal + tipo */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, alignItems: 'flex-end' }}>
        <div>
          <label style={labelStyle}>Desde</label>
          <input type="date" value={filtros.desde ?? ''} onChange={(e) => set({ desde: e.target.value || undefined })} style={inputStyle} />
        </div>
        <div>
          <label style={labelStyle}>Hasta</label>
          <input type="date" value={filtros.hasta ?? ''} onChange={(e) => set({ hasta: e.target.value || undefined })} style={inputStyle} />
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
        {hayFiltros && (
          <button
            type="button"
            onClick={() => onChange({ id_area: areaDefault })}
            style={{ ...inputStyle, cursor: 'pointer', color: 'var(--zaris-orange)', borderColor: 'var(--zaris-orange)', background: 'transparent', fontWeight: 600 }}
          >
            Limpiar
          </button>
        )}
      </div>
    </div>
  )
}

const wrapStyle: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 10,
  background: 'var(--surface-300)', border: '1px solid var(--border-primary)',
  borderRadius: 12, padding: '12px 16px',
}
const inputStyle: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.82rem', padding: '6px 10px',
  border: '1px solid var(--border-medium)', borderRadius: 8,
  background: 'var(--surface-100)', color: 'var(--fg-1)',
}
const labelStyle: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.7rem', textTransform: 'uppercase',
  letterSpacing: '0.04em', color: 'var(--fg-3)', fontWeight: 600, marginBottom: 3, display: 'block',
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
