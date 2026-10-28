import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Badge, Button } from '../../../ui'
import { useNotificationsStore } from '../../../stores/notifications'
import { ConfirmModal } from '../../agenda/components/ConfirmModal'
import {
  guardarContorno, pasoDelError, previsualizar, quitarContorno, textoOrigen, traerOficial, verContorno,
  type ContornoVista, type DestinoContorno, type PasoInstructivo,
} from './api'
import { InstructivoContorno } from './InstructivoContorno'
import { MapaContorno } from './MapaContorno'

// Contorno del municipio en el alta, la ficha y Configuración (PLAN_CONTORNO_MUNICIPIO_DISENO.md
// §4.6): traer el oficial del IGN o subir un archivo, verlo en el mapa y recién ahí guardarlo. En el
// alta no se guarda: el contorno viaja en el alta misma (onCambioAlta).
type Props =
  | { destino: Extract<DestinoContorno, { modo: 'config' | 'ficha' }>; onGuardado?: () => void }
  | {
      destino: Extract<DestinoContorno, { modo: 'alta' }>
      codigoOficial: string | null
      valor: ContornoVista | null
      onCambio: (c: ContornoVista | null) => void
    }

const MAX_ARCHIVO = 5_000_000
const fecha = (iso?: string | null) => (iso ? new Date(`${iso}T12:00:00`).toLocaleDateString('es-AR') : null)
const n = (v: number) => v.toLocaleString('es-AR')
const enlace: React.CSSProperties = {
  background: 'none', border: 'none', padding: 0, cursor: 'pointer', color: 'var(--zaris-orange)',
  fontFamily: 'inherit', fontSize: 13, textDecoration: 'underline',
}

function Resumen({ v, previa }: { v: ContornoVista; previa?: boolean }) {
  const vertices = previa && v.vertices_antes !== v.vertices_despues
    ? `${n(v.vertices_antes)} → ${n(v.vertices_despues)} vértices` : `${n(v.vertices_despues)} vértices`
  const cargado = !previa && fecha(v.origen?.fecha)
  return (
    <p style={{ margin: 0, fontSize: 13, color: 'var(--fg-2)' }} data-contorno-resumen>
      {v.partes} {v.partes === 1 ? 'parte' : 'partes'} · {vertices} · {n(v.superficie_km2)} km² · {textoOrigen(v.origen)}
      {cargado ? ` · cargado el ${cargado}` : ''}
    </p>
  )
}

export function ContornoMunicipio(props: Props) {
  const { destino } = props
  const esAlta = destino.modo === 'alta'
  const qc = useQueryClient()
  const push = useNotificationsStore((s) => s.push)
  const clave = ['contorno', destino.modo, destino.modo === 'ficha' ? destino.idMunicipio : 0]
  const guardado = useQuery({
    queryKey: clave,
    queryFn: () => verContorno(destino as Extract<DestinoContorno, { modo: 'config' | 'ficha' }>),
    enabled: !esAlta,
  })
  const actual = props.destino.modo === 'alta' ? (props as Extract<Props, { codigoOficial: string | null }>).valor
    : guardado.data?.contorno ?? null
  const codigoOficial = 'codigoOficial' in props ? props.codigoOficial : guardado.data?.codigo_oficial ?? null

  const [cargando, setCargando] = useState(false)
  const [previa, setPrevia] = useState<ContornoVista | null>(null)
  const [error, setError] = useState<{ mensaje: string; paso: PasoInstructivo | null } | null>(null)
  const [reemplazando, setReemplazando] = useState(false)
  const [confirmarQuitar, setConfirmarQuitar] = useState(false)
  const [instructivo, setInstructivo] = useState<{ abierto: boolean; paso?: PasoInstructivo }>({ abierto: false })
  const archivoRef = useRef<HTMLInputElement>(null)

  async function cargar(pedido: () => Promise<ContornoVista>) {
    setCargando(true); setError(null); setPrevia(null)
    try {
      setPrevia(await pedido())
    } catch (e) {
      setError({ mensaje: e instanceof Error ? e.message : String(e), paso: pasoDelError(e) })
    } finally {
      setCargando(false)
    }
  }
  const subir = (f: File) => {
    if (f.size > MAX_ARCHIVO) {
      setPrevia(null)
      setError({ mensaje: 'El archivo pesa más de 5 MB. Simplificalo en QGIS antes de subirlo.', paso: 'tamano' })
      return
    }
    void cargar(async () => previsualizar(destino, await f.text(), f.name))
  }

  const alGuardar = () => {
    qc.invalidateQueries({ queryKey: ['contorno'] })
    if ('onGuardado' in props) props.onGuardado?.()
  }
  const guardar = useMutation({
    mutationFn: (v: ContornoVista) =>
      guardarContorno(destino as Extract<DestinoContorno, { modo: 'config' | 'ficha' }>, JSON.stringify(v.geometria),
        v.origen ?? { via: 'archivo' }),
    onSuccess: () => {
      alGuardar()
      push({ kind: 'success', title: 'Contorno guardado', body: 'La zona de búsqueda de direcciones se recalculó desde el contorno.' })
    },
    onError: (e: Error) => push({ kind: 'error', title: 'No se pudo guardar el contorno', body: e.message }),
  })
  const quitar = useMutation({
    mutationFn: () => quitarContorno(destino as Extract<DestinoContorno, { modo: 'config' | 'ficha' }>),
    onSuccess: () => { alGuardar(); push({ kind: 'success', title: 'Contorno quitado' }) },
    onError: (e: Error) => push({ kind: 'error', title: 'No se pudo quitar el contorno', body: e.message }),
  })

  // Cierra al confirmar; el resultado llega por toast (CLAUDE.md §23).
  const confirmarPrevia = () => {
    const v = previa
    if (!v) return
    setPrevia(null); setReemplazando(false)
    if ('onCambio' in props) props.onCambio(v)
    else guardar.mutate(v)
  }
  const confirmarQuitado = () => {
    setConfirmarQuitar(false)
    if ('onCambio' in props) props.onCambio(null)
    else quitar.mutate()
  }

  const sinOficial = destino.modo === 'alta' && destino.idPartido == null
    ? 'Elegí el partido para traer su contorno oficial.'
    : 'Este municipio no tiene partido con código oficial: subí un archivo.'
  const opciones = (!actual || reemplazando) && !previa

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }} data-contorno>
      {actual && !previa && !reemplazando && (
        <>
          <MapaContorno geometria={actual.geometria} />
          <Resumen v={actual} />
          <div style={{ display: 'flex', gap: 8 }}>
            <Button type="button" onClick={() => setReemplazando(true)}>Reemplazar</Button>
            <Button type="button" variant="ghost" onClick={() => setConfirmarQuitar(true)}>Quitar</Button>
          </div>
        </>
      )}
      {!actual && !previa && !cargando && !guardado.isLoading && (
        <p style={{ margin: 0, fontSize: 13, color: 'var(--fg-2)' }}>Todavía no tiene contorno.</p>
      )}
      {opciones && (
        <>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <Button type="button" variant="primary" data-contorno-oficial disabled={!codigoOficial || cargando}
                    title={codigoOficial ? 'Trae el límite oficial del Instituto Geográfico Nacional' : sinOficial}
                    onClick={() => void cargar(() => traerOficial(destino))}>
              Traer contorno oficial (IGN)
            </Button>
            <Button type="button" disabled={cargando} onClick={() => archivoRef.current?.click()}>Subir archivo…</Button>
            <input ref={archivoRef} type="file" hidden data-contorno-archivo
                   accept=".geojson,.json,application/geo+json,application/json"
                   onChange={(e) => {
                     const f = e.target.files?.[0]
                     e.target.value = ''
                     if (f) subir(f)
                   }} />
            <button type="button" style={enlace} onClick={() => setInstructivo({ abierto: true })}>
              ¿Cómo armo el archivo?
            </button>
            {reemplazando && <Button type="button" variant="ghost" onClick={() => setReemplazando(false)}>Cancelar</Button>}
          </div>
          {!codigoOficial && <p style={{ margin: 0, fontSize: 12, color: 'var(--fg-3)' }}>{sinOficial}</p>}
        </>
      )}
      {cargando && <p style={{ margin: 0, fontSize: 13, color: 'var(--fg-2)' }}>Cargando el contorno…</p>}
      {error && (
        <div role="alert" data-contorno-error
             style={{ padding: '10px 12px', borderRadius: 'var(--radius-md)', fontSize: 13,
                      background: 'var(--surface-300)', borderLeft: '3px solid var(--color-error)', color: 'var(--fg-1)' }}>
          {error.mensaje}{' '}
          {error.paso && (
            <button type="button" style={enlace} onClick={() => setInstructivo({ abierto: true, paso: error.paso! })}>
              Ver cómo arreglarlo
            </button>
          )}
        </div>
      )}
      {previa && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }} data-contorno-previa>
          <MapaContorno geometria={previa.geometria} />
          <Resumen v={previa} previa />
          {[...previa.avisos, ...(previa.aviso_zona ? [previa.aviso_zona] : [])].map((a) => (
            <div key={a}><Badge kind="warn">Atención</Badge> <span style={{ fontSize: 13 }}>{a}</span></div>
          ))}
          <div style={{ display: 'flex', gap: 8 }}>
            <Button type="button" variant="primary" data-contorno-guardar onClick={confirmarPrevia}>
              {esAlta ? 'Usar este contorno' : 'Guardar contorno'}
            </Button>
            <Button type="button" variant="ghost" onClick={() => setPrevia(null)}>Descartar</Button>
          </div>
        </div>
      )}
      <ConfirmModal open={confirmarQuitar} title="Quitar el contorno"
                    message="Los mapas van a encuadrar por la zona de búsqueda. La zona no se borra."
                    confirmLabel="Quitar" danger onConfirm={confirmarQuitado} onCancel={() => setConfirmarQuitar(false)} />
      <InstructivoContorno abierto={instructivo.abierto} paso={instructivo.paso}
                           onCerrar={() => setInstructivo({ abierto: false })} />
    </div>
  )
}
