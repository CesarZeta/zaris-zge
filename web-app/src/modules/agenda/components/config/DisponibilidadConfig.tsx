import { useMemo, useState } from 'react'
import { Plus, Pencil, Trash2 } from 'lucide-react'
import { Button, Badge, EmptyState, Skeleton, Table } from '../../../../ui'
import { useDisponibilidad, useEliminarDisponibilidad } from '../../hooks/useDisponibilidad'
import { useEspacios } from '../../hooks/useEspacios'
import { listarRecursosAgenda } from '../../api/agendaApi'
import { useQuery } from '@tanstack/react-query'
import { format as formatBitmask } from '../../../../lib/diasSemana'
import type { DisponibilidadRecurso, RecursoItem, TipoRecurso } from '../../types/agenda'
import { DisponibilidadFormModal } from './DisponibilidadFormModal'

export function DisponibilidadConfig() {
  const [filtroTipo, setFiltroTipo] = useState<TipoRecurso | 'todos'>('todos')
  const [formOpen, setFormOpen] = useState<{ disp: DisponibilidadRecurso | null } | null>(null)
  const eliminar = useEliminarDisponibilidad()

  const lista = useDisponibilidad(filtroTipo === 'todos' ? undefined : { tipo_recurso: filtroTipo })

  // Mapas para resolver nombre del recurso. Cargo agentes/equipos/espacios en
  // paralelo (cache de RQ los reutiliza si ya estaban cargados).
  const agentes  = useQuery<RecursoItem[]>({ queryKey: ['agenda', 'recursos', 'agente'],  queryFn: () => listarRecursosAgenda({ tipo: 'agente',  limit: 500 }), staleTime: 60_000 })
  const equipos  = useQuery<RecursoItem[]>({ queryKey: ['agenda', 'recursos', 'equipo'],  queryFn: () => listarRecursosAgenda({ tipo: 'equipo',  limit: 500 }), staleTime: 60_000 })
  const espacios = useEspacios()

  const nombreMap = useMemo(() => {
    const m = new Map<string, string>()
    for (const a of agentes.data  ?? []) m.set(`agente-${a.id_recurso}`,  a.nombre)
    for (const e of equipos.data  ?? []) m.set(`equipo-${e.id_recurso}`,  e.nombre)
    for (const sp of espacios.data ?? []) m.set(`espacio-${sp.id_espacio}`, sp.nombre)
    return m
  }, [agentes.data, equipos.data, espacios.data])

  function nombreRecurso(d: DisponibilidadRecurso): string {
    return nombreMap.get(`${d.tipo_recurso}-${d.id_recurso}`) ?? `${d.tipo_recurso} ${d.id_recurso}`
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <p style={{ margin: 0, color: 'var(--fg-3)', fontSize: 13, fontFamily: 'var(--font-display)' }}>
          Horarios laborales por recurso. Multi-rango: podes tener varias filas por recurso para turnos rotativos (vigencia opcional).
        </p>
        <Button variant="accent" icon={<Plus size={14} strokeWidth={1.5} />} onClick={() => setFormOpen({ disp: null })}>
          Nueva disponibilidad
        </Button>
      </div>

      <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
        <span style={{ fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--font-display)', textTransform: 'uppercase', letterSpacing: '.04em' }}>
          Tipo
        </span>
        {(['todos', 'agente', 'equipo', 'espacio'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setFiltroTipo(t)}
            style={{
              padding: '4px 10px', borderRadius: 999,
              border: filtroTipo === t ? '1px solid var(--zaris-orange)' : '1px solid var(--border-primary)',
              background: filtroTipo === t ? 'var(--zaris-orange)' : 'var(--surface-100)',
              color: filtroTipo === t ? '#fff' : 'var(--fg-2)',
              fontFamily: 'var(--font-display)', fontSize: 12, cursor: 'pointer',
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {lista.isLoading && <Skeleton height={200} />}
      {lista.isError && (
        <div style={{ padding: 16, color: 'var(--color-error)', fontFamily: 'var(--font-mono)', fontSize: 13 }}>
          Error: {(lista.error as Error).message}
        </div>
      )}
      {lista.data && lista.data.length === 0 && (
        <EmptyState
          title="Sin disponibilidad configurada"
          description="Cargá los horarios laborales de cada recurso para que la grilla los pinte como habilitados."
        />
      )}
      {lista.data && lista.data.length > 0 && (
        <div style={{ background: 'var(--surface-100)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-primary)', overflow: 'hidden' }}>
          <Table
            keyField="id_disponibilidad"
            rows={lista.data}
            columns={[
              { key: 'tipo_recurso', header: 'Tipo', render: (r) => <Badge kind="neutral">{r.tipo_recurso}</Badge> },
              { key: '_recurso', header: 'Recurso', render: (r) => nombreRecurso(r) },
              { key: 'dias_semana', header: 'Dias', render: (r) => formatBitmask(r.dias_semana) },
              { key: '_horario', header: 'Horario', render: (r) => `${r.hora_inicio.slice(0,5)} a ${r.hora_fin.slice(0,5)}` },
              { key: 'etiqueta', header: 'Etiqueta', render: (r) => r.etiqueta ?? <span style={{ color: 'var(--fg-3)' }}>—</span> },
              {
                key: '_vigencia',
                header: 'Vigencia',
                render: (r) => {
                  if (!r.vigente_desde && !r.vigente_hasta) return <span style={{ color: 'var(--fg-3)' }}>permanente</span>
                  return `${r.vigente_desde ?? '...'} a ${r.vigente_hasta ?? '...'}`
                },
              },
              {
                key: '_acciones',
                header: '',
                width: 160,
                render: (r) => (
                  <div style={{ display: 'flex', gap: 4, justifyContent: 'flex-end' }}>
                    <Button variant="ghost" icon={<Pencil size={13} strokeWidth={1.5} />} onClick={() => setFormOpen({ disp: r })}>
                      Editar
                    </Button>
                    <Button
                      variant="ghost"
                      icon={<Trash2 size={13} strokeWidth={1.5} />}
                      onClick={() => {
                        if (confirm(`Eliminar esta disponibilidad? Esta accion es reversible (baja logica).`)) {
                          eliminar.mutate(r.id_disponibilidad)
                        }
                      }}
                    >
                      Eliminar
                    </Button>
                  </div>
                ),
              },
            ]}
          />
        </div>
      )}

      <DisponibilidadFormModal
        open={formOpen != null}
        onClose={() => setFormOpen(null)}
        disp={formOpen?.disp ?? null}
      />
    </div>
  )
}
