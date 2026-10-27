import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Modal } from '../../agenda/components/Modal'
import { Badge, Button } from '../../../ui'
import { useNotificationsStore } from '../../../stores/notifications'
import {
  listarExportaciones, obtenerTarea, pedirExportacion, pedirVaciado, planVaciado, urlDescarga,
  type GrupoVaciable, type MunicipioSuper, type PasoPlan,
} from '../api'
import { Casilla } from './AltaMunicipioPage'
import { Campo, input, seccion, subtitulo, tabla, td, th } from './_comun'

// Exportaciones y vaciado de la ficha del municipio (IT-01 F4+F5, Tarea 16; spec §4.7 y §4.8). Las
// dos operaciones corren en segundo plano: la pantalla consulta el estado de la tarea cada 2 s.

const GRUPOS: { codigo: GrupoVaciable; nombre: string; ayuda: string }[] = [
  { codigo: 'operativo', nombre: 'Operativo', ayuda: 'reclamos, OT, turnos, trámites, emergencias, eventos, avisos' },
  { codigo: 'contactos', nombre: 'Contactos', ayuda: 'ciudadanos y empresas, y sus cuentas de la app del vecino' },
  { codigo: 'maestros', nombre: 'Maestros', ayuda: 'catálogos: tipos, subáreas, espacios, prestaciones (las áreas fijas quedan)' },
  { codigo: 'usuarios', nombre: 'Usuarios', ayuda: 'cuentas internas y agentes, salvo el administrador principal' },
]
const NO_VACIABLE = 'Este municipio está o estuvo en producción: sus datos no se pueden vaciar.'
const NO_VACIABLE_BASE = 'El municipio de las direcciones sin prefijo no se puede vaciar.'
const CONFIRMAR = 'Escribí el nombre del municipio para confirmar.'

const fecha = (iso: string | null) => (iso ? new Date(iso).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' }) : '—')

function useTarea(id: string | null) {
  return useQuery({
    queryKey: ['super', 'tarea', id], queryFn: () => obtenerTarea(id!), enabled: !!id,
    refetchInterval: (q) => (q.state.data && ['ok', 'error'].includes(q.state.data.estado) ? false : 2000),
  })
}

export function Exportaciones({ idMun }: { idMun: number }) {
  const qc = useQueryClient()
  const push = useNotificationsStore((s) => s.push)
  const lista = useQuery({ queryKey: ['super', 'exportaciones', idMun], queryFn: () => listarExportaciones(idMun) })
  const [enCurso, setEnCurso] = useState<string | null>(null)
  const tarea = useTarea(enCurso)
  useEffect(() => {
    const e = tarea.data?.estado
    if (e === 'ok' || e === 'error') {
      qc.invalidateQueries({ queryKey: ['super', 'exportaciones', idMun] })
      push(e === 'ok' ? { kind: 'success', title: 'Exportación lista' }
        : { kind: 'error', title: 'La exportación falló', body: String(tarea.data?.detalle?.error ?? '') })
      setEnCurso(null)
    }
  }, [tarea.data, idMun, qc, push])
  const exportar = useMutation({
    mutationFn: () => pedirExportacion(idMun),
    onSuccess: (r) => setEnCurso(r.id_tarea),
    onError: (e: Error) => push({ kind: 'error', title: 'No se pudo exportar', body: e.message }),
  })
  const descargar = useMutation({
    mutationFn: (idTarea: string) => urlDescarga(idMun, idTarea),
    onSuccess: (r) => window.open(r.url, '_blank', 'noopener'),
    onError: (e: Error) => push({ kind: 'error', title: 'No se pudo descargar', body: e.message }),
  })
  return (
    <section style={seccion}>
      <h2 style={subtitulo}>Exportaciones</h2>
      <p style={{ margin: 0, fontSize: 13, color: 'var(--fg-2)' }}>
        Un archivo con todos los datos del municipio. Se guardan 90 días y después se borran solas. Cada
        descarga queda registrada.
      </p>
      <div><Button type="button" disabled={!!enCurso || exportar.isPending} onClick={() => exportar.mutate()}>
        {enCurso ? 'Exportando…' : 'Exportar ahora'}
      </Button></div>
      {(lista.data ?? []).length > 0 && (
        <table style={tabla}>
          <thead><tr><th style={th}>Fecha</th><th style={th}>Vence</th><th style={th}>Estado</th><th style={th} /></tr></thead>
          <tbody>
            {lista.data!.map((e) => (
              <tr key={e.id_tarea}>
                <td style={td}>{fecha(e.fecha_alta)}</td>
                <td style={td}>{fecha(e.vence_en)}</td>
                <td style={td}><Badge kind={e.estado === 'ok' ? 'success' : 'warn'}>{e.estado === 'ok' ? 'lista' : 'en curso'}</Badge></td>
                <td style={{ ...td, textAlign: 'right' }}>
                  {e.estado === 'ok' && (
                    <Button type="button" disabled={descargar.isPending} onClick={() => descargar.mutate(e.id_tarea)}>
                      Descargar
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}

export function Vaciado({ municipio, onTermino }: { municipio: MunicipioSuper; onTermino: () => void }) {
  const qc = useQueryClient()
  const push = useNotificationsStore((s) => s.push)
  const [grupos, setGrupos] = useState<GrupoVaciable[]>([])
  const [plan, setPlan] = useState<PasoPlan[] | null>(null)
  const [confirmando, setConfirmando] = useState(false)
  const [confirmacion, setConfirmacion] = useState('')
  const [enCurso, setEnCurso] = useState<string | null>(null)
  const tarea = useTarea(enCurso)
  const vaciable = (municipio.estado === 'puesta_en_marcha' || municipio.estado === 'demo') && !municipio.fue_produccion
    && !municipio.direccion_base

  useEffect(() => { setPlan(null) }, [grupos])
  useEffect(() => { if (confirmando) setConfirmacion('') }, [confirmando])
  useEffect(() => {
    const e = tarea.data?.estado
    if (e === 'ok' || e === 'error') {
      push(e === 'ok' ? { kind: 'success', title: 'Vaciado terminado' }
        : { kind: 'error', title: 'El vaciado no se hizo', body: String(tarea.data?.detalle?.error ?? '') })
      qc.invalidateQueries({ queryKey: ['super', 'exportaciones', municipio.id_municipio] })
      setEnCurso(null)
      setPlan(null)
      onTermino()
    }
  }, [tarea.data, municipio.id_municipio, qc, push, onTermino])

  const verPlan = useMutation({
    mutationFn: () => planVaciado(municipio.id_municipio, grupos),
    onSuccess: setPlan,
    onError: (e: Error) => push({ kind: 'error', title: 'No se pudo calcular', body: e.message }),
  })
  const vaciar = useMutation({
    mutationFn: () => pedirVaciado(municipio.id_municipio, grupos, confirmacion.trim()),
    onSuccess: (r) => setEnCurso(r.id_tarea),
    onError: (e: Error) => push({ kind: 'error', title: 'No se pudo vaciar', body: e.message }),
  })

  if (!vaciable) {
    return (
      <section style={seccion}>
        <h2 style={subtitulo}>Vaciado de datos</h2>
        <p style={{ margin: 0, fontSize: 13, color: 'var(--fg-2)' }}>
          {municipio.direccion_base ? NO_VACIABLE_BASE : NO_VACIABLE}
        </p>
      </section>
    )
  }
  const totalFilas = (plan ?? []).filter((p) => p.accion === 'borrar').reduce((a, p) => a + p.filas, 0)
  return (
    <section style={seccion}>
      <h2 style={subtitulo}>Vaciado de datos</h2>
      <p style={{ margin: 0, fontSize: 13, color: 'var(--fg-2)' }}>
        Deja el municipio como recién dado de alta: configurado y sin datos. Antes se genera una exportación y,
        si falla, no se borra nada. Nunca se tocan la configuración, las áreas fijas ni el administrador principal.
      </p>
      {GRUPOS.map((g) => (
        <Casilla key={g.codigo} etiqueta={`${g.nombre}: ${g.ayuda}`} marcada={grupos.includes(g.codigo)}
                 onChange={(v) => setGrupos(v ? [...grupos, g.codigo] : grupos.filter((x) => x !== g.codigo))} />
      ))}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <Button type="button" disabled={grupos.length === 0 || verPlan.isPending || !!enCurso} onClick={() => verPlan.mutate()}>
          Ver qué se borra
        </Button>
        <Button type="button" disabled={!plan || !!enCurso} onClick={() => setConfirmando(true)}>
          {enCurso ? 'Vaciando…' : 'Vaciar'}
        </Button>
      </div>
      {plan && (
        plan.length === 0 ? <p style={{ margin: 0, fontSize: 13 }}>No hay nada que borrar en esos grupos.</p> : (
          <table style={tabla} data-plan>
            <thead><tr><th style={th}>Tabla</th><th style={th}>Filas</th><th style={th}>Qué pasa</th></tr></thead>
            <tbody>
              {plan.map((p) => (
                <tr key={`${p.accion}-${p.tabla}`}>
                  <td style={{ ...td, fontFamily: 'var(--font-mono)' }}>{p.tabla}</td>
                  <td style={{ ...td, fontFamily: 'var(--font-mono)' }}>{p.filas}</td>
                  <td style={td}>{p.accion === 'borrar' ? 'se borran' : 'se desvinculan (quedan)'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      )}
      <Modal open={confirmando} onClose={() => setConfirmando(false)} title="Vaciar datos"
             footer={<>
               <Button variant="ghost" type="button" onClick={() => setConfirmando(false)}>Cancelar</Button>
               <Button variant="primary" type="button" disabled={confirmacion.trim() !== municipio.nombre}
                       onClick={() => { vaciar.mutate(); setConfirmando(false) }}>
                 Vaciar {totalFilas} filas
               </Button>
             </>}>
        <Campo etiqueta={CONFIRMAR} ayuda="Se borran las filas del plan. Queda la exportación previa por 90 días.">
          <input style={input} value={confirmacion} placeholder={municipio.nombre}
                 onChange={(e) => setConfirmacion(e.target.value)} />
        </Campo>
      </Modal>
    </section>
  )
}
