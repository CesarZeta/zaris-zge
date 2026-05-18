import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell, CheckCheck, Inbox } from 'lucide-react'
import {
  useNotificaciones,
  useNotificacionesCount,
  useMarcarLeida,
  useMarcarTodasLeidas,
  type NotificacionBackend,
} from '../../lib/notificacionesBackend'

const MAX_BADGE = 9

export function NotificacionesDropdown() {
  const [abierto, setAbierto] = useState(false)
  const wrapperRef = useRef<HTMLDivElement>(null)
  const countQ = useNotificacionesCount()
  const listQ = useNotificaciones({ limit: 20 })
  const marcarLeida = useMarcarLeida()
  const marcarTodas = useMarcarTodasLeidas()
  const navigate = useNavigate()

  const noLeidas = countQ.data?.no_leidas ?? 0
  const items = listQ.data?.items ?? []
  const isEmbedded = typeof window !== 'undefined' && window.self !== window.top

  // Cerrar al click afuera
  useEffect(() => {
    if (!abierto) return
    function onClick(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) setAbierto(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [abierto])

  // Cerrar con Escape
  useEffect(() => {
    if (!abierto) return
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') setAbierto(false) }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [abierto])

  async function handleClick(n: NotificacionBackend) {
    if (!n.leida) {
      try { await marcarLeida.mutateAsync(n.id_notificacion) } catch { /* ignore */ }
    }
    setAbierto(false)
    if (!n.url_destino) return

    if (isEmbedded) {
      // En iframe del shell vanilla: pedirle al padre que navegue el iframe al bundle React
      const url = n.url_destino.startsWith('#') ? `web-app/dist/index.html${n.url_destino}` : n.url_destino
      const w = window.parent as Window & { shellNavigate?: (u: string) => void }
      w?.shellNavigate?.(url)
    } else {
      // Standalone (dev): react-router
      const hash = n.url_destino.startsWith('#/') ? n.url_destino.slice(1) : n.url_destino
      navigate(hash)
    }
  }

  return (
    <div ref={wrapperRef} style={{ position: 'relative' }}>
      <button
        onClick={() => setAbierto((v) => !v)}
        aria-label="Notificaciones"
        style={iconBtnStyle}
      >
        <Bell size={16} strokeWidth={1.5} />
        {noLeidas > 0 && (
          <span style={badgeStyle}>{noLeidas > MAX_BADGE ? `${MAX_BADGE}+` : noLeidas}</span>
        )}
      </button>

      {abierto && (
        <div style={panelStyle} role="dialog" aria-label="Notificaciones">
          <header style={headerStyle}>
            <span style={tituloStyle}>Notificaciones</span>
            <button
              type="button"
              onClick={() => { void marcarTodas.mutateAsync() }}
              disabled={noLeidas === 0 || marcarTodas.isPending}
              style={accionBtnStyle}
              title="Marcar todas como leidas"
            >
              <CheckCheck size={12} strokeWidth={1.5} /> Marcar todas
            </button>
          </header>

          <div style={listaStyle}>
            {listQ.isLoading && (
              <p style={emptyStyle}>Cargando…</p>
            )}
            {!listQ.isLoading && items.length === 0 && (
              <div style={emptyWrapStyle}>
                <Inbox size={28} strokeWidth={1.5} color="var(--fg-3)" />
                <p style={emptyStyle}>Sin notificaciones</p>
              </div>
            )}
            {items.map((n) => (
              <button
                key={n.id_notificacion}
                onClick={() => { void handleClick(n) }}
                style={{ ...itemStyle, ...(n.leida ? {} : itemNuevoStyle) }}
              >
                <div style={{ flex: 1, minWidth: 0, textAlign: 'left' }}>
                  <p style={itemTituloStyle}>{n.titulo}</p>
                  {n.mensaje && <p style={itemMensajeStyle}>{n.mensaje}</p>}
                  <p style={itemFechaStyle}>{formatFecha(n.fecha_alta)}</p>
                </div>
                {!n.leida && <span style={puntoStyle} aria-label="No leida" />}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function formatFecha(iso: string): string {
  const d = new Date(iso)
  const diffMin = Math.round((Date.now() - d.getTime()) / 60_000)
  if (diffMin < 1) return 'ahora'
  if (diffMin < 60) return `hace ${diffMin} min`
  const diffHr = Math.round(diffMin / 60)
  if (diffHr < 24) return `hace ${diffHr} h`
  return d.toLocaleDateString('es-AR', { day: '2-digit', month: 'short' })
}

const iconBtnStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  width: 34, height: 34, border: 'none', background: 'transparent',
  borderRadius: 8, color: 'var(--fg-3)', cursor: 'pointer', position: 'relative',
}

const badgeStyle: React.CSSProperties = {
  position: 'absolute', top: 4, right: 4,
  minWidth: 14, height: 14, padding: '0 3px',
  background: 'var(--color-error)', color: 'white',
  fontSize: 9, fontFamily: 'var(--font-mono)', borderRadius: 99,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
}

const panelStyle: React.CSSProperties = {
  position: 'absolute', top: 'calc(100% + 6px)', right: 0,
  width: 360, maxHeight: 480, overflow: 'hidden',
  background: 'var(--surface-100)',
  border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-lg)',
  boxShadow: '0 8px 32px rgba(0,0,0,.18)',
  zIndex: 100,
  display: 'flex', flexDirection: 'column',
}

const headerStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  padding: '10px 14px', borderBottom: '1px solid var(--border-primary)',
  background: 'var(--surface-200)',
}

const tituloStyle: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: 13, fontWeight: 600, color: 'var(--fg-1)',
}

const accionBtnStyle: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 4,
  background: 'none', border: 'none', cursor: 'pointer',
  color: 'var(--fg-3)', fontSize: 11, fontFamily: 'var(--font-display)',
}

const listaStyle: React.CSSProperties = {
  flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column',
}

const itemStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'flex-start', gap: 8,
  padding: '10px 14px', borderBottom: '1px solid var(--border-primary)',
  background: 'transparent', border: 0, borderBottomWidth: 1, borderBottomStyle: 'solid',
  cursor: 'pointer', width: '100%',
}

const itemNuevoStyle: React.CSSProperties = {
  background: 'rgba(245,78,0,.04)',
}

const itemTituloStyle: React.CSSProperties = {
  margin: 0, fontFamily: 'var(--font-display)', fontSize: 13, fontWeight: 500, color: 'var(--fg-1)',
  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
}

const itemMensajeStyle: React.CSSProperties = {
  margin: '2px 0 0', fontSize: 11, color: 'var(--fg-2)', fontFamily: 'var(--font-display)',
  display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' as const,
  overflow: 'hidden',
}

const itemFechaStyle: React.CSSProperties = {
  margin: '4px 0 0', fontSize: 10, color: 'var(--fg-3)', fontFamily: 'var(--font-display)',
}

const puntoStyle: React.CSSProperties = {
  width: 8, height: 8, borderRadius: 99, background: 'var(--zaris-orange)',
  flexShrink: 0, marginTop: 6,
}

const emptyWrapStyle: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', alignItems: 'center',
  gap: 8, padding: '32px 16px',
}

const emptyStyle: React.CSSProperties = {
  margin: 0, color: 'var(--fg-3)', fontFamily: 'var(--font-display)', fontSize: 12,
}
