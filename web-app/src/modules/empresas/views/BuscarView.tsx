import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useNotificationsStore } from '../../../stores/notifications'
import { buscarEmpresas, useCambiarEstadoEmpresa, useEmpresasRecientes } from '../hooks/useEmpresas'
import { ConfirmModal } from '../../agenda/components/ConfirmModal'
import type { Empresa } from '../types/empresa'

type Modo = 'numero' | 'texto'

export function BuscarView() {
  const navigate = useNavigate()
  const push = useNotificationsStore((s) => s.push)
  const cambiarEstado = useCambiarEstadoEmpresa()
  const recientes = useEmpresasRecientes(5)

  const [modo, setModo] = useState<Modo>('numero')
  const [query, setQuery] = useState('')
  const [resultados, setResultados] = useState<Empresa[] | null>(null)
  const [buscando, setBuscando] = useState(false)
  const [bajaTarget, setBajaTarget] = useState<Empresa | null>(null)

  const unico = resultados && resultados.length === 1 ? resultados[0] : null

  async function ejecutarBusqueda() {
    const q = query.trim()
    if (!q) {
      push({ kind: 'info', title: 'Ingresa un valor para buscar' })
      return
    }
    setBuscando(true)
    try {
      // En busqueda numerica, strip guiones para flexibilidad
      const qEnviar = modo === 'numero' ? q.replace(/-/g, '') : q
      const data = await buscarEmpresas({ q: qEnviar, tipo: modo, limit: 20 })
      setResultados(data)
      if (data.length === 0) {
        push({ kind: 'info', title: 'No se encontro ninguna empresa con esos datos' })
      }
    } catch (err) {
      push({ kind: 'error', title: 'Error en la busqueda', body: (err as Error).message })
    } finally {
      setBuscando(false)
    }
  }

  function confirmarBaja() {
    if (!bajaTarget) return
    const e = bajaTarget
    setBajaTarget(null)
    cambiarEstado.mutate(
      { id: e.id_empresa, activo: false },
      {
        onSuccess: () => {
          push({ kind: 'success', title: 'Empresa dada de baja', body: e.nombre })
          setResultados(null)
          setQuery('')
        },
        onError: (err) => push({ kind: 'error', title: 'Error al dar de baja', body: (err as Error).message }),
      },
    )
  }

  return (
    <>
      <section
        style={{
          background: 'var(--color-cyan-soft, rgba(96,165,200,.08))',
          border: '1px solid var(--border-primary)',
          borderRadius: 'var(--radius-xl)',
          padding: '1rem 1.25rem',
        }}
      >
        <div style={titulo}>Buscar empresa existente</div>

        <div style={{ display: 'flex', gap: 6, marginBottom: '0.6rem' }}>
          <button
            type="button"
            onClick={() => { setModo('numero'); setQuery(''); setResultados(null) }}
            style={{
              ...pillStyle,
              background: modo === 'numero' ? 'var(--zaris-dark)' : 'transparent',
              color: modo === 'numero' ? 'var(--zaris-cream)' : 'var(--fg-2)',
              border: modo === 'numero' ? 'none' : '1px solid var(--border-primary)',
            }}
          >
            # CUIT
          </button>
          <button
            type="button"
            onClick={() => { setModo('texto'); setQuery(''); setResultados(null) }}
            style={{
              ...pillStyle,
              background: modo === 'texto' ? 'var(--zaris-dark)' : 'transparent',
              color: modo === 'texto' ? 'var(--zaris-cream)' : 'var(--fg-2)',
              border: modo === 'texto' ? 'none' : '1px solid var(--border-primary)',
            }}
          >
            Aa Nombre
          </button>
        </div>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); ejecutarBusqueda() } }}
            placeholder={modo === 'numero' ? 'Ingresa CUIT de la empresa...' : 'Ingresa nombre o razon social...'}
            autoFocus
            style={searchInput}
          />
          <button onClick={ejecutarBusqueda} disabled={buscando} style={btnPrimary}>
            {buscando ? 'Buscando...' : 'Buscar'}
          </button>
          <button onClick={() => navigate('/empresas/nuevo')} style={btnAccent}>+ Nuevo</button>
          <button onClick={() => navigate('/empresas/listado')} style={btnGhost}>Listado</button>
        </div>

        {resultados && resultados.length > 0 && (
          <div style={resultadoBox}>
            {unico ? (
              <>
                <div style={{ fontWeight: 600, color: 'var(--fg-1)', fontSize: '1.05rem' }}>{unico.nombre}</div>
                <div style={{ fontSize: '0.85rem', color: 'var(--fg-2)', marginTop: 4 }}>
                  CUIT: {unico.cuit} · {unico.telefono || '-'} · {unico.email || '-'} · {unico.localidad || '-'}
                  {!unico.activo && <span style={{ color: 'var(--color-error)', marginLeft: 8 }}>(inactiva)</span>}
                </div>
                <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
                  <button onClick={() => navigate(`/empresas/${unico.id_empresa}/editar`)} style={btnPrimary}>Editar</button>
                  <button onClick={() => navigate(`/empresas/${unico.id_empresa}`)} style={btnGhost}>Consultar</button>
                  {unico.activo && (
                    <button onClick={() => setBajaTarget(unico)} style={btnDanger}>Dar de baja</button>
                  )}
                  <button onClick={() => navigate('/empresas/nuevo')} style={btnGhost}>+ Alta nueva de todas formas</button>
                </div>
              </>
            ) : (
              <>
                <div style={{ fontWeight: 600, color: 'var(--fg-1)', fontSize: '1.05rem' }}>
                  Se encontraron {resultados.length} empresas:
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
                  {resultados.map((e) => (
                    <div key={e.id_empresa} style={resultadoItem}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <strong style={{ color: 'var(--fg-1)', fontSize: '0.95rem' }}>{e.nombre}</strong>
                        <div style={{ fontSize: '0.82rem', color: 'var(--fg-2)', marginTop: 2 }}>
                          CUIT {e.cuit} · {e.telefono || '-'} · {e.email || '-'}
                          {!e.activo && <span style={{ color: 'var(--color-error)', marginLeft: 6 }}>(inactiva)</span>}
                        </div>
                      </div>
                      <button onClick={() => navigate(`/empresas/${e.id_empresa}/editar`)} style={btnXs}>Editar</button>
                      <button onClick={() => navigate(`/empresas/${e.id_empresa}`)} style={btnXsGhost}>Ver</button>
                    </div>
                  ))}
                </div>
                <div style={{ marginTop: 10 }}>
                  <button onClick={() => navigate('/empresas/nuevo')} style={btnGhost}>+ Alta nueva de todas formas</button>
                </div>
              </>
            )}
          </div>
        )}
      </section>

      <section>
        <div style={titulo}>Ultimas empresas ingresadas</div>
        {recientes.isLoading && <div style={{ color: 'var(--fg-3)', fontSize: '0.82rem' }}>Cargando...</div>}
        {recientes.isError && <div style={{ color: 'var(--color-error)', fontSize: '0.82rem' }}>Error al cargar</div>}
        {recientes.data && recientes.data.length === 0 && (
          <div style={{ color: 'var(--fg-3)', fontSize: '0.82rem' }}>Sin registros</div>
        )}
        {recientes.data && recientes.data.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {recientes.data.map((e) => (
              <button
                key={e.id_empresa}
                onClick={() => navigate(`/empresas/${e.id_empresa}`)}
                style={previewRow}
                onMouseEnter={(ev) => { ev.currentTarget.style.borderColor = 'var(--zaris-orange)'; ev.currentTarget.style.background = 'rgba(245,78,0,0.03)' }}
                onMouseLeave={(ev) => { ev.currentTarget.style.borderColor = 'var(--border-primary)'; ev.currentTarget.style.background = 'var(--surface-100)' }}
              >
                <span style={{ fontWeight: 600, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', textAlign: 'left' }}>
                  {e.nombre}
                </span>
                <span style={{ fontSize: 'var(--size-caption)', color: 'var(--fg-2)', fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap' }}>
                  {e.cuit || '—'}
                </span>
                <span style={{ fontSize: 'var(--size-caption)', color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap' }}>
                  {e.localidad || e.provincia || '—'}
                </span>
                <span style={e.activo ? badgeActivo : badgeInactivo}>{e.activo ? 'Activo' : 'Inactivo'}</span>
              </button>
            ))}
          </div>
        )}
      </section>

      <ConfirmModal
        open={bajaTarget != null}
        title="Confirmar baja"
        message={bajaTarget ? `Dar de baja a "${bajaTarget.nombre}" (CUIT ${bajaTarget.cuit})? La empresa quedara inactiva.` : ''}
        confirmLabel="Dar de baja"
        cancelLabel="Cancelar"
        danger
        onConfirm={confirmarBaja}
        onCancel={() => setBajaTarget(null)}
      />
    </>
  )
}

// ── Estilos ──
const titulo: React.CSSProperties = {
  fontSize: 'var(--size-caption)', fontWeight: 700, textTransform: 'uppercase',
  letterSpacing: '0.07em', color: 'var(--fg-3)', marginBottom: '0.6rem',
}
const pillStyle: React.CSSProperties = {
  padding: '4px 12px', borderRadius: 'var(--radius-pill)',
  fontFamily: 'var(--font-display)', fontSize: '0.78rem', fontWeight: 600,
  cursor: 'pointer', transition: 'background 150ms',
}
const searchInput: React.CSSProperties = {
  flex: 1, minWidth: 240, padding: '9px 12px',
  border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)',
  background: 'var(--surface-100)', fontFamily: 'var(--font-display)',
  fontSize: 'var(--size-ui)', color: 'var(--fg-1)', outline: 'none',
}
const btnPrimary: React.CSSProperties = {
  padding: '9px 14px', background: 'var(--zaris-dark)',
  color: 'var(--zaris-cream)', border: 'none',
  borderRadius: 'var(--radius-lg)', fontFamily: 'var(--font-display)',
  fontSize: 'var(--size-btn)', fontWeight: 500, cursor: 'pointer',
}
const btnAccent: React.CSSProperties = { ...btnPrimary, background: 'var(--zaris-orange)' }
const btnGhost: React.CSSProperties = {
  padding: '9px 14px', background: 'transparent', color: 'var(--fg-2)',
  border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)',
  fontFamily: 'var(--font-display)', fontSize: 'var(--size-btn)', cursor: 'pointer',
}
const btnDanger: React.CSSProperties = { ...btnPrimary, background: 'var(--color-error)' }
const btnXs: React.CSSProperties = {
  padding: '5px 10px', background: 'var(--zaris-dark)', color: 'var(--zaris-cream)',
  border: 'none', borderRadius: 'var(--radius-md)', fontFamily: 'var(--font-display)',
  fontSize: '0.75rem', cursor: 'pointer',
}
const btnXsGhost: React.CSSProperties = {
  ...btnXs, background: 'transparent', color: 'var(--fg-2)',
  border: '1px solid var(--border-primary)',
}
const resultadoBox: React.CSSProperties = {
  background: 'var(--surface-100)', borderRadius: 'var(--radius-lg)',
  padding: '1rem 1.25rem', marginTop: '1rem',
  border: '1px solid var(--border-primary)',
}
const resultadoItem: React.CSSProperties = {
  display: 'flex', alignItems: 'flex-start', gap: 8,
  padding: '8px 0', borderBottom: '1px solid var(--border-primary)',
}
const previewRow: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 10, padding: '8px 14px',
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-md)', cursor: 'pointer',
  fontSize: 'var(--size-ui)', color: 'var(--fg-1)', fontFamily: 'var(--font-display)',
  width: '100%', textAlign: 'left', transition: 'border-color 150ms, background 150ms',
}
const badgeActivo: React.CSSProperties = {
  fontSize: 'var(--size-caption)', fontWeight: 600, padding: '2px 8px',
  borderRadius: 'var(--radius-pill)', whiteSpace: 'nowrap',
  background: 'rgba(31,138,101,.10)', color: 'var(--color-success)',
}
const badgeInactivo: React.CSSProperties = {
  ...badgeActivo, background: 'rgba(207,45,86,.10)', color: 'var(--color-error)',
}
