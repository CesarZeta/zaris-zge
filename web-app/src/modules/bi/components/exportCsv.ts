// Exportación client-side a CSV. Estándar del módulo BI: toda tabla de detalle
// debe ofrecer "Exportar CSV". No requiere endpoint extra — serializa los datos
// que ya tiene el frontend.
//
// - BOM UTF-8 (﻿) para que Excel lea bien tildes y ñ.
// - Separador coma; valores con comillas dobles escapadas (RFC 4180).
// - Descarga vía Blob + <a download>.

export interface CsvColumna<T> {
  header: string
  /** Extrae el valor de la fila. Devolvé string/number/null. */
  value: (row: T) => string | number | null | undefined
}

function escapar(v: string | number | null | undefined): string {
  if (v === null || v === undefined) return ''
  const s = String(v)
  // Si contiene coma, comilla o salto de línea, envolver en comillas y duplicar comillas internas.
  if (/[",\n\r]/.test(s)) {
    return `"${s.replace(/"/g, '""')}"`
  }
  return s
}

export function exportarCsv<T>(filename: string, columnas: CsvColumna<T>[], filas: T[]): void {
  const BOM = String.fromCharCode(0xfeff) // BOM UTF-8 para que Excel lea tildes/ñ
  const head = columnas.map((c) => escapar(c.header)).join(',')
  const body = filas.map((row) => columnas.map((c) => escapar(c.value(row))).join(',')).join('\r\n')
  const csv = BOM + head + '\r\n' + body

  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// Sufijo de fecha YYYY-MM-DD para nombres de archivo.
export function hoyISO(): string {
  return new Date().toISOString().slice(0, 10)
}
