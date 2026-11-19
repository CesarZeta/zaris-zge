// Versión de la publicación (PLAN_VERSIONADO.md): la pasa el build de Cloudflare Pages
// (tools/cloudflare_pages_build.sh) por VITE_APP_VERSION / VITE_APP_COMMIT. En local, «dev».
export const APP_VERSION: string = (import.meta.env.VITE_APP_VERSION as string | undefined) || 'dev'
export const APP_COMMIT: string = (import.meta.env.VITE_APP_COMMIT as string | undefined) || ''

/** «v2026.11.19.1540» o «desarrollo». */
export const versionTexto = APP_VERSION === 'dev' ? 'desarrollo' : `v${APP_VERSION}`
