import { Users, UsersRound, Building2, DoorClosed, MapPin } from 'lucide-react'
import { useAgendaStore } from '../store/agendaStore'
import { useRecursosConteos, useUbicacionesAtencion } from '../hooks/useAgenda'
import type { FiltroRecursoUI, UbicacionAtencionItem } from '../types/agenda'

type Pill = {
  value: FiltroRecursoUI
  label: string
  icon: typeof Users
  conteoKey: 'agentes' | 'equipos' | 'espacios_atendidos' | 'espacios_desatendidos' | null
  // Para qué sirve esta vista — se muestra como subtítulo al seleccionarla.
  proposito: string
}

// Las vistas de Agenda no son intercambiables: cada una sirve a un módulo
// distinto. Las pills lo comunican en el label + el subtítulo.
const PILLS: Pill[] = [
  {
    value: 'ubicacion', label: 'Por ubicación', icon: MapPin, conteoKey: null,
    proposito: 'La agenda de una ubicación de atención: el lugar + los agentes que atienden ahí (mismo enfoque que el módulo Turnos).',
  },
  {
    value: 'agentes', label: 'Agentes', icon: Users, conteoKey: 'agentes',
    proposito: 'Disponibilidad individual de agentes. Base para asignar OT y turnos.',
  },
  {
    value: 'equipos', label: 'Equipos · OT', icon: UsersRound, conteoKey: 'equipos',
    proposito: 'Asignación de Órdenes de Trabajo. Acotado a los equipos de tu subárea (supervisor).',
  },
  {
    value: 'espacios_atendidos', label: 'Esp. atendidos · Turnos', icon: Building2, conteoKey: 'espacios_atendidos',
    proposito: 'Espacios con horario de atención. Base para gestionar Turnos.',
  },
  {
    value: 'espacios_desatendidos', label: 'Esp. eventos · Entradas', icon: DoorClosed, conteoKey: 'espacios_desatendidos',
    proposito: 'Espacios para eventos con cupo. Base para gestionar Entradas.',
  },
]

export function RecursoTogglePills() {
  const filtro = useAgendaStore((s) => s.filtroRecurso)
  const setFiltro = useAgendaStore((s) => s.setFiltroRecurso)
  const ubicacion = useAgendaStore((s) => s.filtroUbicacion)
  const setUbicacion = useAgendaStore((s) => s.setFiltroUbicacion)
  const idMun = useAgendaStore((s) => s.idMunicipio)
  const conteos = useRecursosConteos(idMun)
  // Las ubicaciones se cargan solo cuando el modo 'ubicacion' está activo.
  const ubicaciones = useUbicacionesAtencion(filtro === 'ubicacion')

  const pillActiva = PILLS.find((p) => p.value === filtro)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {PILLS.map((p) => {
          const Icon = p.icon
          const active = filtro === p.value
          const n = p.conteoKey ? conteos.data?.[p.conteoKey] : undefined
          return (
            <button
              key={p.value}
              type="button"
              onClick={() => setFiltro(p.value)}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 6,
                padding: '6px 12px', borderRadius: 999,
                fontFamily: 'var(--font-display)', fontSize: 'var(--size-btn)',
                border: active ? '1px solid var(--zaris-orange)' : '1px solid var(--border-primary)',
                background: active ? 'var(--zaris-orange)' : 'var(--surface-100)',
                color: active ? '#fff' : 'var(--fg-1)',
                cursor: 'pointer',
                transition: 'all 120ms ease',
              }}
            >
              <Icon size={14} strokeWidth={1.5} />
              {p.label}
              {typeof n === 'number' && (
                <span style={{
                  fontSize: 11, opacity: 0.85,
                  padding: '0 6px', borderRadius: 999,
                  background: active ? 'rgba(255,255,255,.2)' : 'var(--surface-300)',
                }}>
                  {n}
                </span>
              )}
            </button>
          )
        })}
      </div>
      {/* Selector de ubicación (solo modo 'ubicacion'): agrupado por gestión. */}
      {filtro === 'ubicacion' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <select
            value={ubicacion?.id ?? ''}
            onChange={(e) => {
              const id = e.target.value === '' ? null : Number(e.target.value)
              const u = (ubicaciones.data ?? []).find((x) => x.id_espacio === id)
              setUbicacion(u ? { id: u.id_espacio, nombre: u.nombre } : null)
            }}
            style={{
              fontFamily: 'var(--font-display)', fontSize: 13, padding: '6px 10px',
              borderRadius: 'var(--radius-md)', border: '1px solid var(--border-medium)',
              background: 'var(--surface-100)', color: 'var(--fg-1)', outline: 'none',
              minWidth: 260,
            }}
          >
            <option value="">Elegí la ubicación…</option>
            {agruparPorGestion(ubicaciones.data ?? []).map(([gestion, items]) => (
              <optgroup key={gestion} label={gestion}>
                {items.map((u) => (
                  <option key={u.id_espacio} value={u.id_espacio}>
                    {u.nombre}{u.agentes > 0 ? ` (${u.agentes} agentes)` : ''}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
          {ubicaciones.isLoading && <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>Cargando ubicaciones…</span>}
          {!ubicaciones.isLoading && (ubicaciones.data ?? []).length === 0 && (
            <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>
              No hay ubicaciones de atención (una ubicación aparece cuando alguna prestación la declara o tiene agentes vinculados).
            </span>
          )}
        </div>
      )}
      {pillActiva && (
        <p style={{
          margin: 0, fontSize: 11, color: 'var(--fg-3)',
          fontFamily: 'var(--font-display)',
        }}>
          {pillActiva.proposito}
        </p>
      )}
    </div>
  )
}

function agruparPorGestion(items: UbicacionAtencionItem[]): [string, UbicacionAtencionItem[]][] {
  const m = new Map<string, UbicacionAtencionItem[]>()
  for (const u of items) {
    const g = u.area_nombre ?? 'Sin gestión asignada'
    if (!m.has(g)) m.set(g, [])
    m.get(g)!.push(u)
  }
  return [...m.entries()]
}
