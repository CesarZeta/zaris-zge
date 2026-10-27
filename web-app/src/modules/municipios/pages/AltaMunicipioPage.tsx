import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Badge, Button, EmptyState, Skeleton } from '../../../ui'
import { useNotificationsStore } from '../../../stores/notifications'
import {
  darDeAlta, listarPaises, listarPartidos, listarProvincias, opcionesAlta,
  type AltaMunicipioBody, type AltaResultado, type OpcionModulo,
} from '../api'
import { Campo, input, seccion, titulo } from './_comun'

// Asistente de alta de un municipio (IT-01 F4+F5, Tarea 15; spec §4.4). Seis pasos y el alta en una
// sola llamada: el backend valida todo antes de escribir y, si algo falla, no queda nada. El
// subdominio se arma solo desde el nombre hasta que el super lo edita (auto-slug, §23).

const PASOS = ['Datos', 'Identidad', 'Qué copiar', 'Módulos', 'Tope de cuentas', 'Primer administrador'] as const

// Los mismos de backend/app/services/municipios/constantes.py.
const PATRON_SUBDOMINIO = /^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$/
const PATRON_CODIGO = /^[A-Z]{2,3}$/
const RESERVADOS = new Set(['www', 'api', 'zge', 'vecinos', 'agentes', 'admin', 'app', 'mail', 'soporte',
  'status', 'demo', 'modelo'])
const SIN_CONTORNO = 'Sin contorno ni bbox: el geocoding usará la zona por defecto (Vicente López).'

const aSubdominio = (s: string) => s.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase()
  .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 63)

interface Form {
  nombre: string; codigo_pais: string; id_provincia: number | null; id_partido: number | null
  zona_horaria: string; codigo_corto: string; subdominio: string
  color: string; logo_url: string; geojson: string; lat: string; lon: string; delta: string
  copiar: string[]; modulos: string[]; tope: string
  a_nombre: string; a_apellido: string; a_dni: string; a_cuil: string; a_sexo: '' | 'HOMBRE' | 'MUJER' | 'OTROS'
  a_fecha_nac: string; a_telefono: string; a_email: string
}

const VACIO: Form = {
  nombre: '', codigo_pais: '', id_provincia: null, id_partido: null, zona_horaria: '', codigo_corto: '',
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
    if (!PATRON_CODIGO.test(f.codigo_corto)) e.codigo_corto = '2 o 3 letras mayúsculas'
    if (!PATRON_SUBDOMINIO.test(f.subdominio)) e.subdominio = 'Solo minúsculas, números y guiones, sin espacios'
    else if (RESERVADOS.has(f.subdominio)) e.subdominio = 'Ese subdominio está reservado'
    if (f.color && !/^#[0-9A-Fa-f]{6}$/.test(f.color)) e.color = 'Formato #RRGGBB'
    const coords = [f.lat, f.lon, f.delta].filter((v) => v.trim() !== '').length
    if (coords > 0 && coords < 3) e.lat = 'Completá centro (latitud y longitud) y radio, o dejá los tres vacíos'
    if (f.tope.trim() !== '' && !(Number.isInteger(Number(f.tope)) && Number(f.tope) >= 1)) e.tope = 'Un número entero, 1 o más'
    if (!f.a_nombre.trim()) e.a_nombre = 'Obligatorio'
    if (!f.a_apellido.trim()) e.a_apellido = 'Obligatorio'
    if (!/^[0-9]{7,8}$/.test(f.a_dni)) e.a_dni = '7 u 8 dígitos'
    if (!/^[0-9]{11}$/.test(f.a_cuil)) e.a_cuil = '11 dígitos, sin guiones'
    if (!f.a_sexo) e.a_sexo = 'Elegí una opción'
    if (!f.a_fecha_nac) e.a_fecha_nac = 'Obligatoria'
    if (f.a_telefono.trim().length < 6) e.a_telefono = 'Al menos 6 dígitos'
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(f.a_email.trim())) e.a_email = 'Email inválido'
    return e
  }, [f, pais])

  const camposDelPaso: (keyof Form)[][] = [
    ['nombre', 'codigo_pais', 'id_provincia', 'codigo_corto', 'subdominio'],
    ['color', 'lat'],
    [],
    [],
    ['tope'],
    ['a_nombre', 'a_apellido', 'a_dni', 'a_cuil', 'a_sexo', 'a_fecha_nac', 'a_telefono', 'a_email'],
  ]
  const errorDependencia = opciones.data ? faltaDependencia(f.modulos, opciones.data.modulos) : null
  const pasoValido = (i: number) => camposDelPaso[i].every((c) => !errores[c]) && (i !== 3 || !errorDependencia)
  const sinContorno = !f.geojson.trim() && f.lat.trim() === ''

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
      nombre: f.nombre.trim(), codigo_pais: f.codigo_pais, id_provincia: f.id_provincia!, id_partido: f.id_partido,
      zona_horaria: f.zona_horaria.trim() || null, codigo_corto: f.codigo_corto, subdominio: f.subdominio,
      identidad: {
        color: f.color || null, logo_url: f.logo_url.trim() || null, geo_limite_geojson: f.geojson.trim() || null,
        geo_bbox_centro_lat: num(f.lat), geo_bbox_centro_lon: num(f.lon), geo_bbox_delta_grados: num(f.delta),
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
            <strong>{f.nombre}</strong> quedó en puesta en marcha. Le mandamos la invitación al primer
            administrador ({f.a_email.trim().toLowerCase()}): vence en 72 horas.
          </p>
          {resultado.advertencias.length > 0 && <Advertencias lista={resultado.advertencias} />}
          <p style={{ margin: 0, fontSize: 13, color: 'var(--fg-2)' }}>
            Falta crear sus tres direcciones con <code>tools/dominios_municipio.py {f.subdominio}</code>. Después,
            en la ficha, «Verificar» y «Probar puesta en marcha».
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
            <Campo etiqueta="Nombre" error={f.nombre ? err('nombre') : undefined}>
              <input style={input} value={f.nombre} maxLength={150} autoFocus
                     onChange={(e) => set({ nombre: e.target.value,
                       ...(subdominioTocado.current ? {} : { subdominio: aSubdominio(e.target.value) }) })} />
            </Campo>
            <Campo etiqueta="País" ayuda="Solo los habilitados para dar de alta municipios.">
              <select style={input} value={f.codigo_pais}
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
            <Campo etiqueta={`${pais?.etiqueta_nivel_2 ?? 'Partido'} (opcional)`}>
              <select style={input} value={f.id_partido ?? ''} disabled={f.id_provincia == null}
                      onChange={(e) => set({ id_partido: e.target.value ? Number(e.target.value) : null })}>
                <option value="">—</option>
                {(partidos.data ?? []).map((p) => <option key={p.id_partido} value={p.id_partido}>{p.nombre}</option>)}
              </select>
            </Campo>
            <Campo etiqueta="Zona horaria" ayuda="Por defecto, la del país.">
              <input style={{ ...input, fontFamily: 'var(--font-mono)' }} value={f.zona_horaria} maxLength={64}
                     onChange={(e) => set({ zona_horaria: e.target.value })} />
            </Campo>
            <Campo etiqueta="Código corto" ayuda="Prefijo de los números (REC-XXX-…). No se puede cambiar después."
                   error={f.codigo_corto ? err('codigo_corto') : undefined}>
              <input style={{ ...input, fontFamily: 'var(--font-mono)' }} value={f.codigo_corto} maxLength={3}
                     onChange={(e) => set({ codigo_corto: e.target.value.toUpperCase().replace(/[^A-Z]/g, '') })} />
            </Campo>
            <Campo etiqueta="Subdominio" ayuda={f.subdominio ? `${f.subdominio}.zge.zaris.com.ar` : 'Se arma desde el nombre'}
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
                   ayuda="Restringe las búsquedas de direcciones a la zona del municipio.">
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <input style={{ ...input, width: 140 }} placeholder="Latitud" value={f.lat} onChange={(e) => set({ lat: e.target.value })} />
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
              Se crea su ficha en la BUC del municipio, su agente y su cuenta de administrador. Recibe un mail para
              elegir la clave y vincular la app de autenticación: nadie más conoce la clave.
            </p>
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
