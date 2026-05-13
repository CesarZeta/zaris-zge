import { useEffect, useRef, useState } from 'react'
import { Upload, X, Check } from 'lucide-react'
import { useIdentidad, useUpdateIdentidad } from '../hooks/useConfig'
import { crearLogoUploadUrl, type IdentidadValues } from '../api/configApi'

const MIME_OK = ['image/png', 'image/jpeg', 'image/webp', 'image/svg+xml']
const MAX_BYTES = 2 * 1024 * 1024

interface FormState {
  app_nombre: string
  municipio_nombre: string
  municipio_logo_url: string
}

function toForm(d: IdentidadValues | undefined): FormState {
  return {
    app_nombre: d?.app_nombre ?? '',
    municipio_nombre: d?.municipio_nombre ?? '',
    municipio_logo_url: d?.municipio_logo_url ?? '',
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
    && (form.app_nombre !== identidad.data.app_nombre
      || form.municipio_nombre !== identidad.data.municipio_nombre
      || form.municipio_logo_url !== identidad.data.municipio_logo_url)

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
        app_nombre: form.app_nombre.trim(),
        municipio_nombre: form.municipio_nombre.trim(),
        municipio_logo_url: form.municipio_logo_url.trim(),
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
          <span style={previewApp}>{form.app_nombre || 'GESTION ESTADO'}</span>
          <span style={previewSep}></span>
          {form.municipio_logo_url ? (
            <img src={form.municipio_logo_url} alt="" style={previewLogo} onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }} />
          ) : null}
          <span style={previewMuni}>{form.municipio_nombre || 'MUNICIPALIDAD'}</span>
        </div>
      </div>

      <div style={fieldGroup}>
        <label style={labelStyle}>Nombre de la aplicación</label>
        <input
          type="text"
          value={form.app_nombre}
          maxLength={80}
          onChange={(e) => setForm((f) => ({ ...f, app_nombre: e.target.value }))}
          style={inputStyle}
          placeholder="GESTION ESTADO"
        />
        <span style={hintStyle}>Aparece al lado del logo ZARIS. Mayúsculas recomendadas.</span>
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

      <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
        <button
          type="button"
          onClick={handleGuardar}
          disabled={!dirty || update.isPending}
          style={btnStyle('primary', !dirty || update.isPending)}
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
