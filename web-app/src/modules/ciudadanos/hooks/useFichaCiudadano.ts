import { useEffect, useRef, useState } from 'react'
import { useNotificationsStore } from '../../../stores/notifications'
import { esAdministrador, useAuthStore } from '../../../stores/auth'
import {
  useCiudadano,
  useCrearCiudadano,
  useCuentasCiudadano,
  useModificarCiudadano,
  useNacionalidades,
  verificarDuplicadoCiudadano,
} from './useCiudadanos'
import { aUsername, usernameValido } from '../components/CuentaZarisCampos'
import {
  extraerDniDeCuil,
  generarCuilDesdeDni,
  soloDigitos,
  validarCuilCuit,
  validarEmail,
  validarTelefono,
} from '../lib/cuilUtils'
import type { Ciudadano, CiudadanoCreate, DocTipo, Sexo, SubareaHit, VerificarDuplicadoResp } from '../types/ciudadano'

export type ModoFicha = 'new' | 'edit' | 'view'

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
  latitud: number | null
  longitud: number | null
  telefono: string
  email: string
  emp_chk: boolean
  es_funcionario: boolean
  // Cuenta ZARIS del funcionario (mig 110): viajan en `cuenta_zaris` al guardar con el tilde.
  zaris_nivel: number
  zaris_subarea: SubareaHit | null
  zaris_username: string
  zaris_username_manual: boolean   // si el admin editó el usuario a mano, no re-proponer
  observaciones: string
}

const emptyForm: FormState = {
  doc_tipo: '', doc_nro: '', cuil: '', cuilManual: false,
  nombre: '', apellido: '', sexo: '', fecha_nac: '',
  id_nacionalidad: '', calle: '', localidad: '', provincia: '',
  latitud: null, longitud: null,
  telefono: '', email: '', emp_chk: false, es_funcionario: false,
  zaris_nivel: 4, zaris_subarea: null, zaris_username: '', zaris_username_manual: false,
  observaciones: '',
}

interface Opciones {
  modo: ModoFicha
  id: number | null
  /** Solo en alta: documento que ya se tipeó en el buscador. */
  docInicial?: string
}

/**
 * Ficha de la persona (BUC): estado del formulario, validación y guardado. La usan la pantalla
 * de Ciudadanos (`FormView`) y la ventana de registro de los formularios de carga
 * (`RegistroVecinoModal`): es UNA sola alta, con los mismos datos y los mismos controles.
 * `guardar()` devuelve la persona guardada, o null si hubo errores (ya informados).
 */
export function useFichaCiudadano({ modo, id, docInicial }: Opciones) {
  const push = useNotificationsStore((s) => s.push)

  const detalle = useCiudadano(modo === 'new' ? null : id)
  const nacionalidades = useNacionalidades()
  const crear = useCrearCiudadano()
  const modificar = useModificarCiudadano(id)

  const [form, setForm] = useState<FormState>(emptyForm)
  const [errores, setErrores] = useState<Record<string, string>>({})

  // ── Cuentas de la persona (mig 110, PLAN_CUENTAS_FUNCIONARIO.md) ──
  // El tilde «funcionario del municipio» lo maneja solo el Administrador y, si la persona
  // todavía no tiene cuenta ZARIS, el guardado la crea con nivel/subárea/usuario
  // (`cuenta_zaris` del POST/PUT). Sin botón ni modal aparte. Destildar NO borra cuentas.
  const nivelUsuario = useAuthStore((s) => s.user?.nivel_acceso)
  const esAdmin = esAdministrador(nivelUsuario)
  const cuentas = useCuentasCiudadano(modo !== 'new' ? id : null)
  const yaTieneZaris = !!cuentas.data?.zaris
  const cuentasListas = modo === 'new' || cuentas.isSuccess
  const debeCrearCuentaZaris = form.es_funcionario && esAdmin && cuentasListas && !yaTieneZaris

  // Hidratar form en modo edit/view desde el detalle
  useEffect(() => {
    if (modo === 'new') {
      setForm(docInicial ? { ...emptyForm, doc_tipo: 'DNI', doc_nro: docInicial } : emptyForm)
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
      latitud: c.latitud ?? null,
      longitud: c.longitud ?? null,
      telefono: c.telefono || '',
      email: c.email || '',
      emp_chk: !!c.emp_chk,
      es_funcionario: !!c.es_funcionario,
      zaris_nivel: 4,
      zaris_subarea: null,
      zaris_username: aUsername(c.nombre || '', c.apellido || ''),
      zaris_username_manual: false,
      observaciones: c.observaciones || '',
    })
  }, [modo, detalle.data, docInicial])

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
      // Usuario de la cuenta ZARIS: se propone nombre.apellido mientras no lo editen a mano;
      // si lo borran, se vuelve a proponer (mismo criterio que el CUIL).
      if (key === 'zaris_username') {
        const limpio = String(value).replace(/\s+/g, '')
        next.zaris_username_manual = limpio.length > 0
        next.zaris_username = limpio || aUsername(prev.nombre, prev.apellido)
      }
      if ((key === 'nombre' || key === 'apellido') && !prev.zaris_username_manual) {
        next.zaris_username = aUsername(key === 'nombre' ? String(value) : prev.nombre,
                                        key === 'apellido' ? String(value) : prev.apellido)
      }
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
    else if (!validarEmail(form.email)) errs.email = 'Formato inválido'
    if (debeCrearCuentaZaris) {
      if (!form.zaris_subarea) errs.zaris_subarea = 'Elegí la subárea del funcionario'
      if (!usernameValido(form.zaris_username)) errs.zaris_username = 'Usuario inválido: letras, números, punto, guión y guión bajo, sin espacios ni tildes'
    }

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
      latitud: form.latitud,
      longitud: form.longitud,
      telefono: soloDigitos(form.telefono),
      email: form.email.trim().toLowerCase(),
      emp_chk: form.emp_chk,
      es_funcionario: form.es_funcionario,
      observaciones: form.observaciones.trim() || null,
    }
    if (debeCrearCuentaZaris && form.zaris_subarea) {
      data.cuenta_zaris = { nivel_acceso: form.zaris_nivel, id_subarea: form.zaris_subarea.id_subarea, username: form.zaris_username }
    }
    return { ok: true, data }
  }

  // ── Guardar ──
  async function guardar(): Promise<{ ciudadano: Ciudadano; avisoZaris: string } | null> {
    const v = validar()
    if (!v.ok || !v.data) {
      push({ kind: 'error', title: 'Revisá los campos marcados' })
      return null
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
        push({ kind: 'error', title: 'Hay datos duplicados', body: 'Revisá el email o el teléfono' })
        return null
      }
    }

    // Con `cuenta_zaris` en el body, el backend crea la cuenta ZARIS en la misma transacción:
    // si el guardado salió bien, la cuenta existe y las credenciales ya se enviaron.
    const avisoZaris = data.cuenta_zaris
      ? ` Cuenta ZARIS creada (usuario ${data.cuenta_zaris.username}); las credenciales se enviaron a ${data.email}.`
      : ''
    try {
      const ciudadano = modo === 'new' ? await crear.mutateAsync(data) : await modificar.mutateAsync(data)
      return { ciudadano, avisoZaris }
    } catch (err) {
      push({ kind: 'error', title: 'Error al guardar', body: (err as Error).message })
      return null
    }
  }

  return {
    form, errores, detalle, cuentas,
    nacionalidades: nacionalidades.data ?? [],
    esAdmin, yaTieneZaris, debeCrearCuentaZaris,
    guardando: crear.isPending || modificar.isPending,
    handleChange, handleCuilBlur, guardar,
  }
}
