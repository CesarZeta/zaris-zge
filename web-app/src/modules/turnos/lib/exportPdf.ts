import { jsPDF } from 'jspdf'
import autoTable from 'jspdf-autotable'

export interface TurnoPdfRow {
  fecha: string
  hora: string
  ciudadano: string
  dni: string
  atiende: string
  prestacion: string
  observaciones: string
  /** Solo se imprime si el export pide conEstado (lista general de turnos). */
  estado?: string
}

interface ExportOpts {
  titulo?: string
  desde?: string
  hasta?: string
  /** Agrega la columna Estado (lista general con reservados/cumplidos/cancelados). */
  conEstado?: boolean
}

/**
 * Exporta un listado de turnos a PDF con encabezado ZARIS.
 * Naranja del DS: #f54e00. Tipografía estándar de jsPDF (helvetica).
 */
export function exportarTurnosPdf(rows: TurnoPdfRow[], opts: ExportOpts = {}) {
  const doc = new jsPDF({ orientation: 'landscape', unit: 'pt', format: 'a4' })

  doc.setFontSize(16)
  doc.setTextColor(38, 37, 30)
  doc.text(`ZARIS — ${opts.titulo ?? 'Turnos'}`, 40, 40)

  doc.setFontSize(10)
  doc.setTextColor(110, 108, 100)
  const rango = opts.desde || opts.hasta
    ? `Periodo: ${opts.desde || '—'} a ${opts.hasta || '—'}`
    : 'Periodo: todos'
  const generado = new Date().toLocaleString('es-AR')
  doc.text(`${rango}   ·   Generado: ${generado}   ·   Total: ${rows.length}`, 40, 58)

  const head = ['Fecha', 'Hora', 'Ciudadano', 'DNI', 'Atiende', 'Prestación']
  if (opts.conEstado) head.push('Estado')
  head.push('Observaciones')

  autoTable(doc, {
    startY: 72,
    head: [head],
    body: rows.map((r) => {
      const fila = [r.fecha, r.hora, r.ciudadano, r.dni, r.atiende, r.prestacion]
      if (opts.conEstado) fila.push(r.estado ?? '')
      fila.push(r.observaciones)
      return fila
    }),
    styles: { fontSize: 8, cellPadding: 4, textColor: [38, 37, 30] },
    headStyles: { fillColor: [245, 78, 0], textColor: [255, 255, 255], fontStyle: 'bold' },
    alternateRowStyles: { fillColor: [247, 247, 244] },
    columnStyles: { [head.length - 1]: { cellWidth: opts.conEstado ? 160 : 200 } },
  })

  const slug = (opts.titulo ?? 'turnos').toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu, '').replace(/[^a-z0-9]+/g, '_')
  const fname = `${slug}_${new Date().toISOString().slice(0, 10)}.pdf`
  doc.save(fname)
}

/** Compat: export del tab Atendidos (turnos cumplidos, sin columna Estado). */
export function exportarAtendidosPdf(rows: TurnoPdfRow[], opts: { desde?: string; hasta?: string } = {}) {
  exportarTurnosPdf(rows, { ...opts, titulo: 'Turnos atendidos' })
}
