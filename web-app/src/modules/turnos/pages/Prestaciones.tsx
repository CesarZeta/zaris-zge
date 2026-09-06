import { useMemo, useState } from 'react'
import { Plus, RefreshCw, Search } from 'lucide-react'
import { usePrestaciones, useEliminarPrestacion } from '../hooks/useTurnos'
import { AvisoBuscar, useBusquedaDiferida } from '../lib/busqueda'
import { PrestacionFormModal } from '../components/PrestacionFormModal'
import { ConfirmModal } from '../../agenda/components/ConfirmModal'
import { useNotificationsStore } from '../../../stores/notifications'
import type { ClasePrestacion, TipoPrestacion } from '../types/turno'

const CLASE_LABEL: Record<ClasePrestacion, string> = {
  atencion: 'Atención de personas',
  reserva_espacio: 'Reserva de espacio',
}

export function Prestaciones() {
  const push = useNotificationsStore((s) => s.push)
  // Búsqueda diferida (§23): el catálogo no se pide al entrar, sino al Buscar.
  const busqueda = useBusquedaDiferida<{ clase: ClasePrestacion | '' }>({ clase: '' })
  const fClase = busqueda.borrador.clase
  const setFClase = (v: ClasePrestacion | '') => busqueda.setBorrador({ clase: v })
  const [fRecurso, setFRecurso] = useState('')
  const [fTexto, setFTexto] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editPrest, setEditPrest] = useState<TipoPrestacion | null>(null)
  const [confirmBaja, setConfirmBaja] = useState<TipoPrestacion | null>(null)

  const { data, isLoading, isError, error, refetch, isFetching } = usePrestaciones(
    { clase: busqueda.aplicado?.clase || undefined },
    { enabled: busqueda.buscado, version: busqueda.version },
  )
  const eliminar = useEliminarPrestacion()

  const prestaciones = data ?? []

  // Filtros por recurso y área de servicio (informe QA 2026-06, hallazgos 3 y 4):
  // opciones derivadas de las prestaciones cargadas (§23 — no catálogos
  // completos), client-side.
  const [fArea, setFArea] = useState('')
  const recursos = useMemo(() => {
    const m = new Map<string, string>()
    for (const p of prestaciones) {
      const key = p.tipo_recurso === 'espacio' ? `espacio:${p.id_espacio}` : `agente:${p.id_agente}`
      if (p.recurso_nombre) m.set(key, p.recurso_nombre)
    }
    return [...m.entries()].map(([value, label]) => ({ value, label })).sort((a, b) => a.label.localeCompare(b.label))
  }, [prestaciones])
  const areas = useMemo(() => {
    const m = new Map<string, string>()
    for (const p of prestaciones) {
      if (p.id_area != null && p.area_nombre) m.set(String(p.id_area), p.area_nombre)
    }
    return [...m.entries()].map(([value, label]) => ({ value, label })).sort((a, b) => a.label.localeCompare(b.label))
  }, [prestaciones])

  const filtradas = useMemo(() => {
    let res = prestaciones
    if (fRecurso) {
      res = res.filter((p) => (p.tipo_recurso === 'espacio' ? `espacio:${p.id_espacio}` : `agente:${p.id_agente}`) === fRecurso)
    }
    if (fArea) {
      res = res.filter((p) => String(p.id_area ?? '') === fArea)
    }
    const txt = fTexto.trim().toLowerCase()
    if (txt) {
      res = res.filter((p) =>
        [p.nombre, p.recurso_nombre, p.ubicacion_nombre, p.descripcion, p.area_nombre, p.subarea_nombre].filter(Boolean).join(' ').toLowerCase().includes(txt))
    }
    return res
  }, [prestaciones, fTexto, fRecurso, fArea])

  async function doBaja(p: TipoPrestacion) {
    setConfirmBaja(null)
    try {
      await eliminar.mutateAsync(p.id_tipo_prestacion)
      push({ kind: 'success', title: 'Prestación dada de baja' })
    } catch (e) {
      push({ kind: 'error', title: 'No se pudo dar de baja', body: (e as Error).message })
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <h1 style={titulo}>prestaciones</h1>
        <p style={{ margin: '6px 0 0', color: 'var(--fg-3)', fontSize: 'var(--size-btn)' }}>
          catálogo de prestaciones que se cumplen con turnos. Cada prestación define su recurso (un agente o un lugar de atención) y la duración del turno.
        </p>
      </div>

      <form style={toolbar} onSubmit={(e) => { e.preventDefault(); busqueda.buscar() }}>
        <div style={field}>
          <label style={lbl}>Buscar</label>
          <input
            type="text"
            value={fTexto}
            onChange={(e) => setFTexto(e.target.value)}
            placeholder="Nombre o recurso"
            style={{ ...inp, minWidth: 220 }}
          />
        </div>
        <div style={field}>
          <label style={lbl}>Tipo</label>
          <select value={fClase} onChange={(e) => setFClase(e.target.value as ClasePrestacion | '')} style={inp}>
            <option value="">Todas</option>
            <option value="atencion">Atención de personas</option>
            <option value="reserva_espacio">Reserva de espacio</option>
          </select>
        </div>
        <div style={field}>
          <label style={lbl}>Recurso</label>
          <select value={fRecurso} onChange={(e) => setFRecurso(e.target.value)} style={inp}>
            <option value="">Todos</option>
            {recursos.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
        </div>
        {areas.length > 0 && (
          <div style={field}>
            <label style={lbl}>Área de servicio</label>
            <select value={fArea} onChange={(e) => setFArea(e.target.value)} style={inp}>
              <option value="">Todas</option>
              {areas.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
            </select>
          </div>
        )}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'flex-end' }}>
          <button type="submit" style={btnPrimary} title="Traer el catálogo con el tipo elegido">
            <Search size={14} strokeWidth={1.5} /> Buscar
          </button>
          <button type="button" onClick={() => refetch()} style={btnGhost} title="Refrescar" disabled={!busqueda.buscado}>
            <RefreshCw size={14} strokeWidth={1.5} style={{ animation: isFetching ? 'spin 1s linear infinite' : undefined }} />
          </button>
          <button type="button" onClick={() => { setEditPrest(null); setModalOpen(true) }} style={btnGhost}>
            <Plus size={14} strokeWidth={1.5} /> Nueva prestación
          </button>
        </div>
      </form>

      {isError && <div style={errorBanner}>{(error as Error)?.message ?? 'Error al cargar prestaciones'}</div>}

      {!busqueda.buscado && (
        <AvisoBuscar texto="Elegí el tipo de prestación que querés ver y presioná Buscar. Los filtros Recurso y Área de servicio se habilitan con lo que traiga la búsqueda." />
      )}

      {busqueda.buscado && <div style={card}>
        <table style={table}>
          <thead>
            <tr>
              <th style={th}>Nombre</th>
              <th style={th}>Tipo</th>
              <th style={th}>Recurso</th>
              <th style={th}>Ubicación</th>
              <th style={th}>Área de servicio</th>
              <th style={th}>Duración</th>
              <th style={{ ...th, textAlign: 'right' }}>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={7} style={empty}>Cargando…</td></tr>}
            {!isLoading && !isError && filtradas.length === 0 && (
              <tr><td colSpan={7} style={empty}>No hay prestaciones para los filtros seleccionados.</td></tr>
            )}
            {filtradas.map((p) => (
              <tr key={p.id_tipo_prestacion}>
                <td style={td}>
                  {p.nombre}
                  {p.descripcion && <div style={{ fontSize: '0.72rem', color: 'var(--fg-3)' }}>{p.descripcion}</div>}
                </td>
                <td style={td}>
                  <ClaseBadge clase={p.clase} />
                  {p.registra_atencion && (
                    <span style={badgeHistoria} title="Al cumplir cada turno se registra la intervención y las recomendaciones en la historia del ciudadano">
                      Historia de atención
                    </span>
                  )}
                </td>
                <td style={td}>
                  {p.recurso_nombre ?? '—'}
                  <div style={{ fontSize: '0.7rem', color: 'var(--fg-3)' }}>
                    {p.tipo_recurso === 'espacio' ? 'Lugar de atención' : 'Agente'}
                  </div>
                </td>
                <td style={td}>
                  {p.ubicacion_nombre
                    ?? <span style={{ color: 'var(--fg-3)' }} title="Cargá la ubicación editando la prestación">Sin ubicación</span>}
                </td>
                <td style={td}>
                  {p.area_nombre ?? '—'}
                  {p.subarea_nombre && <div style={{ fontSize: '0.7rem', color: 'var(--fg-3)' }}>{p.subarea_nombre}</div>}
                </td>
                <td style={td}>{p.duracion_min} min</td>
                <td style={{ ...td, textAlign: 'right', whiteSpace: 'nowrap' }}>
                  <button onClick={() => { setEditPrest(p); setModalOpen(true) }} style={btnGhostSm}>Editar</button>
                  <button onClick={() => setConfirmBaja(p)} style={{ ...btnDangerSm, marginLeft: 4 }}>Dar de baja</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>}

      <PrestacionFormModal open={modalOpen} onClose={() => setModalOpen(false)} prestacion={editPrest} />
      <ConfirmModal
        open={confirmBaja != null}
        title="Dar de baja prestación"
        message={`Dar de baja la prestación "${confirmBaja?.nombre ?? ''}"? No se podrán reservar turnos nuevos con ella (los existentes no se afectan).`}
        confirmLabel="Dar de baja"
        danger
        onConfirm={() => confirmBaja && doBaja(confirmBaja)}
        onCancel={() => setConfirmBaja(null)}
      />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

const badgeHistoria: React.CSSProperties = {
  marginLeft: 6, background: 'rgba(245,78,0,0.12)', color: 'var(--zaris-orange)',
  fontSize: '0.72rem', fontWeight: 600, padding: '2px 9px', borderRadius: 999,
}

function ClaseBadge({ clase }: { clase: ClasePrestacion }) {
  const isAtencion = clase === 'atencion'
  return (
    <span style={{
      background: isAtencion ? 'rgba(31,138,101,0.16)' : 'rgba(106,27,154,0.14)',
      color: isAtencion ? '#1f8a65' : '#6a1b9a',
      fontSize: '0.72rem', fontWeight: 600, padding: '2px 9px', borderRadius: 999,
    }}>{CLASE_LABEL[clase]}</span>
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
const btnSmBase: React.CSSProperties = { ...btnBase, fontSize: '0.76rem', padding: '4px 9px' }
const btnGhostSm: React.CSSProperties = {
  ...btnSmBase, background: 'transparent', color: 'var(--fg-2)', border: '1px solid var(--border-medium)',
}
const btnDangerSm: React.CSSProperties = {
  ...btnSmBase, background: 'transparent', color: 'var(--color-error)', borderColor: 'var(--color-error)',
}
const card: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 12, overflowX: 'auto',
}
const table: React.CSSProperties = {
  width: '100%', borderCollapse: 'separate', borderSpacing: 0, fontSize: '0.84rem', minWidth: 720,
}
const th: React.CSSProperties = {
  textAlign: 'left', fontWeight: 600, fontSize: '0.72rem', textTransform: 'uppercase',
  letterSpacing: '0.04em', color: 'var(--fg-3)', padding: '9px 12px',
  borderBottom: '1px solid var(--border-primary)', background: 'var(--surface-300)', whiteSpace: 'nowrap',
}
const td: React.CSSProperties = {
  padding: '10px 12px', borderBottom: '1px solid var(--border-primary)',
  verticalAlign: 'middle', background: 'var(--surface-100)',
}
const empty: React.CSSProperties = {
  padding: 36, textAlign: 'center', color: 'var(--fg-3)', fontSize: '0.88rem',
}
const errorBanner: React.CSSProperties = {
  background: '#ffebee', border: '1px solid #ffcdd2', borderLeft: '4px solid var(--color-error)',
  borderRadius: 8, padding: '12px 16px', color: '#c62828', fontSize: '0.86rem',
}
