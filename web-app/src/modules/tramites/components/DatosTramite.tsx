import type { TipoTramiteCampo } from '../types'

interface DatosTramiteProps {
  datos: Record<string, unknown>
  campos: TipoTramiteCampo[]
}

export function DatosTramite({ datos, campos }: DatosTramiteProps) {
  if (!campos.length && !Object.keys(datos).length) return null

  const ordenados = [...campos].sort((a, b) => a.orden - b.orden)
  const camposPorNombre = Object.fromEntries(campos.map((c) => [c.nombre_interno, c]))

  // Incluir claves del JSON que no tengan campo definido (fallback)
  const todasLasClaves = [
    ...ordenados.map((c) => c.nombre_interno),
    ...Object.keys(datos).filter((k) => !camposPorNombre[k]),
  ]

  const items = todasLasClaves
    .map((nombre) => {
      const campo = camposPorNombre[nombre]
      const valor = datos[nombre]
      if (valor === null || valor === undefined || valor === '') return null
      return {
        nombre,
        etiqueta: campo?.etiqueta ?? nombre.replace(/_/g, ' '),
        tipoDato: campo?.tipo_dato ?? 'texto',
        valor,
      }
    })
    .filter(Boolean) as { nombre: string; etiqueta: string; tipoDato: string; valor: unknown }[]

  if (!items.length) {
    return (
      <p style={{ margin: 0, fontSize: 13, color: 'var(--fg-3)', fontFamily: 'var(--font-display)', fontStyle: 'italic' }}>
        Sin datos adicionales registrados.
      </p>
    )
  }

  return (
    <dl style={{ margin: 0, display: 'grid', gap: '10px 0' }}>
      {items.map((item) => (
        <div key={item.nombre}>
          <dt style={dtStyle}>{item.etiqueta}</dt>
          <dd style={ddStyle}>{renderValor(item.tipoDato, item.valor)}</dd>
        </div>
      ))}
    </dl>
  )
}

function renderValor(tipoDato: string, valor: unknown): React.ReactNode {
  if (valor === null || valor === undefined) return '—'

  if (tipoDato === 'booleano') {
    return (
      <span style={{
        fontSize: 11, padding: '2px 8px', borderRadius: 'var(--radius-pill)',
        background: valor ? 'rgba(31,138,101,.12)' : 'var(--surface-400)',
        color: valor ? '#1f8a65' : 'var(--fg-3)',
        fontFamily: 'var(--font-display)', fontWeight: 500,
      }}>
        {valor ? 'Sí' : 'No'}
      </span>
    )
  }

  if (tipoDato === 'fecha' && typeof valor === 'string') {
    try {
      return new Date(valor + 'T00:00:00').toLocaleDateString('es-AR', { day: '2-digit', month: 'long', year: 'numeric' })
    } catch { return String(valor) }
  }

  if (tipoDato === 'fecha_hora' && typeof valor === 'string') {
    try {
      return new Date(valor).toLocaleString('es-AR', { day: '2-digit', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' })
    } catch { return String(valor) }
  }

  if (tipoDato === 'moneda' && typeof valor === 'number') {
    return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(valor)
  }

  if (tipoDato === 'seleccion_multiple' && Array.isArray(valor)) {
    return (
      <span style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
        {(valor as string[]).map((v) => (
          <span key={v} style={pillStyle}>{v}</span>
        ))}
      </span>
    )
  }

  if (tipoDato === 'texto_largo' && typeof valor === 'string') {
    return (
      <span style={{ whiteSpace: 'pre-wrap', fontFamily: 'var(--font-display)', fontSize: 13, color: 'var(--fg-1)' }}>
        {valor}
      </span>
    )
  }

  return String(valor)
}

const dtStyle: React.CSSProperties = {
  fontSize: 11, fontWeight: 500, color: 'var(--fg-3)',
  fontFamily: 'var(--font-display)', textTransform: 'uppercase', letterSpacing: '0.04em',
  marginBottom: 2,
}
const ddStyle: React.CSSProperties = {
  margin: 0, fontSize: 13, color: 'var(--fg-1)', fontFamily: 'var(--font-display)',
}
const pillStyle: React.CSSProperties = {
  fontSize: 11, padding: '2px 8px', borderRadius: 'var(--radius-pill)',
  background: 'var(--surface-400)', color: 'var(--fg-2)',
  fontFamily: 'var(--font-display)',
}
