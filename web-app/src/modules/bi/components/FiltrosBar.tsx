import { useCatalogoAreas } from '../hooks/useBi'
import type { BiFiltros } from '../lib/types'

// Barra de filtros compartida. Controlada por el padre (estado en la vista).
export function FiltrosBar({
  filtros,
  onChange,
}: {
  filtros: BiFiltros
  onChange: (f: BiFiltros) => void
}) {
  const { data: areas } = useCatalogoAreas()

  const set = (patch: Partial<BiFiltros>) => onChange({ ...filtros, ...patch })

  const inputStyle: React.CSSProperties = {
    fontFamily: 'var(--font-display)',
    fontSize: '0.82rem',
    padding: '6px 10px',
    border: '1px solid var(--border-medium)',
    borderRadius: 8,
    background: 'var(--surface-100)',
    color: 'var(--fg-1)',
  }
  const labelStyle: React.CSSProperties = {
    fontFamily: 'var(--font-display)',
    fontSize: '0.7rem',
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
    color: 'var(--fg-3)',
    fontWeight: 600,
    marginBottom: 3,
    display: 'block',
  }

  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: 14,
        alignItems: 'flex-end',
        background: 'var(--surface-300)',
        border: '1px solid var(--border-primary)',
        borderRadius: 12,
        padding: '12px 16px',
      }}
    >
      <div>
        <label style={labelStyle}>Desde</label>
        <input
          type="date"
          value={filtros.desde ?? ''}
          onChange={(e) => set({ desde: e.target.value || undefined })}
          style={inputStyle}
        />
      </div>
      <div>
        <label style={labelStyle}>Hasta</label>
        <input
          type="date"
          value={filtros.hasta ?? ''}
          onChange={(e) => set({ hasta: e.target.value || undefined })}
          style={inputStyle}
        />
      </div>
      <div>
        <label style={labelStyle}>Área</label>
        <select
          value={filtros.id_area ?? ''}
          onChange={(e) => set({ id_area: e.target.value ? Number(e.target.value) : undefined })}
          style={{ ...inputStyle, minWidth: 160 }}
        >
          <option value="">Todas</option>
          {(areas ?? []).map((a) => (
            <option key={a.id_area} value={a.id_area}>
              {a.nombre}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label style={labelStyle}>Prioridad</label>
        <select
          value={filtros.prioridad ?? ''}
          onChange={(e) => set({ prioridad: e.target.value || undefined })}
          style={inputStyle}
        >
          <option value="">Todas</option>
          <option value="Alta">Alta</option>
          <option value="Media">Media</option>
          <option value="Baja">Baja</option>
        </select>
      </div>
      {(filtros.desde || filtros.hasta || filtros.id_area || filtros.prioridad) && (
        <button
          onClick={() => onChange({})}
          style={{
            ...inputStyle,
            cursor: 'pointer',
            color: 'var(--zaris-orange)',
            borderColor: 'var(--zaris-orange)',
            background: 'transparent',
            fontWeight: 600,
          }}
        >
          Limpiar
        </button>
      )}
    </div>
  )
}
