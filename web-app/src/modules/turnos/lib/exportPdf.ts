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
}

/**
 * Exporta el listado de turnos atendidos a PDF con encabezado ZARIS.
 * Naranja del DS: #f54e00. Tipografía estándar de jsPDF (helvetica).
 */
export function exportarAtendidosPdf(rows: TurnoPdfRow[], opts: { desde?: string; hasta?: string } = {}) {
  const doc = new jsPDF({ orientation: 'landscape', unit: 'pt', format: 'a4' })

  doc.setFontSize(16)
  doc.setTextColor(38, 37, 30)
  doc.text('ZARIS — Turnos atendidos', 40, 40)

  doc.setFontSize(10)
  doc.setTextColor(110, 108, 100)
  const rango = opts.desde || opts.hasta
    ? `Periodo: ${opts.desde || '—'} a ${opts.hasta || '—'}`
    : 'Periodo: todos'
  const generado = new Date().toLocaleString('es-AR')
  doc.text(`${rango}   ·   Generado: ${generado}   ·   Total: ${rows.length}`, 40, 58)

  autoTable(doc, {
    startY: 72,
    head: [['Fecha', 'Hora', 'Ciudadano', 'DNI', 'Atiende', 'Prestación', 'Observaciones']],
    body: rows.map((r) => [r.fecha, r.hora, r.ciudadano, r.dni, r.atiende, r.prestacion, r.observaciones]),
    styles: { fontSize: 8, cellPadding: 4, textColor: [38, 37, 30] },
    headStyles: { fillColor: [245, 78, 0], textColor: [255, 255, 255], fontStyle: 'bold' },
    alternateRowStyles: { fillColor: [247, 247, 244] },
    columnStyles: { 6: { cellWidth: 200 } },
  })

  const fname = `turnos_atendidos_${new Date().toISOString().slice(0, 10)}.pdf`
  doc.save(fname)
}
