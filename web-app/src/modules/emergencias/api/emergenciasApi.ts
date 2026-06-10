import { api } from '../../../lib/api'
import type {
  ContactoEventual,
  ContactoEventualCreateBody,
  DenuncianteBusqueda,
  EmergenciaCanal,
  EmergenciaEstado,
  EmergenciaEvento,
  EmergenciaEventoDetalle,
  EmergenciaLogEntry,
  EmergenciaOrganismo,
  EmergenciaPrioridad,
  EmergenciaSubtipo,
  EmergenciaTipo,
  EventoCreateBody,
  ListarEventosFiltros,
} from '../types'

const P = '/api/v1/emergencias'

// --- catalogos ---
export const listarTipos = (id_subarea?: number) =>
  api.get<EmergenciaTipo[]>(`${P}/tipos`, { params: { id_subarea } })
export const listarSubtiposDeTipo = (id_tipo: number) =>
  api.get<EmergenciaSubtipo[]>(`${P}/tipos/${id_tipo}/subtipos`)
export const listarPrioridades = () =>
  api.get<EmergenciaPrioridad[]>(`${P}/prioridades`)
export const listarEstados = () =>
  api.get<EmergenciaEstado[]>(`${P}/estados`)
export const listarOrganismos = () =>
  api.get<EmergenciaOrganismo[]>(`${P}/organismos`)
export const listarCanales = () =>
  api.get<EmergenciaCanal[]>(`${P}/canales`)

// --- denunciantes / contactos eventuales ---
export const buscarDenunciante = (criterio: 'dni' | 'telefono' | 'nombre', valor: string) =>
  api.get<DenuncianteBusqueda>(`${P}/denunciantes/buscar`, { params: { [criterio]: valor } })
export const crearContactoEventual = (body: ContactoEventualCreateBody) =>
  api.post<ContactoEventual>(`${P}/contactos-eventuales`, body)
export const promoverContactoABuc = (
  id: number,
  body: { id_ciudadano?: number; apellido?: string; nombre?: string; email?: string },
) =>
  api.post<{ id_ciudadano: number; ciudadano_creado: boolean; eventos_reasignados: number }>(
    `${P}/contactos-eventuales/${id}/promover-a-buc`, body)

// --- eventos ---
export const crearEvento = (body: EventoCreateBody) =>
  api.post<EmergenciaEvento>(`${P}/eventos`, body)
export const listarEventosAbiertos = (params: { id_subarea?: number; id_prioridad?: number } = {}) =>
  api.get<EmergenciaEvento[]>(`${P}/eventos/abiertos`, { params })
export const listarEventos = (filtros: ListarEventosFiltros = {}) =>
  api.get<EmergenciaEvento[]>(`${P}/eventos`, { params: { ...filtros } })
export const detalleEvento = (id: number) =>
  api.get<EmergenciaEventoDetalle>(`${P}/eventos/${id}`)
export const logEvento = (id: number) =>
  api.get<EmergenciaLogEntry[]>(`${P}/eventos/${id}/log`)
export const cambiarEstadoEvento = (id: number, nuevo_estado: string, observaciones?: string) =>
  api.post<EmergenciaEvento>(`${P}/eventos/${id}/cambiar-estado`, { nuevo_estado, observaciones })
export const derivarEvento = (id: number, id_organismo: number, observaciones?: string) =>
  api.post<EmergenciaEvento>(`${P}/eventos/${id}/derivar`, { id_organismo, observaciones })
export const cerrarEvento = (
  id: number,
  body: { veracidad: string; terminal_positivo: boolean; observaciones_cierre?: string },
) =>
  api.post<EmergenciaEvento>(`${P}/eventos/${id}/cerrar`, body)
export const marcarEnSitio = (id: number) =>
  api.post<EmergenciaEvento>(`${P}/eventos/${id}/marcar-en-sitio`)
export const agregarNotaEvento = (id: number, observaciones: string) =>
  api.post<{ ok: boolean }>(`${P}/eventos/${id}/agregar-nota`, { observaciones })
