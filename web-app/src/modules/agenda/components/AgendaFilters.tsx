import { ChevronLeft, ChevronRight, RotateCcw, Calendar } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useAgendaStore, type FiltroRecurso } from '../store/agendaStore'
import { fromIsoDate, sumarDias, toIsoDate, etiquetaFechaLarga } from '../../../lib/dates'
import { listarSubareasAgenda } from '../api/agendaApi'
import type { SubareaItem } from '../types/agenda'

export function AgendaFilters({ showRecursoFilter = true, showSubareaFilter = true }: { showRecursoFilter?: boolean; showSubareaFilter?: boolean }) {
  const fecha     = useAgendaStore((s) => s.fechaActiva)
  const setFecha  = useAgendaStore((s) => s.setFechaActiva)
  const filtro    = useAgendaStore((s) => s.filtroRecurso)
  const setFiltro = useAgendaStore((s) => s.setFiltroRecurso)
  const idSub     = useAgendaStore((s) => s.filtroSubarea)
  const setIdSub  = useAgendaStore((s) => s.setFiltroSubarea)
  const irAHoy    = useAgendaStore((s) => s.irAHoy)
  const idMun     = useAgendaStore((s) => s.idMunicipio)

  const subareas = useQuery<SubareaItem[]>({
    queryKey: ['agenda', 'subareas'],
    queryFn: () => listarSubareasAgenda(undefined, 200),
    staleTime: 5 * 60_000,
    enabled: showSubareaFilter,
  })

  const fechaDate = fromIsoDate(fecha)

  function navegar(dias: number) {
    setFecha(toIsoDate(sumarDias(fechaDate, dias)))
  }

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
      padding: '10px 14px', background: 'var(--surface-200)',
      borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-primary)',
    }}>
      <button
        onClick={() => navegar(-1)}
        aria-label="Dia anterior"
        style={navBtnStyle}
      ><ChevronLeft size={16} strokeWidth={1.5} /></button>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Calendar size={14} strokeWidth={1.5} style={{ color: 'var(--fg-3)' }} />
        <input
          type="date"
          value={fecha}
          onChange={(e) => setFecha(e.target.value)}
          style={{
            fontFamily: 'var(--font-mono)', fontSize: 13, padding: '4px 6px',
            border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-md)',
            background: 'var(--surface-100)', color: 'var(--fg-1)', outline: 'none',
          }}
        />
        <span style={{ color: 'var(--fg-3)', fontSize: 12, fontFamily: 'var(--font-display)' }}>
          {etiquetaFechaLarga(fechaDate)}
        </span>
      </div>

      <button
        onClick={() => navegar(1)}
        aria-label="Dia siguiente"
        style={navBtnStyle}
      ><ChevronRight size={16} strokeWidth={1.5} /></button>

      <button
        onClick={irAHoy}
        style={{ ...navBtnStyle, padding: '6px 10px', gap: 6, display: 'inline-flex', alignItems: 'center' }}
      >
        <RotateCcw size={13} strokeWidth={1.5} /> Hoy
      </button>

      {showSubareaFilter && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginLeft: 'auto' }}>
          <label style={{ fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--font-display)', textTransform: 'uppercase', letterSpacing: '.04em' }}>
            Subarea
          </label>
          <select
            value={idSub ?? ''}
            onChange={(e) => setIdSub(e.target.value ? Number(e.target.value) : null)}
            style={{
              fontFamily: 'var(--font-display)', fontSize: 12, padding: '4px 8px',
              border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-md)',
              background: 'var(--surface-100)', color: 'var(--fg-1)', outline: 'none',
              maxWidth: 220,
            }}
          >
            <option value="">todas</option>
            {subareas.data?.map((s) => (
              <option key={s.id_subarea} value={s.id_subarea}>{s.nombre}</option>
            ))}
          </select>
        </div>
      )}

      {showRecursoFilter && (
        <div style={{ display: 'flex', gap: 4, marginLeft: showSubareaFilter ? 0 : 'auto' }}>
          {(['todos', 'agente', 'equipo'] as FiltroRecurso[]).map((opt) => (
            <button
              key={opt}
              onClick={() => setFiltro(opt)}
              style={{
                padding: '6px 12px', borderRadius: 'var(--radius-pill)',
                border: 'none', cursor: 'pointer',
                background: filtro === opt ? 'var(--zaris-dark)' : 'var(--surface-400)',
                color: filtro === opt ? 'var(--zaris-cream)' : 'var(--fg-2)',
                fontFamily: 'var(--font-display)', fontSize: 12,
              }}
            >
              {opt}
            </button>
          ))}
        </div>
      )}

      <div style={{ fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>
        municipio {idMun}
      </div>
    </div>
  )
}

const navBtnStyle: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-md)', padding: 6, cursor: 'pointer',
  color: 'var(--fg-2)', display: 'inline-flex', alignItems: 'center',
}
