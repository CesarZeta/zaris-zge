import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useEmpresasListado } from '../hooks/useEmpresas'
import type { Empresa } from '../types/empresa'

type Orden = 'reciente' | 'antiguo' | 'az' | 'za'

export function ListView() {
  const navigate = useNavigate()
  const { data, isLoading, isError, error } = useEmpresasListado()

  const [texto, setTexto] = useState('')
  const [orden, setOrden] = useState<Orden>('reciente')
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')

  const filtrados = useMemo<Empresa[]>(() => {
    if (!data) return []
    let rows = [...data]
    const t = texto.toLowerCase().trim()
    if (t) {
      const tDigits = t.replace(/-/g, '')
      rows = rows.filter((e) =>
        (e.nombre || '').toLowerCase().includes(t) ||
        (e.cuit || '').replace(/-/g, '').includes(tDigits),
      )
    }
    if (desde || hasta) {
      rows = rows.filter((e) => {
        const d = (e.fecha_alta || '').slice(0, 10)
        if (!d) return true
        if (desde && d < desde) return false
        if (hasta && d > hasta) return false
        return true
      })
    }
    if (orden === 'reciente') rows.sort((a, b) => (b.id_empresa || 0) - (a.id_empresa || 0))
    else if (orden === 'antiguo') rows.sort((a, b) => (a.id_empresa || 0) - (b.id_empresa || 0))
    else if (orden === 'az') rows.sort((a, b) => (a.nombre || '').localeCompare(b.nombre || '', 'es'))
    else if (orden === 'za') rows.sort((a, b) => (b.nombre || '').localeCompare(a.nombre || '', 'es'))
    return rows
  }, [data, texto, desde, hasta, orden])

  function limpiar() {
    setTexto(''); setDesde(''); setHasta(''); setOrden('reciente')
  }

  const fechaImpresion = new Date().toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' })

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <h2 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600, color: 'var(--fg-1)' }}>
          Listado de empresas
        </h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => window.print()} style={btnGhost}>Imprimir</button>
          <button onClick={() => navigate('/empresas')} style={btnGhost}>← Volver</button>
        </div>
      </div>

      <div className="print-only" style={{ display: 'none' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 700, textAlign: 'center', margin: 0 }}>Padron de Empresas — ZARIS</h2>
        <p style={{ fontSize: '0.78rem', color: '#666', marginTop: 4, textAlign: 'center' }}>
          Listado generado el {fechaImpresion} · {filtrados.length} registro{filtrados.length !== 1 ? 's' : ''}
        </p>
      </div>

      <div className="no-print" style={filterBarStyle}>
        <div style={filterGroup}>
          <label style={filterLabel}>Buscar</label>
          <input
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            placeholder="Nombre o CUIT..."
            style={filterInput}
          />
        </div>
        <div style={filterGroup}>
          <label style={filterLabel}>Ordenar</label>
          <select value={orden} onChange={(e) => setOrden(e.target.value as Orden)} style={filterInput}>
            <option value="reciente">Mas reciente primero</option>
            <option value="az">Nombre A → Z</option>
            <option value="za">Nombre Z → A</option>
            <option value="antiguo">Mas antiguo primero</option>
          </select>
        </div>
        <div style={filterGroup}>
          <label style={filterLabel}>Fecha desde</label>
          <input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} style={filterInput} />
        </div>
        <div style={filterGroup}>
          <label style={filterLabel}>Fecha hasta</label>
          <input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} style={filterInput} />
        </div>
        <div style={{ display: 'flex', gap: 8, alignSelf: 'flex-end' }}>
          <button onClick={limpiar} style={btnGhost}>Limpiar</button>
        </div>
      </div>

      <div style={{ fontSize: 'var(--size-ui)', color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>
        {filtrados.length} empresa{filtrados.length !== 1 ? 's' : ''} encontrada{filtrados.length !== 1 ? 's' : ''}
      </div>

      {isLoading && <div style={{ color: 'var(--fg-3)', padding: 20 }}>Cargando...</div>}
      {isError && <div style={{ color: 'var(--color-error)', padding: 20 }}>Error: {(error as Error).message}</div>}
      {data && filtrados.length === 0 && (
        <div style={{ color: 'var(--fg-3)', textAlign: 'center', padding: 40 }}>Sin resultados</div>
      )}
      {filtrados.length > 0 && (
        <div style={tableWrap}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--size-ui)' }}>
            <thead>
              <tr style={{ background: 'var(--surface-200)' }}>
                <Th>Nombre</Th>
                <Th>CUIT</Th>
                <Th>Localidad</Th>
                <Th>Provincia</Th>
                <Th>Estado</Th>
                <Th className="no-print">Acciones</Th>
              </tr>
            </thead>
            <tbody>
              {filtrados.map((e) => (
                <tr key={e.id_empresa} style={{ borderTop: '1px solid var(--border-primary)' }}>
                  <Td>{e.nombre}</Td>
                  <Td mono>{e.cuit || '—'}</Td>
                  <Td>{e.localidad || '—'}</Td>
                  <Td>{e.provincia || '—'}</Td>
                  <Td>
                    <span style={e.activo ? badgeActivo : badgeInactivo}>
                      {e.activo ? 'Activo' : 'Inactivo'}
                    </span>
                  </Td>
                  <Td className="no-print">
                    <button onClick={() => navigate(`/empresas/${e.id_empresa}`)} style={tblBtn}>Ver</button>
                    <button onClick={() => navigate(`/empresas/${e.id_empresa}/editar`)} style={tblBtn}>Editar</button>
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
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

function Th({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <th className={className} style={{
      padding: '10px 16px', textAlign: 'left', fontWeight: 600,
      fontSize: 'var(--size-caption)', textTransform: 'uppercase',
      letterSpacing: '0.05em', color: 'var(--fg-2)', whiteSpace: 'nowrap',
    }}>
      {children}
    </th>
  )
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
const tableWrap: React.CSSProperties = {
  overflowX: 'auto', borderRadius: 'var(--radius-lg)',
  border: '1px solid var(--border-primary)', background: 'var(--surface-100)',
  boxShadow: 'var(--shadow-ambient)',
}
const tblBtn: React.CSSProperties = {
  border: '1px solid var(--border-primary)', background: 'transparent',
  color: 'var(--fg-2)', padding: '4px 10px', borderRadius: 'var(--radius-md)',
  cursor: 'pointer', fontSize: 'var(--size-caption)',
  fontFamily: 'var(--font-display)', marginRight: 4,
}
const badgeActivo: React.CSSProperties = {
  display: 'inline-block', padding: '2px 10px', borderRadius: 'var(--radius-pill)',
  fontSize: 10, fontWeight: 600,
  background: 'rgba(31,138,101,.12)', color: 'var(--color-success)',
  textTransform: 'uppercase', letterSpacing: '0.04em',
}
const badgeInactivo: React.CSSProperties = {
  ...badgeActivo, background: 'rgba(207,45,86,.12)', color: 'var(--color-error)',
}
