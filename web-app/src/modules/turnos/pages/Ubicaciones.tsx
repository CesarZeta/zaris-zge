import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { ListChecks, MapPin, RefreshCw, Users } from 'lucide-react'
import { useUbicaciones } from '../hooks/useTurnos'
import { useUbicacionTurnosStore } from '../stores/ubicacionTurnos'
import type { UbicacionTurnos } from '../types/turno'

// Landing del módulo Turnos (F2 plan ATENCION): el primer gesto es elegir la
// UBICACIÓN donde se gestiona la atención. Las ubicaciones se agrupan por
// GESTIÓN (el área municipal, vía la subárea del espacio) y muestran los
// contadores de turnos del día.

export function Ubicaciones() {
  const navigate = useNavigate()
  const setUbicacion = useUbicacionTurnosStore((s) => s.setUbicacion)
  const { data, isLoading, isError, error, refetch, isFetching } = useUbicaciones()

  const grupos = useMemo(() => {
    const m = new Map<string, UbicacionTurnos[]>()
    for (const u of data ?? []) {
      const g = u.area_nombre ?? 'Sin gestión asignada'
      if (!m.has(g)) m.set(g, [])
      m.get(g)!.push(u)
    }
    return [...m.entries()]
  }, [data])

  function elegir(u: UbicacionTurnos) {
    setUbicacion({ id_espacio: u.id_espacio, nombre: u.nombre })
    navigate('/turnos/mesa')
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 260 }}>
          <h1 style={titulo}>ubicaciones de atención</h1>
          <p style={{ margin: '6px 0 0', color: 'var(--fg-3)', fontSize: 'var(--size-btn)' }}>
            elegí dónde vas a gestionar la atención. Cada ubicación muestra sus turnos de hoy;
            entrás a su mesa del día con la disponibilidad y la ocupación de cada agente.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => refetch()} style={btnGhost} title="Refrescar">
            <RefreshCw size={14} strokeWidth={1.5} style={{ animation: isFetching ? 'spin 1s linear infinite' : undefined }} />
          </button>
          <button
            onClick={() => { setUbicacion(null); navigate('/turnos/lista') }}
            style={btnGhost}
            title="Ver el listado completo de turnos sin filtrar por ubicación"
          >
            <ListChecks size={14} strokeWidth={1.5} /> Todos los turnos
          </button>
        </div>
      </div>

      {isError && <div style={errorBanner}>{(error as Error)?.message ?? 'Error al cargar las ubicaciones'}</div>}
      {isLoading && <div style={vacio}>Cargando…</div>}
      {!isLoading && !isError && grupos.length === 0 && (
        <div style={vacio}>
          No hay ubicaciones de atención. Una ubicación aparece acá cuando alguna prestación la
          declara como su lugar de atención, o cuando tiene agentes vinculados (Agenda → Espacios).
        </div>
      )}

      {grupos.map(([gestion, ubicaciones]) => (
        <section key={gestion}>
          <h2 style={gestionTitulo}>{gestion}</h2>
          <div style={grid}>
            {ubicaciones.map((u) => (
              <button key={u.id_espacio} onClick={() => elegir(u)} style={cardBtn} title={`Entrar a la mesa del día de ${u.nombre}`}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                  <MapPin size={16} strokeWidth={1.5} style={{ color: 'var(--zaris-orange)', flexShrink: 0, marginTop: 2 }} />
                  <div style={{ minWidth: 0 }}>
                    <div style={cardNombre}>{u.nombre}</div>
                    {u.direccion && <div style={cardMeta}>{u.direccion}</div>}
                    {u.subarea_nombre && <div style={cardMeta}>{u.subarea_nombre}</div>}
                  </div>
                </div>
                <div style={cardFooter}>
                  <span style={metaChip} title="Agentes vinculados a la ubicación">
                    <Users size={12} strokeWidth={1.5} /> {u.agentes}
                  </span>
                  <span style={metaChip} title="Prestaciones que se atienden acá">
                    {u.prestaciones} prest.
                  </span>
                  <span style={{ flex: 1 }} />
                  <span style={{ ...countChip, background: 'rgba(245,127,23,0.14)', color: '#b35900' }} title="Turnos reservados hoy">
                    {u.reservados} res.
                  </span>
                  <span style={{ ...countChip, background: 'rgba(31,138,101,0.16)', color: '#1f8a65' }} title="Turnos cumplidos hoy">
                    {u.cumplidos} cump.
                  </span>
                </div>
              </button>
            ))}
          </div>
        </section>
      ))}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

const titulo: React.CSSProperties = {
  margin: 0, fontFamily: 'var(--font-display)', fontSize: 'var(--size-section)',
  fontWeight: 400, letterSpacing: 'var(--track-section)', color: 'var(--fg-1)',
}
const gestionTitulo: React.CSSProperties = {
  margin: '0 0 10px', fontFamily: 'var(--font-display)', fontSize: '0.78rem',
  fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--fg-2)',
  borderBottom: '1px solid var(--border-primary)', paddingBottom: 6,
}
const grid: React.CSSProperties = {
  display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12,
}
const cardBtn: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 12, textAlign: 'left',
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 12, padding: 14, cursor: 'pointer',
  fontFamily: 'var(--font-display)', color: 'var(--fg-1)',
}
const cardNombre: React.CSSProperties = {
  fontSize: '0.95rem', fontWeight: 600, color: 'var(--fg-1)',
  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
}
const cardMeta: React.CSSProperties = { fontSize: '0.74rem', color: 'var(--fg-3)', marginTop: 2 }
const cardFooter: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', width: '100%',
}
const metaChip: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 4,
  fontSize: '0.72rem', color: 'var(--fg-2)', background: 'var(--surface-300)',
  padding: '2px 8px', borderRadius: 999,
}
const countChip: React.CSSProperties = {
  fontSize: '0.72rem', fontWeight: 600, padding: '2px 8px', borderRadius: 999,
}
const btnGhost: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.82rem', cursor: 'pointer',
  borderRadius: 8, padding: '7px 12px', fontWeight: 500,
  background: 'transparent', color: 'var(--fg-2)', border: '1px solid var(--border-medium)',
  display: 'inline-flex', alignItems: 'center', gap: 6,
}
const vacio: React.CSSProperties = {
  color: 'var(--fg-3)', fontSize: '0.88rem', textAlign: 'center', padding: 40,
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)', borderRadius: 12,
}
const errorBanner: React.CSSProperties = {
  background: '#ffebee', border: '1px solid #ffcdd2', borderLeft: '4px solid var(--color-error)',
  borderRadius: 8, padding: '12px 16px', color: '#c62828', fontSize: '0.86rem',
}
