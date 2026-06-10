// Tablero del dispatcher (plan 5.2): eventos abiertos ordenados por prioridad
// y fecha, tiempo transcurrido en vivo, acciones rapidas y polling de 30s.
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, EmptyState, Skeleton } from '../../../ui'
import { useNotificationsStore } from '../../../stores/notifications'
import {
  useCambiarEstado,
  useCerrarEvento,
  useDerivarEvento,
  useEstadosEmergencia,
  useEventosAbiertos,
  useMarcarEnSitio,
  useTiposEmergencia,
} from '../hooks/useEmergencias'
import type { EmergenciaEvento } from '../types'
import { EstadoBadge, PrioridadPill, formatFechaHora, transcurridoDesde, useAhora } from '../lib/ui'
import { CambiarEstadoModal, CerrarModal, DerivarModal } from '../components/EventoAccionModals'

type Accion =
  | { tipo: 'estado'; destino: string; evento: EmergenciaEvento }
  | { tipo: 'derivar'; evento: EmergenciaEvento }
  | { tipo: 'cerrar'; evento: EmergenciaEvento }

export function Dispatcher() {
  const navigate = useNavigate()
  const push = useNotificationsStore((s) => s.push)
  const ahora = useAhora()

  const [fSubarea, setFSubarea] = useState<number | ''>('')
  const [fPrioridad, setFPrioridad] = useState<string>('')
  const [fEstado, setFEstado] = useState<string>('')
  const [accion, setAccion] = useState<Accion | null>(null)

  const abiertos = useEventosAbiertos({ id_subarea: fSubarea === '' ? undefined : fSubarea })
  const tipos = useTiposEmergencia()
  const estados = useEstadosEmergencia()

  const cambiar = useCambiarEstado()
  const derivar = useDerivarEvento()
  const cerrar = useCerrarEvento()
  const enSitio = useMarcarEnSitio()
  const busy = cambiar.isPending || derivar.isPending || cerrar.isPending || enSitio.isPending

  const subareas = useMemo(() => {
    const m = new Map<number, string>()
    for (const t of tipos.data ?? []) m.set(t.id_subarea, t.subarea_nombre ?? `Subárea ${t.id_subarea}`)
    return [...m.entries()].sort((a, b) => a[1].localeCompare(b[1]))
  }, [tipos.data])

  const eventos = useMemo(() => {
    let lista = abiertos.data ?? []
    if (fPrioridad) lista = lista.filter((e) => e.prioridad_codigo === fPrioridad)
    if (fEstado) lista = lista.filter((e) => e.estado_codigo === fEstado)
    return lista
  }, [abiertos.data, fPrioridad, fEstado])

  const onError = (e: unknown) =>
    push({ kind: 'error', title: 'No se pudo aplicar la acción', body: e instanceof Error ? e.message : String(e) })

  const ejecutarAccion = (obsOrBody?: string | { veracidad: string; terminal_positivo: boolean; observaciones_cierre?: string }, idOrg?: number) => {
    if (!accion) return
    const id = accion.evento.id_emergencia_evento
    const done = (msg: string) => () => {
      push({ kind: 'success', title: msg, body: accion.evento.numero_operativo })
      setAccion(null)
    }
    if (accion.tipo === 'estado') {
      cambiar.mutate({ id, nuevo_estado: accion.destino, observaciones: obsOrBody as string | undefined },
        { onSuccess: done(`Evento ${accion.destino.replace(/_/g, ' ')}`), onError })
    } else if (accion.tipo === 'derivar') {
      derivar.mutate({ id, id_organismo: idOrg as number, observaciones: obsOrBody as string | undefined },
        { onSuccess: done('Evento derivado'), onError })
    } else {
      cerrar.mutate({ id, ...(obsOrBody as { veracidad: string; terminal_positivo: boolean; observaciones_cierre?: string }) },
        { onSuccess: done('Evento cerrado'), onError })
    }
  }

  return (
    <div>
      {/* filtros */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', marginBottom: 14 }}>
        <select style={selectStyle} value={fSubarea} onChange={(e) => setFSubarea(e.target.value ? Number(e.target.value) : '')}>
          <option value="">Todas las subáreas</option>
          {subareas.map(([id, nombre]) => <option key={id} value={id}>{nombre}</option>)}
        </select>
        <select style={selectStyle} value={fPrioridad} onChange={(e) => setFPrioridad(e.target.value)}>
          <option value="">Toda prioridad</option>
          <option value="P1">P1</option>
          <option value="P2">P2</option>
          <option value="P3">P3</option>
        </select>
        <select style={selectStyle} value={fEstado} onChange={(e) => setFEstado(e.target.value)}>
          <option value="">Todo estado abierto</option>
          {(estados.data ?? []).filter((s) => !s.es_terminal).map((s) => (
            <option key={s.codigo} value={s.codigo}>{s.nombre}</option>
          ))}
        </select>
        <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>
          {eventos.length} abiertos · refresco cada 30s
        </span>
        <Button variant="accent" onClick={() => navigate('/emergencias/recepcion')}>+ Recibir llamado</Button>
      </div>

      {abiertos.isLoading && <Skeleton height={220} />}
      {abiertos.isError && (
        <EmptyState title="No se pudo cargar el tablero" description={String(abiertos.error)} />
      )}
      {!abiertos.isLoading && !abiertos.isError && eventos.length === 0 && (
        <EmptyState
          title="Sin eventos abiertos"
          description="Cuando se reciba un llamado o un reporte de la App Vecinos, aparece acá."
          action={<Button variant="accent" onClick={() => navigate('/emergencias/recepcion')}>Recibir llamado</Button>}
        />
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {eventos.map((ev) => (
          <div key={ev.id_emergencia_evento} style={cardStyle}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <PrioridadPill codigo={ev.prioridad_codigo} colorToken={ev.prioridad_color_token} />
              <button style={nroBtn} onClick={() => navigate(`/emergencias/evento/${ev.id_emergencia_evento}`)}>
                {ev.numero_operativo}
              </button>
              <EstadoBadge codigo={ev.estado_codigo} nombre={ev.estado_nombre} />
              <span style={{ fontFamily: 'var(--font-display)', fontWeight: 600, color: 'var(--fg-1)' }}>
                {ev.tipo_nombre}{ev.subtipo_nombre ? ` · ${ev.subtipo_nombre}` : ''}
              </span>
              <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--fg-2)' }}>
                {formatFechaHora(ev.fecha_hora_recepcion)} · hace {transcurridoDesde(ev.fecha_hora_recepcion, ahora)}
              </span>
            </div>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginTop: 6, fontSize: 13, color: 'var(--fg-2)' }}>
              <span>{ev.direccion_evento}</span>
              <span>Denunciante: <strong>{ev.denunciante_nombre ?? '—'}</strong></span>
              <span>{ev.subarea_nombre}</span>
              {ev.organismo_nombre && <span>Derivable a: {ev.organismo_nombre}</span>}
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
              <Button onClick={() => navigate(`/emergencias/evento/${ev.id_emergencia_evento}`)}>Ver</Button>
              {ev.estado_codigo === 'PENDIENTE' && (
                <Button onClick={() => setAccion({ tipo: 'estado', destino: 'EN_PREPARACION', evento: ev })}>En preparación</Button>
              )}
              {ev.estado_codigo === 'EN_PREPARACION' && (
                <Button onClick={() => setAccion({ tipo: 'estado', destino: 'EN_CAMINO', evento: ev })}>En camino</Button>
              )}
              {(ev.estado_codigo === 'EN_CAMINO' || ev.estado_codigo === 'DERIVADO') && (
                <Button disabled={busy} onClick={() =>
                  enSitio.mutate(ev.id_emergencia_evento, {
                    onSuccess: () => push({ kind: 'success', title: 'Arribo registrado', body: ev.numero_operativo }),
                    onError,
                  })
                }>En sitio</Button>
              )}
              {ev.estado_codigo !== 'DERIVADO' && (
                <Button onClick={() => setAccion({ tipo: 'derivar', evento: ev })}>Derivar</Button>
              )}
              {['PENDIENTE', 'EN_PREPARACION', 'EN_SITIO', 'DERIVADO'].includes(ev.estado_codigo) && (
                <Button onClick={() => setAccion({ tipo: 'cerrar', evento: ev })}>Cerrar</Button>
              )}
            </div>
          </div>
        ))}
      </div>

      <CambiarEstadoModal
        open={accion?.tipo === 'estado'}
        destino={accion?.tipo === 'estado' ? accion.destino : ''}
        titulo={accion?.tipo === 'estado' ? `${accion.evento.numero_operativo} → ${accion.destino.replace(/_/g, ' ')}` : ''}
        busy={busy}
        onConfirm={(obs) => ejecutarAccion(obs)}
        onCancel={() => setAccion(null)}
      />
      <DerivarModal
        open={accion?.tipo === 'derivar'}
        busy={busy}
        onConfirm={(idOrg, obs) => ejecutarAccion(obs, idOrg)}
        onCancel={() => setAccion(null)}
      />
      <CerrarModal
        open={accion?.tipo === 'cerrar'}
        busy={busy}
        permiteResuelto={accion?.tipo === 'cerrar' && ['EN_SITIO', 'DERIVADO'].includes(accion.evento.estado_codigo)}
        permiteDesestimado={accion?.tipo === 'cerrar' && ['PENDIENTE', 'EN_PREPARACION'].includes(accion.evento.estado_codigo)}
        onConfirm={(body) => ejecutarAccion(body)}
        onCancel={() => setAccion(null)}
      />
    </div>
  )
}

const selectStyle: React.CSSProperties = {
  padding: '7px 10px', border: '1px solid var(--border-medium)', borderRadius: 8,
  background: 'var(--surface-100)', color: 'var(--fg-1)',
  fontFamily: 'var(--font-display)', fontSize: 13,
}
const cardStyle: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 12, padding: '12px 16px',
}
const nroBtn: React.CSSProperties = {
  fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700,
  color: 'var(--zaris-orange)', background: 'transparent', border: 'none',
  cursor: 'pointer', padding: 0, textDecoration: 'underline',
}
