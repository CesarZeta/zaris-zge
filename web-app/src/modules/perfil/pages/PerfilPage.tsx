import { useEffect, useRef, useState } from 'react'
import QRCode from 'qrcode'
import {
  Camera, Check, Copy, ExternalLink, Eye, EyeOff, KeyRound, LayoutGrid, Smartphone, Trash2, User,
} from 'lucide-react'
import { useAuthStore } from '../../../stores/auth'
import { useNotificationsStore } from '../../../stores/notifications'
import { Button, Input } from '../../../ui'
import { useCambiarPassword, useIdentidadPerfil, useQuitarFoto, useSubirFoto } from '../hooks/usePerfil'
import s from './PerfilPage.module.css'

// ─────────────────────────────────────────────────────────────────────────────
// Vista «Mi perfil»: datos del usuario logueado + tarjeta de la App del vecino
// (QR + link para instalarla desde el celular) + cambio voluntario de clave.
// Sin permiso de módulo (solo toca datos propios). Se entra desde el menú del
// avatar del shell (§14). Plan: PLAN_MI_PERFIL.md (2026-09-26).
// ─────────────────────────────────────────────────────────────────────────────

const ROL_LABEL: Record<number, string> = {
  1: 'Administrador', 2: 'Supervisor', 3: 'Atención', 4: 'Gestión', 5: 'Consultor',
}

// Catálogo `modulos` (código → nombre visible). Solo lectura, para que el
// usuario (y soporte) vean a qué accede. Un código nuevo cae al código pelado.
const MODULO_LABEL: Record<string, string> = {
  emergencias: 'Emergencias',
  reclamos: 'Reclamos',
  turnos: 'Turnos',
  entradas: 'Entradas',
  tramites: 'Trámites',
  ot_supervisor: 'OT · Supervisor',
  ot_agente: 'OT · Agente',
  ot_auditoria: 'OT · Auditoría',
  agenda: 'Agenda',
  padrones: 'Contactos (ciudadanos y empresas)',
  bi: 'Datos',
  encuestas: 'Encuestas',
  usuarios: 'Usuarios',
  admin_tablas: 'Maestros',
}

const FOTO_MIME_OK = ['image/png', 'image/jpeg']
const FOTO_MAX_BYTES = 2 * 1024 * 1024

function goInicio(e: React.MouseEvent) {
  e.preventDefault()
  const w = window.parent as Window & { shellNavigate?: (url: string) => void }
  if (w?.shellNavigate) w.shellNavigate('web-app/dist/index.html#/dashboard')
  else window.location.href = '/'
}

function iniciales(nombre: string | undefined): string {
  return (nombre ?? '').split(' ').slice(0, 2).map((w) => w[0] ?? '').join('').toUpperCase() || 'ZG'
}

export function PerfilPage() {
  const user = useAuthStore((st) => st.user)
  const refreshSession = useAuthStore((st) => st.refreshSession)

  // La sesión guardada puede estar vieja (foto, cargo, módulos): refrescar al
  // montar contra /auth/me. El store persiste → el shell vanilla se entera por
  // el evento `storage` y actualiza su topbar sin recargar.
  useEffect(() => { void refreshSession() }, [refreshSession])

  return (
    <div className={s.page}>
      <nav aria-label="Ruta de navegación" className={s.breadcrumb}>
        <a href="#" onClick={goInicio}>INICIO</a>
        <span className={s.bcSep}>›</span>
        <span className={s.bcCurrent}>Mi perfil</span>
      </nav>

      <div>
        <h1 className={s.title}>Mi perfil</h1>
        <p className={s.subtitle}>Tus datos en ZARIS, la app del vecino para compartir y la seguridad de tu cuenta.</p>
      </div>

      <div className={s.grid}>
        <section className={`${s.card} ${s.full}`} aria-labelledby="perfil-cabecera">
          <Cabecera />
        </section>

        <section className={s.card} aria-labelledby="perfil-app">
          <AppVecino />
        </section>

        <section className={s.card} aria-labelledby="perfil-seguridad">
          <Seguridad />
        </section>

        <section className={`${s.card} ${s.full}`} aria-labelledby="perfil-modulos">
          <div className={s.cardHead}>
            <span className={s.cardIcon}><LayoutGrid size={16} strokeWidth={1.5} /></span>
            <div>
              <div className={s.eyebrow}>Accesos</div>
              <h2 id="perfil-modulos" className={s.cardTitle}>Módulos a los que accedés</h2>
            </div>
          </div>
          {user?.modulos_permitidos?.length ? (
            <div className={s.modulos}>
              {user.modulos_permitidos.map((code) => (
                <span key={code} className={s.pill} title={code}>{MODULO_LABEL[code] ?? code}</span>
              ))}
            </div>
          ) : (
            <p className={`${s.text} ${s.muted}`}>Todavía no tenés módulos asignados.</p>
          )}
          <p className={`${s.text} ${s.muted}`}>
            Los accesos los define el administrador desde el módulo Usuarios. Si te falta alguno, pedíselo.
          </p>
        </section>
      </div>
    </div>
  )
}

/* ── Cabecera: avatar + datos + cambiar/quitar foto ───────────────────────── */
function Cabecera() {
  const user = useAuthStore((st) => st.user)
  const push = useNotificationsStore((st) => st.push)
  const subir = useSubirFoto()
  const quitar = useQuitarFoto()
  const fileRef = useRef<HTMLInputElement>(null)

  async function onArchivo(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (fileRef.current) fileRef.current.value = ''
    if (!file) return
    if (!FOTO_MIME_OK.includes(file.type)) {
      push({ kind: 'error', title: 'Formato no permitido', body: 'Subí una imagen PNG o JPG.' })
      return
    }
    if (file.size > FOTO_MAX_BYTES) {
      push({ kind: 'error', title: 'La imagen es muy pesada', body: 'El máximo es 2 MB.' })
      return
    }
    try {
      await subir.mutateAsync(file)
      push({ kind: 'success', title: 'Foto actualizada' })
    } catch (err) {
      push({ kind: 'error', title: 'No se pudo cambiar la foto', body: (err as Error).message })
    }
  }

  async function onQuitar() {
    try {
      await quitar.mutateAsync()
      push({ kind: 'success', title: 'Foto quitada' })
    } catch (err) {
      push({ kind: 'error', title: 'No se pudo quitar la foto', body: (err as Error).message })
    }
  }

  const ocupado = subir.isPending || quitar.isPending
  const rol = user ? (ROL_LABEL[user.nivel_acceso] ?? `Nivel ${user.nivel_acceso}`) : ''

  return (
    <div className={s.header}>
      <div className={s.avatar} aria-hidden="true">
        {user?.foto_url ? <img src={user.foto_url} alt="" /> : iniciales(user?.nombre)}
      </div>
      <div className={s.who}>
        <h2 id="perfil-cabecera" className={s.nombre}>{user?.nombre ?? '—'}</h2>
        <span className={s.email}>{user?.email ?? ''}</span>
        <div className={s.pills}>
          {rol && <span className={`${s.pill} ${s.pillStrong}`}>{rol}</span>}
          {user?.cargo_nombre && <span className={s.pill}>Cargo: {user.cargo_nombre}</span>}
          {user?.subarea_nombre && <span className={s.pill}>Gestión: {user.subarea_nombre}</span>}
        </div>
      </div>
      <div className={s.actions}>
        <input
          ref={fileRef}
          type="file"
          accept="image/png,image/jpeg"
          hidden
          onChange={onArchivo}
          data-testid="perfil-input-foto"
        />
        <Button
          type="button"
          icon={<Camera size={14} strokeWidth={1.5} />}
          disabled={ocupado}
          onClick={() => fileRef.current?.click()}
        >
          {subir.isPending ? 'Subiendo…' : 'Cambiar foto'}
        </Button>
        {user?.foto_url && (
          <Button
            type="button"
            variant="ghost"
            icon={<Trash2 size={14} strokeWidth={1.5} />}
            disabled={ocupado}
            onClick={onQuitar}
          >
            Quitar foto
          </Button>
        )}
      </div>
    </div>
  )
}

/* ── App del vecino: QR + link + pasos de instalación ─────────────────────── */
function AppVecino() {
  const identidad = useIdentidadPerfil()
  const push = useNotificationsStore((st) => st.push)
  const [copiado, setCopiado] = useState(false)
  const url = (identidad.data?.app_vecinos_url ?? '').trim()

  async function copiar() {
    try {
      await navigator.clipboard.writeText(url)
      setCopiado(true)
      setTimeout(() => setCopiado(false), 2000)
    } catch {
      push({ kind: 'error', title: 'No se pudo copiar', body: 'Seleccioná el link y copialo a mano.' })
    }
  }

  return (
    <>
      <div className={s.cardHead}>
        <span className={s.cardIcon}><Smartphone size={16} strokeWidth={1.5} /></span>
        <div>
          <div className={s.eyebrow}>App del vecino</div>
          <h2 id="perfil-app" className={s.cardTitle}>Portal del Ciudadano</h2>
        </div>
      </div>
      <p className={s.text}>
        Los vecinos la instalan desde el navegador del celular; no está en las tiendas.
        Mostrales este código o pasales el link.
      </p>

      {identidad.isLoading ? (
        <p className={`${s.text} ${s.muted}`}>Cargando…</p>
      ) : !url ? (
        <p className={`${s.text} ${s.muted}`}>
          La URL de la app del vecino no está configurada en este servidor. Pedile al administrador
          que la cargue (variable APP_VECINOS_FRONTEND_URL del backend).
        </p>
      ) : (
        <div className={s.appBody}>
          <div className={s.qrBox}>
            <QrCanvas value={url} size={220} />
          </div>
          <div className={s.appInfo}>
            <a className={s.link} href={url} target="_blank" rel="noopener noreferrer">
              {url}
              <ExternalLink size={13} strokeWidth={1.5} />
            </a>
            <div className={s.actions}>
              <Button
                type="button"
                icon={copiado ? <Check size={14} strokeWidth={1.5} /> : <Copy size={14} strokeWidth={1.5} />}
                onClick={copiar}
              >
                {copiado ? 'Copiado' : 'Copiar link'}
              </Button>
            </div>
            <ul className={s.steps}>
              <li><strong>Android:</strong><span>abrir el link en Chrome; la bienvenida ofrece «Instalar».</span></li>
              <li><strong>iPhone:</strong><span>abrir el link en Safari, tocar Compartir y luego «Agregar a inicio».</span></li>
            </ul>
          </div>
        </div>
      )}
      {/* Cuando exista la app de agentes (zaris-agentes) va una tarjeta gemela acá. */}
    </>
  )
}

function QrCanvas({ value, size }: { value: string; size: number }) {
  const ref = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    if (!ref.current || !value) return
    // Negro sobre blanco fijo (no tokens): un QR con colores del tema oscuro no se escanea.
    QRCode.toCanvas(ref.current, value, {
      width: size,
      margin: 1,
      errorCorrectionLevel: 'M',
      color: { dark: '#26251e', light: '#ffffff' },
    }).catch((e) => console.warn('QR render error:', e))
  }, [value, size])
  return <canvas ref={ref} className={s.qrCanvas} role="img" aria-label={`Código QR de ${value}`} />
}

/* ── Seguridad: cambio voluntario de contraseña ───────────────────────────── */
function Seguridad() {
  const push = useNotificationsStore((st) => st.push)
  const cambio = useCambiarPassword()
  const [actual, setActual] = useState('')
  const [nueva, setNueva] = useState('')
  const [repetir, setRepetir] = useState('')
  const [ver, setVer] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const nuevaOk = nueva.length >= 8 && nueva.length <= 100
  const coincide = repetir.length > 0 && nueva === repetir
  const distinta = nueva.length > 0 && nueva !== actual
  const valido = actual.length > 0 && nuevaOk && coincide && distinta

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!valido || cambio.isPending) return
    setError(null)
    try {
      await cambio.mutateAsync({ actual, nueva })
      setActual(''); setNueva(''); setRepetir('')
      push({ kind: 'success', title: 'Contraseña actualizada', body: 'Tu sesión sigue abierta.' })
    } catch (err) {
      // 401 = la actual no coincide · 422 = regla de la nueva. Se muestra el detail tal cual.
      setError((err as Error).message)
    }
  }

  const tipo = ver ? 'text' : 'password'

  return (
    <>
      <div className={s.cardHead}>
        <span className={s.cardIcon}><KeyRound size={16} strokeWidth={1.5} /></span>
        <div>
          <div className={s.eyebrow}>Seguridad</div>
          <h2 id="perfil-seguridad" className={s.cardTitle}>Cambiar mi contraseña</h2>
        </div>
      </div>
      <form className={s.form} onSubmit={onSubmit} autoComplete="off">
        <div className={s.field}>
          <label className={s.label} htmlFor="perfil-pass-actual">Contraseña actual</label>
          <Input
            id="perfil-pass-actual"
            type={tipo}
            value={actual}
            onChange={(e) => setActual(e.target.value)}
            autoComplete="current-password"
            required
          />
        </div>
        <div className={s.field}>
          <label className={s.label} htmlFor="perfil-pass-nueva">Contraseña nueva</label>
          <Input
            id="perfil-pass-nueva"
            type={tipo}
            value={nueva}
            onChange={(e) => setNueva(e.target.value)}
            autoComplete="new-password"
            required
          />
          <span className={`${s.hint} ${nueva.length === 0 ? '' : nuevaOk && distinta ? s.hintOk : s.hintErr}`}>
            {nueva.length === 0
              ? 'Mínimo 8 caracteres.'
              : !nuevaOk
                ? 'Mínimo 8 caracteres.'
                : !distinta
                  ? 'Tiene que ser distinta de la actual.'
                  : <><Check size={12} strokeWidth={1.5} /> Cumple el mínimo.</>}
          </span>
        </div>
        <div className={s.field}>
          <label className={s.label} htmlFor="perfil-pass-repetir">Repetir contraseña nueva</label>
          <Input
            id="perfil-pass-repetir"
            type={tipo}
            value={repetir}
            onChange={(e) => setRepetir(e.target.value)}
            autoComplete="new-password"
            required
          />
          <span className={`${s.hint} ${repetir.length === 0 ? '' : coincide ? s.hintOk : s.hintErr}`}>
            {repetir.length === 0 ? ' ' : coincide ? <><Check size={12} strokeWidth={1.5} /> Coinciden.</> : 'No coinciden.'}
          </span>
        </div>
        <label className={s.check}>
          <input type="checkbox" checked={ver} onChange={(e) => setVer(e.target.checked)} />
          {ver ? <EyeOff size={13} strokeWidth={1.5} /> : <Eye size={13} strokeWidth={1.5} />}
          Mostrar contraseñas
        </label>
        {error && <div className={s.error} role="alert">{error}</div>}
        <div className={s.actions}>
          <Button type="submit" variant="primary" icon={<User size={14} strokeWidth={1.5} />} disabled={!valido || cambio.isPending}>
            {cambio.isPending ? 'Guardando…' : 'Cambiar contraseña'}
          </Button>
          <span className={`${s.hint} ${s.muted}`}>No cierra tu sesión.</span>
        </div>
      </form>
    </>
  )
}
