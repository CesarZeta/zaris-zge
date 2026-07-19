import { useEffect, useRef, useState } from 'react'
import { Upload, X, Check, Copy, ExternalLink } from 'lucide-react'
import { useIdentidad, useUpdateIdentidad } from '../hooks/useConfig'
import { crearLogoUploadUrl, type IdentidadValues } from '../api/configApi'

/**
 * Base pública del producto (donde vive el shell vanilla + frontend/).
 * En iframe del shell, usamos el origin+path del padre (prod: zge.zaris.com.ar/...).
 * Standalone dev (localhost:5173) cae al shell vanilla local (8080).
 */
function basePublica(): string {
  if (typeof window !== 'undefined' && window.self !== window.top) {
    try {
      const loc = window.parent.location
      const path = loc.pathname.replace(/[^/]*$/, '') // recorta index.html
      return `${loc.origin}${path}`.replace(/\/$/, '')
    } catch {
      /* cross-origin: cae al fallback */
    }
  }
  if (typeof window !== 'undefined' && window.location.hostname === 'localhost' && window.location.port === '5173') {
    return 'http://localhost:8080'
  }
  return typeof window !== 'undefined' ? window.location.origin : ''
}

const MIME_OK = ['image/png', 'image/jpeg', 'image/webp', 'image/svg+xml']
const MAX_BYTES = 2 * 1024 * 1024
// '' = color sin definir (la PWA usa su default); si hay valor debe ser #RRGGBB.
const HEX_RE = /^#[0-9a-fA-F]{6}$/
const hexValido = (v: string) => v === '' || HEX_RE.test(v)

interface FormState {
  municipio_nombre: string
  municipio_logo_url: string
  municipio_descripcion: string
  municipio_color_primary: string
  municipio_color_accent: string
}

function toForm(d: IdentidadValues | undefined): FormState {
  return {
    municipio_nombre: d?.municipio_nombre ?? '',
    municipio_logo_url: d?.municipio_logo_url ?? '',
    municipio_descripcion: d?.municipio_descripcion ?? '',
    municipio_color_primary: d?.municipio_color_primary ?? '',
    municipio_color_accent: d?.municipio_color_accent ?? '',
  }
}

export function IdentidadView() {
  const identidad = useIdentidad()
  const update = useUpdateIdentidad()
  const [form, setForm] = useState<FormState>(toForm(undefined))
  const [subiendo, setSubiendo] = useState(false)
  const [errorUpload, setErrorUpload] = useState<string | null>(null)
  const [okMsg, setOkMsg] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  // Hidratar el form cuando llega el detalle del backend
  useEffect(() => {
    if (identidad.data) setForm(toForm(identidad.data))
  }, [identidad.data])

  const dirty = identidad.data
    && (form.municipio_nombre !== identidad.data.municipio_nombre
      || form.municipio_logo_url !== identidad.data.municipio_logo_url
      || form.municipio_descripcion !== identidad.data.municipio_descripcion
      || form.municipio_color_primary !== identidad.data.municipio_color_primary
      || form.municipio_color_accent !== identidad.data.municipio_color_accent)
  const coloresValidos = hexValido(form.municipio_color_primary) && hexValido(form.municipio_color_accent)

  async function handleArchivo(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setErrorUpload(null)
    if (!MIME_OK.includes(file.type)) {
      setErrorUpload(`Tipo no permitido. Acepta: PNG, JPG, WebP, SVG.`)
      return
    }
    if (file.size > MAX_BYTES) {
      setErrorUpload(`Excede 2MB (${(file.size / 1024 / 1024).toFixed(2)}MB).`)
      return
    }
    setSubiendo(true)
    try {
      const signed = await crearLogoUploadUrl(file.type, file.size)
      const putRes = await fetch(signed.upload_url, {
        method: 'PUT',
        headers: { 'Content-Type': file.type, 'x-upsert': 'true' },
        body: file,
      })
      if (!putRes.ok) {
        const txt = await putRes.text()
        throw new Error(`Storage PUT ${putRes.status}: ${txt}`)
      }
      // Persistir la public_url en configuracion_general
      await update.mutateAsync({ municipio_logo_url: signed.public_url })
      setForm((f) => ({ ...f, municipio_logo_url: signed.public_url }))
      setOkMsg('Logo actualizado.')
      setTimeout(() => setOkMsg(null), 3000)
    } catch (err) {
      setErrorUpload(err instanceof Error ? err.message : 'Error subiendo el logo')
    } finally {
      setSubiendo(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  async function handleGuardar() {
    setOkMsg(null)
    try {
      await update.mutateAsync({
        municipio_nombre: form.municipio_nombre.trim(),
        municipio_logo_url: form.municipio_logo_url.trim(),
        municipio_descripcion: form.municipio_descripcion.trim(),
        municipio_color_primary: form.municipio_color_primary.trim(),
        municipio_color_accent: form.municipio_color_accent.trim(),
      })
      setOkMsg('Cambios guardados.')
      setTimeout(() => setOkMsg(null), 3000)
    } catch (err) {
      setErrorUpload(err instanceof Error ? err.message : 'Error guardando')
    }
  }

  async function handleQuitarLogo() {
    try {
      await update.mutateAsync({ municipio_logo_url: '' })
      setForm((f) => ({ ...f, municipio_logo_url: '' }))
      setOkMsg('Logo eliminado.')
      setTimeout(() => setOkMsg(null), 3000)
    } catch (err) {
      setErrorUpload(err instanceof Error ? err.message : 'Error quitando logo')
    }
  }

  if (identidad.isLoading) {
    return <div style={{ color: 'var(--fg-3)', fontSize: '0.86rem' }}>Cargando…</div>
  }
  if (identidad.isError) {
    return <div style={{ color: 'var(--color-error)', fontSize: '0.86rem' }}>Error: {(identidad.error as Error).message}</div>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <p style={{ fontSize: '0.86rem', color: 'var(--fg-3)' }}>
        Configura el nombre de la aplicación y la identidad del municipio que se muestra en el topbar.
        Los cambios se aplican al recargar la app.
      </p>

      {okMsg && (
        <div style={notifStyle('success')}>
          <Check size={16} /> {okMsg}
        </div>
      )}
      {errorUpload && (
        <div style={notifStyle('error')}>
          <X size={16} /> {errorUpload}
          <button onClick={() => setErrorUpload(null)} style={notifCloseStyle}>×</button>
        </div>
      )}

      {/* Preview del topbar */}
      <div style={previewWrap}>
        <div style={previewLabel}>Vista previa</div>
        <div style={previewBar}>
          <span style={previewZaris}>ZARIS</span>
          <span style={previewApp}>GESTION ESTADO</span>
          <span style={previewSep}></span>
          {form.municipio_logo_url ? (
            <img src={form.municipio_logo_url} alt="" style={previewLogo} onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }} />
          ) : null}
          <span style={previewMuni}>{form.municipio_nombre || 'MUNICIPALIDAD'}</span>
        </div>
      </div>

      <div style={fieldGroup}>
        <label style={labelStyle}>Nombre del municipio</label>
        <input
          type="text"
          value={form.municipio_nombre}
          maxLength={120}
          onChange={(e) => setForm((f) => ({ ...f, municipio_nombre: e.target.value }))}
          style={inputStyle}
          placeholder="MUNICIPALIDAD DE SAN ANDRÉS"
        />
        <span style={hintStyle}>Aparece a la derecha del logo ZARIS, después del separador.</span>
      </div>

      <div style={fieldGroup}>
        <label style={labelStyle}>Logo del municipio</label>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={logoPreviewStyle}>
            {form.municipio_logo_url ? (
              <img src={form.municipio_logo_url} alt="" style={logoPreviewImg} onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }} />
            ) : (
              <span style={{ fontSize: '0.78rem', color: 'var(--fg-3)' }}>sin logo</span>
            )}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <input
              ref={fileRef}
              type="file"
              accept={MIME_OK.join(',')}
              onChange={handleArchivo}
              hidden
            />
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={subiendo}
              style={btnStyle('primary')}
            >
              <Upload size={14} />
              {subiendo ? 'Subiendo…' : (form.municipio_logo_url ? 'Reemplazar logo' : 'Subir logo')}
            </button>
            {form.municipio_logo_url && (
              <button type="button" onClick={handleQuitarLogo} style={btnStyle('ghost')}>
                Quitar logo
              </button>
            )}
            <span style={hintStyle}>PNG, JPG, WebP o SVG. Máx 2MB. Ideal: cuadrado.</span>
          </div>
        </div>
      </div>

      {/* Marca de la App Vecinos (PWA) — unificado acá desde Sistema (2026-07-16) */}
      <div style={enlacesWrap}>
        <div style={labelStyle}>App Vecinos (PWA) — marca y bienvenida</div>
        <span style={hintStyle}>
          Colores y texto que ven los vecinos en la app pública ({'vecinos.zaris.com.ar'}).
          El color primario pinta la barra superior, la barra inferior y el marco de la app.
        </span>
        <div style={{ ...fieldGroup, marginTop: 8 }}>
          <label style={labelStyle}>Texto de bienvenida</label>
          <input
            type="text"
            value={form.municipio_descripcion}
            maxLength={300}
            onChange={(e) => setForm((f) => ({ ...f, municipio_descripcion: e.target.value }))}
            style={inputStyle}
            placeholder="Servicio oficial de atención al vecino"
          />
          <span style={hintStyle}>Frase corta de la pantalla de inicio de sesión de la app.</span>
        </div>
        <div style={{ display: 'flex', gap: 28, flexWrap: 'wrap', marginTop: 8 }}>
          <ColorCampo
            label="Color primario"
            hint="Botones, barras y marco de la app."
            value={form.municipio_color_primary}
            onChange={(v) => setForm((f) => ({ ...f, municipio_color_primary: v }))}
          />
          <ColorCampo
            label="Color de acento"
            hint="Badges y links (opcional)."
            value={form.municipio_color_accent}
            onChange={(v) => setForm((f) => ({ ...f, municipio_color_accent: v }))}
          />
        </div>
      </div>

      {/* Enlaces públicos del municipio (solo lectura) */}
      <EnlacesPublicos slug={identidad.data?.municipio_slug ?? null} />

      <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
        <button
          type="button"
          onClick={handleGuardar}
          disabled={!dirty || !coloresValidos || update.isPending}
          style={btnStyle('primary', !dirty || !coloresValidos || update.isPending)}
          title={coloresValidos ? undefined : 'Hay un color con formato inválido (usar #RRGGBB)'}
        >
          {update.isPending ? 'Guardando…' : 'Guardar cambios'}
        </button>
        {dirty && (
          <button
            type="button"
            onClick={() => identidad.data && setForm(toForm(identidad.data))}
            style={btnStyle('ghost')}
          >
            Descartar
          </button>
        )}
      </div>
    </div>
  )
}

// ── Color de marca (picker + hex editable) ───────────────────────
function ColorCampo({ label, hint, value, onChange }: {
  label: string
  hint: string
  value: string
  onChange: (v: string) => void
}) {
  const valido = hexValido(value)
  return (
    <div style={fieldGroup}>
      <label style={labelStyle}>{label}</label>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <input
          type="color"
          value={valido && value !== '' ? value : '#888888'}
          onChange={(e) => onChange(e.target.value)}
          style={{ width: 36, height: 32, padding: 2, border: '1px solid var(--border-primary)', borderRadius: 6, background: 'var(--surface-100)', cursor: 'pointer' }}
          title="Elegir color"
        />
        <input
          type="text"
          value={value}
          maxLength={7}
          onChange={(e) => onChange(e.target.value.trim())}
          placeholder="sin definir"
          style={{
            ...inputStyle,
            maxWidth: 110,
            fontFamily: 'var(--font-mono)',
            borderColor: valido ? 'var(--border-primary)' : 'var(--color-error)',
          }}
        />
        {value !== '' && (
          <button type="button" onClick={() => onChange('')} style={btnStyle('ghost')} title="Quitar color (la app usa su color por defecto)">
            Quitar
          </button>
        )}
      </div>
      <span style={{ ...hintStyle, color: valido ? 'var(--fg-3)' : 'var(--color-error)' }}>
        {valido ? hint : 'Formato inválido: usar #RRGGBB (ej. #1f8a65).'}
      </span>
    </div>
  )
}

// ── Enlaces públicos del municipio ───────────────────────────────
interface EnlaceDef {
  titulo: string
  descripcion: string
  /** Ruta relativa a la base pública, con {slug} interpolado. */
  ruta: (slug: string) => string
}

const ENLACES: EnlaceDef[] = [
  {
    titulo: 'Alta de vecinos',
    descripcion: 'El vecino crea su cuenta desde el celular. Compartí este enlace en la web del municipio, redes o QR.',
    ruta: (slug) => `/frontend/alta-vecino.html?m=${encodeURIComponent(slug)}`,
  },
]

function EnlacesPublicos({ slug }: { slug: string | null }) {
  const base = basePublica()
  return (
    <div style={enlacesWrap}>
      <div style={labelStyle}>Enlaces públicos del municipio</div>
      <span style={hintStyle}>
        URLs que pueden compartirse con los vecinos. Cambian según el código del municipio.
      </span>
      {!slug ? (
        <div style={{ ...notifStyle('error'), marginTop: 4 }}>
          <X size={16} /> No hay un código de municipio configurado. Asigná uno en Maestros → Municipios
          (campo "código corto") para habilitar los enlaces públicos.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 4 }}>
          {ENLACES.map((e) => (
            <EnlacePublico key={e.titulo} def={e} url={`${base}${e.ruta(slug)}`} />
          ))}
        </div>
      )}
    </div>
  )
}

function EnlacePublico({ def, url }: { def: EnlaceDef; url: string }) {
  const [copiado, setCopiado] = useState(false)

  async function copiar() {
    try {
      await navigator.clipboard.writeText(url)
    } catch {
      // fallback para contextos sin clipboard API
      const ta = document.createElement('textarea')
      ta.value = url
      document.body.appendChild(ta)
      ta.select()
      try { document.execCommand('copy') } catch { /* noop */ }
      document.body.removeChild(ta)
    }
    setCopiado(true)
    setTimeout(() => setCopiado(false), 2000)
  }

  return (
    <div style={enlaceCard}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
        <span style={enlaceTitulo}>{def.titulo}</span>
        <span style={enlaceDesc}>{def.descripcion}</span>
        <code style={enlaceUrl} title={url}>{url}</code>
      </div>
      <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
        <button type="button" onClick={copiar} style={btnStyle(copiado ? 'primary' : 'ghost')} title="Copiar enlace">
          {copiado ? <Check size={14} /> : <Copy size={14} />}
          {copiado ? 'Copiado' : 'Copiar'}
        </button>
        <a href={url} target="_blank" rel="noopener noreferrer" style={{ ...btnStyle('ghost'), textDecoration: 'none' }} title="Abrir en pestaña nueva">
          <ExternalLink size={14} />
          Abrir
        </a>
      </div>
    </div>
  )
}

const enlacesWrap: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 6,
  padding: 14,
  background: 'var(--surface-100)',
  border: '1px solid var(--border-primary)',
  borderRadius: 10,
}
const enlaceCard: React.CSSProperties = {
  display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12,
  padding: '12px 14px',
  background: 'var(--surface-300)',
  border: '1px solid var(--border-primary)',
  borderRadius: 8,
}
const enlaceTitulo: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.88rem', fontWeight: 600, color: 'var(--fg-1)',
}
const enlaceDesc: React.CSSProperties = {
  fontSize: '0.78rem', color: 'var(--fg-3)', lineHeight: 1.4,
}
const enlaceUrl: React.CSSProperties = {
  fontFamily: 'var(--font-mono)', fontSize: '0.74rem', color: 'var(--fg-2)',
  marginTop: 2, wordBreak: 'break-all',
}

// ── styles ───────────────────────────────────────────────────────
const fieldGroup: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 6,
}
const labelStyle: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: '0.84rem', fontWeight: 600, color: 'var(--fg-1)',
}
const inputStyle: React.CSSProperties = {
  padding: '8px 12px',
  fontSize: '0.92rem',
  fontFamily: 'var(--font-display)',
  background: 'var(--surface-100)',
  border: '1px solid var(--border-primary)',
  borderRadius: 8,
  color: 'var(--fg-1)',
  outline: 'none',
  maxWidth: 480,
}
const hintStyle: React.CSSProperties = {
  fontSize: '0.78rem', color: 'var(--fg-3)',
}
const logoPreviewStyle: React.CSSProperties = {
  width: 80, height: 80,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  background: 'var(--surface-100)',
  border: '1px dashed var(--border-medium)',
  borderRadius: 8,
  overflow: 'hidden',
}
const logoPreviewImg: React.CSSProperties = {
  width: '100%', height: '100%', objectFit: 'contain',
}
function btnStyle(variant: 'primary' | 'ghost', disabled = false): React.CSSProperties {
  const base: React.CSSProperties = {
    display: 'inline-flex', alignItems: 'center', gap: 6,
    padding: '7px 14px',
    fontFamily: 'var(--font-display)', fontSize: '0.86rem', fontWeight: 600,
    borderRadius: 8,
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.5 : 1,
    border: '1px solid transparent',
    transition: 'background 150ms ease',
  }
  if (variant === 'primary') {
    // #fff fijo a proposito: --zaris-orange no cambia entre temas (caso avatar §13).
    return { ...base, background: 'var(--zaris-orange)', color: '#fff', borderColor: 'var(--zaris-orange)' }
  }
  return { ...base, background: 'transparent', color: 'var(--fg-2)', borderColor: 'var(--border-primary)' }
}
function notifStyle(kind: 'success' | 'error'): React.CSSProperties {
  return {
    display: 'flex', alignItems: 'center', gap: 8,
    padding: '8px 12px',
    fontSize: '0.84rem',
    background: kind === 'success' ? 'rgba(31,138,101,0.1)' : 'rgba(207,45,86,0.08)',
    color: kind === 'success' ? 'var(--color-success)' : 'var(--color-error)',
    border: `1px solid ${kind === 'success' ? 'rgba(31,138,101,0.3)' : 'rgba(207,45,86,0.3)'}`,
    borderRadius: 8,
    position: 'relative',
  }
}
const notifCloseStyle: React.CSSProperties = {
  marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer',
  color: 'inherit', fontSize: '1.1rem', padding: '0 4px',
}
const previewWrap: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 6,
  padding: 14,
  background: 'var(--surface-100)',
  border: '1px solid var(--border-primary)',
  borderRadius: 10,
}
const previewLabel: React.CSSProperties = {
  fontSize: '0.74rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--fg-3)',
}
const previewBar: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 24,
  padding: '12px 16px',
  background: 'rgba(242,241,237,.88)',
  border: '1px solid var(--border-primary)',
  borderRadius: 8,
  minHeight: 48,
}
const previewZaris: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: 17, fontWeight: 500,
  letterSpacing: '-0.8px', color: 'var(--fg-1)',
}
const previewApp: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: 11, fontWeight: 600,
  letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--fg-3)',
  paddingLeft: 8, borderLeft: '1px solid var(--border-primary)',
}
const previewSep: React.CSSProperties = {
  width: 1, height: 28, background: 'var(--border-medium)',
}
const previewLogo: React.CSSProperties = {
  width: 24, height: 24, objectFit: 'contain', borderRadius: 4,
}
const previewMuni: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: 12, fontWeight: 600,
  letterSpacing: '0.04em', textTransform: 'uppercase', color: 'var(--fg-2)',
}
