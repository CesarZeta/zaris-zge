import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, X } from 'lucide-react'
import { listarRecursosAgenda } from '../api/agendaApi'
import type { RecursoItem } from '../types/agenda'

// El endpoint /agenda/catalogos/recursos solo soporta 'agente' y 'equipo'.
// Los espacios se eligen con su propio listado (modulo Espacios o EspacioPicker).
type TipoRecursoPickeable = 'agente' | 'equipo'

interface Props {
  tipo: TipoRecursoPickeable
  value: number | null
  onChange: (id: number | null) => void
  idMunicipio?: number
  placeholder?: string
}

/**
 * Buscador con autocompletar para agente / equipo / espacio. Input + dropdown
 * debounced contra GET /agenda/catalogos/recursos?q=. Reemplaza al <select>
 * nativo previo: con 84+ agentes en prod un select largo es inusable.
 *
 * Cuando ya hay un value seleccionado se resuelve su nombre con una query
 * puntual (sin q) para mostrarlo en el input. Si el consumidor cambia `tipo`,
 * tambien resetea `value` a null (patron en EventoEncargadosModal/OcupacionModal).
 */
export function RecursoPicker({ tipo, value, onChange, idMunicipio, placeholder }: Props) {
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const reqIdRef = useRef(0)
  // Tras un pick, setQ() rellena el input con el nombre, lo cual reabriria el
  // dropdown por el effect debounced. El flag salta un ciclo. Ver CiudadanoSearch.
  const skipNextRef = useRef(false)
  const [results, setResults] = useState<RecursoItem[]>([])
  const [loading, setLoading] = useState(false)

  // Resuelve el nombre del recurso ya seleccionado (value) para mostrarlo en el
  // input cuando el componente monta o el value cambia desde afuera.
  const seleccionado = useQuery<RecursoItem[]>({
    queryKey: ['agenda', 'recursos', 'lookup', tipo, idMunicipio ?? null],
    queryFn: () => listarRecursosAgenda({ tipo, id_municipio: idMunicipio, limit: 200 }),
    staleTime: 60_000,
    enabled: value != null,
  })

  // Sincronizar el texto del input con el value seleccionado.
  useEffect(() => {
    if (value == null) {
      // Solo limpiar si no estamos en medio de una busqueda activa.
      if (!open) setQ('')
      return
    }
    const rec = seleccionado.data?.find((r) => r.id_recurso === value)
    if (rec) {
      skipNextRef.current = true
      setQ(rec.nombre)
    }
  }, [value, seleccionado.data]) // eslint-disable-line react-hooks/exhaustive-deps

  // Busqueda debounced.
  useEffect(() => {
    if (skipNextRef.current) {
      skipNextRef.current = false
      return
    }
    if (q.trim().length < 1) {
      setResults([]); setOpen(false); return
    }
    const myId = ++reqIdRef.current
    setLoading(true); setOpen(true)
    const t = setTimeout(async () => {
      try {
        const rows = await listarRecursosAgenda({ tipo, q: q.trim(), id_municipio: idMunicipio, limit: 20 })
        if (myId === reqIdRef.current) setResults(rows)
      } catch {
        if (myId === reqIdRef.current) setResults([])
      } finally {
        if (myId === reqIdRef.current) setLoading(false)
      }
    }, 250)
    return () => clearTimeout(t)
  }, [q, tipo, idMunicipio])

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  function limpiar() {
    onChange(null)
    setQ('')
    setResults([])
    setOpen(false)
  }

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%' }}>
      <div style={{ position: 'relative' }}>
        <Search size={14} strokeWidth={1.5} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--fg-3)' }} />
        <input
          value={q}
          onChange={(e) => {
            setQ(e.target.value)
            // Tipear despues de elegir invalida la seleccion previa.
            if (value != null) onChange(null)
          }}
          placeholder={placeholder ?? `Buscar ${tipo} por nombre...`}
          onFocus={() => q.trim().length >= 1 && results.length > 0 && setOpen(true)}
          style={{
            fontFamily: 'var(--font-display)', fontSize: 'var(--size-ui)', width: '100%',
            padding: '8px 32px 8px 32px', borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-primary)', background: 'var(--surface-100)',
            outline: 'none', color: 'var(--fg-1)',
          }}
        />
        {(value != null || q.length > 0) && (
          <button
            type="button"
            onClick={limpiar}
            aria-label="Limpiar seleccion"
            style={{
              position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
              background: 'transparent', border: 'none', cursor: 'pointer',
              color: 'var(--fg-3)', padding: 2, display: 'flex', alignItems: 'center',
            }}
          >
            <X size={14} strokeWidth={1.5} />
          </button>
        )}
      </div>
      {open && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0,
          background: 'var(--surface-100)', borderRadius: 'var(--radius-lg)',
          boxShadow: 'var(--shadow-card)', maxHeight: 240, overflowY: 'auto',
          zIndex: 50, border: '1px solid var(--border-primary)',
        }}>
          {loading && (
            <div style={{ padding: 12, color: 'var(--fg-3)', fontSize: 13 }}>Buscando...</div>
          )}
          {!loading && results.length === 0 && (
            <div style={{ padding: 12, color: 'var(--fg-3)', fontSize: 13 }}>Sin resultados.</div>
          )}
          {results.map((r) => (
            <button
              key={`${r.tipo_recurso}-${r.id_recurso}`}
              type="button"
              onClick={() => {
                skipNextRef.current = true
                onChange(r.id_recurso)
                setQ(r.nombre)
                setOpen(false)
                setResults([])
              }}
              style={{
                display: 'block', width: '100%', textAlign: 'left', padding: '8px 12px',
                background: 'transparent', border: 'none', cursor: 'pointer',
                borderBottom: '1px solid var(--border-primary)', fontFamily: 'var(--font-display)',
                fontSize: 13, color: 'var(--fg-1)',
              }}
            >
              {r.nombre}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
