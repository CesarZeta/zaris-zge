import { useEffect, useRef, useState } from 'react'
import { Search, UserPlus } from 'lucide-react'
import { buscarCiudadanos } from '../api/agendaApi'
import type { CiudadanoMinimo } from '../types/agenda'
import { RegistroVecinoModal } from '../../ciudadanos/components/RegistroVecinoModal'

interface Props {
  onSelect: (c: CiudadanoMinimo) => void
  placeholder?: string
  /** Muestra el botón "+ Nuevo" que abre el registro del vecino en una ventana, sin perder lo
   *  que se está cargando. Default true; false donde no aplica crear uno nuevo. */
  permitirNuevo?: boolean
  /** La transacción exige la cuenta del vecino (reclamos, turnos, reservas, trámites): si el
   *  elegido no la tiene, se abre su ficha para completarla antes de seguir. */
  exigirCuenta?: boolean
}

export function CiudadanoSearch({ onSelect, placeholder = 'DNI, CUIL, teléfono o nombre...', permitirNuevo = true, exigirCuenta = false }: Props) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<CiudadanoMinimo[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  // Ventana de registro: {id: null} = persona nueva; con id, completar la ficha de ese vecino.
  const [registro, setRegistro] = useState<{ id: number | null; doc?: string } | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const reqIdRef = useRef(0)
  // Tras un pick, setQ() rellena el input con el nombre, lo cual reabriria
  // el dropdown ("Sin resultados") por el effect debounced. Este flag salta
  // un ciclo del effect para que la linea "Seleccionado: ..." quede visible.
  const skipNextRef = useRef(false)

  useEffect(() => {
    if (skipNextRef.current) {
      skipNextRef.current = false
      return
    }
    if (q.trim().length < 2) {
      setResults([]); setOpen(false); return
    }
    const myId = ++reqIdRef.current
    setLoading(true); setOpen(true)
    const t = setTimeout(async () => {
      try {
        const rows = await buscarCiudadanos(q.trim(), 10)
        if (myId === reqIdRef.current) setResults(rows)
      } catch {
        if (myId === reqIdRef.current) setResults([])
      } finally {
        if (myId === reqIdRef.current) setLoading(false)
      }
    }, 280)
    return () => clearTimeout(t)
  }, [q])

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  function abrirAlta() {
    const digitos = q.replace(/\D/g, '')
    setOpen(false)
    setRegistro({ id: null, doc: /^[\d.\s]+$/.test(q.trim()) && /^\d{7,8}$/.test(digitos) ? digitos : undefined })
  }

  function elegir(c: CiudadanoMinimo) {
    // `=== false`: un backend que todavía no informa la cuenta no frena (lo controla él al guardar).
    if (exigirCuenta && c.tiene_cuenta === false) {
      setOpen(false)
      setRegistro({ id: c.id_ciudadano })
      return
    }
    confirmar(c)
  }

  function confirmar(c: CiudadanoMinimo) {
    const texto = `${c.apellido ?? ''}, ${c.nombre ?? ''}`.trim()
    // Solo si setQ cambia el texto corre el effect que hay que saltear.
    if (texto !== q) skipNextRef.current = true
    onSelect(c)
    setOpen(false)
    setResults([])
    setQ(texto)
  }

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%' }}>
      <div style={{ display: 'flex', gap: 8 }}>
        <div style={{ position: 'relative', flex: 1 }}>
          <Search size={14} strokeWidth={1.5} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--fg-3)' }} />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={placeholder}
            onFocus={() => q.length >= 2 && setOpen(true)}
            style={{
              fontFamily: 'var(--font-display)', fontSize: 'var(--size-ui)', width: '100%',
              padding: '9px 12px 9px 32px', borderRadius: 'var(--radius-lg)',
              border: '1px solid var(--border-primary)', background: 'transparent',
              outline: 'none', color: 'var(--fg-1)',
            }}
          />
        </div>
        {permitirNuevo && (
          <button
            type="button"
            onClick={abrirAlta}
            title="Registrar un vecino nuevo"
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap',
              padding: '9px 12px', borderRadius: 'var(--radius-lg)',
              border: '1px solid var(--border-primary)', background: 'var(--surface-100)',
              color: 'var(--fg-1)', cursor: 'pointer',
              fontFamily: 'var(--font-display)', fontSize: 'var(--size-btn)', fontWeight: 500,
            }}
          >
            <UserPlus size={14} strokeWidth={1.5} /> Nuevo
          </button>
        )}
      </div>
      {open && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0,
          background: 'var(--surface-100)', borderRadius: 'var(--radius-lg)',
          boxShadow: 'var(--shadow-card)', maxHeight: 280, overflowY: 'auto',
          zIndex: 50,
        }}>
          {loading && (
            <div style={{ padding: 12, color: 'var(--fg-3)', fontSize: 13 }}>Buscando...</div>
          )}
          {!loading && results.length === 0 && (
            <div style={{ padding: 12, fontSize: 13 }}>
              <div style={{ color: 'var(--fg-3)', marginBottom: permitirNuevo ? 8 : 0 }}>Sin resultados.</div>
              {permitirNuevo && (
                <button
                  type="button"
                  onClick={abrirAlta}
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: 6,
                    padding: '6px 10px', borderRadius: 'var(--radius-md)',
                    border: 'none', background: 'var(--zaris-orange)', color: '#fff',
                    cursor: 'pointer', fontFamily: 'var(--font-display)', fontSize: 12, fontWeight: 600,
                  }}
                >
                  <UserPlus size={13} strokeWidth={1.5} /> Registrar un vecino
                </button>
              )}
            </div>
          )}
          {results.map((c) => (
            <button
              key={c.id_ciudadano}
              type="button"
              onClick={() => elegir(c)}
              style={{
                display: 'block', width: '100%', textAlign: 'left', padding: '8px 12px',
                background: 'transparent', border: 'none', cursor: 'pointer',
                borderBottom: '1px solid var(--border-primary)', fontFamily: 'var(--font-display)',
              }}
            >
              <div style={{ fontSize: 13, color: 'var(--fg-1)' }}>
                <strong>{c.apellido}, {c.nombre}</strong>
                {c.doc_nro && <span style={{ color: 'var(--fg-3)' }}> · DNI {c.doc_nro}</span>}
                {exigirCuenta && c.tiene_cuenta === false && (
                  <span style={{ color: 'var(--color-error)' }}> · sin cuenta: completar su ficha</span>
                )}
              </div>
              <div style={{ fontSize: 11, color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>
                {[c.telefono, c.email].filter(Boolean).join(' · ')}
              </div>
            </button>
          ))}
        </div>
      )}
      {registro && (
        <RegistroVecinoModal
          idCiudadano={registro.id}
          docInicial={registro.doc}
          onCerrar={() => setRegistro(null)}
          onListo={(c) => { setRegistro(null); confirmar({ ...c, tiene_cuenta: true }) }}
        />
      )}
    </div>
  )
}
