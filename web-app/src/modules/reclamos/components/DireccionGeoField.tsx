import { GeocodingSearch } from './GeocodingSearch'
import { MapaPicker } from './MapaPicker'

// Bloque reutilizable de "direccion normalizada + georreferenciada" (regla §23):
// buscador OSM (normaliza texto Y captura lat/lon) + mapa con pin manual +
// input de direccion editable que NO borra las coordenadas + hint mono con
// coords y boton "Quitar pin". Referencia canonica: FormView de Reclamos.
// Usado por: EspacioFormModal (Agenda) y campo dinamico 'direccion' (Tramites).

export interface DireccionGeoValue {
  texto: string
  lat: number | null
  lon: number | null
}

interface Props {
  value: DireccionGeoValue
  onChange: (next: DireccionGeoValue) => void
  mapHeight?: number
  placeholder?: string
}

export function DireccionGeoField({ value, onChange, mapHeight = 240, placeholder }: Props) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <span style={labelStyle}>Buscar dirección</span>
        <GeocodingSearch
          placeholder={placeholder}
          onPick={(r) => {
            if (r.lat == null || r.lon == null) return
            onChange({ texto: r.display_name ?? value.texto, lat: r.lat, lon: r.lon })
          }}
        />
        <span style={hintStyle}>
          Tipeá una calle y elegí una sugerencia. También podés hacer clic en el mapa o arrastrar el pin.
        </span>
      </div>

      <MapaPicker
        lat={value.lat}
        lon={value.lon}
        height={mapHeight}
        onChange={(la, lo) => onChange({ ...value, lat: la, lon: lo })}
      />

      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <span style={labelStyle}>Dirección</span>
        <input
          value={value.texto}
          onChange={(e) => onChange({ ...value, texto: e.target.value })}
          maxLength={300}
          style={inputStyle}
        />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ ...hintStyle, fontFamily: 'var(--font-mono)' }}>
            {value.lat != null && value.lon != null
              ? `Coordenadas: ${value.lat.toFixed(6)}, ${value.lon.toFixed(6)}`
              : 'Sin coordenadas. Buscá o tocá el mapa para fijar un punto.'}
          </span>
          {value.lat != null && value.lon != null && (
            <button
              type="button"
              onClick={() => onChange({ ...value, lat: null, lon: null })}
              style={btnQuitarStyle}
            >
              Quitar pin
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

const labelStyle: React.CSSProperties = {
  fontFamily: 'var(--font-display)',
  fontSize: 11,
  color: 'var(--fg-3)',
  textTransform: 'uppercase',
  letterSpacing: '.04em',
}

const hintStyle: React.CSSProperties = {
  fontSize: 'var(--size-caption)',
  color: 'var(--fg-3)',
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  fontFamily: 'var(--font-display)',
  fontSize: 13,
  padding: '8px 10px',
  border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-md)',
  background: 'var(--surface-100)',
  color: 'var(--fg-1)',
  outline: 'none',
  boxSizing: 'border-box',
}

const btnQuitarStyle: React.CSSProperties = {
  fontFamily: 'var(--font-display)',
  fontSize: 12,
  padding: '2px 10px',
  border: '1px solid var(--border-medium)',
  borderRadius: 'var(--radius-md)',
  background: 'transparent',
  color: 'var(--fg-2)',
  cursor: 'pointer',
  whiteSpace: 'nowrap',
}
