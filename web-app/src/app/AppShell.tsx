import { Outlet, useNavigate } from 'react-router-dom'
import { useEffect } from 'react'
import { Sidebar } from '../shell/Sidebar/Sidebar'
import { TopBar } from '../shell/TopBar/TopBar'
import { CommandMenu } from '../shell/CommandMenu/CommandMenu'
import { Notifications } from '../shell/Notifications/Notifications'
import { useAuthStore } from '../stores/auth'
import { useUiStore } from '../stores/ui'
import s from './AppShell.module.css'

// Cuando el shell React vive embebido en iframe del shell vanilla (regla CLAUDE.md §14),
// debe ocultar su propio sidebar+topbar y mostrar solo el contenido. La navegacion lateral
// y la sesion son responsabilidad del shell vanilla.
const isEmbedded = typeof window !== 'undefined' && window.self !== window.top

export function AppShell() {
  const user = useAuthStore((s) => s.user)
  const refreshSession = useAuthStore((s) => s.refreshSession)
  const openCmdk = useUiStore((s) => s.openCmdk)
  const navigate = useNavigate()

  // Guard: si no hay sesion redirigir a login
  useEffect(() => {
    if (!user) navigate('/login', { replace: true })
  }, [user, navigate])

  // CLAUDE.md §30: si el user fue persistido antes del feature de permisos,
  // refrescamos contra /auth/me para traer modulos_permitidos sin re-loguear.
  useEffect(() => {
    if (user && !Array.isArray(user.modulos_permitidos)) {
      void refreshSession()
    }
  }, [user, refreshSession])

  // Atajo Ctrl+K solo standalone (en iframe el shell vanilla maneja sus atajos)
  useEffect(() => {
    if (isEmbedded) return
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        openCmdk()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [openCmdk])

  if (!user) return null

  // Modo embebido: solo el contenido + toasts. Sin sidebar/topbar/cmdk.
  if (isEmbedded) {
    return (
      <main className={s.embeddedContent}>
        <Outlet />
        <Notifications />
      </main>
    )
  }

  return (
    <div className={s.shell}>
      <Sidebar />
      <div className={s.main}>
        <TopBar />
        <main className={s.content}>
          <Outlet />
        </main>
      </div>
      <CommandMenu />
      <Notifications />
    </div>
  )
}
