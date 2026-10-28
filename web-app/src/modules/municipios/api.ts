import { api } from '../../lib/api'

// Endpoints exclusivos del super administrador (IT-01 F3/F4, backend/app/api/routes/super_admin.py)
// y el catálogo geográfico (backend/app/api/routes/geo.py).

export type EstadoMunicipio = 'puesta_en_marcha' | 'produccion' | 'demo' | 'modelo' | 'baja'

export const ESTADO_ETIQUETA: Record<EstadoMunicipio, string> = {
  puesta_en_marcha: 'Puesta en marcha',
  produccion: 'Producción',
  demo: 'Demo',
  modelo: 'Modelo',
  baja: 'Baja',
}

export interface MunicipioSuper {
  id_municipio: number
  nombre: string
  codigo_corto: string | null
  subdominio: string | null
  codigo_pais: string
  pais: string | null
  pais_nombre: string | null
  etiqueta_nivel_1: string | null
  etiqueta_nivel_2: string | null
  id_provincia: number | null
  provincia_nombre: string | null
  id_partido: number | null
  partido_nombre: string | null
  zona_horaria: string
  direccion_base: boolean
  activo: boolean
  estado: EstadoMunicipio
  fue_produccion: boolean
  max_usuarios_activos: number | null
  cuentas_activas: number
}

export interface MunicipioSuperUpdate {
  nombre: string
  subdominio: string | null
  codigo_pais: string
  id_provincia: number | null
  id_partido: number | null
  zona_horaria: string
  /** Confirma quitar el contorno oficial del partido anterior al cambiar el partido (409 sin esto). */
  quitar_contorno?: boolean
}

export interface FiltrosMunicipios {
  codigo_pais?: string
  id_provincia?: number
  estado?: EstadoMunicipio
}

export interface Pais {
  codigo_pais: string
  nombre: string
  etiqueta_nivel_1: string
  etiqueta_nivel_2: string
  zona_horaria: string
  habilitado_para_alta: boolean
}

export interface Provincia { id_provincia: number; nombre: string; codigo_pais: string }
export interface Partido {
  id_partido: number; id_provincia: number; nombre: string
  // Catálogo de gobiernos locales (mig 132): código de Georef, el que usa el contorno oficial del IGN.
  nombre_completo: string | null; categoria: string | null; codigo_georef: string | null
}

export const listarMunicipios = (filtros: FiltrosMunicipios = {}) =>
  api.get<MunicipioSuper[]>('/api/v1/super/municipios', { params: { ...filtros } })

export const editarMunicipio = (id: number, body: MunicipioSuperUpdate) =>
  api.put<MunicipioSuper & { aviso_contorno?: string | null }>(`/api/v1/super/municipios/${id}`, body)

export const listarPaises = (paraAlta = false) =>
  api.get<Pais[]>('/api/v1/geo/paises', { params: paraAlta ? { para_alta: true } : {} })

export const listarProvincias = (codigoPais: string) =>
  api.get<Provincia[]>('/api/v1/geo/provincias', { params: { codigo_pais: codigoPais } })

// Una provincia puede tener cientos (Córdoba, 427): se busca por texto, nunca se lista entera.
export const buscarPartidos = (idProvincia: number, q: string, limit = 20) =>
  api.get<Partido[]>('/api/v1/geo/partidos', { params: { id_provincia: idProvincia, q, limit } })

// ── Alta, ficha y super administradores (IT-01 F4+F5, Tarea 15) ───────────────────────────────

export interface OpcionModulo { codigo: string; nombre: string; fijo: boolean; dependencias: string[] }
/** Zona horaria con nombre de región y su desfase de hoy respecto de Greenwich ("-03:00"). */
export interface ZonaHoraria { nombre: string; desfase: string }
export interface OpcionesAlta {
  zonas: ZonaHoraria[]
  catalogos: { codigo: string; nombre: string }[]
  modulos: OpcionModulo[]
}

export interface AltaMunicipioBody {
  nombre: string
  codigo_pais: string
  id_provincia: number
  id_partido: number | null
  /** Municipio de demo o de prueba, sin partido (uno real lleva su partido). */
  ficticio: boolean
  zona_horaria: string | null
  codigo_corto: string
  subdominio: string
  identidad: {
    color: string | null
    logo_url: string | null
    geo_limite_geojson: string | null
    geo_limite_origen: import('./contorno/api').OrigenContorno | null
    geo_bbox_centro_lat: number | null
    geo_bbox_centro_lon: number | null
    geo_bbox_delta_grados: number | null
  }
  copiar: string[]
  modulos: string[]
  max_usuarios_activos: number | null
  administrador: {
    nombre: string; apellido: string; dni: string; cuil: string; sexo: 'HOMBRE' | 'MUJER' | 'OTROS'
    fecha_nac: string; telefono: string; email: string
  }
}
export interface AltaResultado { id_municipio: number; id_administrador: number; advertencias: string[] }

export interface Cupo { activas: number; maximo: number | null; aviso: boolean }
export interface AdministradorMunicipio {
  id_usuario: number; nombre: string; email: string | null; activo: boolean; invitacion_pendiente: boolean
  /** De la última invitación: cuándo se envió y cuándo vence; y si alguna vez la aceptó. */
  invitacion_enviada_en: string | null; invitacion_vence_en: string | null; invitacion_aceptada_en: string | null
}
export interface FichaMunicipio {
  municipio: MunicipioSuper
  modulos: (OpcionModulo & { habilitado: boolean })[]
  administradores: AdministradorMunicipio[]
  cupo: Cupo
  advertencias: string[]
}
export interface Dominio { app: string; host: string; dns: boolean; https: number | null }
export interface Chequeo { nombre: string; ok: boolean; detalle: string }
export interface SuperAdministrador {
  id_usuario: number; nombre: string; email: string | null; activo: boolean; invitacion_pendiente: boolean
}

export const opcionesAlta = () => api.get<OpcionesAlta>('/api/v1/super/alta/opciones')
export interface Disponible { disponible: boolean; motivo: string | null }
export type Disponibilidad = Partial<Record<'codigo_corto' | 'subdominio' | 'id_partido', Disponible>>
export const disponibilidadAlta = (q: { codigo_corto?: string; subdominio?: string; id_partido?: number; excluir?: number }) =>
  api.get<Disponibilidad>('/api/v1/super/alta/disponibilidad', { params: q })
/** «UTC−03:00 · America/Argentina/Buenos_Aires» (signo menos tipográfico). */
export const etiquetaZona = (z: ZonaHoraria) => `UTC${z.desfase.replace('-', '−')} · ${z.nombre}`
export const darDeAlta = (body: AltaMunicipioBody) => api.post<AltaResultado>('/api/v1/super/municipios', body)
export const fichaMunicipio = (id: number) => api.get<FichaMunicipio>(`/api/v1/super/municipios/${id}`)
export const cambiarEstado = (id: number, estado: 'produccion' | 'baja' | 'reactivar', confirmacion?: string) =>
  api.post<MunicipioSuper>(`/api/v1/super/municipios/${id}/estado`, { estado, confirmacion })
export const cambiarModulos = (id: number, modulos: { codigo: string; habilitado: boolean }[]) =>
  api.put<{ habilitados: string[] }>(`/api/v1/super/municipios/${id}/modulos`, { modulos })
export const cambiarTope = (id: number, maximo: number | null) =>
  api.put<MunicipioSuper>(`/api/v1/super/municipios/${id}/tope`, { maximo })
export const verificarDominios = (id: number) => api.get<Dominio[]>(`/api/v1/super/municipios/${id}/dominios`)
export const probarPuestaEnMarcha = (id: number) => api.post<Chequeo[]>(`/api/v1/super/municipios/${id}/prueba`)
/** Envía (o vuelve a enviar) la invitación. A un administrador de municipio, solo con sus tres
 *  direcciones respondiendo (409 si no). */
export const reenviarInvitacion = (idUsuario: number) =>
  api.post<{ enviada: boolean; enviada_en: string | null }>(`/api/v1/super/usuarios/${idUsuario}/invitacion`)
/** La dirección resuelve y responde por HTTPS sin error (la misma regla que el backend). */
export const dominioOk = (d: Dominio) => !!d.host && d.dns && d.https != null && d.https < 400
export const listarSupers = () => api.get<SuperAdministrador[]>('/api/v1/super/administradores')
export const altaSuper = (body: { nombre: string; apellido: string; email: string }) =>
  api.post<{ id_usuario: number }>('/api/v1/super/administradores', body)
export const bajaSuper = (id: number) => api.post<{ baja: boolean }>(`/api/v1/super/administradores/${id}/baja`)

// ── Exportación y vaciado (IT-01 F4+F5, Tarea 16) ─────────────────────────────────────────────

export type GrupoVaciable = 'operativo' | 'contactos' | 'maestros' | 'usuarios'
export interface Tarea {
  id_tarea: string; id_municipio: number; tipo: 'alta' | 'exportacion' | 'vaciado'
  estado: 'pendiente' | 'corriendo' | 'ok' | 'error'
  detalle: Record<string, unknown> | null; archivo: string | null; vence_en: string | null
  fecha_alta: string; fecha_modificacion: string
}
export interface Exportacion {
  id_tarea: string; estado: Tarea['estado']; detalle: Record<string, unknown> | null
  archivo: string | null; vence_en: string | null; fecha_alta: string
}
export interface PasoPlan { tabla: string; filas: number; accion: 'borrar' | 'desvincular' }

export const obtenerTarea = (id: string) => api.get<Tarea>(`/api/v1/super/tareas/${id}`)
export const listarExportaciones = (idMun: number) =>
  api.get<Exportacion[]>(`/api/v1/super/municipios/${idMun}/exportaciones`)
export const pedirExportacion = (idMun: number) =>
  api.post<{ id_tarea: string }>(`/api/v1/super/municipios/${idMun}/exportaciones`)
export const urlDescarga = (idMun: number, idTarea: string) =>
  api.get<{ url: string }>(`/api/v1/super/municipios/${idMun}/exportaciones/${idTarea}/descarga`)
export const planVaciado = (idMun: number, grupos: GrupoVaciable[]) =>
  api.post<PasoPlan[]>(`/api/v1/super/municipios/${idMun}/vaciado/plan`, { grupos })
export const pedirVaciado = (idMun: number, grupos: GrupoVaciable[], confirmacion: string) =>
  api.post<{ id_tarea: string }>(`/api/v1/super/municipios/${idMun}/vaciado`, { grupos, confirmacion })
