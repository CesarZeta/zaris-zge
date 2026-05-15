import { useMemo } from 'react'
import { ChevronLeft, ChevronRight, RotateCcw } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useCalendarioMes } from '../hooks/useAgenda'
import { useAgendaStore, filtroUIaBackend } from '../store/agendaStore'
import { MonthlyCalendar } from '../components/MonthlyCalendar'
import { Skeleton } from '../../../ui'
import { fromIsoDate } from '../../../lib/dates'
import { listarSubareasAgenda } from '../api/agendaApi'
import type { SubareaItem } from '../types/agenda'

export function MonthlyView() {
  const idMun = useAgendaStore((s) => s.idMunicipio)
  const fecha = useAgendaStore((s) => s.fechaActiva)
  const setFecha = useAgendaStore((s) => s.setFechaActiva)
  const setVistaGrilla = useAgendaStore((s) => s.setVistaGrilla)
  const filtroRec = useAgendaStore((s) => s.filtroRecurso)
  const filtroSubarea = useAgendaStore((s) => s.filtroSubarea)
  const setFiltroSubarea = useAgendaStore((s) => s.setFiltroSubarea)
  const { tipo_recurso } = filtroUIaBackend(filtroRec)

  const subareas = useQuery<SubareaItem[]>({
    queryKey: ['agenda', 'subareas'],
    queryFn: () => listarSubareasAgenda(undefined, 200),
    staleTime: 5 * 60_000,
  })

  const { anio, mes } = useMemo(() => {
    const d = fromIsoDate(fecha)
    return { anio: d.getFullYear(), mes: d.getMonth() + 1 }
  }, [fecha])

  const cal = useCalendarioMes(anio, mes, idMun, tipo_recurso, filtroSubarea)

  function navegar(dx: number) {
    let nm = mes + dx, ny = anio
    if (nm < 1)  { nm = 12; ny-- }
    if (nm > 12) { nm = 1;  ny++ }
    // Mantenemos el dia 1 del mes navegado.
    setFecha(`${ny}-${String(nm).padStart(2, '0')}-01`)
  }

  function irAHoy() {
    const t = new Date()
    setFecha(`${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}-${String(t.getDate()).padStart(2, '0')}`)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
        <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 'var(--size-subhead)', fontWeight: 400, letterSpacing: 'var(--track-subhead)', color: 'var(--fg-1)' }}>
          vista mensual
        </h2>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <label style={{ fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--font-display)', textTransform: 'uppercase', letterSpacing: '.04em' }}>
              Subarea
            </label>
            <select
              value={filtroSubarea ?? ''}
              onChange={(e) => setFiltroSubarea(e.target.value ? Number(e.target.value) : null)}
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
          <div style={{ display: 'flex', gap: 6 }}>
            <button onClick={() => navegar(-1)} aria-label="Mes anterior" style={navBtn}><ChevronLeft size={14} strokeWidth={1.5} /></button>
            <button onClick={irAHoy} style={{ ...navBtn, gap: 6, display: 'inline-flex', alignItems: 'center', padding: '6px 10px' }}>
              <RotateCcw size={13} strokeWidth={1.5} /> Hoy
            </button>
            <button onClick={() => navegar(1)} aria-label="Mes siguiente" style={navBtn}><ChevronRight size={14} strokeWidth={1.5} /></button>
          </div>
        </div>
      </div>
      {cal.isLoading && <Skeleton height={400} />}
      {cal.isError && (
        <div style={{ padding: 16, color: 'var(--color-error)', fontFamily: 'var(--font-mono)', fontSize: 13 }}>
          Error: {(cal.error as Error).message}
        </div>
      )}
      {cal.data && (
        <MonthlyCalendar
          data={cal.data}
          onDiaClick={(fechaIso) => {
            setFecha(fechaIso)
            setVistaGrilla('dia')
          }}
        />
      )}
    </div>
  )
}

const navBtn: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-md)', padding: 6, cursor: 'pointer', color: 'var(--fg-2)',
  display: 'inline-flex', alignItems: 'center',
}
