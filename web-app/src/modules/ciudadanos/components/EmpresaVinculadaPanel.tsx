import { useEffect, useState } from 'react'
import { useNotificationsStore } from '../../../stores/notifications'
import { useActividades, useCrearEmpresaYVincular, useTiposRepresentacion } from '../hooks/useCiudadanos'
import { soloDigitos, validarCuilCuit, validarEmail, validarTelefono } from '../lib/cuilUtils'
import type { EmpresaVinculada } from '../types/ciudadano'

interface EmpresaForm {
  cuit: string
  nombre: string
  id_actividad: string
  id_tipo_representacion: string
  calle: string
  localidad: string
  provincia: string
  telefono: string
  email: string
  observaciones: string
}

const emptyEmpresa: EmpresaForm = {
  cuit: '', nombre: '', id_actividad: '', id_tipo_representacion: '',
  calle: '', localidad: '', provincia: '', telefono: '', email: '', observaciones: '',
}

interface Props {
  idCiudadano: number
  readonly: boolean
  modoAlta: boolean
  empresa?: EmpresaVinculada
  onBusy: (busy: boolean) => void
}

export function EmpresaVinculadaPanel({ idCiudadano, readonly, modoAlta, empresa, onBusy }: Props) {
  const push = useNotificationsStore((s) => s.push)
  const actividades = useActividades()
  const tiposRep = useTiposRepresentacion()
  const crear = useCrearEmpresaYVincular()

  const [form, setForm] = useState<EmpresaForm>(emptyEmpresa)
  const [errores, setErrores] = useState<Record<string, string>>({})

  useEffect(() => {
    if (modoAlta) {
      setForm(emptyEmpresa)
    } else if (empresa) {
      setForm({
        cuit: empresa.cuit || '',
        nombre: empresa.nombre || '',
        id_actividad: String(empresa.id_actividad || ''),
        id_tipo_representacion: String(empresa.id_tipo_representacion || ''),
        calle: empresa.calle || '',
        localidad: empresa.localidad || '',
        provincia: empresa.provincia || '',
        telefono: empresa.telefono || '',
        email: empresa.email || '',
        observaciones: '',
      })
    }
  }, [modoAlta, empresa])

  useEffect(() => { onBusy(crear.isPending) }, [crear.isPending, onBusy])

  const verSolamente = readonly || !modoAlta

  function set<K extends keyof EmpresaForm>(key: K, value: EmpresaForm[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
    if (errores[key as string]) setErrores((prev) => { const n = { ...prev }; delete n[key as string]; return n })
  }

  function validar(): boolean {
    const errs: Record<string, string> = {}
    if (!form.id_tipo_representacion) errs.id_tipo_representacion = 'Requerido'
    if (!form.cuit) errs.cuit = 'Requerido'
    else {
      const r = validarCuilCuit(form.cuit)
      if (!r.valido) errs.cuit = r.error
    }
    if (!form.nombre.trim()) errs.nombre = 'Requerido'
    if (!form.id_actividad) errs.id_actividad = 'Requerido'
    if (!form.calle.trim()) errs.calle = 'Requerido'
    if (!form.localidad.trim()) errs.localidad = 'Requerido'
    if (!form.provincia.trim()) errs.provincia = 'Requerido'
    if (!form.telefono.trim()) errs.telefono = 'Requerido'
    else {
      const t = validarTelefono(form.telefono)
      if (!t.valido) errs.telefono = t.error
    }
    if (!form.email.trim()) errs.email = 'Requerido'
    else if (!validarEmail(form.email)) errs.email = 'Formato invalido'

    setErrores(errs)
    return Object.keys(errs).length === 0
  }

  async function guardar() {
    if (!validar()) {
      push({ kind: 'error', title: 'Revisa los campos de la empresa' })
      return
    }
    const cuitFmt = validarCuilCuit(form.cuit).formateado || form.cuit
    try {
      const emp = await crear.mutateAsync({
        empresa: {
          cuit: cuitFmt,
          nombre: form.nombre.trim(),
          id_actividad: Number(form.id_actividad),
          calle: form.calle.trim() || null,
          localidad: form.localidad.trim() || null,
          provincia: form.provincia.trim() || null,
          telefono: soloDigitos(form.telefono),
          email: form.email.trim().toLowerCase(),
          observaciones: form.observaciones.trim() || null,
        },
        id_ciudadano: idCiudadano,
        id_tipo_representacion: Number(form.id_tipo_representacion),
      })
      push({ kind: 'success', title: 'Empresa vinculada', body: `ID empresa: ${emp.id_empresa}` })
      // Tras guardar, cambiar a modo "ya existe" reseteando el form (queryClient invalida el listado)
      setForm(emptyEmpresa)
    } catch (err) {
      push({ kind: 'error', title: 'Error al vincular empresa', body: (err as Error).message })
    }
  }

  return (
    <section style={cardStyle}>
      <header style={cardHeaderStyle}>
        <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 'var(--size-title-sm)', fontWeight: 500, color: 'var(--fg-1)' }}>
          {modoAlta ? 'Alta de empresa vinculada' : 'Empresa representada'}
        </h2>
        <span style={{
          display: 'inline-flex', alignItems: 'center', padding: '4px 12px',
          borderRadius: 'var(--radius-pill)', fontSize: 'var(--size-caption)',
          fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em',
          background: 'rgba(96,165,200,.14)', color: '#3a6f8f',
        }}>
          {modoAlta ? 'Flujo desde ciudadano' : 'Solo lectura'}
        </span>
      </header>

      <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <Row cols="1fr 1fr">
          <Field label="Tipo de Representacion" required error={errores.id_tipo_representacion}>
            <select
              value={form.id_tipo_representacion}
              onChange={(e) => set('id_tipo_representacion', e.target.value)}
              disabled={verSolamente}
              style={inputStyle(verSolamente)}
            >
              <option value="">Seleccionar...</option>
              {(tiposRep.data ?? []).map((t) => (
                <option key={t.id} value={t.id}>{t.tipo}</option>
              ))}
            </select>
          </Field>
          <Field label="CUIT" required error={errores.cuit}>
            <input
              type="text"
              value={form.cuit}
              onChange={(e) => set('cuit', e.target.value)}
              disabled={verSolamente}
              maxLength={13}
              placeholder="XX-XXXXXXXX-X"
              style={inputStyle(verSolamente)}
            />
          </Field>
        </Row>
        <Row cols="1fr 1fr">
          <Field label="Nombre de Empresa" required error={errores.nombre}>
            <input
              type="text"
              value={form.nombre}
              onChange={(e) => set('nombre', e.target.value)}
              disabled={verSolamente}
              maxLength={100}
              placeholder="Razon social"
              style={inputStyle(verSolamente)}
            />
          </Field>
          <Field label="Actividad (CLAE)" required error={errores.id_actividad}>
            <select
              value={form.id_actividad}
              onChange={(e) => set('id_actividad', e.target.value)}
              disabled={verSolamente}
              style={inputStyle(verSolamente)}
            >
              <option value="">Seleccionar...</option>
              {(actividades.data ?? []).map((a) => (
                <option key={a.id} value={a.id}>{a.codigo_clae} — {a.descripcion}</option>
              ))}
            </select>
          </Field>
        </Row>

        <SubTitle>Domicilio empresa</SubTitle>
        <Row cols="1fr 1fr">
          <Field label="Calle y Altura" required error={errores.calle}>
            <input
              type="text"
              value={form.calle}
              onChange={(e) => set('calle', e.target.value)}
              disabled={verSolamente}
              maxLength={200}
              style={inputStyle(verSolamente)}
            />
          </Field>
          <Field label="Localidad" required error={errores.localidad}>
            <input
              type="text"
              value={form.localidad}
              onChange={(e) => set('localidad', e.target.value)}
              disabled={verSolamente}
              maxLength={100}
              style={inputStyle(verSolamente)}
            />
          </Field>
        </Row>
        <Row cols="1fr 1fr 1fr">
          <Field label="Provincia" required error={errores.provincia}>
            <input
              type="text"
              value={form.provincia}
              onChange={(e) => set('provincia', e.target.value)}
              disabled={verSolamente}
              maxLength={100}
              style={inputStyle(verSolamente)}
            />
          </Field>
          <Field label="Telefono" required error={errores.telefono}>
            <input
              type="text"
              value={form.telefono}
              onChange={(e) => set('telefono', e.target.value.replace(/\D/g, '').slice(0, 10))}
              disabled={verSolamente}
              maxLength={10}
              placeholder="10 digitos"
              style={inputStyle(verSolamente)}
            />
          </Field>
          <Field label="Email" required error={errores.email}>
            <input
              type="email"
              value={form.email}
              onChange={(e) => set('email', e.target.value)}
              disabled={verSolamente}
              maxLength={150}
              style={inputStyle(verSolamente)}
            />
          </Field>
        </Row>

        <Field label="" hint={modoAlta ? `${form.observaciones.length}/500 caracteres` : undefined}>
          <textarea
            value={form.observaciones}
            onChange={(e) => set('observaciones', e.target.value)}
            disabled={verSolamente}
            maxLength={500}
            rows={2}
            placeholder="Observaciones (max. 500)"
            style={{ ...inputStyle(verSolamente), resize: 'vertical', fontFamily: 'var(--font-display)' }}
          />
        </Field>
      </div>

      {modoAlta && !readonly && (
        <footer style={cardFooterStyle}>
          <button onClick={guardar} disabled={crear.isPending} style={btnAccent}>
            {crear.isPending ? 'Guardando...' : 'Guardar empresa'}
          </button>
        </footer>
      )}
    </section>
  )
}

// ── Componentes internos ──
function SubTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 style={{
      margin: 0, fontFamily: 'var(--font-display)',
      fontSize: 'var(--size-caption)', fontWeight: 700,
      textTransform: 'uppercase', letterSpacing: '0.07em',
      color: 'var(--fg-3)', borderBottom: '1px solid var(--border-primary)',
      paddingBottom: 4,
    }}>{children}</h3>
  )
}

function Row({ cols, children }: { cols: string; children: React.ReactNode }) {
  return <div style={{ display: 'grid', gridTemplateColumns: cols, gap: 12 }}>{children}</div>
}

function Field({ label, required, error, hint, children }: {
  label: string
  required?: boolean
  error?: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      {label && (
        <label style={{ fontSize: 'var(--size-caption)', fontWeight: 600, color: 'var(--fg-2)' }}>
          {label}{required && <span style={{ color: 'var(--zaris-orange)', marginLeft: 4 }}>*</span>}
        </label>
      )}
      {children}
      {error && <div style={{ fontSize: 'var(--size-caption)', color: 'var(--color-error)' }}>{error}</div>}
      {hint && !error && <div style={{ fontSize: 'var(--size-caption)', color: 'var(--fg-3)' }}>{hint}</div>}
    </div>
  )
}

function inputStyle(readonly: boolean): React.CSSProperties {
  return {
    width: '100%',
    padding: '9px 12px',
    fontFamily: 'var(--font-display)',
    fontSize: 'var(--size-ui)',
    color: readonly ? 'var(--fg-2)' : 'var(--fg-1)',
    background: readonly ? 'var(--surface-300)' : 'var(--surface-100)',
    border: '1px solid var(--border-primary)',
    borderRadius: 'var(--radius-lg)',
    outline: 'none',
    cursor: readonly ? 'not-allowed' : 'text',
  }
}

const cardStyle: React.CSSProperties = {
  background: 'var(--surface-100)',
  border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-xl)',
  boxShadow: 'var(--shadow-ambient)',
  overflow: 'hidden',
  marginTop: 20,
}

const cardHeaderStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '14px 20px',
  borderBottom: '1px solid var(--border-primary)',
  background: 'var(--surface-200)',
}

const cardFooterStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'flex-end',
  gap: 10,
  padding: '14px 20px',
  borderTop: '1px solid var(--border-primary)',
  background: 'var(--surface-200)',
}

const btnAccent: React.CSSProperties = {
  padding: '10px 18px',
  background: 'var(--zaris-orange)',
  color: 'var(--zaris-cream)',
  border: 'none',
  borderRadius: 'var(--radius-lg)',
  fontFamily: 'var(--font-display)',
  fontSize: 'var(--size-btn)',
  fontWeight: 500,
  cursor: 'pointer',
}
