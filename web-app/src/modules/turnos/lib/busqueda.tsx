import { useCallback, useState } from 'react'
import { Search } from 'lucide-react'

/**
 * Búsqueda diferida — regla §23 "sin precarga al entrar" (pedido de César,
 * 2026-09-06): una pantalla de listado NO pide datos al montar. Muestra los
 * filtros con una leyenda y el request sale recién cuando el usuario presiona
 * Buscar. Los filtros que viajan al backend viven en dos copias:
 *
 *   - `borrador`: lo que el usuario está editando (cambiarlo no dispara nada).
 *   - `aplicado`: lo que se buscó por última vez; `null` hasta la primera
 *     búsqueda (=> la query queda `enabled: false`).
 *
 * `version` sube en cada Buscar y va a la queryKey: presionar Buscar con los
 * mismos filtros vuelve a pedir al backend (sin eso react-query devolvería el
 * caché sin tocar la red). Los filtros client-side (texto, selects derivados de
 * lo cargado) siguen siendo en vivo: no hacen requests.
 */
export function useBusquedaDiferida<F extends object>(inicial: F) {
  const [borrador, setBorrador] = useState<F>(inicial)
  const [aplicado, setAplicado] = useState<F | null>(null)
  const [version, setVersion] = useState(0)
  const buscar = useCallback(() => {
    setAplicado({ ...borrador })
    setVersion((v) => v + 1)
  }, [borrador])
  return { borrador, setBorrador, aplicado, buscar, buscado: aplicado != null, version }
}

/** Leyenda que ocupa el lugar de la tabla/grilla hasta la primera búsqueda. */
export function AvisoBuscar({
  texto = 'Elegí qué querés ver y presioná Buscar.',
}: {
  texto?: string
}) {
  return (
    <div style={aviso} role="status">
      <Search size={18} strokeWidth={1.5} style={{ color: 'var(--zaris-orange)', flexShrink: 0 }} />
      <span>{texto}</span>
    </div>
  )
}

const aviso: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
  padding: '36px 16px', color: 'var(--fg-2)', fontSize: '0.92rem',
  fontFamily: 'var(--font-display)',
  background: 'var(--surface-100)', border: '1px dashed var(--border-medium)', borderRadius: 12,
}
