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
    tipo_recurso: Literal["agente", "equipo"]
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
    tipo_recurso: Literal["agente", "equipo"]
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
    tipo_recurso: Optional[Literal["agente", "equipo"]] = None
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


class CalendarioRecurso(BaseModel):
    tipo: str
    id_recurso: int
    nombre: Optional[str] = None
    ocupaciones: list[OcupacionOut] = []
    ausencias: list[AusenciaOut] = []


class CalendarioDiaOut(BaseModel):
    fecha: date
    id_municipio: int
    recursos: list[CalendarioRecurso] = []


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
    """Listado de agentes/equipos con nombre, para selectores por nombre."""
    tipo_recurso: Literal["agente", "equipo"]
    id_recurso: int
    nombre: str


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
