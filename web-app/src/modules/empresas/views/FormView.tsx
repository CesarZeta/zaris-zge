import { useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { useNotificationsStore } from '../../../stores/notifications'
import {
  useActividades,
  useCrearEmpresa,
  useEmpresa,
  useModificarEmpresa,
  useTiposRepresentacion,
  verificarDuplicadoEmpresa,
} from '../hooks/useEmpresas'
import { EmpresaForm } from '../components/EmpresaForm'
import { CiudadanoSearch } from '../../agenda/components/CiudadanoSearch'
import type { CiudadanoMinimo } from '../../agenda/types/agenda'
import { soloDigitos, validarCuilCuit, validarEmail, validarTelefono } from '../lib/cuitUtils'
import type { EmpresaCreate } from '../types/empresa'

type Modo = 'new' | 'edit' | 'view'

export interface EmpresaFormState {
  cuit: string
  nombre: string
  id_actividad: string
  calle: string
  localidad: string
  provincia: string
  latitud: number | null
  longitud: number | null
  telefono: string
  email: string
  observaciones: string
}

const emptyForm: EmpresaFormState = {
  cuit: '', nombre: '', id_actividad: '',
  calle: '', localidad: '', provincia: '',
  latitud: null, longitud: null,
  telefono: '', email: '', observaciones: '',
}

export function FormView() {
  const navigate = useNavigate()
  const location = useLocation()
  const params = useParams<{ id?: string }>()
  const push = useNotificationsStore((s) => s.push)

  const modo: Modo = useMemo(() => {
    if (location.pathname.endsWith('/nuevo')) return 'new'
    if (location.pathname.endsWith('/editar')) return 'edit'
    return 'view'
  }, [location.pathname])

  const id = params.id ? Number(params.id) : null
  const readonly = modo === 'view'

  const detalle = useEmpresa(modo === 'new' ? null : id)
  const actividades = useActividades()
  const tiposRep = useTiposRepresentacion()
  const crear = useCrearEmpresa()
  const modificar = useModificarEmpresa(id)

  const [form, setForm] = useState<EmpresaFormState>(emptyForm)
  const [errores, setErrores] = useState<Record<string, string>>({})
  // Representante: toda empresa nace con un vecino (BUC §2). Obligatorio solo en alta.
  const [representante, setRepresentante] = useState<CiudadanoMinimo | null>(null)
  const [idTipoRep, setIdTipoRep] = useState<string>('1')

  // Hidratar form en edit/view
  useEffect(() => {
    if (modo === 'new') {
      setForm(emptyForm)
      return
    }
    if (!detalle.data) return
    const e = detalle.data
    setForm({
      cuit: e.cuit || '',
      nombre: e.nombre || '',
      id_actividad: String(e.id_actividad || ''),
      calle: e.calle || '',
      localidad: e.localidad || '',
      provincia: e.provincia || '',
      latitud: e.latitud ?? null,
      longitud: e.longitud ?? null,
      telefono: e.telefono || '',
      email: e.email || '',
      observaciones: e.observaciones || '',
    })
  }, [modo, detalle.data])

  // Lookup duplicado CUIT al completar 11 digitos
  const cuitTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  function programarLookupCuit(valor: string) {
    if (cuitTimer.current) clearTimeout(cuitTimer.current)
    cuitTimer.current = setTimeout(async () => {
      try {
        const r = await verificarDuplicadoEmpresa('cuit', valor, id ?? undefined)
        if (r.existe && r.id && r.id !== id) {
          push({
            kind: 'info',
            title: 'CUIT ya registrado',
            body: `${r.nombre} — usa Buscar para traerla`,
            ttl: 6000,
          })
        }
      } catch { /* silencioso */ }
    }, 800)
  }

  function handleChange<K extends keyof EmpresaFormState>(key: K, value: EmpresaFormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
    if (errores[key as string]) {
      setErrores((prev) => { const n = { ...prev }; delete n[key as string]; return n })
    }
    if (key === 'cuit' && typeof value === 'string') {
      const digits = soloDigitos(value)
      if (digits.length === 11) {
        const fmt = validarCuilCuit(value).formateado || value
        programarLookupCuit(fmt)
      }
    }
  }

  function validar(): { ok: boolean; data?: EmpresaCreate } {
    const errs: Record<string, string> = {}

    // Representante obligatorio SOLO en alta (en edición no se cambia el vínculo acá)
    if (modo === 'new' && !representante) errs.representante = 'Seleccioná el vecino representante'

    if (!form.cuit.trim()) errs.cuit = 'Requerido'
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
    if (Object.keys(errs).length > 0) return { ok: false }

    const cuitFmt = validarCuilCuit(form.cuit).formateado || form.cuit
    const data: EmpresaCreate = {
      cuit: cuitFmt,
      nombre: form.nombre.trim(),
      id_actividad: Number(form.id_actividad),
      calle: form.calle.trim() || null,
      localidad: form.localidad.trim() || null,
      provincia: form.provincia.trim() || null,
      latitud: form.latitud,
      longitud: form.longitud,
      telefono: soloDigitos(form.telefono),
      email: form.email.trim().toLowerCase(),
      observaciones: form.observaciones.trim() || null,
      // El backend crea empresa + vínculo en una transacción. En edición el PUT
      // ignora estos campos (usa EmpresaUpdate), así que un fallback es inocuo.
      id_ciudadano: representante?.id_ciudadano ?? 0,
      id_tipo_representacion: Number(idTipoRep) || 1,
    }
    return { ok: true, data }
  }

  async function handleGuardar() {
    const v = validar()
    if (!v.ok || !v.data) {
      push({ kind: 'error', title: 'Revisa los campos marcados' })
      return
    }
    const data = v.data

    // Duplicados solo en alta
    if (modo === 'new') {
      const [emailDup, telDup] = await Promise.all([
        verificarDuplicadoEmpresa('email', data.email, id ?? undefined).catch(() => ({ existe: false })),
        verificarDuplicadoEmpresa('telefono', data.telefono, id ?? undefined).catch(() => ({ existe: false })),
      ])
      const dupErrs: Record<string, string> = {}
      if (emailDup.existe) dupErrs.email = `Ya registrado: ${(emailDup as { nombre?: string }).nombre ?? ''}`
      if (telDup.existe) dupErrs.telefono = `Ya registrado: ${(telDup as { nombre?: string }).nombre ?? ''}`
      if (Object.keys(dupErrs).length > 0) {
        setErrores((prev) => ({ ...prev, ...dupErrs }))
        push({ kind: 'error', title: 'Hay datos duplicados', body: 'Revisa email/telefono' })
        return
      }
    }

    try {
      if (modo === 'new') {
        const e = await crear.mutateAsync(data)
        push({ kind: 'success', title: 'Empresa dada de alta', body: e.nombre })
        navigate('/empresas')
      } else if (modo === 'edit' && id) {
        await modificar.mutateAsync(data)
        push({ kind: 'success', title: 'Empresa actualizada', body: data.nombre })
        navigate('/empresas')
      }
    } catch (err) {
      push({ kind: 'error', title: 'Error al guardar', body: (err as Error).message })
    }
  }

  const titulo = modo === 'new' ? 'Alta de empresa' : modo === 'edit' ? 'Modificar empresa' : 'Consulta de empresa'
  const estadoBadge = modo === 'new'
    ? { label: 'NUEVO', bg: 'rgba(31,138,101,.12)', fg: 'var(--color-success)' }
    : modo === 'edit'
      ? { label: 'EDICION', bg: 'rgba(192,133,50,.14)', fg: 'var(--zaris-gold, #c08532)' }
      : { label: 'CONSULTA', bg: 'rgba(38,37,30,.08)', fg: 'var(--fg-2)' }

  if (modo !== 'new' && detalle.isLoading) {
    return <div style={{ color: 'var(--fg-3)', padding: 20 }}>Cargando empresa...</div>
  }
  if (modo !== 'new' && detalle.isError) {
    return <div style={{ color: 'var(--color-error)', padding: 20 }}>Error: {(detalle.error as Error).message}</div>
  }

  return (
    <section style={cardStyle}>
      <header style={cardHeaderStyle}>
        <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 'var(--size-title-sm)', fontWeight: 500, color: 'var(--fg-1)' }}>
          {titulo}
        </h2>
        <span style={{
          display: 'inline-flex', alignItems: 'center', padding: '4px 12px',
          borderRadius: 'var(--radius-pill)', fontSize: 'var(--size-caption)',
          fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em',
          background: estadoBadge.bg, color: estadoBadge.fg,
        }}>
          {estadoBadge.label}
        </span>
      </header>

      <div style={{ padding: 20 }}>
        {modo === 'new' && (
          <div style={{
            marginBottom: 20, padding: 16,
            background: 'var(--surface-200)',
            border: '1px solid var(--border-primary)',
            borderRadius: 'var(--radius-lg)',
            display: 'flex', flexDirection: 'column', gap: 12,
          }}>
            <div style={{
              fontFamily: 'var(--font-display)', fontSize: 'var(--size-caption)',
              fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em',
              color: 'var(--fg-3)',
            }}>
              Vecino representante / contacto <span style={{ color: 'var(--zaris-orange)' }}>*</span>
            </div>
            {representante ? (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
                <div style={{ fontSize: 'var(--size-ui)', color: 'var(--fg-1)' }}>
                  <strong>{representante.apellido}, {representante.nombre}</strong>
                  <span style={{ color: 'var(--fg-3)', marginLeft: 8, fontFamily: 'var(--font-mono)' }}>
                    DNI {representante.doc_nro}
                  </span>
                </div>
                <button
                  onClick={() => setRepresentante(null)}
                  style={{
                    padding: '6px 12px', background: 'transparent', color: 'var(--fg-2)',
                    border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-md)',
                    fontSize: 'var(--size-caption)', cursor: 'pointer',
                  }}
                >Cambiar</button>
              </div>
            ) : (
              <CiudadanoSearch
                onSelect={(c) => {
                  setRepresentante(c)
                  if (errores.representante) {
                    setErrores((prev) => { const n = { ...prev }; delete n.representante; return n })
                  }
                }}
                placeholder="Buscar vecino por DNI, CUIL, teléfono o nombre..."
              />
            )}
            {errores.representante && (
              <div style={{ fontSize: 'var(--size-caption)', color: 'var(--color-error)' }}>
                {errores.representante}
              </div>
            )}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxWidth: 320 }}>
              <label style={{ fontSize: 'var(--size-caption)', fontWeight: 600, color: 'var(--fg-2)' }}>
                Tipo de representación <span style={{ color: 'var(--zaris-orange)' }}>*</span>
              </label>
              <select
                value={idTipoRep}
                onChange={(e) => setIdTipoRep(e.target.value)}
                style={{
                  padding: '9px 12px', fontFamily: 'var(--font-display)',
                  fontSize: 'var(--size-ui)', color: 'var(--fg-1)',
                  background: 'var(--surface-100)', border: '1px solid var(--border-primary)',
                  borderRadius: 'var(--radius-lg)', outline: 'none',
                }}
              >
                {(tiposRep.data ?? []).map((t) => (
                  <option key={t.id} value={t.id}>{t.tipo}</option>
                ))}
              </select>
            </div>
          </div>
        )}
        <EmpresaForm
          form={form}
          errores={errores}
          readonly={readonly}
          actividades={actividades.data ?? []}
          onChange={handleChange}
        />
      </div>

      <footer style={cardFooterStyle}>
        <button onClick={() => navigate('/empresas')} style={btnGhost}>
          {readonly ? '← Volver' : 'Cancelar'}
        </button>
        {!readonly && (
          <button onClick={handleGuardar} disabled={crear.isPending || modificar.isPending} style={btnPrimary}>
            {(crear.isPending || modificar.isPending) ? 'Guardando...' : 'Guardar empresa'}
          </button>
        )}
      </footer>
    </section>
  )
}

const cardStyle: React.CSSProperties = {
  background: 'var(--surface-100)',
  border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-xl)',
  boxShadow: 'var(--shadow-ambient)',
  overflow: 'hidden',
}
const cardHeaderStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  padding: '14px 20px', borderBottom: '1px solid var(--border-primary)',
  background: 'var(--surface-200)',
}
const cardFooterStyle: React.CSSProperties = {
  display: 'flex', justifyContent: 'flex-end', gap: 10,
  padding: '14px 20px', borderTop: '1px solid var(--border-primary)',
  background: 'var(--surface-200)',
}
const btnPrimary: React.CSSProperties = {
  padding: '10px 18px', background: 'var(--zaris-dark)', color: 'var(--zaris-cream)',
  border: 'none', borderRadius: 'var(--radius-lg)', fontFamily: 'var(--font-display)',
  fontSize: 'var(--size-btn)', fontWeight: 500, cursor: 'pointer',
}
const btnGhost: React.CSSProperties = {
  padding: '10px 18px', background: 'transparent', color: 'var(--fg-2)',
  border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)',
  fontFamily: 'var(--font-display)', fontSize: 'var(--size-btn)', cursor: 'pointer',
}
