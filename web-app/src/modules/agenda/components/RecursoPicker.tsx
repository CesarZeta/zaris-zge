import { useQuery } from '@tanstack/react-query'
import { listarRecursosAgenda } from '../api/agendaApi'
import type { RecursoItem, TipoRecurso } from '../types/agenda'

interface Props {
  tipo: TipoRecurso
  value: number | null
  onChange: (id: number | null) => void
  idMunicipio?: number
  placeholder?: string
}

/**
 * Selector simple por nombre para agente o equipo. Trae la lista entera (hasta
 * 100) en un <select> nativo. Como son catalogos chicos no hace falta
 * autocompletar; si llegamos a >100 agentes hay que migrar a buscador asincrono.
 */
export function RecursoPicker({ tipo, value, onChange, idMunicipio, placeholder }: Props) {
  const q = useQuery<RecursoItem[]>({
    queryKey: ['agenda', 'recursos', tipo, idMunicipio ?? null],
    queryFn: () => listarRecursosAgenda({ tipo, id_municipio: idMunicipio, limit: 200 }),
    staleTime: 60_000,
  })

  return (
    <select
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
      style={{
        fontFamily: 'var(--font-display)', fontSize: 'var(--size-ui)', color: 'var(--fg-1)',
        padding: '8px 10px', borderRadius: 'var(--radius-md)',
        border: '1px solid var(--border-primary)', background: 'var(--surface-100)',
        outline: 'none', width: '100%',
      }}
    >
      <option value="">{placeholder ?? `-- elegir ${tipo} --`}</option>
      {q.isLoading && <option disabled>cargando...</option>}
      {q.data?.map((r) => (
        <option key={`${r.tipo_recurso}-${r.id_recurso}`} value={r.id_recurso}>
          {r.nombre}
        </option>
      ))}
    </select>
  )
}
