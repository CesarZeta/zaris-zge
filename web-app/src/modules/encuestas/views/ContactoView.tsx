import { useState } from 'react'
import { PhoneCall, Mail, FileText, Check, RefreshCw } from 'lucide-react'
import { usePendientesContacto, useAtenderContacto } from '../hooks/useEncuestas'
import { ConfirmModal } from '../../agenda/components/ConfirmModal'
import { useNotificationsStore } from '../../../stores/notifications'
import { colorCsat } from '../components/charts'
import type { RespuestaPendienteContacto } from '../lib/types'

export function ContactoView() {
  const push = useNotificationsStore((s) => s.push)
  const { data, isLoading, isError, error, refetch, isFetching } = usePendientesContacto()
  const atender = useAtenderContacto()
  const [confirmar, setConfirmar] = useState<RespuestaPendienteContacto | null>(null)

  const items = data ?? []

  async function doAtender(item: RespuestaPendienteContacto) {
    setConfirmar(null)
    try {
      await atender.mutateAsync(item.id_encuesta_respuesta)
      push({ kind: 'success', title: 'Marcado como atendido' })
    } catch (e) {
      push({ kind: 'error', title: 'No se pudo marcar', body: (e as Error).message })
    }
  }

  function nombreCompleto(i: RespuestaPendienteContacto): string {
    return [i.ciudadano_nombre, i.ciudadano_apellido].filter(Boolean).join(' ') || `Ciudadano #${i.id_ciudadano}`
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <p style={{ margin: 0, color: 'var(--fg-2)', fontSize: '0.88rem' }}>
          Vecinos <strong>insatisfechos</strong> que pidieron ser contactados. Al marcar uno como atendido, sale de la lista.
        </p>
        <button onClick={() => refetch()} style={btnGhost} title="Refrescar">
          <RefreshCw size={14} strokeWidth={1.5} style={{ animation: isFetching ? 'spin 1s linear infinite' : undefined }} />
        </button>
      </div>

      {isError && <div style={errorBanner}>{(error as Error)?.message ?? 'Error al cargar la bandeja'}</div>}

      {isLoading ? (
        <p style={vacio}>Cargando…</p>
      ) : items.length === 0 ? (
        <div style={emptyCard}>
          <PhoneCall size={26} strokeWidth={1.5} color="var(--fg-3)" />
          <p style={{ margin: '10px 0 0', fontWeight: 600, color: 'var(--fg-1)' }}>Sin pedidos pendientes</p>
          <p style={{ margin: '4px 0 0', fontSize: '0.84rem', color: 'var(--fg-3)' }}>
            Ningún vecino está esperando que lo contacten ahora mismo.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {items.map((i) => (
            <div key={i.id_encuesta_respuesta} style={contactCard}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                  <span style={{ fontWeight: 600, color: 'var(--fg-1)', fontSize: '0.95rem' }}>{nombreCompleto(i)}</span>
                  <span style={{
                    fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600,
                    color: colorCsat(i.clasificacion_inicial),
                    background: 'var(--surface-300)', padding: '2px 8px', borderRadius: 999,
                  }}>
                    {i.clasificacion_inicial}★ · {i.rama_seguida}
                  </span>
                </div>
                <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: '0.82rem', color: 'var(--fg-2)' }}>
                  {i.ciudadano_telefono && (
                    <a href={`tel:${i.ciudadano_telefono}`} style={dato}>
                      <PhoneCall size={13} strokeWidth={1.5} /> {i.ciudadano_telefono}
                    </a>
                  )}
                  {i.ciudadano_email && (
                    <a href={`mailto:${i.ciudadano_email}`} style={dato}>
                      <Mail size={13} strokeWidth={1.5} /> {i.ciudadano_email}
                    </a>
                  )}
                  {i.nro_reclamo && (
                    <span style={{ ...dato, color: 'var(--fg-3)' }}>
                      <FileText size={13} strokeWidth={1.5} /> {i.nro_reclamo}
                    </span>
                  )}
                  {i.fecha_respuesta && (
                    <span style={{ color: 'var(--fg-3)', fontSize: '0.78rem' }}>
                      {new Date(i.fecha_respuesta).toLocaleDateString('es-AR', { day: '2-digit', month: 'short', year: 'numeric' })}
                    </span>
                  )}
                </div>
              </div>
              <button style={btnSuccess} onClick={() => setConfirmar(i)} disabled={atender.isPending}>
                <Check size={14} strokeWidth={2} /> Atendido
              </button>
            </div>
          ))}
        </div>
      )}

      <ConfirmModal
        open={confirmar != null}
        title="Marcar como atendido"
        message={confirmar ? `Confirmás que contactaste a ${nombreCompleto(confirmar)}? Saldrá de la lista de pendientes.` : ''}
        confirmLabel="Marcar atendido"
        onConfirm={() => confirmar && doAtender(confirmar)}
        onCancel={() => setConfirmar(null)}
      />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

const dato: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 5, color: 'var(--fg-2)', textDecoration: 'none',
}
const contactCard: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap',
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderLeft: '3px solid var(--zaris-orange)', borderRadius: 12, padding: '14px 16px',
}
const emptyCard: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center',
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)', borderRadius: 12, padding: 36,
}
const btnGhost: React.CSSProperties = {
  fontFamily: 'var(--font-display)', cursor: 'pointer', borderRadius: 8, padding: '6px 9px',
  background: 'transparent', color: 'var(--fg-2)', border: '1px solid var(--border-medium)',
  display: 'inline-flex', alignItems: 'center',
}
const btnSuccess: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.82rem', fontWeight: 500, cursor: 'pointer',
  borderRadius: 8, padding: '8px 14px', background: '#1f8a65', color: 'white', border: 'none',
  display: 'inline-flex', alignItems: 'center', gap: 6, flexShrink: 0,
}
const vacio: React.CSSProperties = { color: 'var(--fg-3)', fontSize: 13, textAlign: 'center', padding: 20 }
const errorBanner: React.CSSProperties = {
  background: '#ffebee', border: '1px solid #ffcdd2', borderLeft: '4px solid var(--color-error)',
  borderRadius: 8, padding: '12px 16px', color: '#c62828', fontSize: '0.86rem',
}
