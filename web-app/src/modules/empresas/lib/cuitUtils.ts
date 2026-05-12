// Helpers especificos de CUIT. Reusa la validacion por modulo 11 de ciudadanos.

export { validarCuilCuit, validarTelefono, validarEmail, soloDigitos } from '../../ciudadanos/lib/cuilUtils'

/** Formatea CUIT on-input: XX-XXXXXXXX-X. Solo digitos. */
export function formatCuitInput(valor: string): string {
  const d = String(valor || '').replace(/\D/g, '')
  if (d.length <= 2) return d
  if (d.length <= 10) return `${d.substring(0, 2)}-${d.substring(2)}`
  return `${d.substring(0, 2)}-${d.substring(2, 10)}-${d.substring(10, 11)}`
}
