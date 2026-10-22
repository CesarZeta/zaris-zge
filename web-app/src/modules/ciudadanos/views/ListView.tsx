import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Search } from 'lucide-react'
import { useCiudadanosListado } from '../hooks/useCiudadanos'
import { AvisoBuscar, useBusquedaDiferida } from '../../../ui/busqueda'
import { ThOrden, useOrden } from '../../../ui/orden'
import type { OrdenCiudadanos } from '../api/ciudadanosApi'

/** Filas por página del padrón. */
const POR_PAGINA = 100

export function ListView() {
  const navigate = useNavigate()
  const location = useLocation()

  // Búsqueda diferida (§23): texto y fechas de alta son el borrador y viajan al
  // backend recién con Buscar. Con un padrón real no se puede traer todo y
  // filtrar en pantalla: esconde a los que no entraron en la carga.
  const busqueda = useBusquedaDiferida({ texto: '', desde: '', hasta: '' })
  const { borrador, setBorrador, aplicado, buscado, buscar: aplicarFiltros } = busqueda
  const [offset, setOffset] = useState(0)
  // Orden por columna: lo resuelve el backend. Sin columna elegida, el más
  // reciente primero. Cambiarlo vuelve a la primera página.
  const { orden, alternar, setOrden } = useOrden<OrdenCiudadanos>()

  const { data, isLoading, isError, error } = useCiudadanosListado({
    q: aplicado?.texto.trim() || undefined,
    desde: aplicado?.desde || undefined,
    hasta: aplicado?.hasta || undefined,
    orden: orden?.campo, dir: orden?.dir,
    limit: POR_PAGINA, offset,
  }, { enabled: buscado, version: busqueda.version })

  function buscar() {
    setOffset(0)
    aplicarFiltros()
  }
  function ordenar(campo: OrdenCiudadanos) {
    setOffset(0)
    alternar(campo)
  }
  function limpiar() {
    setBorrador({ texto: '', desde: '', hasta: '' })
    setOrden(null)
  }

  // Intención explícita: el botón "Listado" de BuscarView navega con
  // state { buscar: true } — ese clic YA es la búsqueda, así que arrancamos
  // buscando. Por URL directa (sin state) se muestra el gate. El state se
  // limpia (replace) para que un F5 o volver atrás no vuelvan a auto-buscar.
  const autoBuscar = (location.state as { buscar?: boolean } | null)?.buscar === true
  useEffect(() => {
    if (!autoBuscar) return
    aplicarFiltros()
    navigate(location.pathname, { replace: true, state: null })
  }, [autoBuscar, aplicarFiltros, navigate, location.pathname])

  const filas = data?.filas ?? []
  const total = data?.total ?? 0
  const rango = filas.length ? `${offset + 1}–${offset + filas.length} de ${total}` : `0 de ${total}`
  const fechaImpresion = new Date().toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' })

  return (
    <>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <h2 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600, color: 'var(--fg-1)' }}>
          Listado de ciudadanos
        </h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            type="button"
            onClick={() => window.print()}
            style={buscado ? btnGhost : btnGhostOff}
            disabled={!buscado}
            title={buscado ? 'Imprimir la página visible' : 'Primero presioná Buscar'}
          >
            Imprimir
          </button>
          <button type="button" onClick={() => navigate('/ciudadanos')} style={btnGhost}>← Volver</button>
        </div>
      </div>

      {/* Encabezado para impresion (solo visible al imprimir) */}
      <div className="print-only" style={{ display: 'none' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 700, textAlign: 'center', margin: 0 }}>Padron de Ciudadanos — ZARIS</h2>
        <p style={{ fontSize: '0.78rem', color: '#666', marginTop: 4, textAlign: 'center' }}>
          Listado generado el {fechaImpresion} · registros {rango}
        </p>
      </div>

      {/* Filtros: viajan al backend. Enter = Buscar. */}
      <form className="no-print" style={filterBarStyle} onSubmit={(e) => { e.preventDefault(); buscar() }}>
        <div style={filterGroup}>
          <label style={filterLabel}>Buscar</label>
          <input
            value={borrador.texto}
            onChange={(e) => setBorrador((b) => ({ ...b, texto: e.target.value }))}
            placeholder="Nombre, apellido, DNI, CUIL o email..."
            style={{ ...filterInput, minWidth: 260 }}
          />
        </div>
        <div style={filterGroup}>
          <label style={filterLabel}>Alta desde</label>
          <input type="date" value={borrador.desde} onChange={(e) => setBorrador((b) => ({ ...b, desde: e.target.value }))} style={filterInput} />
        </div>
        <div style={filterGroup}>
          <label style={filterLabel}>Alta hasta</label>
          <input type="date" value={borrador.hasta} onChange={(e) => setBorrador((b) => ({ ...b, hasta: e.target.value }))} style={filterInput} />
        </div>
        <div style={{ display: 'flex', gap: 8, alignSelf: 'flex-end' }}>
          <button type="submit" style={btnBuscar} title="Traer los ciudadanos con estos filtros">
            <Search size={14} strokeWidth={1.5} /> Buscar
          </button>
          <button type="button" onClick={limpiar} style={btnGhost}>Limpiar</button>
        </div>
      </form>

      {!buscado && (
        <AvisoBuscar texto="Escribí un nombre, documento o rango de alta (o dejalos vacíos para ver todo) y presioná Buscar." />
      )}

      {buscado && data && (
        <div style={{ fontSize: 'var(--size-ui)', color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>
          {total} ciudadano{total !== 1 ? 's' : ''} encontrado{total !== 1 ? 's' : ''}
          {total > POR_PAGINA && <> · se muestran de a {POR_PAGINA}</>}
        </div>
      )}

      {isLoading && <div style={{ color: 'var(--fg-3)', padding: 20 }}>Cargando...</div>}
      {isError && <div style={{ color: 'var(--color-error)', padding: 20 }}>Error: {(error as Error).message}</div>}
      {data && filas.length === 0 && (
        <div style={{ color: 'var(--fg-3)', textAlign: 'center', padding: 40 }}>Sin resultados</div>
      )}
      {filas.length > 0 && (
        <div style={tableWrap}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--size-ui)' }}>
            <thead>
              <tr style={{ background: 'var(--surface-200)' }}>
                <ThOrden campo="nombre" orden={orden} onOrdenar={ordenar} style={thStyle}>Apellido, Nombre</ThOrden>
                <ThOrden campo="documento" orden={orden} onOrdenar={ordenar} style={thStyle}>Documento</ThOrden>
                <ThOrden campo="cuil" orden={orden} onOrdenar={ordenar} style={thStyle}>CUIL</ThOrden>
                <ThOrden campo="email" orden={orden} onOrdenar={ordenar} style={thStyle}>Email</ThOrden>
                <ThOrden campo="alta" orden={orden} onOrdenar={ordenar} style={thStyle}>Alta</ThOrden>
                <ThOrden campo="estado" orden={orden} onOrdenar={ordenar} style={thStyle}>Estado</ThOrden>
                <th className="no-print" style={thStyle}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {filas.map((c) => (
                <tr key={c.id_ciudadano} style={{ borderTop: '1px solid var(--border-primary)' }}>
                  <Td>{c.apellido}, {c.nombre}</Td>
                  <Td mono>{c.doc_tipo} {c.doc_nro || '—'}</Td>
                  <Td mono>{c.cuil || '—'}</Td>
                  <Td>{c.email || '—'}</Td>
                  <Td mono>{fmtFecha(c.fecha_alta)}</Td>
                  <Td>
                    <span style={c.activo ? badgeActivo : badgeInactivo}>
                      {c.activo ? 'Activo' : 'Inactivo'}
                    </span>
                  </Td>
                  <Td className="no-print">
                    <button onClick={() => navigate(`/ciudadanos/${c.id_ciudadano}`)} style={tblBtn}>Ver</button>
                    <button onClick={() => navigate(`/ciudadanos/${c.id_ciudadano}/editar`)} style={tblBtn}>Editar</button>
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {buscado && total > POR_PAGINA && (
        <div className="no-print" style={{ display: 'flex', gap: 8, alignItems: 'center', justifyContent: 'flex-end' }}>
          <button type="button" style={offset > 0 ? btnGhost : btnGhostOff} disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - POR_PAGINA))}>Anterior</button>
          <span style={{ fontSize: 'var(--size-caption)', color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>{rango}</span>
          <button type="button" style={offset + POR_PAGINA < total ? btnGhost : btnGhostOff} disabled={offset + POR_PAGINA >= total}
            onClick={() => setOffset(offset + POR_PAGINA)}>Siguiente</button>
        </div>
      )}

      <style>{`
        @media print {
          .no-print { display: none !important; }
          .print-only { display: block !important; margin-bottom: 1rem; }
        }
      `}</style>
    </>
  )
}

function fmtFecha(iso: string | null | undefined): string {
  const d = iso ? new Date(iso) : null
  if (!d || isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

const thStyle: React.CSSProperties = {
  padding: '10px 16px', textAlign: 'left', fontWeight: 600,
  fontSize: 'var(--size-caption)', textTransform: 'uppercase',
  letterSpacing: '0.05em', color: 'var(--fg-2)', whiteSpace: 'nowrap',
}

function Td({ children, mono, className }: { children: React.ReactNode; mono?: boolean; className?: string }) {
  return (
    <td className={className} style={{
      padding: '10px 16px', color: mono ? 'var(--fg-2)' : 'var(--fg-1)',
      fontFamily: mono ? 'var(--font-mono)' : 'var(--font-display)',
      fontSize: 'var(--size-ui)',
    }}>
      {children}
    </td>
  )
}

const filterBarStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'flex-end',
  gap: 12,
  flexWrap: 'wrap',
  background: 'var(--surface-100)',
  border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-lg)',
  padding: '1rem 1.25rem',
}

const filterGroup: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
}

const filterLabel: React.CSSProperties = {
  fontSize: 'var(--size-caption)',
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  color: 'var(--fg-3)',
}

const filterInput: React.CSSProperties = {
  background: 'var(--surface-100)',
  border: '1px solid var(--border-primary)',
  color: 'var(--fg-1)',
  padding: '6px 10px',
  borderRadius: 'var(--radius-md)',
  fontSize: 'var(--size-ui)',
  fontFamily: 'var(--font-display)',
  outline: 'none',
  minWidth: 140,
}

const btnGhost: React.CSSProperties = {
  padding: '7px 14px',
  background: 'transparent',
  color: 'var(--fg-2)',
  border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-lg)',
  fontFamily: 'var(--font-display)',
  fontSize: 'var(--size-btn)',
  cursor: 'pointer',
}

// "Buscar": acento del módulo (mismo que + Nuevo en BuscarView) + icono.
const btnBuscar: React.CSSProperties = {
  ...btnGhost,
  background: 'var(--zaris-orange)',
  color: 'var(--zaris-cream)',
  border: '1px solid var(--zaris-orange)',
  fontWeight: 500,
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
}

// Ghost deshabilitado (Imprimir antes de buscar, paginado en los extremos).
const btnGhostOff: React.CSSProperties = { ...btnGhost, opacity: 0.5, cursor: 'not-allowed' }

const tableWrap: React.CSSProperties = {
  overflowX: 'auto',
  borderRadius: 'var(--radius-lg)',
  border: '1px solid var(--border-primary)',
  background: 'var(--surface-100)',
  boxShadow: 'var(--shadow-ambient)',
}

const tblBtn: React.CSSProperties = {
  border: '1px solid var(--border-primary)',
  background: 'transparent',
  color: 'var(--fg-2)',
  padding: '4px 10px',
  borderRadius: 'var(--radius-md)',
  cursor: 'pointer',
  fontSize: 'var(--size-caption)',
  fontFamily: 'var(--font-display)',
  marginRight: 4,
}

const badgeActivo: React.CSSProperties = {
  display: 'inline-block',
  padding: '2px 10px',
  borderRadius: 'var(--radius-pill)',
  fontSize: 10,
  fontWeight: 600,
  background: 'rgba(31,138,101,.12)',
  color: 'var(--color-success)',
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
}

const badgeInactivo: React.CSSProperties = {
  ...badgeActivo,
  background: 'rgba(207,45,86,.12)',
  color: 'var(--color-error)',
}
