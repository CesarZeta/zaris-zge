import { useMemo, useState } from 'react'
import { Download, RefreshCw, Search } from 'lucide-react'
import { useTurnos } from '../hooks/useTurnos'
import { TurnoDetalleModal } from '../components/TurnoDetalleModal'
import { useNotificationsStore } from '../../../stores/notifications'
import { useTurnoFiltros, TurnoFiltrosBar } from '../lib/turnoFiltros'
import { AvisoBuscar, useBusquedaDiferida } from '../lib/busqueda'
import { exportarAtendidosPdf, type TurnoPdfRow } from '../lib/exportPdf'
import { useUbicacionTurnosStore } from '../stores/ubicacionTurnos'
import type { Turno } from '../types/turno'

export function Atendidos() {
  const push = useNotificationsStore((s) => s.push)

  const [detalle, setDetalle] = useState<Turno | null>(null)
  const [fTexto, setFTexto] = useState('')
  // Búsqueda diferida (§23): las fechas viajan al backend recién al Buscar.
  const busqueda = useBusquedaDiferida<{ desde: string; hasta: string }>({ desde: '', hasta: '' })
  const { desde: fDesde, hasta: fHasta } = busqueda.borrador
  const setFDesde = (v: string) => busqueda.setBorrador({ ...busqueda.borrador, desde: v })
  const setFHasta = (v: string) => busqueda.setBorrador({ ...busqueda.borrador, hasta: v })

  // Contexto ubicación-primero (F2): respeta la ubicación elegida en el módulo.
  const ubicacion = useUbicacionTurnosStore((s) => s.ubicacion)
  const { data, isLoading, isError, error, refetch, isFetching } = useTurnos({
    estado: 'cumplido',
    fecha_desde: busqueda.aplicado?.desde || undefined,
    fecha_hasta: busqueda.aplicado?.hasta || undefined,
    id_espacio_ubicacion: ubicacion?.id_espacio,
  }, { enabled: busqueda.buscado, version: busqueda.version })

  const turnos = data ?? []

  // Barra de filtros unificada del modulo (Prestacion / Atiende / Ciudadano),
  // la misma de Turnos y Agenda (informe QA 2026-06, hallazgo 2). Reemplaza a
  // los antiguos selects de agente/lugar solo-supervisor: las opciones se
  // derivan de los turnos cargados, ya scopeados por nivel en el backend.
  const { filtros, setFiltros, opciones, filtrar, hayActivos, limpiar } = useTurnoFiltros(turnos)

  const filtrados = useMemo(() => {
    let res = filtrar(turnos)
    const txt = fTexto.trim().toLowerCase()
    if (txt) {
      res = res.filter((t) =>
        [t.ciudadano_nombre, t.ciudadano_dni, t.recurso_nombre, t.prestacion_nombre, t.observaciones]
          .filter(Boolean)
          .join(' ')
          .toLowerCase()
          .includes(txt),
      )
    }
    return res
  }, [turnos, fTexto, filtrar])

  function doExport() {
    if (filtrados.length === 0) {
      push({ kind: 'error', title: 'No hay turnos para exportar' })
      return
    }
    const rows: TurnoPdfRow[] = filtrados.map((t) => ({
      fecha: t.fecha,
      hora: `${t.hora_inicio.slice(0, 5)}-${t.hora_fin.slice(0, 5)}`,
      ciudadano: t.ciudadano_nombre ?? '',
      dni: t.ciudadano_dni ?? '',
      atiende: t.recurso_nombre ?? t.agente_nombre ?? '',
      prestacion: t.prestacion_nombre ?? '',
      observaciones: t.observaciones ?? '',
    }))
    exportarAtendidosPdf(rows, { desde: fDesde, hasta: fHasta })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <h1 style={titulo}>atendidos</h1>
        <p style={{ margin: '6px 0 0', color: 'var(--fg-3)', fontSize: 'var(--size-btn)' }}>
          turnos cumplidos. Filtrá por fecha, prestación, quién atiende o ciudadano, y exportá a PDF. Clic en una fila para ver la atención registrada.
        </p>
      </div>

      <form style={toolbar} onSubmit={(e) => { e.preventDefault(); busqueda.buscar() }}>
        <div style={field}>
          <label style={lbl}>Buscar</label>
          <input
            type="text"
            value={fTexto}
            onChange={(e) => setFTexto(e.target.value)}
            placeholder="Ciudadano, DNI o servicio"
            style={{ ...inp, minWidth: 200 }}
          />
        </div>
        <div style={field}>
          <label style={lbl}>Desde</label>
          <input type="date" value={fDesde} onChange={(e) => setFDesde(e.target.value)} style={inp} />
        </div>
        <div style={field}>
          <label style={lbl}>Hasta</label>
          <input type="date" value={fHasta} onChange={(e) => setFHasta(e.target.value)} style={inp} />
        </div>
        <TurnoFiltrosBar opciones={opciones} filtros={filtros} setFiltros={setFiltros} />
        {hayActivos && (
          <button type="button" onClick={limpiar} style={{ ...btnGhost, alignSelf: 'flex-end' }} title="Limpiar filtros de prestación, recurso y ciudadano">
            Limpiar
          </button>
        )}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'flex-end' }}>
          <button type="submit" style={btnPrimary} title="Traer los turnos atendidos del rango elegido">
            <Search size={14} strokeWidth={1.5} /> Buscar
          </button>
          <button type="button" onClick={() => refetch()} style={btnGhost} title="Refrescar" disabled={!busqueda.buscado}>
            <RefreshCw size={14} strokeWidth={1.5} style={{ animation: isFetching ? 'spin 1s linear infinite' : undefined }} />
          </button>
          <button type="button" onClick={doExport} style={btnGhost} disabled={!busqueda.buscado}>
            <Download size={14} strokeWidth={1.5} /> Exportar PDF
          </button>
        </div>
      </form>

      {busqueda.buscado && (
        <div style={{ fontSize: '0.82rem', color: 'var(--fg-3)' }}>
          {filtrados.length} turno{filtrados.length === 1 ? '' : 's'} atendido{filtrados.length === 1 ? '' : 's'}
        </div>
      )}

      {isError && <div style={errorBanner}>{(error as Error)?.message ?? 'Error al cargar turnos'}</div>}

      {!busqueda.buscado && (
        <AvisoBuscar texto="Elegí el rango de fechas (o dejalo vacío para todo) y presioná Buscar para ver los turnos atendidos." />
      )}

      {busqueda.buscado && <div style={card}>
        <table style={table}>
          <thead>
            <tr>
              <th style={th}>Fecha / Hora</th>
              <th style={th}>Ciudadano</th>
              <th style={th}>Atendió</th>
              <th style={th}>Prestación</th>
              <th style={th}>Observaciones</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={5} style={empty}>Cargando…</td></tr>}
            {!isLoading && !isError && filtrados.length === 0 && (
              <tr><td colSpan={5} style={empty}>No hay turnos atendidos para los filtros seleccionados.</td></tr>
            )}
            {filtrados.map((t) => (
              <tr key={t.id_turno} onClick={() => setDetalle(t)} style={{ cursor: 'pointer' }} title="Ver detalle y atención registrada">
                <td style={td}>
                  <div style={mono}>{t.fecha}</div>
                  <div style={{ ...mono, fontSize: '0.74rem', color: 'var(--fg-3)' }}>
                    {t.hora_inicio.slice(0, 5)}–{t.hora_fin.slice(0, 5)}
                  </div>
                </td>
                <td style={td}>
                  {t.ciudadano_nombre ?? '—'}
                  {t.ciudadano_dni && <div style={{ fontSize: '0.72rem', color: 'var(--fg-3)' }}>DNI {t.ciudadano_dni}</div>}
                </td>
                <td style={td}>
                  {t.recurso_nombre ?? t.agente_nombre ?? '—'}
                  <div style={{ fontSize: '0.7rem', color: 'var(--fg-3)' }}>
                    {t.id_espacio != null ? 'Lugar de atención' : 'Agente'}
                  </div>
                </td>
                <td style={td}>{t.prestacion_nombre ?? '—'}</td>
                <td style={{ ...td, maxWidth: 280, color: 'var(--fg-3)', whiteSpace: 'pre-wrap' }}>{t.observaciones ?? ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>}
      <TurnoDetalleModal turno={detalle} onClose={() => setDetalle(null)} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

const titulo: React.CSSProperties = {
  margin: 0, fontFamily: 'var(--font-display)', fontSize: 'var(--size-section)',
  fontWeight: 400, letterSpacing: 'var(--track-section)', color: 'var(--fg-1)',
}
const toolbar: React.CSSProperties = {
  display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end',
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 12, padding: 14,
}
const field: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: 4 }
const lbl: React.CSSProperties = {
  fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--fg-3)',
}
const inp: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: 13, padding: '6px 10px',
  borderRadius: 'var(--radius-md)', border: '1px solid var(--border-primary)',
  background: 'var(--surface-100)', outline: 'none',
}
const btnBase: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.82rem', cursor: 'pointer',
  borderRadius: 8, padding: '7px 12px', border: '1px solid transparent', fontWeight: 500,
  display: 'inline-flex', alignItems: 'center', gap: 6,
}
const btnPrimary: React.CSSProperties = {
  ...btnBase, background: 'var(--zaris-orange)', color: 'white', borderColor: 'var(--zaris-orange)',
}
const btnGhost: React.CSSProperties = {
  ...btnBase, background: 'transparent', color: 'var(--fg-2)', border: '1px solid var(--border-medium)',
}
const card: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 12, overflowX: 'auto',
}
const table: React.CSSProperties = {
  width: '100%', borderCollapse: 'separate', borderSpacing: 0,
  fontSize: '0.84rem', minWidth: 780,
}
const th: React.CSSProperties = {
  textAlign: 'left', fontWeight: 600, fontSize: '0.72rem',
  textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--fg-3)',
  padding: '9px 12px', borderBottom: '1px solid var(--border-primary)',
  background: 'var(--surface-300)', whiteSpace: 'nowrap',
}
const td: React.CSSProperties = {
  padding: '10px 12px', borderBottom: '1px solid var(--border-primary)',
  verticalAlign: 'middle', background: 'var(--surface-100)',
}
const mono: React.CSSProperties = {
  fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--fg-2)', whiteSpace: 'nowrap',
}
const empty: React.CSSProperties = {
  padding: 36, textAlign: 'center', color: 'var(--fg-3)', fontSize: '0.88rem',
}
const errorBanner: React.CSSProperties = {
  background: '#ffebee', border: '1px solid #ffcdd2', borderLeft: '4px solid var(--color-error)',
  borderRadius: 8, padding: '12px 16px', color: '#c62828', fontSize: '0.86rem',
}
