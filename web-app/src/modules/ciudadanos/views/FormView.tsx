import { useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { useNotificationsStore } from '../../../stores/notifications'
import {
  useCiudadano,
  useCrearCiudadano,
  useEmpresasVinculadas,
  useModificarCiudadano,
  useNacionalidades,
  verificarDuplicadoCiudadano,
} from '../hooks/useCiudadanos'
import { CiudadanoForm } from '../components/CiudadanoForm'
import { EmpresaVinculadaPanel } from '../components/EmpresaVinculadaPanel'
import {
  extraerDniDeCuil,
  generarCuilDesdeDni,
  soloDigitos,
  validarCuilCuit,
  validarEmail,
  validarTelefono,
} from '../lib/cuilUtils'
import type { CiudadanoCreate, DocTipo, Sexo, VerificarDuplicadoResp } from '../types/ciudadano'

type Modo = 'new' | 'edit' | 'view'

export interface FormState {
  doc_tipo: DocTipo | ''
  doc_nro: string
  cuil: string
  cuilManual: boolean   // si el usuario edito el CUIL a mano, no auto-generar
  nombre: string
  apellido: string
  sexo: Sexo | ''
  fecha_nac: string
  id_nacionalidad: string
  calle: string
  localidad: string
  provincia: string
  telefono: string
  email: string
  emp_chk: boolean
  observaciones: string
}

const emptyForm: FormState = {
  doc_tipo: '', doc_nro: '', cuil: '', cuilManual: false,
  nombre: '', apellido: '', sexo: '', fecha_nac: '',
  id_nacionalidad: '', calle: '', localidad: '', provincia: '',
  telefono: '', email: '', emp_chk: false, observaciones: '',
}

export function FormView() {
  const navigate = useNavigate()
  const location = useLocation()
  const params = useParams<{ id?: string }>()
  const push = useNotificationsStore((s) => s.push)

  // Modo: derivado de la URL.
  // /ciudadanos/nuevo               → new
  // /ciudadanos/:id                 → view
  // /ciudadanos/:id/editar          → edit
  const modo: Modo = useMemo(() => {
    if (location.pathname.endsWith('/nuevo')) return 'new'
    if (location.pathname.endsWith('/editar')) return 'edit'
    return 'view'
  }, [location.pathname])

  const id = params.id ? Number(params.id) : null
  const readonly = modo === 'view'

  const detalle = useCiudadano(modo === 'new' ? null : id)
  const nacionalidades = useNacionalidades()
  const empresas = useEmpresasVinculadas(modo === 'new' ? null : id)
  const crear = useCrearCiudadano()
  const modificar = useModificarCiudadano(id)

  const [form, setForm] = useState<FormState>(emptyForm)
  const [errores, setErrores] = useState<Record<string, string>>({})
  const [empPanelOpen, setEmpPanelOpen] = useState(false)
  const [bloqueoEmpresaGuardar, setBloqueoEmpresaGuardar] = useState(false)

  // Hidratar form en modo edit/view desde el detalle
  useEffect(() => {
    if (modo === 'new') {
      setForm(emptyForm)
      setEmpPanelOpen(false)
      return
    }
    if (!detalle.data) return
    const c = detalle.data
    setForm({
      doc_tipo: c.doc_tipo,
      doc_nro: c.doc_nro || '',
      cuil: c.cuil || '',
      cuilManual: true, // ya cargado, no autogenerar
      nombre: c.nombre || '',
      apellido: c.apellido || '',
      sexo: c.sexo,
      fecha_nac: c.fecha_nac ? c.fecha_nac.substring(0, 10) : '',
      id_nacionalidad: String(c.id_nacionalidad || ''),
      calle: c.calle || '',
      localidad: c.localidad || '',
      provincia: c.provincia || '',
      telefono: c.telefono || '',
      email: c.email || '',
      emp_chk: !!c.emp_chk,
      observaciones: c.observaciones || '',
    })
    if (c.emp_chk) setEmpPanelOpen(true)
  }, [modo, detalle.data])

  // Lookup duplicados con debounce (DNI / CUIL al tipear)
  const lookupTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  function programarLookup(campo: 'doc_nro' | 'cuil', valor: string) {
    if (lookupTimer.current) clearTimeout(lookupTimer.current)
    lookupTimer.current = setTimeout(async () => {
      try {
        const r = await verificarDuplicadoCiudadano(campo, valor, id ?? undefined)
        if (r.existe && r.id && r.id !== id) {
          push({
            kind: 'info',
            title: `${campo === 'cuil' ? 'CUIL' : 'DNI'} ya registrado`,
            body: `${r.nombre} - usa Buscar para traerlo`,
            ttl: 6000,
          })
        }
      } catch { /* silencioso */ }
    }, 800)
  }

  // Actualiza un campo y dispara reglas automaticas
  function handleChange<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => {
      const next: FormState = { ...prev, [key]: value }
      // Si tocan CUIL manualmente, marcamos manual
      if (key === 'cuil') next.cuilManual = String(value).length > 0
      // Auto-generar CUIL desde DNI si no fue editado manualmente
      if ((key === 'doc_nro' || key === 'sexo' || key === 'doc_tipo') && !prev.cuilManual) {
        const docTipo = key === 'doc_tipo' ? (value as string) : prev.doc_tipo
        const docNro = key === 'doc_nro' ? (value as string) : prev.doc_nro
        const sexo = key === 'sexo' ? (value as string) : prev.sexo
        const generado = generarCuilDesdeDni(docNro, sexo, docTipo)
        if (generado) next.cuil = generado
        else if (next.cuil && !prev.cuilManual) next.cuil = ''
      }
      return next
    })
    // limpiar error del campo
    if (errores[key as string]) {
      setErrores((prev) => { const n = { ...prev }; delete n[key as string]; return n })
    }
    // Lookups
    if (key === 'doc_nro' && typeof value === 'string') {
      const digits = soloDigitos(value)
      if (digits.length >= 7) programarLookup('doc_nro', digits)
    }
    if (key === 'cuil' && typeof value === 'string') {
      const digits = soloDigitos(value)
      if (digits.length === 11) programarLookup('cuil', value)
    }
  }

  // Al perder foco del CUIL, si DNI esta vacio, extraer DNI del CUIL
  function handleCuilBlur() {
    if (!form.doc_nro && form.cuil) {
      const dni = extraerDniDeCuil(form.cuil)
      if (dni) setForm((prev) => ({ ...prev, doc_nro: dni }))
    }
  }

  // ── Validar formulario ──
  function validar(): { ok: boolean; data?: CiudadanoCreate } {
    const errs: Record<string, string> = {}

    if (!form.doc_tipo) errs.doc_tipo = 'Requerido'
    if (!form.doc_nro && !form.cuil) {
      errs.doc_nro = 'Ingresa DNI o CUIL'
      errs.cuil = 'Ingresa DNI o CUIL'
    }
    if (form.cuil) {
      const r = validarCuilCuit(form.cuil)
      if (!r.valido) errs.cuil = r.error
    }
    if (!form.nombre.trim()) errs.nombre = 'Requerido'
    if (!form.apellido.trim()) errs.apellido = 'Requerido'
    if (!form.sexo) errs.sexo = 'Requerido'
    if (!form.fecha_nac) errs.fecha_nac = 'Requerido'
    if (!form.id_nacionalidad) errs.id_nacionalidad = 'Requerido'
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

    // Construir payload (con CUIL formateado, telefono y email sin guiones/trim)
    const cuilFmt = validarCuilCuit(form.cuil).formateado || form.cuil
    const data: CiudadanoCreate = {
      doc_tipo: form.doc_tipo as DocTipo,
      doc_nro: soloDigitos(form.doc_nro) || extraerDniDeCuil(cuilFmt) || form.doc_nro,
      cuil: cuilFmt,
      nombre: form.nombre.trim(),
      apellido: form.apellido.trim(),
      sexo: form.sexo as Sexo,
      fecha_nac: form.fecha_nac,
      id_nacionalidad: Number(form.id_nacionalidad),
      calle: form.calle.trim() || null,
      localidad: form.localidad.trim() || null,
      provincia: form.provincia.trim() || null,
      telefono: soloDigitos(form.telefono),
      email: form.email.trim().toLowerCase(),
      emp_chk: form.emp_chk,
      observaciones: form.observaciones.trim() || null,
    }
    return { ok: true, data }
  }

  // ── Guardar ──
  async function handleGuardar() {
    const v = validar()
    if (!v.ok || !v.data) {
      push({ kind: 'error', title: 'Revisa los campos marcados' })
      return
    }
    const data = v.data

    // Verificacion de duplicados solo en alta
    if (modo === 'new') {
      const noDup: VerificarDuplicadoResp = { existe: false }
      const [emailDup, telDup] = await Promise.all([
        verificarDuplicadoCiudadano('email', data.email, id ?? undefined).catch(() => noDup),
        verificarDuplicadoCiudadano('telefono', data.telefono, id ?? undefined).catch(() => noDup),
      ])
      const dupErrs: Record<string, string> = {}
      if (emailDup.existe) dupErrs.email = `Ya registrado: ${emailDup.nombre}`
      if (telDup.existe) dupErrs.telefono = `Ya registrado: ${telDup.nombre}`
      if (Object.keys(dupErrs).length > 0) {
        setErrores((prev) => ({ ...prev, ...dupErrs }))
        push({ kind: 'error', title: 'Hay datos duplicados', body: 'Revisa email/telefono' })
        return
      }
    }

    try {
      if (modo === 'new') {
        const c = await crear.mutateAsync(data)
        push({ kind: 'success', title: 'Ciudadano dado de alta', body: `${c.apellido}, ${c.nombre}` })
        if (form.emp_chk) {
          // Quedarse en edicion del nuevo ciudadano y abrir panel empresa
          navigate(`/ciudadanos/${c.id_ciudadano}/editar`, { replace: true })
          setEmpPanelOpen(true)
        } else {
          navigate('/ciudadanos')
        }
      } else if (modo === 'edit' && id) {
        await modificar.mutateAsync(data)
        push({ kind: 'success', title: 'Ciudadano actualizado', body: `${data.apellido}, ${data.nombre}` })
        navigate('/ciudadanos')
      }
    } catch (err) {
      push({ kind: 'error', title: 'Error al guardar', body: (err as Error).message })
    }
  }

  // ── Toggle emp_chk ──
  function handleEmpChk(checked: boolean) {
    handleChange('emp_chk', checked)
    if (!checked) {
      setEmpPanelOpen(false)
      return
    }
    if (modo === 'edit' && id) {
      setEmpPanelOpen(true)
    } else if (modo === 'new') {
      push({ kind: 'info', title: 'Guarda el ciudadano primero para vincular la empresa' })
    }
  }

  // Estado de UI superior
  const titulo = modo === 'new' ? 'Alta de ciudadano' : modo === 'edit' ? 'Modificar ciudadano' : 'Consulta de ciudadano'
  const estadoBadge = modo === 'new'
    ? { label: 'NUEVO', bg: 'rgba(31,138,101,.12)', fg: 'var(--color-success)' }
    : modo === 'edit'
      ? { label: 'EDICION', bg: 'rgba(192,133,50,.14)', fg: 'var(--zaris-gold, #c08532)' }
      : { label: 'CONSULTA', bg: 'rgba(38,37,30,.08)', fg: 'var(--fg-2)' }

  if (modo !== 'new' && detalle.isLoading) {
    return <div style={{ color: 'var(--fg-3)', padding: 20 }}>Cargando ciudadano...</div>
  }
  if (modo !== 'new' && detalle.isError) {
    return <div style={{ color: 'var(--color-error)', padding: 20 }}>Error: {(detalle.error as Error).message}</div>
  }

  return (
    <>
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
          <CiudadanoForm
            form={form}
            errores={errores}
            readonly={readonly}
            nacionalidades={nacionalidades.data ?? []}
            onChange={handleChange}
            onCuilBlur={handleCuilBlur}
            onEmpChkChange={handleEmpChk}
          />
        </div>

        <footer style={cardFooterStyle}>
          <button onClick={() => navigate('/ciudadanos')} style={btnGhost}>
            {readonly ? '← Volver' : 'Cancelar'}
          </button>
          {!readonly && (
            <button onClick={handleGuardar} disabled={crear.isPending || modificar.isPending || bloqueoEmpresaGuardar} style={btnPrimary}>
              {(crear.isPending || modificar.isPending) ? 'Guardando...' : 'Guardar ciudadano'}
            </button>
          )}
        </footer>
      </section>

      {/* Panel empresa vinculada */}
      {(empPanelOpen || (empresas.data && empresas.data.length > 0 && form.emp_chk)) && id && (
        <EmpresaVinculadaPanel
          idCiudadano={id}
          readonly={readonly}
          modoAlta={!empresas.data || empresas.data.length === 0}
          empresa={empresas.data?.[0]}
          onBusy={setBloqueoEmpresaGuardar}
        />
      )}
    </>
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

const btnPrimary: React.CSSProperties = {
  padding: '10px 18px',
  background: 'var(--zaris-dark)',
  color: 'var(--zaris-cream)',
  border: 'none',
  borderRadius: 'var(--radius-lg)',
  fontFamily: 'var(--font-display)',
  fontSize: 'var(--size-btn)',
  fontWeight: 500,
  cursor: 'pointer',
}

const btnGhost: React.CSSProperties = {
  padding: '10px 18px',
  background: 'transparent',
  color: 'var(--fg-2)',
  border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-lg)',
  fontFamily: 'var(--font-display)',
  fontSize: 'var(--size-btn)',
  cursor: 'pointer',
}
