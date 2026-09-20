import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search } from 'lucide-react'
import { useAreasCatalogo, useSubareasCatalogo, useReclamosListado, type FiltrosReclamos } from '../hooks/useReclamos'
import { StatsBar } from '../components/StatsBar'
import { Badge } from '../components/Badge'
import { AvisoBuscar, useBusquedaDiferida } from '../../../ui/busqueda'

const ESTADOS_VALIDOS = [
  'Sin asignar', 'En gestión', 'En espera', 'En auditoría', 'Resuelto', 'Cancelado',
] as const

// Filtros que viajan al backend (§23): se editan en el `borrador` y se aplican
// recién al presionar Buscar. El texto ya no tiene debounce: viaja con Buscar.
interface FiltrosBorrador {
  estado: string | null
  idArea: number | null
  idSubarea: number | null
  texto: string
}

const FILTROS_INICIALES: FiltrosBorrador = { estado: null, idArea: null, idSubarea: null, texto: '' }

export function ListView() {
  const navigate = useNavigate()

  // Búsqueda diferida (§23): entrar NO pide reclamos ni stats. Los catálogos
  // (áreas/subáreas) sí cargan al entrar: son las opciones del filtro.
  const busqueda = useBusquedaDiferida<FiltrosBorrador>(FILTROS_INICIALES)
  const { borrador, setBorrador, aplicado, buscar, buscado } = busqueda
  const { estado, idArea, idSubarea, texto } = borrador

  const filtros: FiltrosReclamos = {
    estado: aplicado?.estado ?? undefined,
    id_area: aplicado?.idArea ?? undefined,
    id_subarea: aplicado?.idSubarea ?? undefined,
    texto: aplicado?.texto.trim() || undefined,
    limit: 200,
  }

  const areas = useAreasCatalogo()
  const subareas = useSubareasCatalogo(idArea ?? undefined)
  const listado = useReclamosListado(filtros, { enabled: buscado, version: busqueda.version })

  // Si cambia el área y la subárea elegida ya no pertenece a ella, resetearla
  // (sobre el borrador; se aplica con el próximo Buscar).
  useEffect(() => {
    if (idSubarea == null || subareas.data == null) return
    if (!subareas.data.some((s) => s.id_subarea === idSubarea)) setBorrador((b) => ({ ...b, idSubarea: null }))
  }, [subareas.data, idSubarea, setBorrador])

  // Clic en una tarjeta de StatsBar o en el badge de estado de una fila = filtro
  // explícito, equivalente a Buscar: actualiza el borrador Y busca. Como
  // `buscar()` toma el borrador del render actual, el disparo se difiere a un
  // effect acotado que corre cuando `buscar` ya se rehizo con el borrador nuevo.
  const buscarPendiente = useRef(false)
  useEffect(() => {
    if (!buscarPendiente.current) return
    buscarPendiente.current = false
    buscar()
  }, [buscar])

  function filtrarPorEstado(nuevo: string | null) {
    buscarPendiente.current = true
    setBorrador((b) => ({ ...b, estado: nuevo }))
  }

  function limpiar() {
    setBorrador(FILTROS_INICIALES)
  }

  const cantidad = listado.data?.length ?? 0

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button type="button" onClick={() => navigate('/reclamos/nuevo')} style={btnAccent}>+ Nuevo reclamo</button>
      </div>

      {/* Toolbar: es un form para que Enter en cualquier filtro dispare Buscar. */}
      <form style={filterBarStyle} onSubmit={(e) => { e.preventDefault(); buscar() }}>
        <div style={filterGroup}>
          <label style={filterLabel}>Buscar</label>
          <input
            value={texto}
            onChange={(e) => { const v = e.target.value; setBorrador((b) => ({ ...b, texto: v })) }}
            placeholder="Nro reclamo, ciudadano, DNI, descripción..."
            style={{ ...filterInput, minWidth: 240 }}
          />
        </div>
        <div style={filterGroup}>
          <label style={filterLabel}>Estado</label>
          <select
            value={estado ?? ''}
            onChange={(e) => { const v = e.target.value || null; setBorrador((b) => ({ ...b, estado: v })) }}
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
            onChange={(e) => { const v = e.target.value ? Number(e.target.value) : null; setBorrador((b) => ({ ...b, idArea: v, idSubarea: null })) }}
            disabled={areas.isLoading}
            style={filterInput}
          >
            <option value="">Todas</option>
            {(areas.data ?? []).map((a) => <option key={a.id_area} value={a.id_area}>{a.nombre}</option>)}
          </select>
        </div>
        <div style={filterGroup}>
          <label style={filterLabel}>Subárea</label>
          <select
            value={idSubarea ?? ''}
            onChange={(e) => { const v = e.target.value ? Number(e.target.value) : null; setBorrador((b) => ({ ...b, idSubarea: v })) }}
            disabled={subareas.isLoading}
            style={filterInput}
          >
            <option value="">Todas</option>
            {(subareas.data ?? []).map((s) => <option key={s.id_subarea} value={s.id_subarea}>{s.nombre}</option>)}
          </select>
        </div>
        <div style={{ display: 'flex', gap: 8, alignSelf: 'flex-end' }}>
          <button type="submit" style={btnBuscar} title="Traer los reclamos con los filtros elegidos">
            <Search size={14} strokeWidth={1.5} /> Buscar
          </button>
          <button type="button" onClick={limpiar} style={btnGhost}>Limpiar</button>
        </div>
      </form>

      {/* Contadores por estado: consultan al backend, así que recién después de la
          primera búsqueda. Clic en una tarjeta filtra por ese estado y busca. */}
      {buscado && <StatsBar estadoActivo={estado} onSelectEstado={filtrarPorEstado} />}

      {!buscado && (
        <AvisoBuscar texto="Elegí estado, área o texto (o dejá Todos) y presioná Buscar para ver los reclamos." />
      )}

      {buscado && (
        <div style={{ fontSize: 'var(--size-ui)', color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>
          {listado.isLoading
            ? 'Cargando reclamos...'
            : `${cantidad} reclamo${cantidad !== 1 ? 's' : ''} encontrado${cantidad !== 1 ? 's' : ''}`}
        </div>
      )}

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
                    {(r.subarea_nombre || r.area_nombre) && (
                      <div style={{ fontSize: '0.72rem', color: 'var(--fg-3)' }}>{r.subarea_nombre || r.area_nombre}</div>
                    )}
                  </Td>
                  <Td>
                    {/* #6 — clic en el badge filtra el listado, no navega al detalle */}
                    <span
                      onClick={(e) => { e.stopPropagation(); filtrarPorEstado(r.estado) }}
                      title={`Filtrar por estado "${r.estado}"`}
                      style={badgeClickable}
                    >
                      <Badge kind="estado" value={r.estado} />
                    </span>
                  </Td>
                  <Td>
                    <Badge kind="prioridad" value={r.prioridad ?? 'Media'} />
                  </Td>
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
// Buscar de la barra de filtros: mismo acento, alto alineado con Limpiar + icono.
const btnBuscar: React.CSSProperties = {
  ...btnAccent, padding: '7px 14px',
  display: 'inline-flex', alignItems: 'center', gap: 6,
}
const badgeClickable: React.CSSProperties = {
  display: 'inline-flex', cursor: 'pointer',
}
const tableWrap: React.CSSProperties = {
  overflowX: 'auto', borderRadius: 'var(--radius-lg)',
  border: '1px solid var(--border-primary)', background: 'var(--surface-100)',
  boxShadow: 'var(--shadow-ambient)',
}
