import { useEffect, useState, type CSSProperties } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Circle, CircleAlert, Loader2 } from 'lucide-react'
import { Modal } from '../../agenda/components/Modal'
import { Badge, Button } from '../../../ui'
import { useNotificationsStore } from '../../../stores/notifications'
import {
  listarExportaciones, obtenerTarea, pedirExportacion, pedirVaciado, planVaciado, urlDescarga,
  type GrupoVaciable, type MunicipioSuper, type PasoPlan, type Tarea,
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
  const [fallaPedido, setFallaPedido] = useState<string | null>(null)
  const tarea = useTarea(enCurso)
  const terminado = tarea.data?.estado === 'ok' || tarea.data?.estado === 'error'
  const vaciable = (municipio.estado === 'puesta_en_marcha' || municipio.estado === 'demo') && !municipio.fue_produccion
    && !municipio.direccion_base

  useEffect(() => { setPlan(null) }, [grupos])
  useEffect(() => { if (confirmando) setConfirmacion('') }, [confirmando])
  useEffect(() => {
    if (!terminado) return
    qc.invalidateQueries({ queryKey: ['super', 'exportaciones', municipio.id_municipio] })
    onTermino()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- una sola vez por vaciado, al terminar
  }, [terminado])

  const verPlan = useMutation({
    mutationFn: () => planVaciado(municipio.id_municipio, grupos),
    onSuccess: setPlan,
    onError: (e: Error) => push({ kind: 'error', title: 'No se pudo calcular', body: e.message }),
  })
  const vaciar = useMutation({
    mutationFn: () => pedirVaciado(municipio.id_municipio, grupos, confirmacion.trim()),
    onSuccess: (r) => setEnCurso(r.id_tarea),
    onError: (e: Error) => setFallaPedido(e.message),
  })
  const cerrarVentana = () => {
    setEnCurso(null)
    setFallaPedido(null)
    setGrupos([])
    vaciar.reset()
  }

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
      <VentanaVaciado abierta={vaciar.isPending || !!enCurso || fallaPedido !== null} nombre={municipio.nombre}
                      estado={tarea.data} sinRespuesta={tarea.isError} fallaPedido={fallaPedido} onCerrar={cerrarVentana} />
    </section>
  )
}

const plural = (n: number, uno: string, varios: string) => `${n} ${n === 1 ? uno : varios}`

/** Testigo del vaciado (pedido de César, prueba de cierre del 2026-11-03): es una operación que no se
 *  deshace, así que ni la espera ni el resultado pueden depender de un aviso que se va solo. */
function VentanaVaciado({ abierta, nombre, estado, sinRespuesta, fallaPedido, onCerrar }: {
  abierta: boolean
  nombre: string
  estado: Tarea | undefined
  sinRespuesta: boolean
  fallaPedido: string | null
  onCerrar: () => void
}) {
  const exportacion = useTarea(typeof estado?.detalle?.exportacion === 'string' ? estado.detalle.exportacion : null)
  const listo = estado?.estado === 'ok'
  const fallo = fallaPedido !== null || estado?.estado === 'error'
  const corriendo = abierta && !listo && !fallo
  const [segundos, setSegundos] = useState(0)

  useEffect(() => {
    if (!corriendo) return
    setSegundos(0)
    const inicio = Date.now()
    const reloj = setInterval(() => setSegundos(Math.round((Date.now() - inicio) / 1000)), 1000)
    const avisar = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = '' }
    window.addEventListener('beforeunload', avisar)
    // El menú y la barra superior son del shell, fuera de este iframe (CLAUDE.md §14): un clic ahí
    // cambiaría de módulo y haría desaparecer esta ventana con el vaciado corriendo.
    const shell = window.parent === window ? []
      : [...window.parent.document.querySelectorAll<HTMLElement>('.sidebar, .topbar')]
    shell.forEach((el) => { el.style.pointerEvents = 'none'; el.style.opacity = '0.5' })
    return () => {
      clearInterval(reloj)
      window.removeEventListener('beforeunload', avisar)
      shell.forEach((el) => { el.style.pointerEvents = ''; el.style.opacity = '' })
    }
  }, [corriendo])

  const exportada = exportacion.data?.estado === 'ok'
  const plan = (estado?.detalle?.plan ?? []) as PasoPlan[]
  const filas = plan.filter((p) => p.accion === 'borrar').reduce((a, p) => a + p.filas, 0)
  const archivos = Number(estado?.detalle?.archivos ?? 0)
  const noBorrados = Number(estado?.detalle?.archivos_no_borrados ?? 0)
  const motivo = fallaPedido ?? String(estado?.detalle?.error ?? '')

  return (
    <Modal open={abierta} onClose={() => undefined} cerrable={false} width={520}
           title={corriendo ? 'Vaciando datos…' : listo ? 'Vaciado terminado' : 'El vaciado no se hizo'}
           footer={corriendo ? undefined : (
             <Button variant="primary" type="button" onClick={onCerrar}>Cerrar</Button>
           )}>
      <style>{'@keyframes vaciado-giro { to { transform: rotate(360deg) } }'}</style>
      {corriendo && (
        <div style={columna}>
          <p style={avisoFuerte}>No cierres esta ventana ni esta pestaña hasta que termine.</p>
          <PasoVentana estado={exportada ? 'listo' : 'en_curso'} texto="Generar la exportación de resguardo" />
          <PasoVentana estado={exportada ? 'en_curso' : 'espera'} texto={`Borrar los datos de ${nombre}`} />
          <p style={{ margin: 0, fontSize: 13, color: 'var(--fg-2)', fontFamily: 'var(--font-mono)' }}>
            Tiempo transcurrido: {segundos} s
          </p>
          {sinRespuesta && (
            <p style={{ margin: 0, fontSize: 13, color: 'var(--color-error)' }}>
              No pudimos consultar el estado. El proceso sigue en el servidor: seguimos intentando.
            </p>
          )}
        </div>
      )}
      {listo && (
        <div style={columna}>
          <p style={resultado}>
            <Check size={22} strokeWidth={1.5} color="var(--color-success)" style={{ flexShrink: 0 }} />
            Se borraron {plural(filas, 'fila', 'filas')} y {plural(archivos, 'archivo', 'archivos')} de {nombre}.
          </p>
          <p style={{ margin: 0, fontSize: 13, color: 'var(--fg-2)' }}>
            Antes de borrar se guardó una exportación: la podés descargar desde esta ficha durante 90 días.
          </p>
          {noBorrados > 0 && (
            <p style={{ margin: 0, fontSize: 13, color: 'var(--color-error)' }}>
              {plural(noBorrados, 'archivo no se pudo', 'archivos no se pudieron')} borrar del almacenamiento. Los datos ya no están.
            </p>
          )}
        </div>
      )}
      {fallo && (
        <div style={columna}>
          <p style={resultado}>
            <CircleAlert size={22} strokeWidth={1.5} color="var(--color-error)" style={{ flexShrink: 0 }} />
            No se borró nada: los datos siguen como estaban.
          </p>
          {motivo && (
            <p style={{ margin: 0, fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--fg-2)', overflowWrap: 'anywhere', maxHeight: 140, overflowY: 'auto' }}>
              {motivo}
            </p>
          )}
        </div>
      )}
    </Modal>
  )
}

function PasoVentana({ estado, texto }: { estado: 'espera' | 'en_curso' | 'listo'; texto: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 14, color: estado === 'espera' ? 'var(--fg-3)' : 'var(--fg-1)' }}>
      {estado === 'listo' && <Check size={18} strokeWidth={1.5} color="var(--color-success)" style={{ flexShrink: 0 }} />}
      {estado === 'en_curso' && <Loader2 size={18} strokeWidth={1.5} color="var(--zaris-orange)" style={{ flexShrink: 0, animation: 'vaciado-giro 1s linear infinite' }} />}
      {estado === 'espera' && <Circle size={18} strokeWidth={1.5} style={{ flexShrink: 0 }} />}
      {texto}
    </div>
  )
}

const columna: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 12 }
const avisoFuerte: CSSProperties = {
  margin: 0, padding: '10px 12px', fontSize: 14, fontWeight: 600, color: 'var(--fg-1)', background: 'var(--surface-400)',
  borderLeft: '3px solid var(--zaris-orange)', borderRadius: 'var(--radius-md)',
}
const resultado: CSSProperties = { margin: 0, display: 'flex', alignItems: 'center', gap: 10, fontSize: 15, color: 'var(--fg-1)' }
