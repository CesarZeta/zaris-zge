import { useQuery } from '@tanstack/react-query'
import { listarSubareasAgenda } from '../api/agendaApi'
import type { SubareaItem } from '../types/agenda'

// Selector de gestión (subárea) por nombre, agrupado por secretaría. Reemplaza el campo
// numérico «ID subárea» de los formularios de espacio y evento (prueba de cierre de F4+F5).
export function SubareaSelect({ value, onChange, style }: {
  value: number | null
  onChange: (id: number | null) => void
  style?: React.CSSProperties
}) {
  const subareas = useQuery<SubareaItem[]>({
    queryKey: ['agenda', 'subareas'],
    queryFn: () => listarSubareasAgenda(undefined, 200),
    staleTime: 5 * 60_000,
  })
  const lista = subareas.data ?? []
  const areas = [...new Set(lista.map((s) => s.area_nombre || 'Sin secretaría'))]
  // Un valor guardado que no está en la lista (inactiva, otra secretaría) se sigue viendo.
  const huerfano = value != null && subareas.isSuccess && !lista.some((s) => s.id_subarea === value)

  return (
    <select
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
      disabled={subareas.isLoading}
      style={style}
    >
      <option value="">{subareas.isLoading ? 'Cargando…' : 'Sin gestión'}</option>
      {huerfano && <option value={value}>Gestión #{value}</option>}
      {areas.map((a) => (
        <optgroup key={a} label={a}>
          {lista.filter((s) => (s.area_nombre || 'Sin secretaría') === a).map((s) => (
            <option key={s.id_subarea} value={s.id_subarea}>{s.nombre}</option>
          ))}
        </optgroup>
      ))}
    </select>
  )
}
