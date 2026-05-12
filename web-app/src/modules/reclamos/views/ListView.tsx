import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAreasCatalogo, useReclamosListado, type FiltrosReclamos } from '../hooks/useReclamos'
import { StatsBar } from '../components/StatsBar'
import { Badge } from '../components/Badge'
import type { Prioridad } from '../types/reclamo'

const ESTADOS_VALIDOS = [
  'Sin asignar', 'En gestión', 'En espera', 'En auditoría', 'Resuelto', 'Cancelado',
] as const

const PRIORIDADES: Prioridad[] = ['Baja', 'Media', 'Alta']

export function ListView() {
  const navigate = useNavigate()

  const [estado, setEstado] = useState<string | null>(null)
  const [idArea, setIdArea] = useState<number | null>(null)
  const [prioridad, setPrioridad] = useState<string | null>(null)
  const [texto, setTexto] = useState('')
  const [textoDebounced, setTextoDebounced] = useState('')

  useEffect(() => {
    const t = setTimeout(() => setTextoDebounced(texto.trim()), 300)
    return () => clearTimeout(t)
  }, [texto])

  const filtros: FiltrosReclamos = {
    estado: estado ?? undefined,
    id_area: idArea ?? undefined,
    prioridad: prioridad ?? undefined,
    texto: textoDebounced || undefined,
    limit: 200,
  }

  const areas = useAreasCatalogo()
  const listado = useReclamosListado(filtros)

  function limpiar() {
    setEstado(null); setIdArea(null); setPrioridad(null); setTexto('')
  }

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button onClick={() => navigate('/reclamos/nuevo')} style={btnAccent}>+ Nuevo reclamo</button>
      </div>

      <StatsBar estadoActivo={estado} onSelectEstado={setEstado} />

      <div style={filterBarStyle}>
        <div style={filterGroup}>
          <label style={filterLabel}>Buscar</label>
          <input
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            placeholder="Nro reclamo, ciudadano, DNI, descripción..."
            style={{ ...filterInput, minWidth: 240 }}
          />
        </div>
        <div style={filterGroup}>
          <label style={filterLabel}>Estado</label>
          <select
            value={estado ?? ''}
            onChange={(e) => setEstado(e.target.value || null)}
            style={filterInput}
          >
            <option value="">Todos</option>
            {ESTADOS_VALIDOS.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div style={filterGroup}>
          <label style={filterLabel}>Área</label>
          <select
            value={idArea ?? ''}
            onChange={(e) => setIdArea(e.target.value ? Number(e.target.value) : null)}
            disabled={areas.isLoading}
            style={filterInput}
          >
            <option value="">Todas</option>
            {(areas.data ?? []).map((a) => <option key={a.id_area} value={a.id_area}>{a.nombre}</option>)}
          </select>
        </div>
        <div style={filterGroup}>
          <label style={filterLabel}>Prioridad</label>
          <select
            value={prioridad ?? ''}
            onChange={(e) => setPrioridad(e.target.value || null)}
            style={filterInput}
          >
            <option value="">Todas</option>
            {PRIORIDADES.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        <div style={{ display: 'flex', gap: 8, alignSelf: 'flex-end' }}>
          <button onClick={limpiar} style={btnGhost}>Limpiar</button>
        </div>
      </div>

      <div style={{ fontSize: 'var(--size-ui)', color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>
        {listado.isLoading
          ? 'Cargando reclamos...'
          : `${listado.data?.length ?? 0} reclamo${(listado.data?.length ?? 0) !== 1 ? 's' : ''} encontrado${(listado.data?.length ?? 0) !== 1 ? 's' : ''}`}
      </div>

      {listado.isError && (
        <div style={{ color: 'var(--color-error)', padding: 16 }}>
          Error: {(listado.error as Error).message}
        </div>
      )}

      {listado.data && listado.data.length === 0 && !listado.isLoading && (
        <div style={{ color: 'var(--fg-3)', textAlign: 'center', padding: 40 }}>
          Sin reclamos que coincidan con los filtros
        </div>
      )}

      {listado.data && listado.data.length > 0 && (
        <div style={tableWrap}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--size-ui)' }}>
            <thead>
              <tr style={{ background: 'var(--surface-200)' }}>
                <Th>N° reclamo</Th>
                <Th>Ciudadano</Th>
                <Th>Tipo</Th>
                <Th>Estado</Th>
                <Th>Prioridad</Th>
                <Th>Fecha</Th>
                <Th>Responsable</Th>
              </tr>
            </thead>
            <tbody>
              {listado.data.map((r) => (
                <tr
                  key={r.id_reclamo}
                  onClick={() => navigate(`/reclamos/${r.id_reclamo}`)}
                  style={{ borderTop: '1px solid var(--border-primary)', cursor: 'pointer' }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--surface-200)' }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
                >
                  <Td mono>{r.nro_reclamo || `#${r.id_reclamo}`}</Td>
                  <Td>
                    <strong style={{ fontSize: '0.85rem' }}>
                      {r.ciudadano_apellido || '—'}, {r.ciudadano_nombre || '—'}
                    </strong>
                    <div style={{ fontSize: '0.72rem', color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>
                      {r.doc_nro || '—'}
                    </div>
                  </Td>
                  <Td>
                    <div style={{ fontSize: '0.84rem', fontWeight: 500 }}>{r.tipo_nombre || '—'}</div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--fg-3)' }}>{r.area_nombre || '—'}</div>
                  </Td>
                  <Td><Badge kind="estado" value={r.estado} /></Td>
                  <Td><Badge kind="prioridad" value={r.prioridad ?? 'Media'} /></Td>
                  <Td mono style={{ fontSize: '0.78rem' }}>{formatFecha(r.fecha_alta)}</Td>
                  <Td style={{ fontSize: '0.82rem', color: 'var(--fg-2)' }}>{r.agente_nombre || '—'}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

function formatFecha(iso: string): string {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleString('es-AR', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return iso
  }
}

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th style={{
      padding: '10px 16px', textAlign: 'left', fontWeight: 600,
      fontSize: 'var(--size-caption)', textTransform: 'uppercase',
      letterSpacing: '0.05em', color: 'var(--fg-2)', whiteSpace: 'nowrap',
    }}>
      {children}
    </th>
  )
}

function Td({ children, mono, style }: { children: React.ReactNode; mono?: boolean; style?: React.CSSProperties }) {
  return (
    <td style={{
      padding: '10px 16px',
      color: mono ? 'var(--fg-2)' : 'var(--fg-1)',
      fontFamily: mono ? 'var(--font-mono)' : 'var(--font-display)',
      fontSize: 'var(--size-ui)',
      ...style,
    }}>
      {children}
    </td>
  )
}

const filterBarStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'flex-end', gap: 12, flexWrap: 'wrap',
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-lg)', padding: '1rem 1.25rem',
}
const filterGroup: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: 4 }
const filterLabel: React.CSSProperties = {
  fontSize: 'var(--size-caption)', fontWeight: 600,
  textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--fg-3)',
}
const filterInput: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  color: 'var(--fg-1)', padding: '6px 10px', borderRadius: 'var(--radius-md)',
  fontSize: 'var(--size-ui)', fontFamily: 'var(--font-display)', outline: 'none',
  minWidth: 140,
}
const btnGhost: React.CSSProperties = {
  padding: '7px 14px', background: 'transparent', color: 'var(--fg-2)',
  border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)',
  fontFamily: 'var(--font-display)', fontSize: 'var(--size-btn)', cursor: 'pointer',
}
const btnAccent: React.CSSProperties = {
  padding: '9px 16px', background: 'var(--zaris-orange)', color: '#fff',
  border: 'none', borderRadius: 'var(--radius-lg)', fontFamily: 'var(--font-display)',
  fontSize: 'var(--size-btn)', fontWeight: 500, cursor: 'pointer',
}
const tableWrap: React.CSSProperties = {
  overflowX: 'auto', borderRadius: 'var(--radius-lg)',
  border: '1px solid var(--border-primary)', background: 'var(--surface-100)',
  boxShadow: 'var(--shadow-ambient)',
}
