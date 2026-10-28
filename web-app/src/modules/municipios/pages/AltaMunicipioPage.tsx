import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Badge, Button, EmptyState, Skeleton } from '../../../ui'
import { useNotificationsStore } from '../../../stores/notifications'
import {
  darDeAlta, disponibilidadAlta, etiquetaZona, listarPaises, listarPartidos, listarProvincias, opcionesAlta,
  type AltaMunicipioBody, type AltaResultado, type Disponible, type OpcionModulo,
} from '../api'
import { Campo, input, seccion, titulo } from './_comun'
import { normalizarNumero, parLatLon, problemaZona } from '../../../lib/zonaBusqueda'

// Asistente de alta de un municipio (IT-01 F4+F5, Tarea 15; spec §4.4). Seis pasos y el alta en una
// sola llamada: el backend valida todo antes de escribir y, si algo falla, no queda nada. El
// subdominio se arma solo desde el nombre hasta que el super lo edita (auto-slug, §23).
// Corte B (César, 2026-10-27): el municipio ES el partido (obligatorio, salvo los ficticios de demo y
// prueba) y propone nombre, subdominio y código; la zona horaria es un combo ordenado por desfase; el
// código corto lleva 4 letras y, como el subdominio y el partido, se comprueba libre mientras se escribe.

const PASOS = ['Datos', 'Identidad', 'Qué copiar', 'Módulos', 'Tope de cuentas', 'Primer administrador'] as const

// Los mismos de backend/app/services/municipios/constantes.py.
const PATRON_SUBDOMINIO = /^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$/
const LARGO_CODIGO = 4
const PATRON_CODIGO = new RegExp(`^[A-Z]{${LARGO_CODIGO}}$`)
const RESERVADOS = new Set(['www', 'api', 'zge', 'vecinos', 'agentes', 'admin', 'app', 'mail', 'soporte',
  'status', 'demo', 'modelo'])
// Sin zona, el buscador de direcciones del municipio nuevo responde «sin zona» (geo.py), no busca en otro lado.
const SIN_CONTORNO = 'Sin zona de búsqueda: el buscador de direcciones no va a funcionar hasta que se cargue '
  + 'acá o en Configuración → Sistema.'

// Qué decir de cada campo cuando falta o está mal (el botón se deshabilita y la lista explica por qué).
const ETIQUETAS: Partial<Record<keyof Form, string>> = {
  nombre: 'Nombre', codigo_pais: 'País', id_provincia: 'Provincia', id_partido: 'Partido',
  zona_horaria: 'Zona horaria', codigo_corto: 'Código corto', subdominio: 'Subdominio', color: 'Color principal',
  lat: 'Zona del geocoding', tope: 'Tope de cuentas', a_nombre: 'Nombre', a_apellido: 'Apellido', a_dni: 'DNI',
  a_cuil: 'CUIL', a_sexo: 'Sexo', a_fecha_nac: 'Fecha de nacimiento', a_telefono: 'Teléfono', a_email: 'Email',
}

const sinTildes = (s: string) => s.normalize('NFD').replace(/\p{Diacritic}/gu, '')
const aSubdominio = (s: string) => sinTildes(s).toLowerCase()
  .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 63)
const aCodigo = (s: string) => sinTildes(s).toUpperCase().replace(/[^A-Z]/g, '').slice(0, LARGO_CODIGO)

// El valor después de que dejó de cambiar `ms` milisegundos (para no consultar en cada tecla).
function useEstable<T>(valor: T, ms = 350): T {
  const [estable, setEstable] = useState(valor)
  const clave = JSON.stringify(valor)
  useEffect(() => {
    const t = setTimeout(() => setEstable(JSON.parse(clave) as T), ms)
    return () => clearTimeout(t)
  }, [clave, ms])
  return estable
}

interface Form {
  nombre: string; codigo_pais: string; id_provincia: number | null; id_partido: number | null; ficticio: boolean
  zona_horaria: string; codigo_corto: string; subdominio: string
  color: string; logo_url: string; geojson: string; lat: string; lon: string; delta: string
  copiar: string[]; modulos: string[]; tope: string
  a_nombre: string; a_apellido: string; a_dni: string; a_cuil: string; a_sexo: '' | 'HOMBRE' | 'MUJER' | 'OTROS'
  a_fecha_nac: string; a_telefono: string; a_email: string
}

const VACIO: Form = {
  nombre: '', codigo_pais: '', id_provincia: null, id_partido: null, ficticio: false, zona_horaria: '', codigo_corto: '',
  subdominio: '', color: '', logo_url: '', geojson: '', lat: '', lon: '', delta: '', copiar: [], modulos: [],
  tope: '', a_nombre: '', a_apellido: '', a_dni: '', a_cuil: '', a_sexo: '', a_fecha_nac: '', a_telefono: '',
  a_email: '',
}

const num = (v: string) => (v.trim() === '' ? null : Number(v))

// «{modulo} necesita {dependencia} habilitado.» (texto fijo del plan), o null si está todo bien.
export function faltaDependencia(elegidos: string[], modulos: OpcionModulo[]): string | null {
  const nombre = (c: string) => modulos.find((m) => m.codigo === c)?.nombre ?? c
  for (const m of modulos) {
    if (!elegidos.includes(m.codigo)) continue
    const falta = m.dependencias.find((d) => !elegidos.includes(d))
    if (falta) return `${nombre(m.codigo)} necesita ${nombre(falta)} habilitado.`
  }
  return null
}

export function AltaMunicipioPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const push = useNotificationsStore((s) => s.push)
  const [paso, setPaso] = useState(0)
  const [f, setF] = useState<Form>(VACIO)
  const [resultado, setResultado] = useState<AltaResultado | null>(null)
  const subdominioTocado = useRef(false)
  const nombreTocado = useRef(false)
  const codigoTocado = useRef(false)
  const set = (cambios: Partial<Form>) => setF((prev) => ({ ...prev, ...cambios }))

  const opciones = useQuery({ queryKey: ['super', 'alta', 'opciones'], queryFn: opcionesAlta })
  const paises = useQuery({ queryKey: ['geo', 'paises', 'alta'], queryFn: () => listarPaises(true) })
  const provincias = useQuery({
    queryKey: ['geo', 'provincias', f.codigo_pais], queryFn: () => listarProvincias(f.codigo_pais),
    enabled: !!f.codigo_pais,
  })
  const partidos = useQuery({
    queryKey: ['geo', 'partidos', f.id_provincia], queryFn: () => listarPartidos(f.id_provincia!),
    enabled: f.id_provincia != null,
  })
  const pais = paises.data?.find((p) => p.codigo_pais === f.codigo_pais)
  const nivel2 = (pais?.etiqueta_nivel_2 ?? 'Partido').toLowerCase()

  // Lo que propone el partido (o el nombre, si es ficticio) mientras el super no escriba lo suyo.
  const proponer = (base: string, nombre?: string): Partial<Form> => ({
    ...(nombre !== undefined && !nombreTocado.current ? { nombre } : {}),
    ...(subdominioTocado.current ? {} : { subdominio: aSubdominio(base) }),
    ...(codigoTocado.current ? {} : { codigo_corto: aCodigo(base) }),
  })

  // Disponibilidad del código, el subdominio y el partido, comprobada en el backend al dejar de escribir.
  const consulta = useEstable({
    codigo_corto: PATRON_CODIGO.test(f.codigo_corto) ? f.codigo_corto : undefined,
    subdominio: PATRON_SUBDOMINIO.test(f.subdominio) && !RESERVADOS.has(f.subdominio) ? f.subdominio : undefined,
    id_partido: f.ficticio ? undefined : f.id_partido ?? undefined,
  })
  const disp = useQuery({
    queryKey: ['super', 'alta', 'disponibilidad', consulta], queryFn: () => disponibilidadAlta(consulta),
    enabled: !!(consulta.codigo_corto || consulta.subdominio || consulta.id_partido),
  })
  // undefined = todavía no se sabe (escribiendo o consultando); si no, lo que dijo el backend.
  const estado = (campo: 'codigo_corto' | 'subdominio' | 'id_partido', valor: unknown): Disponible | undefined =>
    consulta[campo] === valor && !disp.isFetching ? disp.data?.[campo] : undefined
  const dispCodigo = estado('codigo_corto', f.codigo_corto)
  const dispSub = estado('subdominio', f.subdominio)
  const dispPartido = estado('id_partido', f.id_partido ?? undefined)

  // Al llegar las opciones: todos los catálogos y todos los módulos elegidos (el super quita).
  useEffect(() => {
    if (!opciones.data) return
    setF((prev) => prev.copiar.length || prev.modulos.length ? prev : {
      ...prev,
      copiar: opciones.data.catalogos.map((c) => c.codigo),
      modulos: opciones.data.modulos.map((m) => m.codigo),
    })
  }, [opciones.data])

  const errores = useMemo(() => {
    const e: Partial<Record<keyof Form, string>> = {}
    if (f.nombre.trim().length < 3) e.nombre = 'Al menos 3 letras'
    if (!f.codigo_pais) e.codigo_pais = 'Elegí el país'
    if (f.id_provincia == null) e.id_provincia = `Elegí la ${(pais?.etiqueta_nivel_1 ?? 'provincia').toLowerCase()}`
    if (!f.ficticio && f.id_partido == null) e.id_partido = `Elegí el ${nivel2}, o marcá el municipio como ficticio`
    else if (dispPartido?.disponible === false) e.id_partido = dispPartido.motivo ?? 'No disponible'
    if (!PATRON_CODIGO.test(f.codigo_corto)) e.codigo_corto = `${LARGO_CODIGO} letras mayúsculas, sin tildes`
    else if (dispCodigo?.disponible === false) e.codigo_corto = dispCodigo.motivo ?? 'No disponible'
    if (!PATRON_SUBDOMINIO.test(f.subdominio)) e.subdominio = 'Solo minúsculas, números y guiones, sin espacios'
    else if (RESERVADOS.has(f.subdominio)) e.subdominio = 'Ese subdominio está reservado'
    else if (dispSub?.disponible === false) e.subdominio = dispSub.motivo ?? 'No disponible'
    if (!f.zona_horaria) e.zona_horaria = 'Elegí la zona horaria'
    if (f.color && !/^#[0-9A-Fa-f]{6}$/.test(f.color)) e.color = 'Formato #RRGGBB'
    const coords = [f.lat, f.lon, f.delta].filter((v) => v.trim() !== '').length
    const malZona = ([['Latitud', 'geo_bbox_centro_lat', f.lat], ['Longitud', 'geo_bbox_centro_lon', f.lon],
      ['Radio', 'geo_bbox_delta_grados', f.delta]] as const)
      .map(([nombre, clave, v]) => { const p = problemaZona(clave, v); return p && `${nombre}: ${p.toLowerCase()}` })
      .find(Boolean)
    if (coords > 0 && coords < 3) e.lat = 'Completá centro (latitud y longitud) y radio, o dejá los tres vacíos'
    else if (malZona) e.lat = malZona
    if (f.tope.trim() !== '' && !(Number.isInteger(Number(f.tope)) && Number(f.tope) >= 1)) e.tope = 'Un número entero, 1 o más'
    if (!f.a_nombre.trim()) e.a_nombre = 'Obligatorio'
    if (!f.a_apellido.trim()) e.a_apellido = 'Obligatorio'
    if (!/^[0-9]{7,8}$/.test(f.a_dni)) e.a_dni = '7 u 8 dígitos'
    if (!/^[0-9]{11}$/.test(f.a_cuil)) e.a_cuil = '11 dígitos, sin guiones'
    if (!f.a_sexo) e.a_sexo = 'Elegí una opción'
    if (!f.a_fecha_nac) e.a_fecha_nac = 'Obligatoria'
    if (f.a_telefono.trim().length < 6) e.a_telefono = 'Al menos 6 dígitos'
    if (!f.a_email.trim()) e.a_email = 'Obligatorio'
    else if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(f.a_email.trim())) e.a_email = 'Email inválido'
    return e
  }, [f, pais, nivel2, dispPartido, dispCodigo, dispSub])
  // El paso Datos espera a que el backend confirme que el código, el subdominio y el partido están libres.
  const libres = dispCodigo?.disponible === true && dispSub?.disponible === true
    && (f.ficticio || dispPartido?.disponible === true)

  const camposDelPaso: (keyof Form)[][] = [
    ['nombre', 'codigo_pais', 'id_provincia', 'id_partido', 'zona_horaria', 'codigo_corto', 'subdominio'],
    ['color', 'lat'],
    [],
    [],
    ['tope'],
    ['a_nombre', 'a_apellido', 'a_dni', 'a_cuil', 'a_sexo', 'a_fecha_nac', 'a_telefono', 'a_email'],
  ]
  const errorDependencia = opciones.data ? faltaDependencia(f.modulos, opciones.data.modulos) : null
  const pasoValido = (i: number) => camposDelPaso[i].every((c) => !errores[c]) && (i !== 3 || !errorDependencia)
    && (i !== 0 || libres)
  const sinContorno = f.lat.trim() === ''
  // Lo que impide avanzar en el paso actual, con el motivo (antes el botón se deshabilitaba sin decir por qué).
  const faltan = camposDelPaso[paso].flatMap((c) => (errores[c] ? [[c, errores[c]!] as const] : []))

  const alta = useMutation({
    mutationFn: darDeAlta,
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ['super', 'municipios'] })
      setResultado(r)
    },
    onError: (e: Error) => push({ kind: 'error', title: 'No se pudo dar de alta', body: e.message }),
  })

  const enviar = () => {
    if (alta.isPending || !PASOS.every((_, i) => pasoValido(i))) return
    const body: AltaMunicipioBody = {
      nombre: f.nombre.trim(), codigo_pais: f.codigo_pais, id_provincia: f.id_provincia!,
      id_partido: f.ficticio ? null : f.id_partido, ficticio: f.ficticio,
      zona_horaria: f.zona_horaria.trim() || null, codigo_corto: f.codigo_corto, subdominio: f.subdominio,
      identidad: {
        color: f.color || null, logo_url: f.logo_url.trim() || null, geo_limite_geojson: f.geojson.trim() || null,
        geo_bbox_centro_lat: num(normalizarNumero(f.lat)), geo_bbox_centro_lon: num(normalizarNumero(f.lon)),
        geo_bbox_delta_grados: num(normalizarNumero(f.delta)),
      },
      copiar: f.copiar,
      modulos: [...new Set([...f.modulos, ...opciones.data!.modulos.filter((m) => m.fijo).map((m) => m.codigo)])],
      max_usuarios_activos: num(f.tope),
      administrador: {
        nombre: f.a_nombre.trim(), apellido: f.a_apellido.trim(), dni: f.a_dni, cuil: f.a_cuil,
        sexo: f.a_sexo as 'HOMBRE' | 'MUJER' | 'OTROS', fecha_nac: f.a_fecha_nac, telefono: f.a_telefono.trim(),
        email: f.a_email.trim().toLowerCase(),
      },
    }
    alta.mutate(body)
  }

  if (resultado) {
    return (
      <div style={pagina}>
        <h1 style={titulo}>Municipio dado de alta</h1>
        <div style={seccion}>
          <p style={{ margin: 0 }}>
            <strong>{f.nombre}</strong> quedó en puesta en marcha, con la cuenta de su primer administrador
            ({f.a_email.trim().toLowerCase()}). Todavía no le mandamos la invitación.
          </p>
          {resultado.advertencias.length > 0 && <Advertencias lista={resultado.advertencias} />}
          <p style={{ margin: 0, fontSize: 13, color: 'var(--fg-2)' }}>
            Falta crear sus tres direcciones con <code>tools/dominios_municipio.py {f.subdominio}</code>. Después,
            en la ficha: «Verificar», y con las tres en verde, «Enviar invitación» (vence en 72 horas) y «Probar
            puesta en marcha».
          </p>
          <div><Button variant="primary" type="button" onClick={() => navigate(`/municipios/${resultado.id_municipio}`)}>
            Ir a la ficha
          </Button></div>
        </div>
      </div>
    )
  }

  if (opciones.isLoading || paises.isLoading) return <div style={pagina}><Skeleton height={240} /></div>
  if (opciones.isError) return <div style={pagina}><EmptyState title="No se pudo cargar el asistente" description={opciones.error.message} /></div>

  const err = (c: keyof Form) => errores[c]
  return (
    <div style={pagina}>
      <header>
        <h1 style={titulo}>Dar de alta un municipio</h1>
        <ol style={{ display: 'flex', flexWrap: 'wrap', gap: 6, listStyle: 'none', padding: 0, margin: '10px 0 0' }}>
          {PASOS.map((p, i) => (
            <li key={p}>
              <button type="button" data-paso={i} onClick={() => setPaso(i)}
                      disabled={i > paso && !PASOS.slice(0, i).every((_, j) => pasoValido(j))}
                      style={{ ...chip, ...(i === paso ? chipActivo : {}) }}>
                {i + 1}. {p}{i < paso && pasoValido(i) ? ' ✓' : ''}
              </button>
            </li>
          ))}
        </ol>
      </header>

      <div style={seccion}>
        {paso === 0 && (
          <>
            <Campo etiqueta="País" ayuda="Solo los habilitados para dar de alta municipios.">
              <select style={input} value={f.codigo_pais} autoFocus
                      onChange={(e) => {
                        const p = paises.data?.find((x) => x.codigo_pais === e.target.value)
                        set({ codigo_pais: e.target.value, id_provincia: null, id_partido: null, zona_horaria: p?.zona_horaria ?? '' })
                      }}>
                <option value="">—</option>
                {(paises.data ?? []).map((p) => <option key={p.codigo_pais} value={p.codigo_pais}>{p.nombre}</option>)}
              </select>
            </Campo>
            <Campo etiqueta={pais?.etiqueta_nivel_1 ?? 'Provincia'}>
              <select style={input} value={f.id_provincia ?? ''} disabled={!f.codigo_pais}
                      onChange={(e) => set({ id_provincia: e.target.value ? Number(e.target.value) : null, id_partido: null })}>
                <option value="">—</option>
                {(provincias.data ?? []).map((p) => <option key={p.id_provincia} value={p.id_provincia}>{p.nombre}</option>)}
              </select>
            </Campo>
            <Campo etiqueta={pais?.etiqueta_nivel_2 ?? 'Partido'}
                   ayuda={f.ficticio ? 'Municipio ficticio: no lleva partido y no puede pasar a producción.'
                     : dispPartido?.disponible ? 'Libre: ningún otro municipio lo tiene.' : 'El municipio es el partido: uno por partido.'}
                   error={!f.ficticio && f.id_partido != null ? err('id_partido') : undefined}>
              <select style={input} value={f.id_partido ?? ''} disabled={f.id_provincia == null || f.ficticio}
                      onChange={(e) => {
                        const id = e.target.value ? Number(e.target.value) : null
                        const p = partidos.data?.find((x) => x.id_partido === id)
                        set({ id_partido: id, ...(p ? proponer(p.nombre, `Municipalidad de ${p.nombre}`) : {}) })
                      }}>
                <option value="">—</option>
                {(partidos.data ?? []).map((p) => <option key={p.id_partido} value={p.id_partido}>{p.nombre}</option>)}
              </select>
            </Campo>
            <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 14 }}>
              <input type="checkbox" checked={f.ficticio}
                     onChange={(e) => set({ ficticio: e.target.checked, id_partido: null })} />
              Municipio ficticio (demo o prueba), sin {nivel2}
            </label>
            <Campo etiqueta="Nombre" ayuda={f.ficticio ? undefined : `Se propone desde el ${nivel2}; se puede cambiar.`}
                   error={f.nombre ? err('nombre') : undefined}>
              <input style={input} value={f.nombre} maxLength={150}
                     onChange={(e) => {
                       nombreTocado.current = true
                       set({ nombre: e.target.value, ...(f.ficticio ? proponer(e.target.value) : {}) })
                     }} />
            </Campo>
            <Campo etiqueta="Zona horaria" ayuda="Ordenadas por su diferencia con Greenwich. Por defecto, la del país."
                   error={err('zona_horaria')}>
              <select style={{ ...input, fontFamily: 'var(--font-mono)' }} value={f.zona_horaria}
                      onChange={(e) => set({ zona_horaria: e.target.value })}>
                <option value="">—</option>
                {(opciones.data?.zonas ?? []).map((z) => <option key={z.nombre} value={z.nombre}>{etiquetaZona(z)}</option>)}
              </select>
            </Campo>
            <Campo etiqueta={`Código corto (${LARGO_CODIGO} letras)`}
                   ayuda={`${dispCodigo?.disponible ? 'Libre. ' : ''}Prefijo de los números: REC-${f.codigo_corto || 'XXXX'}-${new Date().getFullYear()}-000001. No se puede cambiar después.`}
                   error={f.codigo_corto ? err('codigo_corto') : undefined}>
              <input style={{ ...input, fontFamily: 'var(--font-mono)' }} value={f.codigo_corto} maxLength={LARGO_CODIGO}
                     onChange={(e) => { codigoTocado.current = true; set({ codigo_corto: aCodigo(e.target.value) }) }} />
            </Campo>
            <Campo etiqueta="Subdominio"
                   ayuda={f.subdominio ? `${dispSub?.disponible ? 'Libre: ' : ''}${f.subdominio}.zge.zaris.com.ar` : 'Se arma desde el partido o el nombre'}
                   error={f.subdominio ? err('subdominio') : undefined}>
              <input style={{ ...input, fontFamily: 'var(--font-mono)' }} value={f.subdominio} maxLength={63}
                     onChange={(e) => { subdominioTocado.current = true; set({ subdominio: e.target.value.toLowerCase() }) }} />
            </Campo>
          </>
        )}

        {paso === 1 && (
          <>
            <p style={ayudaPaso}>Todo es opcional: lo que no se cargue queda con los valores por defecto.</p>
            <Campo etiqueta="Color principal" error={err('color')}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input type="color" value={f.color || '#f54e00'} onChange={(e) => set({ color: e.target.value })} />
                <input style={{ ...input, fontFamily: 'var(--font-mono)', width: 120 }} value={f.color} maxLength={7}
                       placeholder="#RRGGBB" onChange={(e) => set({ color: e.target.value })} />
              </div>
            </Campo>
            <Campo etiqueta="Logo (URL)">
              <input style={input} value={f.logo_url} maxLength={500} onChange={(e) => set({ logo_url: e.target.value })} />
            </Campo>
            <Campo etiqueta="Zona del geocoding: centro y radio en grados" error={err('lat')}
                   ayuda="Restringe las búsquedas de direcciones a la zona del municipio. En la latitud se puede pegar «latitud, longitud» como lo copia Google Maps. Radio: 0.1 ≈ 11 km.">
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <input style={{ ...input, width: 140 }} placeholder="Latitud" value={f.lat}
                       onChange={(e) => { const par = parLatLon(e.target.value); set(par ? { lat: par[0], lon: par[1] } : { lat: e.target.value }) }} />
                <input style={{ ...input, width: 140 }} placeholder="Longitud" value={f.lon} onChange={(e) => set({ lon: e.target.value })} />
                <input style={{ ...input, width: 110 }} placeholder="Radio" value={f.delta} onChange={(e) => set({ delta: e.target.value })} />
              </div>
            </Campo>
            <Campo etiqueta="Contorno del municipio (GeoJSON)">
              <textarea style={{ ...input, minHeight: 90, fontFamily: 'var(--font-mono)', fontSize: 12 }}
                        value={f.geojson} onChange={(e) => set({ geojson: e.target.value })} />
            </Campo>
            {sinContorno && <Advertencias lista={[SIN_CONTORNO]} />}
          </>
        )}

        {paso === 2 && (
          <>
            <p style={ayudaPaso}>Catálogos que se copian del municipio modelo. Las áreas fijas se copian siempre.</p>
            {opciones.data!.catalogos.map((c) => (
              <Casilla key={c.codigo} etiqueta={c.nombre} marcada={f.copiar.includes(c.codigo)}
                       onChange={(v) => set({ copiar: v ? [...f.copiar, c.codigo] : f.copiar.filter((x) => x !== c.codigo) })} />
            ))}
          </>
        )}

        {paso === 3 && (
          <>
            <p style={ayudaPaso}>Los módulos fijos no se pueden deshabilitar: el municipio no funciona sin ellos.</p>
            {opciones.data!.modulos.map((m) => (
              <Casilla key={m.codigo} etiqueta={m.nombre} marcada={m.fijo || f.modulos.includes(m.codigo)} deshabilitada={m.fijo}
                       nota={m.fijo ? 'fijo' : undefined}
                       onChange={(v) => set({ modulos: v ? [...f.modulos, m.codigo] : f.modulos.filter((x) => x !== m.codigo) })} />
            ))}
            {errorDependencia && <span style={{ fontSize: 13, color: 'var(--color-error)' }}>{errorDependencia}</span>}
          </>
        )}

        {paso === 4 && (
          <Campo etiqueta="Tope de cuentas internas activas (opcional)" error={err('tope')}
                 ayuda="Vacío = sin tope. Al llegar, crear o reactivar una cuenta da error. No cuentan los vecinos.">
            <input style={{ ...input, width: 160 }} inputMode="numeric" value={f.tope}
                   onChange={(e) => set({ tope: e.target.value.replace(/[^0-9]/g, '') })} />
          </Campo>
        )}

        {paso === 5 && (
          <>
            <p style={ayudaPaso}>
              Se crea su ficha en la BUC del municipio, su agente y su cuenta de administrador. Después, desde la
              ficha del municipio, se le envía una invitación para elegir la clave y vincular la app de
              autenticación: nadie más conoce la clave. Todos los campos son obligatorios.
            </p>
            <div data-resumen-direcciones style={{ ...ayudaPaso, padding: '10px 12px', borderRadius: 8,
              border: '1px solid var(--border-medium)', background: 'var(--surface-200)' }}>
              El link de la invitación lleva a <strong style={{ fontFamily: 'var(--font-mono)' }}>
              {f.subdominio || '—'}.zge.zaris.com.ar</strong>. Revisá que sea el subdominio que querés: las tres
              direcciones ({f.subdominio || '—'}.zge, .vecinos y .agentes) se crean con{' '}
              <code>tools/dominios_municipio.py {f.subdominio || '<subdominio>'}</code>, y la invitación se envía
              desde la ficha cuando las tres responden.
            </div>
            <div style={grilla}>
              <Campo etiqueta="Nombre">
                <input style={input} value={f.a_nombre} maxLength={100} onChange={(e) => set({ a_nombre: e.target.value })} />
              </Campo>
              <Campo etiqueta="Apellido">
                <input style={input} value={f.a_apellido} maxLength={100} onChange={(e) => set({ a_apellido: e.target.value })} />
              </Campo>
              <Campo etiqueta="DNI" error={f.a_dni ? err('a_dni') : undefined}>
                <input style={input} inputMode="numeric" value={f.a_dni} maxLength={8}
                       onChange={(e) => set({ a_dni: e.target.value.replace(/[^0-9]/g, '') })} />
              </Campo>
              <Campo etiqueta="CUIL" error={f.a_cuil ? err('a_cuil') : undefined}>
                <input style={input} inputMode="numeric" value={f.a_cuil} maxLength={11}
                       onChange={(e) => set({ a_cuil: e.target.value.replace(/[^0-9]/g, '') })} />
              </Campo>
              <Campo etiqueta="Sexo">
                <select style={input} value={f.a_sexo} onChange={(e) => set({ a_sexo: e.target.value as Form['a_sexo'] })}>
                  <option value="">—</option><option value="MUJER">Mujer</option><option value="HOMBRE">Hombre</option>
                  <option value="OTROS">Otros</option>
                </select>
              </Campo>
              <Campo etiqueta="Fecha de nacimiento">
                <input type="date" style={input} value={f.a_fecha_nac} onChange={(e) => set({ a_fecha_nac: e.target.value })} />
              </Campo>
              <Campo etiqueta="Teléfono" error={f.a_telefono ? err('a_telefono') : undefined}>
                <input style={input} value={f.a_telefono} maxLength={15}
                       onChange={(e) => set({ a_telefono: e.target.value.replace(/[^0-9]/g, '') })} />
              </Campo>
              <Campo etiqueta="Email" error={f.a_email ? err('a_email') : undefined}>
                <input style={input} type="email" value={f.a_email} maxLength={150} onChange={(e) => set({ a_email: e.target.value })} />
              </Campo>
            </div>
          </>
        )}
      </div>

      {faltan.length > 0 && (
        <div data-faltan role="status" style={{ fontSize: 13, color: 'var(--fg-2)' }}>
          Para seguir falta: {faltan.map(([c, m], i) => (
            <span key={c}>{i > 0 && ' · '}<strong>{ETIQUETAS[c] ?? c}</strong> ({m.charAt(0).toLowerCase() + m.slice(1)})</span>
          ))}
        </div>
      )}
      {faltan.length === 0 && paso === 0 && !libres && (
        <div role="status" style={{ fontSize: 13, color: 'var(--fg-3)' }}>
          Comprobando que el código, el subdominio y el {nivel2} estén libres…
        </div>
      )}
      <div style={{ display: 'flex', gap: 8, justifyContent: 'space-between', flexWrap: 'wrap' }}>
        <Button variant="ghost" type="button" onClick={() => (paso === 0 ? navigate('/municipios') : setPaso(paso - 1))}>
          {paso === 0 ? 'Cancelar' : '← Anterior'}
        </Button>
        {paso < PASOS.length - 1 ? (
          <Button variant="primary" type="button" disabled={!pasoValido(paso)} onClick={() => setPaso(paso + 1)}>
            Siguiente →
          </Button>
        ) : (
          <Button variant="primary" type="button" disabled={alta.isPending || !PASOS.every((_, i) => pasoValido(i))}
                  onClick={enviar}>
            {alta.isPending ? 'Dando de alta…' : 'Dar de alta'}
          </Button>
        )}
      </div>
    </div>
  )
}

export function Advertencias({ lista }: { lista: string[] }) {
  return (
    <div role="alert" data-advertencias style={{
      padding: '10px 12px', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-warning, #c08a00)',
      background: 'var(--surface-400)', fontSize: 13, display: 'flex', flexDirection: 'column', gap: 4,
    }}>
      {lista.map((a) => <span key={a}><Badge kind="warn">Atención</Badge> {a}</span>)}
    </div>
  )
}

export function Casilla({ etiqueta, marcada, onChange, deshabilitada, nota }: {
  etiqueta: string; marcada: boolean; onChange: (v: boolean) => void; deshabilitada?: boolean; nota?: string
}) {
  return (
    <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 14, opacity: deshabilitada ? 0.7 : 1 }}>
      <input type="checkbox" checked={marcada} disabled={deshabilitada} onChange={(e) => onChange(e.target.checked)} />
      {etiqueta}{nota && <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>({nota})</span>}
    </label>
  )
}

const pagina: React.CSSProperties = { padding: 24, display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 820 }
const ayudaPaso: React.CSSProperties = { margin: 0, fontSize: 13, color: 'var(--fg-2)' }
const grilla: React.CSSProperties = { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12 }
const chip: React.CSSProperties = {
  fontFamily: 'var(--font-display)', fontSize: 12, padding: '5px 10px', borderRadius: 999, cursor: 'pointer',
  border: '1px solid var(--border-medium)', background: 'var(--surface-100)', color: 'var(--fg-2)',
}
const chipActivo: React.CSSProperties = { borderColor: 'var(--zaris-orange)', color: 'var(--fg-1)', fontWeight: 600 }
