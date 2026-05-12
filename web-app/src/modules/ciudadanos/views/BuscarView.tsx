import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useNotificationsStore } from '../../../stores/notifications'
import { useCambiarEstadoCiudadano, useCiudadanosRecientes, buscarCiudadanos } from '../hooks/useCiudadanos'
import { ConfirmModal } from '../../agenda/components/ConfirmModal'
import type { Ciudadano } from '../types/ciudadano'

type Modo = 'numero' | 'texto'

export function BuscarView() {
  const navigate = useNavigate()
  const push = useNotificationsStore((s) => s.push)
  const cambiarEstado = useCambiarEstadoCiudadano()
  const recientes = useCiudadanosRecientes(5)

  const [modo, setModo] = useState<Modo>('numero')
  const [query, setQuery] = useState('')
  const [resultados, setResultados] = useState<Ciudadano[] | null>(null)
  const [total, setTotal] = useState(0)
  const [buscando, setBuscando] = useState(false)
  const [bajaTarget, setBajaTarget] = useState<Ciudadano | null>(null)

  const ciudadanoUnico = resultados && resultados.length === 1 ? resultados[0] : null

  async function ejecutarBusqueda() {
    const q = query.trim()
    if (!q) {
      push({ kind: 'info', title: 'Ingresa un valor para buscar' })
      return
    }
    setBuscando(true)
    try {
      const res = await buscarCiudadanos({ q, tipo: modo, limit: 20 })
      setResultados(res.data)
      setTotal(Number(res.headers.get('X-Total-Count') ?? res.data.length))
      if (res.data.length === 0) {
        push({ kind: 'info', title: 'No se encontro ningun ciudadano con esos datos' })
      }
    } catch (err) {
      push({ kind: 'error', title: 'Error en la busqueda', body: (err as Error).message })
    } finally {
      setBuscando(false)
    }
  }

  function confirmarBaja() {
    if (!bajaTarget) return
    const c = bajaTarget
    setBajaTarget(null)
    cambiarEstado.mutate(
      { id: c.id_ciudadano, activo: false },
      {
        onSuccess: () => {
          push({ kind: 'success', title: 'Ciudadano dado de baja', body: `${c.apellido}, ${c.nombre}` })
          setResultados(null)
          setQuery('')
        },
        onError: (e) => push({ kind: 'error', title: 'Error al dar de baja', body: (e as Error).message }),
      },
    )
  }

  return (
    <>
      {/* Panel busqueda (color celeste DS) */}
      <section
        style={{
          background: 'var(--color-cyan-soft, rgba(96,165,200,.08))',
          border: '1px solid var(--border-primary)',
          borderRadius: 'var(--radius-xl)',
          padding: '1rem 1.25rem',
        }}
      >
        <div style={{ fontSize: 'var(--size-caption)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--fg-3)', marginBottom: '0.6rem' }}>
          Buscar ciudadano existente
        </div>

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
            # DNI / CUIL
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
            placeholder={modo === 'numero' ? 'Ingresa Nro. de Documento o CUIL...' : 'Ingresa nombre o apellido...'}
            autoFocus
            style={{
              flex: 1, minWidth: 240,
              padding: '9px 12px',
              border: '1px solid var(--border-primary)',
              borderRadius: 'var(--radius-lg)',
              background: 'var(--surface-100)',
              fontFamily: 'var(--font-display)',
              fontSize: 'var(--size-ui)',
              color: 'var(--fg-1)',
              outline: 'none',
            }}
          />
          <button onClick={ejecutarBusqueda} disabled={buscando} style={btnPrimary}>
            {buscando ? 'Buscando...' : 'Buscar'}
          </button>
          <button onClick={() => navigate('/ciudadanos/nuevo')} style={btnAccent}>
            + Nuevo
          </button>
          <button onClick={() => navigate('/ciudadanos/listado')} style={btnGhost}>
            Listado
          </button>
        </div>

        {/* Resultados de busqueda */}
        {resultados && resultados.length > 0 && (
          <div style={resultadoBox}>
            {ciudadanoUnico ? (
              <>
                <div style={{ fontWeight: 600, color: 'var(--fg-1)', fontSize: '1.05rem' }}>
                  {ciudadanoUnico.apellido}, {ciudadanoUnico.nombre}
                </div>
                <div style={{ fontSize: '0.85rem', color: 'var(--fg-2)', marginTop: 4 }}>
                  {ciudadanoUnico.doc_tipo} {ciudadanoUnico.doc_nro} · CUIL: {ciudadanoUnico.cuil} · {ciudadanoUnico.telefono} · {ciudadanoUnico.email}
                  {!ciudadanoUnico.activo && <span style={{ color: 'var(--color-error)', marginLeft: 8 }}>(inactivo)</span>}
                </div>
                <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
                  <button onClick={() => navigate(`/ciudadanos/${ciudadanoUnico.id_ciudadano}/editar`)} style={btnPrimary}>Editar</button>
                  <button onClick={() => navigate(`/ciudadanos/${ciudadanoUnico.id_ciudadano}`)} style={btnGhost}>Consultar</button>
                  {ciudadanoUnico.activo && (
                    <button onClick={() => setBajaTarget(ciudadanoUnico)} style={btnDanger}>Dar de baja</button>
                  )}
                  <button onClick={() => navigate('/ciudadanos/nuevo')} style={btnGhost}>+ Alta nueva de todas formas</button>
                </div>
              </>
            ) : (
              <>
                <div style={{ fontWeight: 600, color: 'var(--fg-1)', fontSize: '1.05rem' }}>
                  Se encontraron {resultados.length} ciudadanos {total > resultados.length && `(de ${total})`}:
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
                  {resultados.map((c) => (
                    <div key={c.id_ciudadano} style={resultadoItem}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <strong style={{ color: 'var(--fg-1)', fontSize: '0.95rem' }}>{c.apellido}, {c.nombre}</strong>
                        <div style={{ fontSize: '0.82rem', color: 'var(--fg-2)', marginTop: 2 }}>
                          {c.doc_tipo} {c.doc_nro} · {c.telefono || '-'} · {c.email || '-'}
                          {!c.activo && <span style={{ color: 'var(--color-error)', marginLeft: 6 }}>(inactivo)</span>}
                        </div>
                      </div>
                      <button onClick={() => navigate(`/ciudadanos/${c.id_ciudadano}/editar`)} style={btnXs}>Editar</button>
                      <button onClick={() => navigate(`/ciudadanos/${c.id_ciudadano}`)} style={btnXsGhost}>Ver</button>
                    </div>
                  ))}
                </div>
                <div style={{ marginTop: 10 }}>
                  <button onClick={() => navigate('/ciudadanos/nuevo')} style={btnGhost}>+ Alta nueva de todas formas</button>
                </div>
              </>
            )}
          </div>
        )}
      </section>

      {/* Vista previa: ultimos ingresados */}
      <section>
        <div style={{ fontSize: 'var(--size-caption)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--fg-3)', marginBottom: '0.5rem' }}>
          Ultimos ciudadanos ingresados
        </div>
        {recientes.isLoading && <div style={{ color: 'var(--fg-3)', fontSize: '0.82rem' }}>Cargando...</div>}
        {recientes.isError && <div style={{ color: 'var(--color-error)', fontSize: '0.82rem' }}>Error al cargar</div>}
        {recientes.data && recientes.data.length === 0 && (
          <div style={{ color: 'var(--fg-3)', fontSize: '0.82rem' }}>Sin registros</div>
        )}
        {recientes.data && recientes.data.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {recientes.data.map((c) => (
              <button
                key={c.id_ciudadano}
                onClick={() => navigate(`/ciudadanos/${c.id_ciudadano}`)}
                style={previewRow}
                onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--zaris-orange)'; e.currentTarget.style.background = 'rgba(245,78,0,0.03)' }}
                onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border-primary)'; e.currentTarget.style.background = 'var(--surface-100)' }}
              >
                <span style={{ fontWeight: 600, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', textAlign: 'left' }}>
                  {c.apellido}, {c.nombre}
                </span>
                <span style={{ fontSize: 'var(--size-caption)', color: 'var(--fg-2)', fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap' }}>
                  {c.doc_tipo} {c.doc_nro || '-'}
                </span>
                <span style={{ fontSize: 'var(--size-caption)', color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap' }}>
                  {c.cuil || '-'}
                </span>
                <span style={c.activo ? badgeActivo : badgeInactivo}>{c.activo ? 'Activo' : 'Inactivo'}</span>
              </button>
            ))}
          </div>
        )}
      </section>

      <ConfirmModal
        open={bajaTarget != null}
        title="Confirmar baja"
        message={bajaTarget ? `Dar de baja a ${bajaTarget.apellido}, ${bajaTarget.nombre} (CUIL ${bajaTarget.cuil})? El registro quedara inactivo y no aparecera en busquedas.` : ''}
        confirmLabel="Dar de baja"
        cancelLabel="Cancelar"
        danger
        onConfirm={confirmarBaja}
        onCancel={() => setBajaTarget(null)}
      />
    </>
  )
}

// ── Estilos inline ──
const pillStyle: React.CSSProperties = {
  padding: '4px 12px',
  borderRadius: 'var(--radius-pill)',
  fontFamily: 'var(--font-display)',
  fontSize: '0.78rem',
  fontWeight: 600,
  cursor: 'pointer',
  transition: 'background 150ms',
}

const btnPrimary: React.CSSProperties = {
  padding: '9px 14px',
  background: 'var(--zaris-dark)',
  color: 'var(--zaris-cream)',
  border: 'none',
  borderRadius: 'var(--radius-lg)',
  fontFamily: 'var(--font-display)',
  fontSize: 'var(--size-btn)',
  fontWeight: 500,
  cursor: 'pointer',
}

const btnAccent: React.CSSProperties = {
  ...btnPrimary,
  background: 'var(--zaris-orange)',
}

const btnGhost: React.CSSProperties = {
  padding: '9px 14px',
  background: 'transparent',
  color: 'var(--fg-2)',
  border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-lg)',
  fontFamily: 'var(--font-display)',
  fontSize: 'var(--size-btn)',
  cursor: 'pointer',
}

const btnDanger: React.CSSProperties = {
  ...btnPrimary,
  background: 'var(--color-error)',
}

const btnXs: React.CSSProperties = {
  padding: '5px 10px',
  background: 'var(--zaris-dark)',
  color: 'var(--zaris-cream)',
  border: 'none',
  borderRadius: 'var(--radius-md)',
  fontFamily: 'var(--font-display)',
  fontSize: '0.75rem',
  cursor: 'pointer',
}

const btnXsGhost: React.CSSProperties = {
  ...btnXs,
  background: 'transparent',
  color: 'var(--fg-2)',
  border: '1px solid var(--border-primary)',
}

const resultadoBox: React.CSSProperties = {
  background: 'var(--surface-100)',
  borderRadius: 'var(--radius-lg)',
  padding: '1rem 1.25rem',
  marginTop: '1rem',
  border: '1px solid var(--border-primary)',
}

const resultadoItem: React.CSSProperties = {
  display: 'flex',
  alignItems: 'flex-start',
  gap: 8,
  padding: '8px 0',
  borderBottom: '1px solid var(--border-primary)',
}

const previewRow: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 10,
  padding: '8px 14px',
  background: 'var(--surface-100)',
  border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-md)',
  cursor: 'pointer',
  fontSize: 'var(--size-ui)',
  color: 'var(--fg-1)',
  fontFamily: 'var(--font-display)',
  width: '100%',
  textAlign: 'left',
  transition: 'border-color 150ms, background 150ms',
}

const badgeActivo: React.CSSProperties = {
  fontSize: 'var(--size-caption)',
  fontWeight: 600,
  padding: '2px 8px',
  borderRadius: 'var(--radius-pill)',
  whiteSpace: 'nowrap',
  background: 'rgba(31,138,101,.10)',
  color: 'var(--color-success)',
}

const badgeInactivo: React.CSSProperties = {
  ...badgeActivo,
  background: 'rgba(207,45,86,.10)',
  color: 'var(--color-error)',
}
