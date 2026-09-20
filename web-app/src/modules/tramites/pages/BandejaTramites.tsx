import { useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { Plus, Search, RefreshCw } from 'lucide-react'
import { Button, Input, Skeleton, EmptyState } from '../../../ui'
import { AvisoBuscar } from '../../../ui/busqueda'
import { useBandeja, useTiposTramite } from '../hooks/useTramites'
import { EstadoBadge } from '../components/EstadoBadge'
import type { TramiteBandejaItem, BandejaParams } from '../types'

const LIMIT = 50

/** Filtros que viajan al backend. Lo APLICADO vive en la URL (deep links y
 *  paginación); lo que el usuario edita vive en un borrador local. */
type FiltrosBandeja = { q: string; numero: string; tipo: string; iniciador: string; estado: string }

const FILTROS_URL = ['q', 'numero', 'tipo', 'iniciador', 'estado'] as const

const FILTROS_VACIOS: FiltrosBandeja = { q: '', numero: '', tipo: '', iniciador: '', estado: '' }

function leerFiltros(sp: URLSearchParams): FiltrosBandeja {
  return {
    q: sp.get('q') ?? '',
    numero: sp.get('numero') ?? '',
    tipo: sp.get('tipo') ?? '',
    iniciador: sp.get('iniciador') ?? '',
    estado: sp.get('estado') ?? '',
  }
}

export function BandejaTramites() {
  const navigate = useNavigate()
  const [sp, setSp] = useSearchParams()

  // Búsqueda diferida (§23): la URL es lo APLICADO (se escribe entera al
  // presionar Buscar y la paginación la reusa); el borrador es lo que el
  // usuario edita y NO dispara nada hasta el próximo Buscar. Un deep link con
  // filtros (o con buscar=1) es intención explícita: se busca al montar.
  const aplicado = leerFiltros(sp)
  const [borrador, setBorrador] = useState<FiltrosBandeja>(() => leerFiltros(sp))
  const [version, setVersion] = useState(0)
  const hayFiltrosEnUrl = FILTROS_URL.some((k) => (sp.get(k) ?? '') !== '')
  const buscado = sp.get('buscar') === '1' || hayFiltrosEnUrl
  const paginaParam = parseInt(sp.get('pagina') ?? '1', 10)
  const paginaActual = Number.isFinite(paginaParam) && paginaParam >= 1 ? paginaParam : 1

  const setB = (patch: Partial<FiltrosBandeja>) => setBorrador((b) => ({ ...b, ...patch }))

  /** Escribe TODOS los filtros del borrador en la URL de una vez (vuelve a la
   *  página 1) y sube `version` para que Buscar con los mismos filtros vuelva
   *  a la red. */
  function buscar() {
    const next = new URLSearchParams()
    FILTROS_URL.forEach((k) => {
      const v = borrador[k].trim()
      if (v) next.set(k, v)
    })
    next.set('buscar', '1')
    setSp(next)
    setVersion((v) => v + 1)
  }

  /** "Limpiar filtros" es una acción explícita: vacía el borrador y vuelve a
   *  buscar sin filtros (como hacía antes, que mostraba toda la bandeja). */
  function limpiar() {
    setBorrador(FILTROS_VACIOS)
    const next = new URLSearchParams()
    next.set('buscar', '1')
    setSp(next)
    setVersion((v) => v + 1)
  }

  const idTipo = aplicado.tipo ? Number(aplicado.tipo) : undefined
  const offset = (paginaActual - 1) * LIMIT

  const params: BandejaParams = {
    limit: LIMIT,
    offset,
    ...(aplicado.estado ? { estado_codigo: aplicado.estado } : {}),
    ...(idTipo ? { id_tipo_tramite: idTipo } : {}),
    ...(aplicado.iniciador ? { iniciador_tipo: aplicado.iniciador } : {}),
    ...(aplicado.numero ? { numero: aplicado.numero } : {}),
    ...(aplicado.q ? { q: aplicado.q } : {}),
  }

  const { data, isLoading, error, refetch } = useBandeja(params, { enabled: buscado, version })
  // Opciones del select de tipo: catálogo liviano, sí carga al entrar.
  const tipos = useTiposTramite()

  const total = data?.total ?? 0
  const items = data?.items ?? []
  const totalPaginas = Math.ceil(total / LIMIT)

  // Paginar es una acción explícita: re-pide (mantiene filtros y buscar=1).
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
        <Button type="button" variant="accent" icon={<Plus size={16} strokeWidth={1.5} />} onClick={() => navigate('/tramites/nuevo')}>
          Nuevo trámite
        </Button>
      </div>

      {/* Filtros: form para que Enter en cualquier campo dispare Buscar (§23). */}
      <form
        style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}
        onSubmit={(e) => { e.preventDefault(); buscar() }}
      >
        <div style={{ flex: '1 1 200px', minWidth: 160 }}>
          <label style={filterLabelStyle}>Buscar</label>
          <Input
            icon={<Search size={14} />}
            value={borrador.q}
            onChange={(e) => setB({ q: e.target.value })}
            placeholder="Asunto, descripción..."
          />
        </div>
        <div style={{ flex: '1 1 140px', minWidth: 120 }}>
          <label style={filterLabelStyle}>Número</label>
          <Input
            value={borrador.numero}
            onChange={(e) => setB({ numero: e.target.value })}
            placeholder="POD-LPL-2026-0001"
          />
        </div>
        <div style={{ flex: '1 1 160px', minWidth: 120 }}>
          <label style={filterLabelStyle}>Tipo</label>
          <select
            value={borrador.tipo}
            onChange={(e) => setB({ tipo: e.target.value })}
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
          <select value={borrador.iniciador} onChange={(e) => setB({ iniciador: e.target.value })} style={selectStyle}>
            <option value="">Todos</option>
            <option value="ciudadano">Ciudadano</option>
            <option value="empresa">Empresa</option>
            <option value="area_interna">Área interna</option>
          </select>
        </div>
        <div style={{ flex: '1 1 140px', minWidth: 120 }}>
          <label style={filterLabelStyle}>Estado</label>
          <Input
            value={borrador.estado}
            onChange={(e) => setB({ estado: e.target.value })}
            placeholder="iniciado, revisión..."
          />
        </div>
        <Button type="submit" variant="accent" icon={<Search size={15} strokeWidth={1.5} />} title="Traer la bandeja con los filtros elegidos">
          Buscar
        </Button>
        <button
          type="button"
          onClick={() => { void refetch() }}
          title="Actualizar"
          style={{ ...iconBtnStyle, ...(buscado ? {} : iconBtnDisabledStyle) }}
          disabled={!buscado}
        >
          <RefreshCw size={15} strokeWidth={1.5} />
        </button>
      </form>

      {/* Tabla: recién después de la primera búsqueda */}
      {!buscado ? (
        <AvisoBuscar texto="Elegí estado, tipo, iniciador o texto (o dejá todo en Todos) y presioná Buscar para ver la bandeja." />
      ) : error ? (
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
            <Button type="button" variant="ghost" onClick={limpiar}>
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
                type="button"
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
                type="button"
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
const iconBtnDisabledStyle: React.CSSProperties = { opacity: 0.5, cursor: 'not-allowed' }
