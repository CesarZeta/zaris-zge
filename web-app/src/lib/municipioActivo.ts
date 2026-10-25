/**
 * Municipio en el que opera el super administrador (IT-01 F3, PLAN_MULTI_MUNICIPIO_F3.md).
 *
 * Lo elige el selector del shell vanilla (`frontend/js/menu.js`) y vive en localStorage con la
 * clave `zaris_municipio_activo`: el shell y el iframe son del mismo origen y lo comparten. Viaja
 * como header `X-Municipio` solo para una sesión de super administrador (para cualquier otra
 * cuenta el backend lo ignora igual).
 */
export const MUNICIPIO_ACTIVO_KEY = 'zaris_municipio_activo'

function esSuperAdmin(): boolean {
  try {
    const raw = localStorage.getItem('zaris_session')
    if (!raw) return false
    const s = JSON.parse(raw)
    return (s?.state?.user ?? s?.user)?.es_super_admin === true
  } catch {
    return false
  }
}

export function getMunicipioActivo(): number | null {
  try {
    const v = localStorage.getItem(MUNICIPIO_ACTIVO_KEY)
    return v && /^[0-9]{1,9}$/.test(v) ? Number(v) : null
  } catch {
    return null
  }
}

export function setMunicipioActivo(id: number): void {
  try {
    localStorage.setItem(MUNICIPIO_ACTIVO_KEY, String(id))
  } catch {
    /* sin storage: el backend responde 400 y la pantalla lo dice */
  }
}

/** `{ 'X-Municipio': id }` para el super administrador con municipio elegido; `{}` para el resto. */
export function headerMunicipio(): Record<string, string> {
  const id = esSuperAdmin() ? getMunicipioActivo() : null
  return id != null ? { 'X-Municipio': String(id) } : {}
}
