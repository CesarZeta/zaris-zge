import { ChevronLeft, ChevronRight, RotateCcw, Calendar } from 'lucide-react'
import { useAgendaStore, type FiltroRecurso } from '../store/agendaStore'
import { fromIsoDate, sumarDias, toIsoDate, etiquetaFechaLarga } from '../../../lib/dates'

export function AgendaFilters({ showRecursoFilter = true }: { showRecursoFilter?: boolean }) {
  const fecha     = useAgendaStore((s) => s.fechaActiva)
  const setFecha  = useAgendaStore((s) => s.setFechaActiva)
  const filtro    = useAgendaStore((s) => s.filtroRecurso)
  const setFiltro = useAgendaStore((s) => s.setFiltroRecurso)
  const irAHoy    = useAgendaStore((s) => s.irAHoy)
  const idMun     = useAgendaStore((s) => s.idMunicipio)

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

      {showRecursoFilter && (
        <div style={{ display: 'flex', gap: 4, marginLeft: 'auto' }}>
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

      <div style={{ fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', marginLeft: showRecursoFilter ? 8 : 'auto' }}>
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
