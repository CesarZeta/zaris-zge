import { useEffect, useRef, useState } from 'react'
import { buscarSubareas } from '../api/ciudadanosApi'
import type { CuentaZarisIn, SubareaHit } from '../types/ciudadano'

/**
 * Mini-modal de «Crear cuenta aplicación ZARIS» (PLAN_CUENTAS_FUNCIONARIO.md, decisión 3):
 * pide lo que la ficha del ciudadano NO tiene — nivel de acceso, subárea y nombre de
 * usuario — y devuelve el body de POST /buc/ciudadanos/{id}/cuenta-zaris.
 *
 * Patrones del proyecto (§23/§29): el usuario se autocompleta desde nombre.apellido y se
 * respeta si el admin lo edita (validación en vivo, Guardar deshabilitado si es inválido);
 * los campos se resetean al abrir; click-fuera seguro (mousedown Y mouseup en el overlay);
 * confirmar cierra el modal de inmediato y el padre dispara la mutación (toast con el resultado).
 */

// Niveles de acceso (CLAUDE.md §3). Copia local: no se importa del módulo Usuarios.
const NIVELES: Array<{ valor: number; label: string; ayuda: string }> = [
  { valor: 1, label: 'Administrador', ayuda: 'Ve y gestiona todo' },
  { valor: 2, label: 'Supervisor', ayuda: 'Gestiona su subárea' },
  { valor: 3, label: 'Atención', ayuda: 'Ventanilla: crea y consulta reclamos' },
  { valor: 4, label: 'Gestión', ayuda: 'Agente de OT: trabaja sus órdenes' },
  { valor: 5, label: 'Consultor', ayuda: 'Solo lectura' },
]

const USERNAME_RE = /^[a-zA-Z0-9_.\-]+$/

/** nombre + apellido → "nombre.apellido" (sin tildes, minúsculas, solo [a-z0-9.]). */
export function aUsername(nombre: string, apellido: string): string {
  const limpiar = (t: string) =>
    t.normalize('NFD').replace(/\p{Diacritic}/gu, '')
      .toLowerCase().replace(/[^a-z0-9]+/g, '')
  const partes = [limpiar(nombre), limpiar(apellido)].filter(Boolean)
  return partes.join('.').slice(0, 50)
}

interface Props {
  open: boolean
  ciudadano: { nombre: string; apellido: string; email: string }
  onClose: () => void
  onConfirm: (body: CuentaZarisIn) => void
}

export function CuentaZarisModal({ open, ciudadano, onClose, onConfirm }: Props) {
  const [nivel, setNivel] = useState(4)
  const [subarea, setSubarea] = useState<SubareaHit | null>(null)
  const [username, setUsername] = useState('')
  const usernameManual = useRef(false)
  const [errSubarea, setErrSubarea] = useState<string | undefined>()
  const downEnOverlay = useRef(false)

  // Reset al abrir: el modal vive montado con open=false (§29).
  useEffect(() => {
    if (!open) return
    setNivel(4)
    setSubarea(null)
    setUsername(aUsername(ciudadano.nombre, ciudadano.apellido))
    usernameManual.current = false
    setErrSubarea(undefined)
  }, [open, ciudadano.nombre, ciudadano.apellido])

  if (!open) return null

  const usernameOk = username.length > 0 && username.length <= 50 && USERNAME_RE.test(username)
  const puedeConfirmar = usernameOk && subarea != null

  function confirmar() {
    if (!subarea) { setErrSubarea('Elegí la subárea del funcionario'); return }
    if (!usernameOk) return
    onConfirm({ nivel_acceso: nivel, id_subarea: subarea.id_subarea, username })
  }

  return (
    <div
      style={overlay}
      onMouseDown={(e) => { downEnOverlay.current = e.target === e.currentTarget }}
      onMouseUp={(e) => {
        if (downEnOverlay.current && e.target === e.currentTarget) onClose()
        downEnOverlay.current = false
      }}
    >
      <div style={box} role="dialog" aria-modal="true" aria-labelledby="cuenta-zaris-titulo">
        <div style={header}>
          <h2 id="cuenta-zaris-titulo" style={{ margin: 0, fontSize: '1.05rem', color: 'var(--fg-1)', fontFamily: 'var(--font-display)' }}>
            Crear cuenta aplicación ZARIS
          </h2>
          <button onClick={onClose} style={cerrarBtn} aria-label="Cerrar">×</button>
        </div>

        <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 14, overflowY: 'auto' }}>
          <p style={{ margin: 0, fontSize: 'var(--size-caption)', color: 'var(--fg-2)', lineHeight: 1.5 }}>
            Cuenta de <strong>{ciudadano.apellido}, {ciudadano.nombre}</strong> para el sistema y la app de agentes.
            Las credenciales (clave temporal) se envían a <strong>{ciudadano.email}</strong>; en el primer
            ingreso el sistema le pide elegir su propia contraseña. Puede ingresar con su email o su DNI.
          </p>

          <div style={campo}>
            <label style={labelStyle}>Nivel de acceso <span style={{ color: 'var(--color-error)' }}>*</span></label>
            <select value={nivel} onChange={(e) => setNivel(Number(e.target.value))} style={inputStyle}>
              {NIVELES.map((n) => (
                <option key={n.valor} value={n.valor}>{n.label} — {n.ayuda}</option>
              ))}
            </select>
          </div>

          <SubareaSearch valor={subarea} error={errSubarea} onPick={(s) => { setSubarea(s); if (s) setErrSubarea(undefined) }} />

          <div style={campo}>
            <label style={labelStyle}>Nombre de usuario <span style={{ color: 'var(--color-error)' }}>*</span></label>
            <div style={{ position: 'relative' }}>
              <input
                type="text"
                value={username}
                maxLength={50}
                autoComplete="off"
                onChange={(e) => {
                  usernameManual.current = true
                  setUsername(e.target.value.replace(/\s+/g, ''))
                }}
                style={{
                  ...inputStyle,
                  paddingRight: 32,
                  borderColor: username ? (usernameOk ? 'var(--color-success)' : 'var(--color-error)') : 'var(--border-primary)',
                }}
              />
              {username && (
                <span aria-hidden="true" style={{
                  position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
                  fontWeight: 700, color: usernameOk ? 'var(--color-success)' : 'var(--color-error)',
                }}>{usernameOk ? '✓' : '✕'}</span>
              )}
            </div>
            <span style={{ fontSize: '0.78rem', color: usernameOk || !username ? 'var(--fg-3)' : 'var(--color-error)' }}>
              Se propone <code>nombre.apellido</code>; podés cambiarlo. Letras, números, punto, guión y guión bajo, <strong>sin espacios ni tildes</strong>.
            </span>
          </div>
        </div>

        <div style={footer}>
          <button type="button" onClick={onClose} style={btnGhost}>Cancelar</button>
          <button type="button" onClick={confirmar} disabled={!puedeConfirmar} style={{ ...btnPrimary, opacity: puedeConfirmar ? 1 : 0.5, cursor: puedeConfirmar ? 'pointer' : 'not-allowed' }}>
            Crear cuenta y enviar credenciales
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Buscador predictivo de subárea (mismo patrón skipNextRef que Usuarios, §29) ──
function SubareaSearch({ valor, error, onPick }: {
  valor: SubareaHit | null
  error?: string
  onPick: (s: SubareaHit | null) => void
}) {
  const [texto, setTexto] = useState('')
  const [hits, setHits] = useState<SubareaHit[] | null>(null)
  const skipNextRef = useRef(false)
  const wrapRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (skipNextRef.current) { skipNextRef.current = false; return }
    const q = texto.trim()
    if (!q) { setHits(null); return }
    const t = setTimeout(async () => {
      try { setHits(await buscarSubareas(q)) } catch { setHits([]) }
    }, 280)
    return () => clearTimeout(t)
  }, [texto])

  useEffect(() => {
    function clickFuera(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setHits(null)
    }
    document.addEventListener('click', clickFuera)
    return () => document.removeEventListener('click', clickFuera)
  }, [])

  return (
    <div ref={wrapRef} style={{ ...campo, position: 'relative' }}>
      <label style={labelStyle}>Subárea <span style={{ color: 'var(--color-error)' }}>*</span></label>
      <input
        type="text"
        value={texto}
        placeholder="Escribí para buscar la subárea…"
        autoComplete="off"
        onChange={(e) => {
          setTexto(e.target.value)
          if (valor) onPick(null) // tipear invalida la selección previa
        }}
        style={{ ...inputStyle, borderColor: error ? 'var(--color-error)' : 'var(--border-primary)' }}
      />
      {hits && (
        <div style={dropdownStyle}>
          {hits.length === 0 && <div style={{ padding: '8px 12px', fontSize: '0.82rem', color: 'var(--fg-3)' }}>Sin resultados</div>}
          {hits.map((s) => (
            <div
              key={s.id_subarea}
              style={dropdownItem}
              onClick={() => {
                skipNextRef.current = true
                setTexto(s.nombre)
                setHits(null)
                onPick(s)
              }}
            >
              <span style={{ fontSize: '0.86rem', color: 'var(--fg-1)' }}>{s.nombre}</span>
              {s.area_nombre && <span style={{ fontSize: '0.76rem', color: 'var(--fg-3)', marginLeft: 8 }}>{s.area_nombre}</span>}
            </div>
          ))}
        </div>
      )}
      {error
        ? <span style={{ fontSize: '0.78rem', color: 'var(--color-error)' }}>{error}</span>
        : valor && <span style={{ fontSize: '0.78rem', color: 'var(--fg-3)' }}>Subárea seleccionada{valor.area_nombre ? ` · ${valor.area_nombre}` : ''}.</span>}
    </div>
  )
}

// ── Estilos (tokens del DS) ──
const overlay: React.CSSProperties = {
  position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  zIndex: 1000, padding: 20,
}
const box: React.CSSProperties = {
  background: 'var(--surface-100)', borderRadius: 'var(--radius-lg)',
  width: '100%', maxWidth: 520, boxShadow: '0 10px 40px rgba(0,0,0,0.2)',
  display: 'flex', flexDirection: 'column', maxHeight: '90vh', overflow: 'hidden',
}
const header: React.CSSProperties = {
  padding: '14px 16px', borderBottom: '1px solid var(--border-primary)',
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
}
const footer: React.CSSProperties = {
  padding: '12px 16px', borderTop: '1px solid var(--border-primary)',
  display: 'flex', justifyContent: 'flex-end', gap: 10, background: 'var(--surface-200)',
}
const cerrarBtn: React.CSSProperties = {
  background: 'transparent', border: 'none', cursor: 'pointer',
  fontSize: 24, lineHeight: 1, color: 'var(--fg-3)', padding: '0 4px',
}
const campo: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: 6 }
const labelStyle: React.CSSProperties = {
  fontSize: 'var(--size-caption)', fontWeight: 600, color: 'var(--fg-2)', fontFamily: 'var(--font-display)',
}
const inputStyle: React.CSSProperties = {
  width: '100%', padding: '9px 12px', fontFamily: 'var(--font-display)', fontSize: 'var(--size-ui)',
  color: 'var(--fg-1)', background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-lg)', outline: 'none',
}
const dropdownStyle: React.CSSProperties = {
  position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 20, marginTop: 2,
  background: 'var(--surface-100)', border: '1px solid var(--border-medium)',
  borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-ambient)', maxHeight: 220, overflowY: 'auto',
}
const dropdownItem: React.CSSProperties = {
  padding: '8px 12px', cursor: 'pointer', display: 'flex', alignItems: 'baseline',
  borderBottom: '1px solid var(--border-primary)',
}
const btnPrimary: React.CSSProperties = {
  padding: '10px 18px', background: 'var(--zaris-dark)', color: 'var(--zaris-cream)',
  border: 'none', borderRadius: 'var(--radius-lg)', fontFamily: 'var(--font-display)',
  fontSize: 'var(--size-btn)', fontWeight: 500,
}
const btnGhost: React.CSSProperties = {
  padding: '10px 18px', background: 'transparent', color: 'var(--fg-2)',
  border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)',
  fontFamily: 'var(--font-display)', fontSize: 'var(--size-btn)', cursor: 'pointer',
}
