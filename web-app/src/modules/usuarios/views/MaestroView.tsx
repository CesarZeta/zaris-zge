import { useEffect, useMemo, useRef, useState } from 'react'
import { useNotificationsStore } from '../../../stores/notifications'
import { ConfirmModal } from '../../agenda/components/ConfirmModal'
import { useModulosCatalogo } from '../../config/hooks/useConfig'
import { buscarSubareas, buscarUsuarios } from '../api/usuariosApi'
import {
  useActualizarUsuario,
  useCambiarEstadoUsuario,
  useCrearUsuario,
  useLoginLog,
  useUsuariosLista,
} from '../hooks/useUsuarios'
import { NIVELES } from '../types'
import type { SubareaHit, Usuario, UsuarioUpdatePayload } from '../types'

// Migrado del vanilla frontend/usuarios.html + js/usuarios.js (2026-07-16).
// Mismos flujos: buscar predictivo, preview de últimos 5, listado con filtros
// client-side, form en 3 modos (nuevo/edición/consulta), subárea predictiva,
// clave temporal por mail en el alta (§39 Fase 3), historial de accesos.
// Simplificación documentada: el modal post-alta del vanilla ("cargar otro /
// salir") se reemplaza por toast + pasar a consulta del usuario creado.

type Modo = 'nuevo' | 'edicion' | 'consulta'

interface FormState {
  username: string
  email: string
  nivel: string
  bucAcceso: boolean
  esExterno: boolean
  subareaId: number | null
  subareaNombre: string
  password: string
  passwordConfirm: string
}

const FORM_VACIO: FormState = {
  username: '', email: '', nivel: '', bucAcceso: false, esExterno: false,
  subareaId: null, subareaNombre: '', password: '', passwordConfirm: '',
}

const USERNAME_RE = /^[a-zA-Z0-9_.\-]+$/
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

function fmtFechaHora(iso: string | null | undefined): string {
  if (!iso) return 'Nunca'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '—'
  return d.toLocaleString('es-AR', {
    day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

export function MaestroView() {
  const push = useNotificationsStore((s) => s.push)
  const lista = useUsuariosLista()
  const crear = useCrearUsuario()
  const actualizar = useActualizarUsuario()
  const cambiarEstado = useCambiarEstadoUsuario()

  const [vista, setVista] = useState<'home' | 'listado'>('home')
  const [q, setQ] = useState('')
  const [resultados, setResultados] = useState<Usuario[] | null>(null)
  const [modo, setModo] = useState<Modo | null>(null)
  const [usuario, setUsuario] = useState<Usuario | null>(null)
  const [form, setForm] = useState<FormState>(FORM_VACIO)
  const [confirmar, setConfirmar] = useState<null | 'baja' | 'reactivar' | 'cancelar'>(null)
  const [historialAbierto, setHistorialAbierto] = useState(false)
  const formRef = useRef<HTMLDivElement>(null)

  // ── Búsqueda predictiva (debounce 280ms, igual que el vanilla) ────────────
  useEffect(() => {
    const texto = q.trim()
    if (!texto) { setResultados(null); return }
    const t = setTimeout(async () => {
      try {
        setResultados(await buscarUsuarios(texto))
      } catch (err) {
        push({ kind: 'error', title: 'Error al buscar', body: (err as Error).message })
      }
    }, 280)
    return () => clearTimeout(t)
  }, [q, push])

  // Preview: últimos 5 por última actividad (fecha_modif desc, fallback alta/id).
  const recientes = useMemo(() => {
    const data = lista.data ?? []
    const ts = (u: Usuario) => Date.parse(u.fecha_modif || u.fecha_alta || '') || u.id_usuario
    return [...data].sort((a, b) => ts(b) - ts(a)).slice(0, 5)
  }, [lista.data])

  function abrirUsuario(u: Usuario, modoNuevo: Modo) {
    setUsuario(u)
    setForm({
      username: u.username, email: u.email ?? '', nivel: String(u.nivel_acceso),
      bucAcceso: u.buc_acceso, esExterno: u.es_externo,
      subareaId: u.id_subarea, subareaNombre: u.subarea_nombre ?? '',
      password: '', passwordConfirm: '',
    })
    setModo(modoNuevo)
    setTimeout(() => formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
  }

  function abrirNuevo() {
    setUsuario(null)
    setForm(FORM_VACIO)
    setModo('nuevo')
    setTimeout(() => formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
  }

  function cerrarForm() {
    setModo(null)
    setUsuario(null)
    setForm(FORM_VACIO)
  }

  function pedirCancelar() {
    if (modo === 'nuevo' && (form.username || form.email)) setConfirmar('cancelar')
    else cerrarForm()
  }

  // ── Validación (espejo del vanilla) ───────────────────────────────────────
  const errores = useMemo(() => {
    const e: Record<string, string> = {}
    if (!modo || modo === 'consulta') return e
    if (!form.username.trim()) e.username = 'El nombre de usuario es requerido'
    else if (!USERNAME_RE.test(form.username.trim())) e.username = 'Solo letras, números, puntos y guiones'
    if (!form.nivel) e.nivel = 'Seleccioná un nivel de acceso'
    if (!form.esExterno && form.subareaId == null) e.subarea = 'La subárea es obligatoria (o marcá "Usuario externo")'
    if (modo === 'nuevo') {
      const email = form.email.trim()
      if (!email) e.email = 'El email es requerido'
      else if (!EMAIL_RE.test(email)) e.email = 'Formato de email inválido'
    }
    if (modo === 'edicion' && form.password) {
      if (form.password.length < 8) e.password = 'Mínimo 8 caracteres'
      else if (form.password !== form.passwordConfirm) e.passwordConfirm = 'Las contraseñas no coinciden'
    }
    return e
  }, [modo, form])

  const puedeGuardar = modo !== 'consulta' && Object.keys(errores).length === 0

  async function guardar() {
    // puedeGuardar ya excluye el modo consulta (TS lo narrowea vía el alias).
    if (!puedeGuardar || !modo) return
    const base = {
      nivel_acceso: parseInt(form.nivel, 10),
      buc_acceso: form.bucAcceso,
      es_externo: form.esExterno,
      id_subarea: form.esExterno ? null : form.subareaId,
    }
    try {
      if (modo === 'nuevo') {
        const u = await crear.mutateAsync({
          ...base, username: form.username.trim(), email: form.email.trim(),
        })
        push({
          kind: 'success', title: `Usuario ${u.username} creado`,
          body: `Se le envió una contraseña temporal a ${u.email}; deberá cambiarla en su primer ingreso.`,
          ttl: 8000,
        })
        abrirUsuario(u, 'consulta')
      } else if (usuario) {
        const payload: UsuarioUpdatePayload = { ...base }
        const email = form.email.trim()
        if (email) payload.email = email
        if (form.password) payload.password = form.password
        const u = await actualizar.mutateAsync({ id: usuario.id_usuario, payload })
        push({ kind: 'success', title: 'Usuario guardado correctamente' })
        abrirUsuario(u, 'consulta')
      }
    } catch (err) {
      push({ kind: 'error', title: 'Error al guardar', body: (err as Error).message })
    }
  }

  async function ejecutarCambioEstado(nuevoActivo: boolean) {
    if (!usuario) return
    setConfirmar(null)
    try {
      const u = await cambiarEstado.mutateAsync({ id: usuario.id_usuario, activo: nuevoActivo })
      push({ kind: 'success', title: nuevoActivo ? 'Usuario reactivado' : 'Usuario dado de baja' })
      abrirUsuario(u, 'edicion')
    } catch (err) {
      push({ kind: 'error', title: 'Error', body: (err as Error).message })
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      {vista === 'home' && (
        <>
          {/* Panel de búsqueda (§15) */}
          <div style={panelBusqueda}>
            <div style={panelTitulo}>Buscar usuario existente</div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <input
                type="text"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Usuario, email o subárea…"
                style={{ ...inputStyle, flex: 1, minWidth: 220 }}
                autoFocus
              />
              <button type="button" style={btn('primary')} onClick={abrirNuevo}>+ Nuevo</button>
              <button type="button" style={btn('outline')} onClick={() => setVista('listado')}>Listado</button>
            </div>

            {resultados && (
              <div style={{ marginTop: 12 }}>
                {resultados.length === 0 && (
                  <div style={{ fontSize: '0.84rem', color: 'var(--fg-3)' }}>
                    No se encontraron usuarios con ese criterio.
                  </div>
                )}
                {resultados.map((u) => (
                  <div key={u.id_usuario} style={filaResultado}>
                    <span style={{ fontSize: '0.88rem', minWidth: 0 }}>
                      <strong>{u.username}</strong>
                      <span style={{ color: 'var(--fg-3)', marginLeft: 8, fontSize: '0.78rem' }}>
                        {NIVELES[u.nivel_acceso] ?? `Nivel ${u.nivel_acceso}`}
                        {' — '}
                        {u.es_externo ? 'Externo' : (u.subarea_nombre ?? 'Sin subárea')}
                      </span>
                      {!u.activo && (
                        <span style={{ color: 'var(--color-error)', fontSize: '0.75rem', marginLeft: 6 }}>[Inactivo]</span>
                      )}
                    </span>
                    <span style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                      <button type="button" style={btn('primary', 'xs')} onClick={() => abrirUsuario(u, 'edicion')}>Editar</button>
                      <button type="button" style={btn('ghost', 'xs')} onClick={() => abrirUsuario(u, 'consulta')}>Ver</button>
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Últimos ingresados/modificados */}
          <div>
            <div style={seccionTitulo}>Últimos usuarios</div>
            {lista.isLoading && <div style={mutedText}>Cargando…</div>}
            {lista.isError && <div style={{ ...mutedText, color: 'var(--color-error)' }}>No se pudo cargar la vista previa.</div>}
            {recientes.map((u) => (
              <div key={u.id_usuario} style={filaPreview} onClick={() => abrirUsuario(u, 'consulta')}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.86rem', fontWeight: 600, color: 'var(--fg-1)' }}>
                  {u.username}
                </span>
                <span style={metaPreview}>{NIVELES[u.nivel_acceso] ?? `Nivel ${u.nivel_acceso}`}</span>
                <span style={{ ...metaPreview, flex: 1, minWidth: 0 }}>{u.es_externo ? 'Externo' : (u.subarea_nombre ?? '—')}</span>
                <span style={metaPreview} title="Último inicio de sesión">↪ {fmtFechaHora(u.fecha_ultimo_login)}</span>
                <span style={badgeEstado(u.activo)}>{u.activo ? 'Activo' : 'Inactivo'}</span>
                <span style={{ fontSize: '0.78rem', color: 'var(--zaris-orange)', fontWeight: 600 }}>Ver →</span>
              </div>
            ))}
          </div>
        </>
      )}

      {vista === 'listado' && (
        <ListadoUsuarios
          usuarios={lista.data ?? []}
          cargando={lista.isLoading}
          onVolver={() => setVista('home')}
          onAbrir={(u, m) => { setVista('home'); abrirUsuario(u, m) }}
        />
      )}

      {modo && (
        <div ref={formRef} style={formCard}>
          <div style={formHeader}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <h2 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600, color: 'var(--fg-1)' }}>
                {modo === 'nuevo' ? 'Alta de usuario' : modo === 'edicion' ? 'Editar usuario' : 'Consulta de usuario'}
              </h2>
              {modo !== 'nuevo' && usuario && (
                <span style={badgeEstado(usuario.activo)}>{usuario.activo ? 'Activo' : 'Inactivo'}</span>
              )}
            </div>
            <span style={chipModo(modo)}>{modo === 'nuevo' ? 'NUEVO' : modo === 'edicion' ? 'EDICIÓN' : 'CONSULTA'}</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={seccionTitulo}>Identificación</div>
            <div style={filaCampos}>
              <Campo label="Nombre de usuario" requerido error={errores.username}
                hint="El usuario es la identidad de la cuenta. Solo letras, números, puntos y guiones.">
                <input
                  type="text" value={form.username} maxLength={50}
                  readOnly={modo !== 'nuevo'} disabled={modo === 'consulta'}
                  onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
                  placeholder="usuario.ejemplo" style={inputStyle}
                />
              </Campo>
              <Campo label="Nivel de acceso" requerido error={errores.nivel}>
                <select
                  value={form.nivel} disabled={modo === 'consulta'}
                  onChange={(e) => setForm((f) => ({ ...f, nivel: e.target.value }))}
                  style={inputStyle}
                >
                  <option value="">Seleccionar…</option>
                  {Object.entries(NIVELES).map(([n, label]) => (
                    <option key={n} value={n}>{n} — {label}</option>
                  ))}
                </select>
                <ChipsModulos usuario={usuario} nivel={form.nivel ? parseInt(form.nivel, 10) : null} />
              </Campo>
            </div>
            <div style={filaCampos}>
              <Campo label="Email" requerido={modo === 'nuevo'} error={errores.email}
                hint="Se usa para iniciar sesión y para enviarle sus credenciales. Debe ser un correo real.">
                <input
                  type="email" value={form.email} maxLength={150} disabled={modo === 'consulta'}
                  onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                  placeholder="usuario@municipio.gob.ar" style={inputStyle}
                />
              </Campo>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, alignSelf: 'end', paddingBottom: 22, fontSize: '0.86rem', color: 'var(--fg-2)' }}>
                <input
                  type="checkbox" checked={form.bucAcceso} disabled={modo === 'consulta'}
                  onChange={(e) => setForm((f) => ({ ...f, bucAcceso: e.target.checked }))}
                />
                Acceso módulo BUC
              </label>
            </div>

            <div style={seccionTitulo}>Pertenencia</div>
            <div style={filaCampos}>
              <SubareaSearch
                deshabilitado={modo === 'consulta' || form.esExterno}
                externo={form.esExterno}
                requerido={!form.esExterno}
                error={errores.subarea}
                valor={{ id: form.subareaId, nombre: form.subareaNombre }}
                onPick={(s) => setForm((f) => ({ ...f, subareaId: s?.id_subarea ?? null, subareaNombre: s?.nombre ?? '' }))}
              />
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, alignSelf: 'end', paddingBottom: 22, fontSize: '0.86rem', color: 'var(--fg-2)' }}>
                <input
                  type="checkbox" checked={form.esExterno} disabled={modo === 'consulta'}
                  onChange={(e) => setForm((f) => ({
                    ...f, esExterno: e.target.checked,
                    ...(e.target.checked ? { subareaId: null, subareaNombre: '' } : {}),
                  }))}
                />
                Usuario externo (sin subárea)
              </label>
            </div>

            <div style={seccionTitulo}>Contraseña</div>
            {modo === 'nuevo' ? (
              <div style={avisoInfo}>
                Se generará una contraseña temporal y se enviará al email del usuario.
                Deberá cambiarla en su primer ingreso.
              </div>
            ) : (
              <div style={filaCampos}>
                <Campo label="Nueva contraseña" error={errores.password}
                  hint={pistaPassword(form.password, form.passwordConfirm)}>
                  <input
                    type="password" value={form.password} maxLength={100} disabled={modo === 'consulta'}
                    autoComplete="new-password" placeholder="Mínimo 8 caracteres"
                    onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                    style={inputStyle}
                  />
                </Campo>
                <Campo label="Confirmar contraseña" error={errores.passwordConfirm}>
                  <input
                    type="password" value={form.passwordConfirm} maxLength={100} disabled={modo === 'consulta'}
                    autoComplete="new-password" placeholder="Repetir contraseña"
                    onChange={(e) => setForm((f) => ({ ...f, passwordConfirm: e.target.value }))}
                    style={inputStyle}
                  />
                </Campo>
              </div>
            )}

            {modo !== 'nuevo' && usuario && (
              <>
                <div style={seccionTitulo}>Actividad</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap', fontSize: '0.86rem', color: 'var(--fg-2)' }}>
                  <span>
                    Último inicio de sesión:
                    <strong style={{ color: 'var(--fg-1)', marginLeft: 6 }}>{fmtFechaHora(usuario.fecha_ultimo_login)}</strong>
                  </span>
                  <button type="button" style={btn('ghost', 'sm')} onClick={() => setHistorialAbierto(true)}>
                    Ver historial de accesos
                  </button>
                </div>
              </>
            )}
          </div>

          <div style={formFooter}>
            <button type="button" style={btn('ghost')} onClick={pedirCancelar}>
              {modo === 'nuevo' ? 'Cancelar' : 'Salir'}
            </button>
            {modo === 'edicion' && usuario?.activo && (
              <button type="button" style={btn('danger')} onClick={() => setConfirmar('baja')}>Dar de baja</button>
            )}
            {modo === 'edicion' && usuario && !usuario.activo && (
              <button type="button" style={btn('success')} onClick={() => setConfirmar('reactivar')}>Reactivar</button>
            )}
            {modo === 'consulta' && (
              <button type="button" style={btn('outline')} onClick={() => setModo('edicion')}>Editar</button>
            )}
            {modo !== 'consulta' && (
              <button
                type="button"
                style={btn('primary', undefined, !puedeGuardar || crear.isPending || actualizar.isPending)}
                disabled={!puedeGuardar || crear.isPending || actualizar.isPending}
                onClick={guardar}
              >
                {crear.isPending || actualizar.isPending ? 'Guardando…' : 'Guardar usuario'}
              </button>
            )}
          </div>
        </div>
      )}

      <ConfirmModal
        open={confirmar === 'baja'}
        title="Dar de baja usuario"
        message={`¿Dar de baja al usuario ${usuario?.username}? No podrá iniciar sesión.`}
        confirmLabel="Sí, dar de baja" cancelLabel="Cancelar" danger
        onConfirm={() => ejecutarCambioEstado(false)}
        onCancel={() => setConfirmar(null)}
      />
      <ConfirmModal
        open={confirmar === 'reactivar'}
        title="Reactivar usuario"
        message={`¿Reactivar al usuario ${usuario?.username}?`}
        confirmLabel="Sí, reactivar" cancelLabel="Cancelar"
        onConfirm={() => ejecutarCambioEstado(true)}
        onCancel={() => setConfirmar(null)}
      />
      <ConfirmModal
        open={confirmar === 'cancelar'}
        title="Cancelar alta"
        message="¿Descartar los datos ingresados?"
        confirmLabel="Sí, descartar" cancelLabel="Seguir editando" danger
        onConfirm={() => { setConfirmar(null); cerrarForm() }}
        onCancel={() => setConfirmar(null)}
      />

      {historialAbierto && usuario && (
        <HistorialModal usuario={usuario} onCerrar={() => setHistorialAbierto(false)} />
      )}
    </div>
  )
}

// ── Chips de módulos a los que accede ───────────────────────────────────────
// Usuario cargado → sus modulos_permitidos reales. Alta nueva → derivados del
// nivel elegido + catálogo (min_nivel_acceso >= nivel, §30). El catálogo trae
// el nombre legible (reemplaza el MODULO_LABEL hardcodeado del vanilla).
function ChipsModulos({ usuario, nivel }: { usuario: Usuario | null; nivel: number | null }) {
  const catalogo = useModulosCatalogo()
  const porCodigo = useMemo(
    () => new Map((catalogo.data ?? []).map((m) => [m.modulo_codigo, m.nombre])),
    [catalogo.data],
  )
  let codigos: string[] | null = null
  if (usuario) codigos = usuario.modulos_permitidos
  else if (nivel) {
    codigos = (catalogo.data ?? [])
      .filter((m) => m.activo !== false && m.min_nivel_acceso >= nivel)
      .map((m) => m.modulo_codigo)
      .sort()
  }
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
      <span style={{ fontSize: '0.74rem', color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        Accede a:
      </span>
      {codigos == null ? (
        <span style={chipMod(true)}>elegí un nivel</span>
      ) : codigos.length === 0 ? (
        <span style={chipMod(true)}>sin acceso</span>
      ) : (
        codigos.map((c) => <span key={c} style={chipMod(false)}>{porCodigo.get(c) ?? c}</span>)
      )}
    </div>
  )
}

// ── Buscador predictivo de subárea (patrón skipNextRef §29) ─────────────────
function SubareaSearch({ deshabilitado, externo, requerido, error, valor, onPick }: {
  deshabilitado: boolean
  externo: boolean
  requerido: boolean
  error?: string
  valor: { id: number | null; nombre: string }
  onPick: (s: SubareaHit | null) => void
}) {
  const [texto, setTexto] = useState(valor.nombre)
  const [hits, setHits] = useState<SubareaHit[] | null>(null)
  const skipNextRef = useRef(false)
  const wrapRef = useRef<HTMLDivElement>(null)

  // Sincronizar el input cuando el padre cambia la selección (cargar usuario, externo).
  useEffect(() => {
    skipNextRef.current = true
    setTexto(valor.nombre)
  }, [valor.id, valor.nombre])

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
    <div ref={wrapRef} style={{ position: 'relative', display: 'flex', flexDirection: 'column', gap: 6 }}>
      <label style={labelStyle}>
        Subárea{requerido && <span style={{ color: 'var(--color-error)' }}> *</span>}
      </label>
      <input
        type="text"
        value={texto}
        disabled={deshabilitado}
        placeholder={externo ? 'No aplica (usuario externo)' : 'Escribí para buscar subárea…'}
        onChange={(e) => {
          setTexto(e.target.value)
          if (valor.id != null) onPick(null) // tipear invalida la selección previa
        }}
        style={inputStyle}
        autoComplete="off"
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
        : valor.id != null && <span style={{ fontSize: '0.78rem', color: 'var(--fg-3)' }}>Subárea seleccionada.</span>}
    </div>
  )
}

// ── Listado completo con filtros client-side ────────────────────────────────
function ListadoUsuarios({ usuarios, cargando, onVolver, onAbrir }: {
  usuarios: Usuario[]
  cargando: boolean
  onVolver: () => void
  onAbrir: (u: Usuario, modo: Modo) => void
}) {
  const [texto, setTexto] = useState('')
  const [nivel, setNivel] = useState('')
  const [subarea, setSubarea] = useState('')
  const [orden, setOrden] = useState('reciente')
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')

  const subareas = useMemo(() => {
    const vistos = new Map<number, string>()
    usuarios.forEach((u) => {
      if (u.id_subarea != null && u.subarea_nombre && !vistos.has(u.id_subarea)) {
        vistos.set(u.id_subarea, u.subarea_nombre)
      }
    })
    return [...vistos.entries()].sort((a, b) => a[1].localeCompare(b[1], 'es'))
  }, [usuarios])

  const filas = useMemo(() => {
    let rows = [...usuarios]
    const t = texto.toLowerCase().trim()
    if (t) rows = rows.filter((u) =>
      u.username.toLowerCase().includes(t) || (u.subarea_nombre ?? '').toLowerCase().includes(t))
    if (nivel) rows = rows.filter((u) => String(u.nivel_acceso) === nivel)
    if (subarea === '__externo') rows = rows.filter((u) => u.es_externo)
    else if (subarea) rows = rows.filter((u) => String(u.id_subarea) === subarea)
    if (desde || hasta) rows = rows.filter((u) => {
      const d = (u.fecha_alta ?? '').slice(0, 10)
      if (!d) return true
      if (desde && d < desde) return false
      if (hasta && d > hasta) return false
      return true
    })
    if (orden === 'reciente') rows.sort((a, b) => b.id_usuario - a.id_usuario)
    else if (orden === 'antiguo') rows.sort((a, b) => a.id_usuario - b.id_usuario)
    else if (orden === 'az') rows.sort((a, b) => a.username.localeCompare(b.username, 'es'))
    else if (orden === 'za') rows.sort((a, b) => b.username.localeCompare(a.username, 'es'))
    return rows
  }, [usuarios, texto, nivel, subarea, orden, desde, hasta])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h2 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600, color: 'var(--fg-1)' }}>Listado de usuarios</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <button type="button" style={btn('ghost', 'sm')} onClick={() => window.print()}>Imprimir</button>
          <button type="button" style={btn('ghost', 'sm')} onClick={onVolver}>← Volver</button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <Filtro label="Buscar">
          <input type="text" value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Usuario o subárea…" style={inputStyle} />
        </Filtro>
        <Filtro label="Nivel">
          <select value={nivel} onChange={(e) => setNivel(e.target.value)} style={inputStyle}>
            <option value="">Todos</option>
            {Object.entries(NIVELES).map(([n, l]) => <option key={n} value={n}>{l}</option>)}
          </select>
        </Filtro>
        <Filtro label="Subárea">
          <select value={subarea} onChange={(e) => setSubarea(e.target.value)} style={inputStyle}>
            <option value="">Todas</option>
            <option value="__externo">Externos (sin subárea)</option>
            {subareas.map(([id, nombre]) => <option key={id} value={String(id)}>{nombre}</option>)}
          </select>
        </Filtro>
        <Filtro label="Ordenar">
          <select value={orden} onChange={(e) => setOrden(e.target.value)} style={inputStyle}>
            <option value="reciente">Más reciente primero</option>
            <option value="az">A → Z</option>
            <option value="za">Z → A</option>
            <option value="antiguo">Más antiguo primero</option>
          </select>
        </Filtro>
        <Filtro label="Fecha alta desde">
          <input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} style={inputStyle} />
        </Filtro>
        <Filtro label="Fecha alta hasta">
          <input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} style={inputStyle} />
        </Filtro>
        <button type="button" style={btn('ghost', 'sm')} onClick={() => { setTexto(''); setNivel(''); setSubarea(''); setOrden('reciente'); setDesde(''); setHasta('') }}>
          Limpiar
        </button>
      </div>

      <div style={{ fontSize: '0.82rem', color: 'var(--fg-3)' }}>
        {cargando ? 'Cargando…' : `${filas.length} usuario${filas.length !== 1 ? 's' : ''} encontrado${filas.length !== 1 ? 's' : ''}`}
      </div>

      {!cargando && filas.length === 0 && (
        <div style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--fg-3)' }}>
          Sin resultados para los filtros aplicados
        </div>
      )}

      {filas.length > 0 && (
        <div style={{ overflowX: 'auto', border: '1px solid var(--border-primary)', borderRadius: 10 }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.86rem' }}>
            <thead>
              <tr>
                {['Usuario', 'Nivel', 'Subárea', 'Último login', 'Estado', 'Acciones'].map((h) => (
                  <th key={h} style={thStyle}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filas.map((u) => (
                <tr key={u.id_usuario}>
                  <td style={{ ...tdStyle, fontFamily: 'var(--font-mono)' }}>{u.username}</td>
                  <td style={tdStyle}>{NIVELES[u.nivel_acceso] ?? u.nivel_acceso}</td>
                  <td style={tdStyle}>{u.es_externo ? <em style={{ color: 'var(--fg-3)' }}>Externo</em> : (u.subarea_nombre ?? '—')}</td>
                  <td style={tdStyle}>{fmtFechaHora(u.fecha_ultimo_login)}</td>
                  <td style={tdStyle}><span style={badgeEstado(u.activo)}>{u.activo ? 'Activo' : 'Inactivo'}</span></td>
                  <td style={tdStyle}>
                    <span style={{ display: 'flex', gap: 6 }}>
                      <button type="button" style={btn('ghost', 'xs')} onClick={() => onAbrir(u, 'consulta')}>Ver</button>
                      <button type="button" style={btn('ghost', 'xs')} onClick={() => onAbrir(u, 'edicion')}>Editar</button>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Modal historial de accesos ──────────────────────────────────────────────
function HistorialModal({ usuario, onCerrar }: { usuario: Usuario; onCerrar: () => void }) {
  const log = useLoginLog(usuario.id_usuario, true)

  useEffect(() => {
    function esc(e: KeyboardEvent) { if (e.key === 'Escape') onCerrar() }
    document.addEventListener('keydown', esc)
    return () => document.removeEventListener('keydown', esc)
  }, [onCerrar])

  return (
    <div style={overlayStyle} onClick={(e) => { if (e.target === e.currentTarget) onCerrar() }}>
      <div style={modalStyle}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600, color: 'var(--fg-1)' }}>
            Historial de accesos — {usuario.username}
          </h3>
          <button type="button" onClick={onCerrar} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.2rem', color: 'var(--fg-2)' }} aria-label="Cerrar">×</button>
        </div>
        {log.isLoading && <div style={mutedText}>Cargando…</div>}
        {log.isError && <div style={{ ...mutedText, color: 'var(--color-error)' }}>Error: {(log.error as Error).message}</div>}
        {log.data && log.data.length === 0 && (
          <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--fg-3)' }}>Sin accesos registrados.</div>
        )}
        {log.data && log.data.length > 0 && (
          <div style={{ overflowX: 'auto', maxHeight: 420, overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.84rem' }}>
              <thead>
                <tr>
                  {['Fecha y hora', 'IP', 'Dispositivo'].map((h) => <th key={h} style={thStyle}>{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {log.data.map((l, i) => (
                  <tr key={i}>
                    <td style={{ ...tdStyle, fontFamily: 'var(--font-mono)' }}>{fmtFechaHora(l.fecha_login)}</td>
                    <td style={{ ...tdStyle, fontFamily: 'var(--font-mono)' }}>{l.ip ?? '—'}</td>
                    <td style={{ ...tdStyle, maxWidth: 340, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={l.user_agent ?? ''}>
                      {l.user_agent ?? '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Piezas chicas ───────────────────────────────────────────────────────────
function Campo({ label, requerido, hint, error, children }: {
  label: string
  requerido?: boolean
  hint?: string
  error?: string
  children: React.ReactNode
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <label style={labelStyle}>
        {label}{requerido && <span style={{ color: 'var(--color-error)' }}> *</span>}
      </label>
      {children}
      {error
        ? <span style={{ fontSize: '0.78rem', color: 'var(--color-error)' }}>{error}</span>
        : hint && <span style={{ fontSize: '0.78rem', color: 'var(--fg-3)' }}>{hint}</span>}
    </div>
  )
}

function Filtro({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label style={{ fontSize: '0.74rem', color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{label}</label>
      {children}
    </div>
  )
}

// Pista en vivo del reset de contraseña (el botón se deshabilita, esto explica por qué).
function pistaPassword(pwd: string, cf: string): string | undefined {
  if (!pwd) return 'Dejar vacío para no cambiar la contraseña.'
  if (pwd.length < 8) return undefined // el error ya lo dice
  if (!cf) return 'Repetí la contraseña para confirmar el cambio.'
  if (pwd === cf) return 'La contraseña coincide.'
  return undefined
}

// ── Estilos ─────────────────────────────────────────────────────────────────
const panelBusqueda: React.CSSProperties = {
  padding: 16,
  background: 'rgba(15, 215, 255, 0.06)',
  border: '1px solid rgba(15, 215, 255, 0.25)',
  borderRadius: 12,
}
const panelTitulo: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.84rem', fontWeight: 600,
  textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--fg-2)',
  marginBottom: 10,
}
const seccionTitulo: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.8rem', fontWeight: 600,
  textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--fg-3)',
  borderBottom: '1px solid var(--border-primary)', paddingBottom: 6, marginBottom: 4,
}
const filaResultado: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10,
  padding: '7px 0', borderBottom: '1px solid var(--border-primary)',
}
const filaPreview: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 14,
  padding: '10px 12px', borderBottom: '1px solid var(--border-primary)',
  cursor: 'pointer',
}
const metaPreview: React.CSSProperties = {
  fontSize: '0.8rem', color: 'var(--fg-3)', whiteSpace: 'nowrap',
  overflow: 'hidden', textOverflow: 'ellipsis',
}
const formCard: React.CSSProperties = {
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 12, padding: 20,
  display: 'flex', flexDirection: 'column', gap: 18,
}
const formHeader: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  borderBottom: '1px solid var(--border-primary)', paddingBottom: 12,
}
const formFooter: React.CSSProperties = {
  display: 'flex', justifyContent: 'flex-end', gap: 10,
  borderTop: '1px solid var(--border-primary)', paddingTop: 14,
}
const filaCampos: React.CSSProperties = {
  display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16,
}
const labelStyle: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.84rem', fontWeight: 600, color: 'var(--fg-1)',
}
const inputStyle: React.CSSProperties = {
  padding: '8px 12px', fontSize: '0.9rem', fontFamily: 'var(--font-display)',
  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
  borderRadius: 8, color: 'var(--fg-1)', outline: 'none', width: '100%', boxSizing: 'border-box',
}
const dropdownStyle: React.CSSProperties = {
  position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 30,
  background: 'var(--surface-100)', border: '1px solid var(--border-medium)',
  borderRadius: 8, boxShadow: '0 8px 24px rgba(0,0,0,0.12)', maxHeight: 260, overflowY: 'auto',
}
const dropdownItem: React.CSSProperties = {
  padding: '8px 12px', cursor: 'pointer', borderBottom: '1px solid var(--border-primary)',
}
const avisoInfo: React.CSSProperties = {
  padding: '10px 14px', fontSize: '0.86rem',
  background: 'rgba(15, 118, 215, 0.08)', border: '1px solid rgba(15, 118, 215, 0.25)',
  borderRadius: 8, color: 'var(--fg-2)',
}
const mutedText: React.CSSProperties = { fontSize: '0.84rem', color: 'var(--fg-3)', padding: '6px 0' }
const overlayStyle: React.CSSProperties = {
  position: 'fixed', inset: 0, zIndex: 100,
  background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center',
  padding: 20,
}
const modalStyle: React.CSSProperties = {
  background: 'var(--surface-100)', borderRadius: 12, padding: 20,
  width: 'min(720px, 100%)', maxHeight: '85vh', overflowY: 'auto',
  border: '1px solid var(--border-primary)',
}
const thStyle: React.CSSProperties = {
  textAlign: 'left', padding: '8px 12px', fontSize: '0.76rem',
  textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--fg-3)',
  borderBottom: '1px solid var(--border-medium)', background: 'var(--surface-300)',
}
const tdStyle: React.CSSProperties = {
  padding: '8px 12px', borderBottom: '1px solid var(--border-primary)', color: 'var(--fg-1)',
}
function badgeEstado(activo: boolean): React.CSSProperties {
  return {
    display: 'inline-block', padding: '2px 10px', borderRadius: 999,
    fontSize: '0.74rem', fontWeight: 600,
    background: activo ? 'rgba(31,138,101,0.12)' : 'rgba(207,45,86,0.1)',
    color: activo ? 'var(--color-success)' : 'var(--color-error)',
  }
}
function chipModo(modo: Modo): React.CSSProperties {
  const color = modo === 'nuevo' ? 'var(--color-success)' : modo === 'edicion' ? 'var(--zaris-orange)' : 'var(--fg-3)'
  return {
    fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.06em',
    color, border: `1px solid ${color}`, borderRadius: 6, padding: '2px 8px',
  }
}
function chipMod(vacio: boolean): React.CSSProperties {
  return {
    display: 'inline-block', padding: '1px 8px', borderRadius: 999, fontSize: '0.72rem',
    background: vacio ? 'transparent' : 'var(--surface-400)',
    border: `1px solid ${vacio ? 'var(--border-primary)' : 'var(--border-medium)'}`,
    color: vacio ? 'var(--fg-3)' : 'var(--fg-2)',
    fontStyle: vacio ? 'italic' : 'normal',
  }
}
function btn(
  variant: 'primary' | 'ghost' | 'outline' | 'danger' | 'success',
  size?: 'xs' | 'sm',
  disabled = false,
): React.CSSProperties {
  const base: React.CSSProperties = {
    display: 'inline-flex', alignItems: 'center', gap: 6,
    padding: size === 'xs' ? '3px 10px' : size === 'sm' ? '5px 12px' : '7px 14px',
    fontFamily: 'var(--font-display)', fontSize: size === 'xs' ? '0.78rem' : '0.86rem', fontWeight: 600,
    borderRadius: 8, cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.5 : 1, border: '1px solid transparent',
    transition: 'background 150ms ease',
  }
  switch (variant) {
    case 'primary': return { ...base, background: 'var(--zaris-orange)', color: '#fff', borderColor: 'var(--zaris-orange)' }
    case 'danger': return { ...base, background: 'transparent', color: 'var(--color-error)', borderColor: 'var(--color-error)' }
    case 'success': return { ...base, background: 'transparent', color: 'var(--color-success)', borderColor: 'var(--color-success)' }
    case 'outline': return { ...base, background: 'transparent', color: 'var(--fg-1)', borderColor: 'var(--border-medium)' }
    default: return { ...base, background: 'transparent', color: 'var(--fg-2)', borderColor: 'var(--border-primary)' }
  }
}
