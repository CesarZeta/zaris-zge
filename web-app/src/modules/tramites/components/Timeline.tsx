import { useState } from 'react'
import {
  ClipboardList, Hash, ArrowRight, Hand, LockOpen, RefreshCw, Zap,
  Paperclip, PenLine, Check, X, MessageSquare, Link2, Ban, RotateCcw,
  Circle, ChevronUp, ChevronDown, BadgeCheck, Flag, Archive, Trash2,
  type LucideIcon,
} from 'lucide-react'
import type { TramiteMovimiento, TipoMovimiento } from '../types'

/* ── Iconos y etiquetas por tipo de movimiento ───────────── */

const TIPO_CONFIG: Record<
  TipoMovimiento,
  { icon: LucideIcon; color: string; etiqueta: (m: TramiteMovimiento) => string }
> = {
  creacion:       { icon: ClipboardList, color: '#1f8a65', etiqueta: (m) => `Trámite creado por ${m.agente_nombre}` },
  numeracion:     { icon: Hash,          color: '#6a1b9a', etiqueta: (m) => `Numerado: ${String(m.metadata_jsonb?.numero_expediente ?? '')}` },
  pase:           { icon: ArrowRight,    color: '#1565c0', etiqueta: (m) => `Pase: ${m.origen_jsonb?.nombre ?? '—'} → ${m.destino_jsonb?.nombre ?? '—'}` },
  toma:           { icon: Hand,          color: '#f57f17', etiqueta: (m) => `Tomado por ${m.agente_nombre}` },
  liberacion:     { icon: LockOpen,      color: '#78909c', etiqueta: (m) => `Liberado por ${m.agente_nombre}` },
  cambio_estado:  { icon: RefreshCw,     color: '#f54e00', etiqueta: (m) => `Estado: ${m.estado_origen_etiqueta ?? '—'} → ${m.estado_destino_etiqueta ?? '—'}` },
  transicion:     { icon: Zap,           color: '#f54e00', etiqueta: (m) => `Transición: ${m.estado_origen_etiqueta ?? '—'} → ${m.estado_destino_etiqueta ?? '—'}` },
  adjunto:        { icon: Paperclip,     color: '#5c6bc0', etiqueta: (m) => `Adjuntó: ${String(m.metadata_jsonb?.nombre ?? 'documento')}` },
  firma_solicitada: { icon: PenLine,     color: '#7b1fa2', etiqueta: (m) => `Firma solicitada en ${String(m.metadata_jsonb?.documento_nombre ?? 'documento')}` },
  firma_realizada:  { icon: Check,       color: '#1f8a65', etiqueta: (m) => `Firmó: ${String(m.metadata_jsonb?.documento_nombre ?? 'documento')}` },
  firma_rechazada:  { icon: X,           color: 'var(--color-error)', etiqueta: (m) => `Rechazó firma de ${String(m.metadata_jsonb?.documento_nombre ?? 'documento')}` },
  comentario:     { icon: MessageSquare, color: '#546e7a', etiqueta: () => 'Comentario' },
  relacion:       { icon: Link2,         color: '#00838f', etiqueta: (m) => `Asoció con ${String(m.metadata_jsonb?.numero_relacionado ?? '')}` },
  desistido:      { icon: Ban,           color: 'var(--color-error)', etiqueta: () => 'Trámite desistido' },
  reapertura:     { icon: RotateCcw,     color: '#f57f17', etiqueta: () => 'Reapertura del trámite' },
  aprobacion:     { icon: BadgeCheck,    color: '#1f8a65', etiqueta: (m) => `Visado: ${String(m.metadata_jsonb?.estado ?? m.comentario ?? 'resuelto')}` },
  resultado:      { icon: Flag,          color: '#6a1b9a', etiqueta: (m) => `Resultado: ${String(m.metadata_jsonb?.resultado_nuevo ?? '—')}` },
  archivado_inactividad: { icon: Archive, color: '#78909c', etiqueta: () => 'Archivado automático por inactividad' },
  purga_binario:  { icon: Trash2,        color: '#90a4ae', etiqueta: () => 'Archivo físico depurado por antigüedad' },
}

function formatFechaRelativa(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const min = Math.floor(diff / 60000)
  if (min < 1) return 'hace un momento'
  if (min < 60) return `hace ${min} min`
  const hs = Math.floor(min / 60)
  if (hs < 24) return `hace ${hs} h`
  const dias = Math.floor(hs / 24)
  if (dias < 7) return `hace ${dias} d`
  return new Date(iso).toLocaleDateString('es-AR', { day: '2-digit', month: 'short', year: 'numeric' })
}

function formatFechaAbsoluta(iso: string): string {
  return new Date(iso).toLocaleString('es-AR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

interface TimelineProps {
  movimientos: TramiteMovimiento[]
}

export function Timeline({ movimientos }: TimelineProps) {
  const [expandido, setExpandido] = useState<number | null>(null)

  if (movimientos.length === 0) {
    return (
      <p style={{ color: 'var(--fg-3)', fontFamily: 'var(--font-display)', fontSize: 13 }}>
        Sin movimientos registrados.
      </p>
    )
  }

  // Ascendente: el más viejo arriba
  const ordenados = [...movimientos].sort((a, b) => a.orden_secuencial - b.orden_secuencial)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
      {ordenados.map((mov, idx) => {
        const cfg = TIPO_CONFIG[mov.tipo] ?? {
          icon: Circle,
          color: 'var(--fg-3)',
          etiqueta: () => mov.tipo,
        }
        const Icono = cfg.icon
        const esUltimo = idx === ordenados.length - 1
        const expandidoActual = expandido === mov.id_tramite_movimiento

        return (
          <div key={mov.id_tramite_movimiento} style={{ display: 'flex', gap: 12 }}>
            {/* Línea vertical */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 28, flexShrink: 0 }}>
              <div
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: '50%',
                  background: `${cfg.color}18`,
                  border: `2px solid ${cfg.color}`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  zIndex: 1,
                }}
              >
                <Icono size={15} strokeWidth={1.5} color={cfg.color} />
              </div>
              {!esUltimo && (
                <div
                  style={{
                    width: 2,
                    flex: 1,
                    minHeight: 16,
                    background: 'var(--border-primary)',
                    marginTop: 4,
                    marginBottom: 4,
                  }}
                />
              )}
            </div>

            {/* Contenido del nodo */}
            <div style={{ flex: 1, paddingBottom: esUltimo ? 0 : 16, paddingTop: 4 }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, flexWrap: 'wrap' }}>
                <span
                  style={{
                    fontFamily: 'var(--font-display)',
                    fontSize: 13,
                    fontWeight: 500,
                    color: 'var(--fg-1)',
                    flex: 1,
                  }}
                >
                  {cfg.etiqueta(mov)}
                </span>
                <span
                  title={formatFechaAbsoluta(mov.fecha_alta)}
                  style={{ fontSize: 11, color: 'var(--fg-3)', whiteSpace: 'nowrap', marginTop: 1 }}
                >
                  {formatFechaRelativa(mov.fecha_alta)}
                </span>
              </div>

              {/* Agente */}
              <p style={{ fontSize: 11, color: 'var(--fg-3)', margin: '2px 0 0', fontFamily: 'var(--font-display)' }}>
                {mov.agente_nombre}
              </p>

              {/* Comentario */}
              {mov.comentario && (
                <p
                  style={{
                    fontSize: 12,
                    color: 'var(--fg-2)',
                    margin: '6px 0 0',
                    padding: '6px 10px',
                    background: 'var(--surface-300)',
                    borderRadius: 'var(--radius-md)',
                    borderLeft: `3px solid ${cfg.color}`,
                    fontFamily: 'var(--font-display)',
                  }}
                >
                  {mov.comentario}
                </p>
              )}

              {/* Toggle metadata */}
              {mov.metadata_jsonb && Object.keys(mov.metadata_jsonb).length > 0 && (
                <button
                  type="button"
                  onClick={() => setExpandido(expandidoActual ? null : mov.id_tramite_movimiento)}
                  style={{
                    background: 'none',
                    border: 'none',
                    fontSize: 11,
                    color: 'var(--fg-3)',
                    cursor: 'pointer',
                    padding: '4px 0',
                    fontFamily: 'var(--font-display)',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                  }}
                >
                  {expandidoActual
                    ? <><ChevronUp size={12} strokeWidth={1.5} /> Ocultar detalles</>
                    : <><ChevronDown size={12} strokeWidth={1.5} /> Ver detalles</>}
                </button>
              )}
              {expandidoActual && mov.metadata_jsonb && (
                <pre
                  style={{
                    fontSize: 11,
                    color: 'var(--fg-3)',
                    background: 'var(--surface-300)',
                    padding: '6px 8px',
                    borderRadius: 'var(--radius-md)',
                    margin: '4px 0 0',
                    overflowX: 'auto',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  {JSON.stringify(mov.metadata_jsonb, null, 2)}
                </pre>
              )}
              {mov.ip && expandidoActual && (
                <p style={{ fontSize: 10, color: 'var(--fg-3)', margin: '2px 0 0' }}>
                  IP: {mov.ip}
                </p>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
