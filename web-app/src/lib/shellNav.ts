/**
 * Navegación al shell vanilla desde un módulo React embebido en iframe.
 *
 * En producción el bundle vive bajo `/zaris-zge/` (GH Pages). Un
 * `window.location.href = '/foo'` salta a `cesarzeta.github.io/foo` SIN el
 * prefijo `/zaris-zge/` → 404 de GitHub Pages dentro del iframe (CLAUDE.md §32
 * Quirk 13). El camino correcto es delegar en `window.parent.shellNavigate`, y
 * solo como fallback (standalone dev en localhost:5173) resolver el subpath del
 * shell padre antes de redirigir.
 *
 * @param target Ruta relativa al shell. Acepta:
 *   - `web-app/dist/index.html#/<modulo>/<ruta>` (módulos React)
 *   - `frontend/<modulo>.html(?...)` (módulos vanilla)
 */
export function shellNavigate(target: string): void {
  const w = window.parent as Window & { shellNavigate?: (url: string) => void }
  if (w?.shellNavigate) {
    w.shellNavigate(target)
    return
  }
  // Fallback standalone: resolver el subpath del shell para no romper bajo /zaris-zge/.
  try {
    const subpath = window.location.pathname.match(/^\/[^/]+\//)?.[0] ?? '/'
    window.location.href = subpath + target
  } catch {
    window.location.href = '/' + target
  }
}

/**
 * Lleva el shell vanilla a su login (sesión vencida o inexistente dentro del iframe). El `/login`
 * del bundle React es solo de desarrollo (localhost:5173) y no pide el código del segundo factor.
 * Puede tirar si el padre no es del mismo origen: el que llama decide el fallback.
 */
export function shellIrAlLogin(): void {
  const padre = window.parent as Window
  padre.location.href = (padre.location.pathname.match(/^\/[^/]+\//)?.[0] ?? '/') + 'frontend/login.html'
}

/** Atajo a la home (Dashboard) del shell. */
export function shellGoInicio(): void {
  shellNavigate('web-app/dist/index.html#/dashboard')
}
