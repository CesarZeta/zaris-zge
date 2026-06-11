import { useMemo, useState } from 'react'
import type { Turno } from '../types/turno'

// Filtros compartidos de turnos (Prestación, Recurso agente/lugar, Ciudadano),
// reutilizados por la vista de Turnos (Overview) y la de Agenda (AgendaTurnos).
//
// Las opciones se DERIVAN de los turnos ya cargados (no se traen catálogos
// completos): un <select> de 85 agentes o de miles de ciudadanos es inusable
// (memoria feedback_select_agentes_es_inusable_en_prod). Así el selector solo
// ofrece lo que realmente aparece en pantalla, y el filtrado es client-side
// igual que el buscador de texto del Overview.

export interface TurnoFiltrosState {
  prestacion: string  // id_tipo_prestacion (string) | ''
  recurso: string     // "agente:ID" | "espacio:ID" | ''
  ciudadano: string   // id_ciudadano (string) | ''
  area: string        // prestacion_id_area (string) | '' — area de servicio (informe QA H4)
}

const VACIO: TurnoFiltrosState = { prestacion: '', recurso: '', ciudadano: '', area: '' }

function recursoKey(t: Turno): string | null {
  if (t.recurso_tipo === 'agente' && t.id_agente != null) return `agente:${t.id_agente}`
  if (t.recurso_tipo === 'espacio' && t.id_espacio != null) return `espacio:${t.id_espacio}`
  return null
}

export interface Opcion {
  value: string
  label: string
}

export function useTurnoFiltros(turnos: Turno[]) {
  const [filtros, setFiltros] = useState<TurnoFiltrosState>(VACIO)

  // Opciones únicas presentes en los turnos cargados.
  const opciones = useMemo(() => {
    const prest = new Map<string, string>()
    const rec = new Map<string, string>()
    const ciud = new Map<string, string>()
    const areas = new Map<string, string>()
    for (const t of turnos) {
      if (t.prestacion_nombre) prest.set(String(t.id_tipo_prestacion), t.prestacion_nombre)
      const rk = recursoKey(t)
      if (rk && t.recurso_nombre) rec.set(rk, t.recurso_nombre)
      if (t.ciudadano_nombre) ciud.set(String(t.id_ciudadano), t.ciudadano_nombre)
      if (t.prestacion_id_area != null && t.prestacion_area_nombre) {
        areas.set(String(t.prestacion_id_area), t.prestacion_area_nombre)
      }
    }
    const sort = (m: Map<string, string>): Opcion[] =>
      [...m.entries()].map(([value, label]) => ({ value, label })).sort((a, b) => a.label.localeCompare(b.label))
    return { prestaciones: sort(prest), recursos: sort(rec), ciudadanos: sort(ciud), areas: sort(areas) }
  }, [turnos])

  const filtrar = useMemo(() => (lista: Turno[]): Turno[] => {
    return lista.filter((t) => {
      if (filtros.prestacion && String(t.id_tipo_prestacion) !== filtros.prestacion) return false
      if (filtros.recurso && recursoKey(t) !== filtros.recurso) return false
      if (filtros.ciudadano && String(t.id_ciudadano) !== filtros.ciudadano) return false
      if (filtros.area && String(t.prestacion_id_area ?? '') !== filtros.area) return false
      return true
    })
  }, [filtros])

  const hayActivos = !!(filtros.prestacion || filtros.recurso || filtros.ciudadano || filtros.area)
  const limpiar = () => setFiltros(VACIO)

  return { filtros, setFiltros, opciones, filtrar, hayActivos, limpiar }
}

// --- UI: barra de los 3 selects ---

export function TurnoFiltrosBar({
  opciones, filtros, setFiltros,
}: {
  opciones: { prestaciones: Opcion[]; recursos: Opcion[]; ciudadanos: Opcion[]; areas: Opcion[] }
  filtros: TurnoFiltrosState
  setFiltros: (f: TurnoFiltrosState) => void
}) {
  return (
    <>
      <Select
        label="Prestación"
        value={filtros.prestacion}
        onChange={(v) => setFiltros({ ...filtros, prestacion: v })}
        options={opciones.prestaciones}
        allLabel="Todas"
      />
      <Select
        label="Atiende"
        value={filtros.recurso}
        onChange={(v) => setFiltros({ ...filtros, recurso: v })}
        options={opciones.recursos}
        allLabel="Todos"
      />
      <Select
        label="Ciudadano"
        value={filtros.ciudadano}
        onChange={(v) => setFiltros({ ...filtros, ciudadano: v })}
        options={opciones.ciudadanos}
        allLabel="Todos"
      />
      {/* Area de servicio (informe QA H4): solo se muestra si las prestaciones
          de los turnos cargados tienen area asignada. */}
      {opciones.areas.length > 0 && (
        <Select
          label="Área de servicio"
          value={filtros.area}
          onChange={(v) => setFiltros({ ...filtros, area: v })}
          options={opciones.areas}
          allLabel="Todas"
        />
      )}
    </>
  )
}

function Select({
  label, value, onChange, options, allLabel,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  options: Opcion[]
  allLabel: string
}) {
  return (
    <div style={field}>
      <label style={lbl}>{label}</label>
      <select value={value} onChange={(e) => onChange(e.target.value)} style={inp} disabled={options.length === 0}>
        <option value="">{allLabel}</option>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  )
}

const field: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: 4 }
const lbl: React.CSSProperties = {
  fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--fg-3)',
}
const inp: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: 13, padding: '6px 10px',
  borderRadius: 'var(--radius-md)', border: '1px solid var(--border-primary)',
  background: 'var(--surface-100)', outline: 'none', maxWidth: 200,
}
