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

/** Atajo a la home (Dashboard) del shell. */
export function shellGoInicio(): void {
  shellNavigate('web-app/dist/index.html#/dashboard')
}
