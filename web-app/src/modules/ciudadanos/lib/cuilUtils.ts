// Helpers de validacion y normalizacion para ciudadanos.
// Mirror de frontend/js/validaciones.js + logica de generacion CUIL desde DNI.

const MULTIPLICADORES = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]

export interface ValidacionResult {
  valido: boolean
  formateado: string
  error: string
}

/** Valida CUIL/CUIT por modulo 11. Acepta con/sin guiones. */
export function validarCuilCuit(valor: string): ValidacionResult {
  const limpio = String(valor || '').replace(/[-\s]/g, '')
  if (!/^\d{11}$/.test(limpio)) {
    return { valido: false, formateado: '', error: 'Debe contener exactamente 11 digitos numericos.' }
  }
  const digitos = limpio.split('').map(Number)
  let suma = 0
  for (let i = 0; i < 10; i++) suma += digitos[i] * MULTIPLICADORES[i]
  const resto = suma % 11
  let esperado: number
  if (resto === 0) esperado = 0
  else if (resto === 1) esperado = 9 // se acepta 9 (caso femenino especial)
  else esperado = 11 - resto

  const valido = digitos[10] === esperado
  const formateado = `${limpio.substring(0, 2)}-${limpio.substring(2, 10)}-${limpio.substring(10)}`
  return {
    valido,
    formateado,
    error: valido ? '' : `Digito verificador invalido (esperaba ${esperado}).`,
  }
}

/** Calcula digito verificador para prefijo+DNI (8 digitos). */
function calcularDigitoVerificador(prefijo: '20' | '23' | '27', dni: string): number {
  const base = `${prefijo}${dni.padStart(8, '0')}`
  let suma = 0
  for (let i = 0; i < 10; i++) suma += parseInt(base[i]) * MULTIPLICADORES[i]
  const resto = suma % 11
  if (resto === 0) return 0
  if (resto === 1) return prefijo === '27' ? 4 : 9
  return 11 - resto
}

/** Genera CUIL desde DNI + sexo. Retorna '' si faltan datos. */
export function generarCuilDesdeDni(dni: string, sexo: string, docTipo: string): string {
  const limpio = String(dni || '').replace(/\D/g, '')
  if (docTipo !== 'DNI' || !sexo || limpio.length < 7) return ''
  const prefijo: '20' | '27' = sexo === 'MUJER' ? '27' : '20'
  const dv = calcularDigitoVerificador(prefijo, limpio)
  return `${prefijo}-${limpio.padStart(8, '0')}-${dv}`
}

/** Extrae DNI desde CUIL (digitos centrales 2-9). */
export function extraerDniDeCuil(cuil: string): string | null {
  const digitos = String(cuil || '').replace(/\D/g, '')
  if (digitos.length !== 11) return null
  return String(parseInt(digitos.substring(2, 10)))
}

/** Formatea CUIL on-input: XX-XXXXXXXX-X. Solo digitos en input. */
export function formatCuilInput(valor: string): string {
  const d = String(valor || '').replace(/\D/g, '')
  if (d.length <= 2) return d
  if (d.length <= 10) return `${d.substring(0, 2)}-${d.substring(2)}`
  return `${d.substring(0, 2)}-${d.substring(2, 10)}-${d.substring(10, 11)}`
}

/** Valida telefono argentino 10 digitos sin el 0 de area. */
export function validarTelefono(valor: string): { valido: boolean; error: string } {
  const limpio = String(valor || '').replace(/[-\s()]/g, '')
  if (!/^\d{10}$/.test(limpio)) {
    return { valido: false, error: 'Telefono debe tener 10 digitos (codigo de area sin 0 + numero).' }
  }
  if (limpio.startsWith('0')) {
    return { valido: false, error: 'No incluir el 0 del codigo de area.' }
  }
  return { valido: true, error: '' }
}

/** Valida formato de email. */
export function validarEmail(valor: string): boolean {
  return /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/.test(String(valor || '').trim())
}

/** Limpia digitos (para tel/cuil antes de enviar al backend). */
export function soloDigitos(valor: string): string {
  return String(valor || '').replace(/\D/g, '')
}
