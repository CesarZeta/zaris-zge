import { createElement } from 'react'
import { createHashRouter, Navigate } from 'react-router-dom'
import { AppShell } from './AppShell'
import { LoginPage } from './LoginPage'
import { modules } from '../modules'

// HashRouter porque GitHub Pages no soporta HTML5 routing sin server-side rewrites.
// URLs quedan tipo `/zaris-zge/web-app/#/agenda/timeline`. Funciona con F5.
export const router = createHashRouter([
  {
    path: '/login',
    element: createElement(LoginPage),
  },
  {
    path: '/',
    element: createElement(AppShell),
    children: [
      { index: true, element: createElement(Navigate, { to: '/dashboard', replace: true }) },
      ...modules.map((mod) => ({
        path: mod.id,
        handle: { breadcrumb: mod.label },
        children: mod.routes.map((r) =>
          r.index
            ? { index: true as const, handle: r.handle, element: createElement(r.element) }
            : { path: r.path,        handle: r.handle, element: createElement(r.element) }
        ),
      })),
    ],
  },
  {
    path: '*',
    element: createElement(Navigate, { to: '/dashboard', replace: true }),
  },
])
