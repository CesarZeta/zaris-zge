import { useEffect, useRef, useState } from 'react'
import { buscarSubareas } from '../api/ciudadanosApi'
import type { SubareaHit } from '../types/ciudadano'

/**
 * Campos de la cuenta ZARIS dentro de la ficha del ciudadano (mig 110): nivel de acceso,
 * subárea y nombre de usuario — lo que la ficha NO tiene. Aparecen debajo del tilde
 * «funcionario del municipio» cuando la persona todavía no tiene cuenta; al guardar la
 * ficha el backend crea la cuenta en la misma transacción (`cuenta_zaris` del POST/PUT).
 * No hay botón ni modal aparte (decisión de César, 2026-10-13).
 *
 * Patrones del proyecto (§23/§29): el usuario se propone desde nombre.apellido y se respeta
 * si el admin lo edita (validación en vivo); subárea predictiva con skipNextRef.
 */

// Niveles de acceso (CLAUDE.md §3). Copia local: no se importa del módulo Usuarios.
export const NIVELES: Array<{ valor: number; label: string; ayuda: string }> = [
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

export function usernameValido(u: string): boolean {
  return u.length > 0 && u.length <= 50 && USERNAME_RE.test(u)
}

interface Props {
  nivel: number
  subarea: SubareaHit | null
  username: string
  email: string
  errores: { subarea?: string; username?: string }
  onNivel: (n: number) => void
  onSubarea: (s: SubareaHit | null) => void
  onUsername: (u: string) => void
}

export function CuentaZarisCampos({ nivel, subarea, username, email, errores, onNivel, onSubarea, onUsername }: Props) {
  const usernameOk = usernameValido(username)
  return (
    <div style={bloque}>
      <p style={{ margin: 0, fontSize: 'var(--size-caption)', color: 'var(--fg-2)', lineHeight: 1.5 }}>
        Al guardar se crea su cuenta para el sistema y la app de agentes. Las credenciales (clave temporal)
        se envían a <strong>{email.trim() || 'el email de la ficha'}</strong>; en el primer ingreso el sistema le
        pide elegir su propia contraseña. Puede ingresar con su email o su DNI.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
        <div style={campo}>
          <label style={labelStyle}>Nivel de acceso <span style={{ color: 'var(--zaris-orange)' }}>*</span></label>
          <select value={nivel} onChange={(e) => onNivel(Number(e.target.value))} style={inputStyle}>
            {NIVELES.map((n) => (
              <option key={n.valor} value={n.valor}>{n.label} — {n.ayuda}</option>
            ))}
          </select>
        </div>

        <SubareaSearch valor={subarea} error={errores.subarea} onPick={onSubarea} />

        <div style={campo}>
          <label style={labelStyle}>Nombre de usuario <span style={{ color: 'var(--zaris-orange)' }}>*</span></label>
          <div style={{ position: 'relative' }}>
            <input
              type="text"
              value={username}
              maxLength={50}
              autoComplete="off"
              onChange={(e) => onUsername(e.target.value)}
              style={{
                ...inputStyle,
                paddingRight: 32,
                borderColor: errores.username
                  ? 'var(--color-error)'
                  : username ? (usernameOk ? 'var(--color-success)' : 'var(--color-error)') : 'var(--border-primary)',
              }}
            />
            {username && (
              <span aria-hidden="true" style={{
                position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
                fontWeight: 700, color: usernameOk ? 'var(--color-success)' : 'var(--color-error)',
              }}>{usernameOk ? '✓' : '✕'}</span>
            )}
          </div>
          <span style={{ fontSize: '0.78rem', color: errores.username || (username && !usernameOk) ? 'var(--color-error)' : 'var(--fg-3)' }}>
            {errores.username ?? <>Se propone <code>nombre.apellido</code>; podés cambiarlo. Letras, números, punto, guión y guión bajo, <strong>sin espacios ni tildes</strong>.</>}
          </span>
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
  // Si el bloque se desmonta y vuelve (destildar/tildar), arranca con la subárea ya elegida.
  const [texto, setTexto] = useState(valor?.nombre ?? '')
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
      <label style={labelStyle}>Subárea <span style={{ color: 'var(--zaris-orange)' }}>*</span></label>
      <input
        type="text"
        value={texto}
        placeholder="Escribí para buscar la subárea…"
        autoComplete="off"
        onChange={(e) => {
          setTexto(e.target.value)
          if (valor) onPick(null) // tipear invalida la selección previa
        }}
        style={{ ...inputStyle, borderColor: error ? 'var(--color-error)' : valor ? 'var(--color-success)' : 'var(--border-primary)' }}
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

// ── Estilos (tokens del DS; espejan los del CiudadanoForm) ──
const bloque: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 12,
  padding: '12px 14px',
  background: 'rgba(96,165,200,.08)',
  border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-md)',
}
const campo: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: 4 }
const labelStyle: React.CSSProperties = {
  fontSize: 'var(--size-caption)', fontWeight: 600, color: 'var(--fg-2)',
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
