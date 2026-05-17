import { useEffect, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { Plus, Search, RefreshCw } from 'lucide-react'
import { Button, Input, Skeleton, EmptyState } from '../../../ui'
import { useBandeja, useTiposTramite } from '../hooks/useTramites'
import { EstadoBadge } from '../components/EstadoBadge'
import type { TramiteBandejaItem, BandejaParams } from '../types'

const LIMIT = 50
const TABS = [
  { id: 'mis_tramites', label: 'Mis trámites' },
  { id: 'mi_subarea', label: 'Mi subárea' },
  { id: 'todos', label: 'Todos' },
]

export function BandejaTramites() {
  const navigate = useNavigate()
  const [sp, setSp] = useSearchParams()

  // Filtros desde URL
  const tabActivo = sp.get('tab') ?? 'todos'
  const estadoCodigo = sp.get('estado') ?? ''
  const idTipo = sp.get('tipo') ? Number(sp.get('tipo')) : undefined
  const iniciadorTipo = sp.get('iniciador') ?? ''
  const numero = sp.get('numero') ?? ''
  const q = sp.get('q') ?? ''
  const paginaActual = parseInt(sp.get('pagina') ?? '1', 10)

  const [busquedaInput, setBusquedaInput] = useState(q)
  const [numeroInput, setNumeroInput] = useState(numero)

  function setParam(key: string, value: string) {
    setSp((prev) => {
      const next = new URLSearchParams(prev)
      if (value) { next.set(key, value) } else { next.delete(key) }
      if (key !== 'pagina') next.delete('pagina')
      return next
    })
  }

  function setTab(tab: string) {
    setSp((prev) => {
      const next = new URLSearchParams(prev)
      next.set('tab', tab)
      next.delete('pagina')
      return next
    })
  }

  // Debounce búsqueda
  useEffect(() => {
    const t = setTimeout(() => setParam('q', busquedaInput), 400)
    return () => clearTimeout(t)
  }, [busquedaInput]) // eslint-disable-line react-hooks/exhaustive-deps

  // Debounce número
  useEffect(() => {
    const t = setTimeout(() => setParam('numero', numeroInput), 400)
    return () => clearTimeout(t)
  }, [numeroInput]) // eslint-disable-line react-hooks/exhaustive-deps

  const offset = (paginaActual - 1) * LIMIT

  const params: BandejaParams = {
    limit: LIMIT,
    offset,
    ...(estadoCodigo ? { estado_codigo: estadoCodigo } : {}),
    ...(idTipo ? { id_tipo_tramite: idTipo } : {}),
    ...(iniciadorTipo ? { iniciador_tipo: iniciadorTipo } : {}),
    ...(numero ? { numero } : {}),
    ...(q ? { q } : {}),
    ...(tabActivo === 'mis_tramites' ? { mis_tramites: true } : {}),
    ...(tabActivo === 'mi_subarea' ? { mi_subarea: true } : {}),
  }

  const { data, isLoading, error, refetch } = useBandeja(params)
  const tipos = useTiposTramite()

  const total = data?.total ?? 0
  const items = data?.items ?? []
  const totalPaginas = Math.ceil(total / LIMIT)

  function irAPagina(p: number) {
    setSp((prev) => {
      const next = new URLSearchParams(prev)
      next.set('pagina', String(p))
      return next
    })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <h1 style={h1Style}>Trámites</h1>
        <Button variant="accent" icon={<Plus size={16} strokeWidth={1.5} />} onClick={() => navigate('/tramites/nuevo')}>
          Nuevo trámite
        </Button>
      </div>

      {/* Tabs rápidos */}
      <div style={{ display: 'flex', gap: 4, background: 'var(--surface-300)', padding: 4, borderRadius: 'var(--radius-lg)', width: 'fit-content' }}>
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setTab(tab.id)}
            style={{
              padding: '6px 14px',
              borderRadius: 'calc(var(--radius-lg) - 2px)',
              border: 'none',
              cursor: 'pointer',
              fontFamily: 'var(--font-display)',
              fontSize: 13,
              fontWeight: tabActivo === tab.id ? 600 : 400,
              background: tabActivo === tab.id ? 'var(--surface-100)' : 'transparent',
              color: tabActivo === tab.id ? 'var(--fg-1)' : 'var(--fg-3)',
              boxShadow: tabActivo === tab.id ? 'var(--ring-border)' : 'none',
              transition: 'all 120ms ease',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Filtros */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <div style={{ flex: '1 1 200px', minWidth: 160 }}>
          <label style={filterLabelStyle}>Buscar</label>
          <Input
            icon={<Search size={14} />}
            value={busquedaInput}
            onChange={(e) => setBusquedaInput(e.target.value)}
            placeholder="Asunto, descripción..."
          />
        </div>
        <div style={{ flex: '1 1 140px', minWidth: 120 }}>
          <label style={filterLabelStyle}>Número</label>
          <Input
            value={numeroInput}
            onChange={(e) => setNumeroInput(e.target.value)}
            placeholder="POD-LPL-2026-0001"
          />
        </div>
        <div style={{ flex: '1 1 160px', minWidth: 120 }}>
          <label style={filterLabelStyle}>Tipo</label>
          <select
            value={idTipo ?? ''}
            onChange={(e) => setParam('tipo', e.target.value)}
            style={selectStyle}
            disabled={tipos.isLoading}
          >
            <option value="">Todos los tipos</option>
            {(tipos.data?.items ?? []).map((t) => (
              <option key={t.id_tipo_tramite} value={t.id_tipo_tramite}>{t.nombre}</option>
            ))}
          </select>
        </div>
        <div style={{ flex: '1 1 140px', minWidth: 120 }}>
          <label style={filterLabelStyle}>Iniciador</label>
          <select value={iniciadorTipo} onChange={(e) => setParam('iniciador', e.target.value)} style={selectStyle}>
            <option value="">Todos</option>
            <option value="ciudadano">Ciudadano</option>
            <option value="empresa">Empresa</option>
            <option value="area_interna">Área interna</option>
          </select>
        </div>
        <div style={{ flex: '1 1 140px', minWidth: 120 }}>
          <label style={filterLabelStyle}>Estado</label>
          <Input
            value={estadoCodigo}
            onChange={(e) => setParam('estado', e.target.value)}
            placeholder="iniciado, revisión..."
          />
        </div>
        <button
          type="button"
          onClick={() => { void refetch() }}
          title="Actualizar"
          style={iconBtnStyle}
        >
          <RefreshCw size={15} strokeWidth={1.5} />
        </button>
      </div>

      {/* Tabla */}
      {error ? (
        <div style={{ color: 'var(--color-error)', fontFamily: 'var(--font-display)', fontSize: 13 }}>
          Error al cargar: {(error as Error).message}
        </div>
      ) : isLoading ? (
        <SkeletonTabla />
      ) : items.length === 0 ? (
        <EmptyState
          title="No hay trámites"
          description="No se encontraron trámites que coincidan con los filtros seleccionados."
          action={
            <Button variant="ghost" onClick={() => setSp(new URLSearchParams())}>
              Limpiar filtros
            </Button>
          }
        />
      ) : (
        <>
          <p style={{ fontSize: 12, color: 'var(--fg-3)', fontFamily: 'var(--font-display)', margin: 0 }}>
            {total} trámite{total !== 1 ? 's' : ''} · página {paginaActual} de {totalPaginas || 1}
          </p>
          <div style={{ overflowX: 'auto' }}>
            <table style={tableStyle}>
              <thead>
                <tr>
                  {['N° Expediente', 'Tipo', 'Estado', 'Iniciador', 'Ubicación actual', 'Tomado por', 'Fecha alta', 'Días en estado'].map((h) => (
                    <th key={h} style={thStyle}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <FilasTramite key={item.id_tramite} item={item} onClick={() => navigate(`/tramites/${item.numero_expediente}`)} />
                ))}
              </tbody>
            </table>
          </div>

          {/* Paginación */}
          {totalPaginas > 1 && (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', justifyContent: 'center' }}>
              <Button
                variant="ghost"
                disabled={paginaActual <= 1}
                onClick={() => irAPagina(paginaActual - 1)}
              >
                ‹ Anterior
              </Button>
              <span style={{ fontSize: 13, color: 'var(--fg-2)', fontFamily: 'var(--font-display)' }}>
                {paginaActual} / {totalPaginas}
              </span>
              <Button
                variant="ghost"
                disabled={paginaActual >= totalPaginas}
                onClick={() => irAPagina(paginaActual + 1)}
              >
                Siguiente ›
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function FilasTramite({ item, onClick }: { item: TramiteBandejaItem; onClick: () => void }) {
  const diasCalientes = item.dias_en_estado_actual > 7
  return (
    <tr
      onClick={onClick}
      style={{
        borderBottom: '1px solid var(--border-primary)',
        cursor: 'pointer',
        transition: 'background 100ms ease',
      }}
      onMouseEnter={(e) => { (e.currentTarget as HTMLTableRowElement).style.background = 'var(--surface-300)' }}
      onMouseLeave={(e) => { (e.currentTarget as HTMLTableRowElement).style.background = '' }}
    >
      <td style={{ ...tdStyle, fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--zaris-orange)', fontWeight: 600 }}>
        {item.numero_expediente}
      </td>
      <td style={tdStyle}>
        <span style={{ fontSize: 12, padding: '2px 8px', borderRadius: 'var(--radius-pill)', background: 'var(--surface-400)', fontFamily: 'var(--font-display)', color: 'var(--fg-2)' }}>
          {item.tipo_nombre}
        </span>
      </td>
      <td style={tdStyle}>
        <EstadoBadge etiqueta={item.estado_etiqueta} color={item.estado_color} />
      </td>
      <td style={tdStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, fontFamily: 'var(--font-display)' }}>
          <span style={{ fontSize: 10, background: 'var(--surface-400)', padding: '1px 6px', borderRadius: 'var(--radius-pill)', color: 'var(--fg-3)', textTransform: 'capitalize' }}>
            {item.iniciador_tipo}
          </span>
          {item.iniciador_nombre}
        </div>
      </td>
      <td style={{ ...tdStyle, fontSize: 12, color: 'var(--fg-2)', fontFamily: 'var(--font-display)' }}>
        {item.destinatario_actual_nombre ?? '—'}
      </td>
      <td style={{ ...tdStyle, fontSize: 12, color: 'var(--fg-3)', fontFamily: 'var(--font-display)' }}>
        {item.tomado_por_nombre ?? 'Sin tomar'}
      </td>
      <td style={{ ...tdStyle, fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--font-display)', whiteSpace: 'nowrap' }}>
        {new Date(item.fecha_alta).toLocaleDateString('es-AR')}
      </td>
      <td style={{ ...tdStyle, fontSize: 13, fontWeight: diasCalientes ? 600 : 400, color: diasCalientes ? 'var(--color-error)' : 'var(--fg-2)', fontFamily: 'var(--font-display)', textAlign: 'right' }}>
        {item.dias_en_estado_actual}d
      </td>
    </tr>
  )
}

function SkeletonTabla() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {Array.from({ length: 8 }).map((_, i) => (
        <Skeleton key={i} height={40} />
      ))}
    </div>
  )
}

const h1Style: React.CSSProperties = {
  fontSize: '1.55rem', fontWeight: 600, letterSpacing: '-0.5px',
  color: 'var(--fg-1)', margin: 0,
}
const filterLabelStyle: React.CSSProperties = {
  display: 'block', fontSize: 11, color: 'var(--fg-3)', marginBottom: 4,
  fontFamily: 'var(--font-display)', textTransform: 'uppercase', letterSpacing: '0.04em',
}
const selectStyle: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: 'var(--size-ui)', color: 'var(--fg-1)',
  background: 'transparent', padding: '9px 12px',
  border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)',
  outline: 'none', width: '100%',
}
const tableStyle: React.CSSProperties = {
  width: '100%', borderCollapse: 'collapse',
  fontSize: 'var(--size-btn)', fontFamily: 'var(--font-display)',
}
const thStyle: React.CSSProperties = {
  padding: '8px 12px', textAlign: 'left', fontWeight: 500,
  color: 'var(--fg-3)', borderBottom: '1px solid var(--border-primary)',
  fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.04em',
}
const tdStyle: React.CSSProperties = {
  padding: '10px 12px', color: 'var(--fg-1)', fontSize: 13,
}
const iconBtnStyle: React.CSSProperties = {
  background: 'var(--surface-300)', border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-lg)', padding: '9px 10px',
  color: 'var(--fg-3)', cursor: 'pointer', display: 'inline-flex', alignItems: 'center',
}
