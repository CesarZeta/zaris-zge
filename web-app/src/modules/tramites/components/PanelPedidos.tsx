import { Download } from 'lucide-react'
import type { PedidoTramite } from '../types'
import { descargarDocumentoBlob } from '../lib/api'
import { useNotificationsStore } from '../../../stores/notifications'

/** Pedidos del municipio al vecino y sus respuestas (mig 139). El abierto va primero. */
export function PanelPedidos({
  numero, pedidos, puedeCancelar, onCancelar,
}: {
  numero: string
  pedidos: PedidoTramite[]
  puedeCancelar: boolean
  onCancelar: (p: PedidoTramite) => void
}) {
  const push = useNotificationsStore((s) => s.push)
  const ordenados = [...pedidos].sort((a, b) => {
    if (a.estado === 'abierto' && b.estado !== 'abierto') return -1
    if (b.estado === 'abierto' && a.estado !== 'abierto') return 1
    return new Date(b.fecha_pedido).getTime() - new Date(a.fecha_pedido).getTime()
  })

  async function descargar(idDoc: number) {
    try {
      const { objectUrl } = await descargarDocumentoBlob(numero, idDoc)
      window.open(objectUrl, '_blank', 'noopener')
    } catch (e) {
      push({ kind: 'error', title: 'No se pudo abrir el archivo', body: e instanceof Error ? e.message : undefined })
    }
  }

  return (
    <section style={cardStyle}>
      <h2 style={cardTitleStyle}>Pedidos al vecino</h2>
      {ordenados.length === 0 ? (
        <p style={vacioStyle}>Todavía no se le pidió nada al vecino.</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {ordenados.map((p) => (
            <div key={p.id_tramite_pedido} style={p.estado === 'abierto' ? filaAbiertaStyle : filaStyle}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'flex-start' }}>
                <p style={metaStyle}>
                  <strong style={{ color: colorEstado(p.estado) }}>{ETIQUETA_ESTADO[p.estado]}</strong>
                  {' · '}{fecha(p.fecha_pedido)}{p.agente_pide ? ` · pidió ${p.agente_pide}` : ''}
                  {p.pide_archivo ? ' · con archivo obligatorio' : ''}
                </p>
                {p.estado === 'abierto' && puedeCancelar && (
                  <button type="button" onClick={() => onCancelar(p)} style={btnSmallStyle}>Cancelar pedido</button>
                )}
              </div>
              <p style={textoStyle}>{p.texto}</p>

              {p.estado === 'respondido' && (
                <div style={respuestaStyle}>
                  <p style={metaStyle}>Respuesta del vecino · {fecha(p.fecha_respuesta)}</p>
                  <p style={textoStyle}>{p.respuesta_texto}</p>
                  {p.documentos_respuesta.map((d) => (
                    d.binario_purgado ? (
                      <p key={d.id_tramite_documento} style={metaStyle}>{d.nombre_archivo_original ?? d.nombre} · Archivo depurado</p>
                    ) : (
                      <button key={d.id_tramite_documento} type="button" onClick={() => { void descargar(d.id_tramite_documento) }} style={btnSmallStyle}>
                        <Download size={13} strokeWidth={1.5} /> {d.nombre_archivo_original ?? d.nombre}
                      </button>
                    )
                  ))}
                </div>
              )}
              {p.estado === 'cancelado' && p.motivo_cancelacion && (
                <p style={metaStyle}>Motivo: {p.motivo_cancelacion}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

const ETIQUETA_ESTADO: Record<PedidoTramite['estado'], string> = {
  abierto: 'Esperando al vecino', respondido: 'Respondido', cancelado: 'Cancelado',
}
function colorEstado(e: PedidoTramite['estado']): string {
  if (e === 'abierto') return 'var(--zaris-gold)'
  if (e === 'respondido') return 'var(--color-success)'
  return 'var(--fg-3)'
}
function fecha(iso: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

const cardStyle: React.CSSProperties = {
  background: 'var(--surface-100)', borderRadius: 'var(--radius-xl)', border: '1px solid var(--border-primary)', padding: 20,
}
const cardTitleStyle: React.CSSProperties = {
  margin: '0 0 14px', fontSize: 14, fontWeight: 600, fontFamily: 'var(--font-display)', color: 'var(--fg-1)',
}
const vacioStyle: React.CSSProperties = { margin: 0, fontSize: 13, color: 'var(--fg-3)', fontFamily: 'var(--font-display)' }
const filaStyle: React.CSSProperties = {
  padding: '10px 12px', background: 'var(--surface-300)', borderRadius: 'var(--radius-lg)',
  display: 'flex', flexDirection: 'column', gap: 6,
}
const filaAbiertaStyle: React.CSSProperties = {
  ...filaStyle, background: 'var(--surface-400)', boxShadow: 'inset 3px 0 0 var(--zaris-gold)',
}
const respuestaStyle: React.CSSProperties = {
  marginTop: 4, paddingTop: 8, borderTop: '1px solid var(--border-primary)',
  display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'flex-start',
}
const metaStyle: React.CSSProperties = { margin: 0, fontSize: 12, color: 'var(--fg-3)', fontFamily: 'var(--font-display)' }
const textoStyle: React.CSSProperties = {
  margin: 0, fontSize: 13, color: 'var(--fg-1)', fontFamily: 'var(--font-display)', whiteSpace: 'pre-wrap',
}
const btnSmallStyle: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 4, padding: '5px 10px', borderRadius: 'var(--radius-lg)',
  border: '1px solid var(--border-primary)', background: 'transparent', color: 'var(--fg-2)', cursor: 'pointer',
  fontFamily: 'var(--font-display)', fontSize: 12, whiteSpace: 'nowrap',
}
