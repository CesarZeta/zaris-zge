"""
Schemas Pydantic v2 para los endpoints de la sub-fase 1.A del modulo Agenda.

Vive en archivo separado de schemas/agenda.py (legacy) para no mezclar con los
schemas de tablas legacy. Cuando 1.B unifique todo, se puede consolidar.
"""
from __future__ import annotations

from datetime import date, time, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# =============================================================================
# Catalogos
# =============================================================================
class EstadoCatalogoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    descripcion: Optional[str] = None
    orden: Optional[int] = None


# =============================================================================
# Eventos
# =============================================================================
class EventoBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=200)
    descripcion: Optional[str] = None
    id_subarea: Optional[int] = None
    fecha: date
    hora_inicio: time
    hora_fin: time
    capacidad_ciudadanos: int = Field(1, ge=0)
    cantidad_encargados: int = Field(0, ge=0)
    tipo_qr: Literal["nominal", "generico", "ninguno"] = "ninguno"
    admite_autoservicio: bool = False

    @model_validator(mode="after")
    def _horario_valido(self) -> "EventoBase":
        if self.hora_fin <= self.hora_inicio:
            raise ValueError("hora_fin debe ser mayor que hora_inicio")
        return self


class EventoCreate(EventoBase):
    """POST /eventos. Estado default = 'activo' (resuelto en backend)."""
    id_municipio: int = 1


class EventoUpdate(BaseModel):
    """PUT /eventos/{id}. Todos opcionales."""
    nombre: Optional[str] = Field(None, min_length=1, max_length=200)
    descripcion: Optional[str] = None
    id_subarea: Optional[int] = None
    fecha: Optional[date] = None
    hora_inicio: Optional[time] = None
    hora_fin: Optional[time] = None
    capacidad_ciudadanos: Optional[int] = Field(None, ge=0)
    cantidad_encargados: Optional[int] = Field(None, ge=0)
    tipo_qr: Optional[Literal["nominal", "generico", "ninguno"]] = None
    admite_autoservicio: Optional[bool] = None


class EventoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_evento: int
    nombre: str
    descripcion: Optional[str]
    id_subarea: Optional[int]
    fecha: date
    hora_inicio: time
    hora_fin: time
    capacidad_ciudadanos: int
    cantidad_encargados: int
    tipo_qr: str
    admite_autoservicio: bool
    token_publico: Optional[str] = None  # solo poblado cuando admite_autoservicio=TRUE
    id_estado_evento: int
    estado_codigo: Optional[str] = None
    activo: bool
    id_municipio: int
    fecha_alta: datetime
    fecha_modificacion: datetime


class EventoDetalleOut(EventoOut):
    cupo_disponible: int
    reservas_activas: int
    encargados: list["EventoEncargadoOut"] = []


# =============================================================================
# Encargados de evento
# =============================================================================
class EventoEncargadoCreate(BaseModel):
    tipo_recurso: Literal["agente", "equipo", "espacio"]
    id_recurso: int


class EventoEncargadoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_evento_encargado: int
    id_evento: int
    tipo_recurso: str
    id_recurso: int
    recurso_nombre: Optional[str] = None
    activo: bool
    fecha_alta: datetime


class EncargadoConflictoWarning(BaseModel):
    encargado: EventoEncargadoOut
    ocupacion_creada_id: int
    conflictos: list[dict[str, Any]] = []
    mensaje: Optional[str] = None


# =============================================================================
# Reservas
# =============================================================================
class ReservaCreate(BaseModel):
    id_ciudadano: int
    origen: Literal["backoffice", "autoservicio"] = "backoffice"


class ReservaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_evento_reserva: int
    id_evento: int
    id_ciudadano: int
    ciudadano_apellido: Optional[str] = None
    ciudadano_nombre: Optional[str] = None
    ciudadano_dni: Optional[str] = None
    id_estado_reserva: int
    estado_codigo: Optional[str] = None
    origen: str
    qr_codigo: Optional[str]
    activo: bool
    fecha_alta: datetime


# =============================================================================
# Ocupaciones
# =============================================================================
class OcupacionCreate(BaseModel):
    tipo: Literal["ot", "evento", "turno"]
    tipo_recurso: Literal["agente", "equipo", "espacio"]
    id_recurso: int
    fecha: date
    hora_inicio: time
    hora_fin: time
    id_orden_trabajo: Optional[int] = None
    id_evento: Optional[int] = None
    id_ciudadano: Optional[int] = None
    duracion_aplicada_min: Optional[int] = Field(None, ge=0)
    rol_en_evento: Optional[str] = None
    motivo: Optional[str] = None
    id_municipio: int = 1

    @model_validator(mode="after")
    def _validar(self) -> "OcupacionCreate":
        if self.hora_fin <= self.hora_inicio:
            raise ValueError("hora_fin debe ser mayor que hora_inicio")
        # Consistencia tipo -> FK especifica
        if self.tipo == "ot":
            if not self.id_orden_trabajo or self.id_evento or self.id_ciudadano:
                raise ValueError("tipo='ot' requiere id_orden_trabajo y excluye id_evento/id_ciudadano")
        elif self.tipo == "evento":
            if not self.id_evento or self.id_orden_trabajo or self.id_ciudadano:
                raise ValueError("tipo='evento' requiere id_evento y excluye id_orden_trabajo/id_ciudadano")
        elif self.tipo == "turno":
            if not self.id_ciudadano or self.id_evento or self.id_orden_trabajo:
                raise ValueError("tipo='turno' requiere id_ciudadano y excluye id_evento/id_orden_trabajo")
        return self


class OcupacionUpdate(BaseModel):
    fecha: Optional[date] = None
    hora_inicio: Optional[time] = None
    hora_fin: Optional[time] = None
    duracion_aplicada_min: Optional[int] = Field(None, ge=0)
    rol_en_evento: Optional[str] = None
    motivo: Optional[str] = None
    tipo_recurso: Optional[Literal["agente", "equipo", "espacio"]] = None
    id_recurso: Optional[int] = None

    @model_validator(mode="after")
    def _validar_recurso(self) -> "OcupacionUpdate":
        # tipo_recurso e id_recurso deben venir juntos o no venir
        if (self.tipo_recurso is None) != (self.id_recurso is None):
            raise ValueError("tipo_recurso e id_recurso deben enviarse juntos")
        return self


class OcupacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_ocupacion: int
    tipo: str
    tipo_recurso: str
    id_recurso: int
    fecha: date
    hora_inicio: time
    hora_fin: time
    id_orden_trabajo: Optional[int]
    id_evento: Optional[int]
    id_ciudadano: Optional[int]
    duracion_aplicada_min: Optional[int]
    rol_en_evento: Optional[str]
    motivo: Optional[str]
    descripcion_corta: Optional[str] = None
    activo: bool
    id_municipio: int
    fecha_alta: datetime


class OcupacionCreatedOut(BaseModel):
    ocupacion: OcupacionOut
    conflictos: list[dict[str, Any]] = []
    mensaje: Optional[str] = None


# =============================================================================
# Conflictos
# =============================================================================
class ConflictoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_conflicto: int
    fecha_deteccion: datetime
    tipo_recurso: str
    id_recurso: int
    id_ocupacion_origen: Optional[int]
    id_ocupacion_conflicto: Optional[int]
    resuelto: bool
    observaciones: Optional[str]
    ocupacion_origen_detalle: Optional[dict[str, Any]] = None
    ocupacion_conflicto_detalle: Optional[dict[str, Any]] = None


class ConflictoResolverIn(BaseModel):
    observaciones: Optional[str] = None


# =============================================================================
# Vista del coordinador
# =============================================================================
class AusenciaOut(BaseModel):
    id_ausencia: int
    fecha_desde: date
    fecha_hasta: date
    motivo: Optional[str]
    genera_alerta: Optional[bool]


class RecursoAgendaOut(BaseModel):
    tipo_recurso: str
    id_recurso: int
    nombre: Optional[str] = None
    desde: date
    hasta: date
    ocupaciones: list[OcupacionOut] = []
    ausencias: list[AusenciaOut] = []


class DisponibilidadRangoEfectivo(BaseModel):
    """Un rango horario de disponibilidad calculada para un dia puntual.

    A diferencia de DisponibilidadRecursoOut (que es CRUD), aqui hora_inicio /
    hora_fin ya estan resueltas para el dia consultado (filtrando por
    dias_semana bitmask y vigencias). Se usa en /calendario, /semana, /mes."""
    hora_inicio: time
    hora_fin: time
    etiqueta: Optional[str] = None


class EventoEnCalendarioOut(BaseModel):
    """Vista liviana de un evento para pintarlo como bloque en la grilla.

    cupo_libre = capacidad - reservas_activas. Cuando es 0, el frontend pinta
    el bloque tachado / con badge 'agotado'."""
    id_evento: int
    nombre: str
    fecha: date
    hora_inicio: time
    hora_fin: time
    capacidad_ciudadanos: int
    reservas_activas: int
    cupo_libre: int
    estado_codigo: Optional[str] = None
    id_espacio: Optional[int] = None
    id_subarea: Optional[int] = None
    # Encargados resueltos a (tipo_recurso, id_recurso) pares para que el
    # frontend pueda decidir en que fila pintar el bloque cuando esta filtrando
    # por agentes/equipos. Si el filtro es por espacio, el id_espacio del propio
    # evento alcanza.
    encargados: list[tuple[str, int]] = []


class CalendarioRecurso(BaseModel):
    tipo: str
    id_recurso: int
    nombre: Optional[str] = None
    # Sub-fase B1: agregado para distinguir espacios atendidos vs desatendidos.
    # None para agente/equipo, True/False para espacio.
    atendido: Optional[bool] = None
    ocupaciones: list[OcupacionOut] = []
    ausencias: list[AusenciaOut] = []
    # Sub-fase B1: rangos horarios de disponibilidad resueltos para esta fecha.
    # Lista vacia => sin horario configurado (frontend pinta toda la fila como
    # "fuera de horario" o "siempre disponible" segun convencion).
    disponibilidad: list[DisponibilidadRangoEfectivo] = []


class CalendarioDiaOut(BaseModel):
    fecha: date
    id_municipio: int
    recursos: list[CalendarioRecurso] = []
    # Sub-fase B1: eventos del dia (resumen ligero) — pintar como bloques.
    eventos: list[EventoEnCalendarioOut] = []


class CalendarioSemanaDiaOut(BaseModel):
    """Un dia dentro de la vista semanal. Mismo shape que /calendario pero
    sin volver a listar los recursos (vienen al nivel raiz de la semana)."""
    fecha: date
    ocupaciones: list[OcupacionOut] = []
    ausencias: list[AusenciaOut] = []
    eventos: list[EventoEnCalendarioOut] = []
    # Mapa recurso -> rangos disponibilidad para ESE dia (puede variar por dia
    # cuando hay turnos rotativos).
    disponibilidad_por_recurso: dict[str, list[DisponibilidadRangoEfectivo]] = {}


class CalendarioSemanaOut(BaseModel):
    """Vista semanal: 7 dias contiguos. Los recursos vienen al nivel raiz
    (no se repiten por dia)."""
    desde: date
    hasta: date
    id_municipio: int
    recursos: list[CalendarioRecurso] = []   # sin disponibilidad ni ocupaciones (vienen en dias[])
    dias: list[CalendarioSemanaDiaOut] = []


class CalendarioMesDia(BaseModel):
    fecha: date
    eventos: int = 0
    ocupaciones_total: int = 0
    ocupaciones_por_tipo: dict[str, int] = {}
    ausencias: int = 0


class CalendarioMesOut(BaseModel):
    anio: int
    mes: int
    id_municipio: int
    dias: list[CalendarioMesDia] = []


# =============================================================================
# Catalogos extra (sub-fase 3.B — autocompletar / filtros)
# =============================================================================
class SubareaOut(BaseModel):
    id_subarea: int
    nombre: str
    id_area: Optional[int] = None
    area_nombre: Optional[str] = None


class RecursoOut(BaseModel):
    """Listado de recursos de agenda con nombre, para selectores."""
    tipo_recurso: Literal["agente", "equipo", "espacio"]
    id_recurso: int
    nombre: str
    # Solo poblado cuando tipo_recurso='espacio'.
    atendido: Optional[bool] = None


class RecursosConteosOut(BaseModel):
    """Conteos de recursos activos por tipo, para los pills del toggle de Agenda B2."""
    agentes: int
    equipos: int
    espacios_atendidos: int
    espacios_desatendidos: int


class OTBusquedaOut(BaseModel):
    """Resultado liviano de busqueda de OT — para autocompletar en OcupacionModal."""
    id_ot: int
    nro_ot: Optional[str] = None
    estado_nombre: Optional[str] = None
    reclamo_descripcion: Optional[str] = None
    nro_reclamo: Optional[str] = None
    id_agente: Optional[int] = None
    id_equipo: Optional[int] = None


class EventoBusquedaOut(BaseModel):
    """Resultado liviano de busqueda de evento — para autocompletar en OcupacionModal."""
    id_evento: int
    nombre: str
    fecha: date
    hora_inicio: time
    hora_fin: time
    estado_codigo: Optional[str] = None


# =============================================================================
# Autoservicio publico (sin JWT) — sub-fase 3.B
# =============================================================================
class EventoPublicoOut(BaseModel):
    """Vista publica de un evento (sin datos sensibles).
    No expone capacidad total ni listado de reservas — solo si hay cupo y datos
    minimos para que el ciudadano sepa que esta reservando."""
    model_config = ConfigDict(from_attributes=True)

    id_evento: int
    nombre: str
    descripcion: Optional[str] = None
    fecha: date
    hora_inicio: time
    hora_fin: time
    cupo_disponible: int
    estado_codigo: str
    admite_autoservicio: bool
    tipo_qr: str


class ReservaPublicaCreate(BaseModel):
    """Form publico de reserva. DNI + apellido + nombre obligatorios;
    telefono y email opcionales."""
    dni: str = Field(..., min_length=6, max_length=15)
    apellido: str = Field(..., min_length=1, max_length=120)
    nombre: str = Field(..., min_length=1, max_length=120)
    telefono: Optional[str] = Field(None, max_length=40)
    email: Optional[str] = Field(None, max_length=200)


class ReservaPublicaOut(BaseModel):
    """Devuelta tras crear o consultar una reserva publica."""
    model_config = ConfigDict(from_attributes=True)

    id_evento_reserva: int
    token_reserva: str  # UUID
    qr_codigo: Optional[str] = None
    estado_codigo: str
    origen: str
    ciudadano_apellido: Optional[str] = None
    ciudadano_nombre: Optional[str] = None
    ciudadano_dni: Optional[str] = None
    evento: EventoPublicoOut


# =============================================================================
# Espacios de agenda (mig 40)
# =============================================================================
class EspacioAgendaBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=150)
    descripcion: Optional[str] = None
    direccion: Optional[str] = Field(None, max_length=300)
    capacidad_personas: Optional[int] = Field(None, ge=0)
    atendido: bool = True
    id_subarea: Optional[int] = None


class EspacioAgendaCreate(EspacioAgendaBase):
    id_municipio: int = 1


class EspacioAgendaUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=1, max_length=150)
    descripcion: Optional[str] = None
    direccion: Optional[str] = Field(None, max_length=300)
    capacidad_personas: Optional[int] = Field(None, ge=0)
    atendido: Optional[bool] = None
    id_subarea: Optional[int] = None
    activo: Optional[bool] = None


class EspacioAgendaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_espacio: int
    nombre: str
    descripcion: Optional[str] = None
    direccion: Optional[str] = None
    capacidad_personas: Optional[int] = None
    atendido: bool
    id_subarea: Optional[int] = None
    subarea_nombre: Optional[str] = None
    activo: bool
    id_municipio: int
    fecha_alta: datetime
    fecha_modificacion: datetime
    # Solo poblado por endpoints de detalle (no por listados):
    agentes_vinculados: list["EspacioAgenteOut"] = []


class EspacioAgenteCreate(BaseModel):
    id_agente: int


class EspacioAgenteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_espacio_agente: int
    id_espacio: int
    id_agente: int
    agente_nombre: Optional[str] = None
    activo: bool
    fecha_alta: datetime


# =============================================================================
# Disponibilidad de recurso (mig 41)
# =============================================================================
class DisponibilidadRecursoBase(BaseModel):
    tipo_recurso: Literal["agente", "equipo", "espacio"]
    id_recurso: int
    dias_semana: int = Field(..., ge=0, le=127, description="Bitmask: Lun=1, Mar=2, Mie=4, Jue=8, Vie=16, Sab=32, Dom=64")
    hora_inicio: time
    hora_fin: time
    vigente_desde: Optional[date] = None
    vigente_hasta: Optional[date] = None
    etiqueta: Optional[str] = Field(None, max_length=60)

    @model_validator(mode="after")
    def _validar(self) -> "DisponibilidadRecursoBase":
        if self.hora_fin <= self.hora_inicio:
            raise ValueError("hora_fin debe ser mayor que hora_inicio")
        if self.vigente_desde and self.vigente_hasta and self.vigente_hasta < self.vigente_desde:
            raise ValueError("vigente_hasta debe ser >= vigente_desde")
        return self


class DisponibilidadRecursoCreate(DisponibilidadRecursoBase):
    id_municipio: int = 1
    id_subarea: Optional[int] = None


class DisponibilidadRecursoUpdate(BaseModel):
    dias_semana: Optional[int] = Field(None, ge=0, le=127)
    hora_inicio: Optional[time] = None
    hora_fin: Optional[time] = None
    vigente_desde: Optional[date] = None
    vigente_hasta: Optional[date] = None
    etiqueta: Optional[str] = Field(None, max_length=60)
    activo: Optional[bool] = None


class DisponibilidadRecursoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_disponibilidad: int
    tipo_recurso: str
    id_recurso: int
    dias_semana: int
    hora_inicio: time
    hora_fin: time
    vigente_desde: Optional[date] = None
    vigente_hasta: Optional[date] = None
    etiqueta: Optional[str] = None
    activo: bool
    id_municipio: int
    fecha_alta: datetime
    fecha_modificacion: datetime
