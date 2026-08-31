import { useEffect, useState } from 'react'
import s from './StatusBar.module.css'

// Statusbar inferior del shell DEV — clon de la .statusbar del shell vanilla
// de producción (§14): estado del servidor (ping /api/health cada 60s) ·
// fecha/hora (refresh 30s) · versión. Fila 3 del grid del AppShell.

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? 'http://127.0.0.1:8000'

type ApiEstado = 'verificando' | 'ok' | 'err'

function formatoReloj(d: Date): string {
  const fecha = d.toLocaleDateString('es-AR', { weekday: 'short', day: 'numeric', month: 'short' })
  const hora = d.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })
  return `${fecha}, ${hora}`
}

export function StatusBar() {
  const [api, setApi] = useState<ApiEstado>('verificando')
  const [reloj, setReloj] = useState(() => formatoReloj(new Date()))

  useEffect(() => {
    let vivo = true
    async function ping() {
      try {
        const r = await fetch(`${BASE}/api/health`, { cache: 'no-store' })
        if (vivo) setApi(r.ok ? 'ok' : 'err')
      } catch {
        if (vivo) setApi('err')
      }
    }
    void ping()
    const timer = window.setInterval(ping, 60_000)
    const onVisible = () => { if (document.visibilityState === 'visible') void ping() }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      vivo = false
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [])

  useEffect(() => {
    const timer = window.setInterval(() => setReloj(formatoReloj(new Date())), 30_000)
    return () => window.clearInterval(timer)
  }, [])

  return (
    <footer className={s.statusbar} role="contentinfo">
      <div className={s.left}>
        <span className={`${s.api} ${api === 'ok' ? s.ok : ''} ${api === 'err' ? s.err : ''}`} title="Estado del servidor">
          <span className={s.dot} aria-hidden="true" />
          <span>
            {api === 'verificando' ? 'Verificando servidor…' : api === 'ok' ? 'Servidor operativo' : 'Sin conexión con el servidor'}
          </span>
        </span>
      </div>
      <div className={s.center}>
        <time className={s.clock}>{reloj}</time>
      </div>
      <div className={s.right}>
        <span className={s.version}>zaris-zge · v0.1</span>
      </div>
    </footer>
  )
}
