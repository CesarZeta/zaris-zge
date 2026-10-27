/**
 * Navegación al shell vanilla desde un módulo React embebido en iframe.
 *
 * El sitio puede vivir en la raíz del dominio (Cloudflare Pages, subdominios de
 * municipio) o bajo un subpath (`/zaris-zge/` en GitHub Pages). Un
 * `window.location.href = '/foo'` absoluto rompe en el segundo caso (CLAUDE.md §32
 * Quirk 13). El camino correcto es delegar en `window.parent.shellNavigate`, y
 * solo como fallback (standalone dev en localhost:5173) resolver la raíz del
 * sitio con `raizDelSitio` antes de redirigir.
 *
 * @param target Ruta relativa al shell. Acepta:
 *   - `web-app/dist/index.html#/<modulo>/<ruta>` (módulos React)
 *   - `frontend/<modulo>.html(?...)` (módulos vanilla)
 */
/**
 * Raíz del sitio del shell a partir de una ruta: lo que está antes de `web-app/` o `frontend/`, o el
 * directorio de la página. `/zaris-zge/web-app/dist/index.html` → `/zaris-zge/`; `/index.html` → `/`.
 */
export function raizDelSitio(pathname: string): string {
  const i = pathname.search(/\/(web-app|frontend)\//)
  if (i >= 0) return pathname.slice(0, i + 1)
  return pathname.slice(0, pathname.lastIndexOf('/') + 1) || '/'
}

export function shellNavigate(target: string): void {
  const w = window.parent as Window & { shellNavigate?: (url: string) => void }
  if (w?.shellNavigate) {
    w.shellNavigate(target)
    return
  }
  // Fallback standalone: resolver la raíz del sitio (raíz del dominio o subpath).
  try {
    window.location.href = raizDelSitio(window.location.pathname) + target
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
  padre.location.href = raizDelSitio(padre.location.pathname) + 'frontend/login.html'
}

/** Atajo a la home (Dashboard) del shell. */
export function shellGoInicio(): void {
  shellNavigate('web-app/dist/index.html#/dashboard')
}
