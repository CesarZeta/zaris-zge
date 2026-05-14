"""
Schemas Pydantic v2 para el modulo Turnos (mig 45).

Un turno reserva un bloque de la disponibilidad de un agente para que un
ciudadano realice un tramite (tipo de servicio). Estados: reservado, cumplido,
cancelado. El backend mantiene una fila espejo en `ocupaciones` (tipo='turno')
para que el turno aparezca en la grilla del modulo Agenda.
"""
from __future__ import annotations

from datetime import date, time, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# =============================================================================
# tipo_servicio_turno (catalogo — se gestiona desde admin_tablas, esto es solo
# para consumirlo en el modulo)
# =============================================================================
class TipoServicioTurnoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_tipo_servicio_turno: int
    nombre: str
    descripcion: Optional[str] = None
    duracion_min: int
    activo: bool


# =============================================================================
# turnos
# =============================================================================
class TurnoCreate(BaseModel):
    id_ciudadano: int
    id_agente: int
    id_tipo_servicio_turno: int
    fecha: date
    hora_inicio: time
    hora_fin: Optional[time] = Field(
        None,
        description="Opcional: si se omite se calcula con duracion_min del tipo de servicio",
    )
    observaciones: Optional[str] = None
    id_municipio: int = 1
    id_subarea: Optional[int] = None

    @model_validator(mode="after")
    def _validar(self) -> "TurnoCreate":
        if self.hora_fin is not None and self.hora_fin <= self.hora_inicio:
            raise ValueError("hora_fin debe ser mayor que hora_inicio")
        return self


class TurnoUpdate(BaseModel):
    """Edicion de un turno en estado 'reservado' (reprogramar)."""
    id_tipo_servicio_turno: Optional[int] = None
    fecha: Optional[date] = None
    hora_inicio: Optional[time] = None
    hora_fin: Optional[time] = None
    observaciones: Optional[str] = None


class TurnoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_turno: int
    id_ciudadano: int
    ciudadano_nombre: Optional[str] = None
    ciudadano_dni: Optional[str] = None
    id_agente: int
    agente_nombre: Optional[str] = None
    id_tipo_servicio_turno: int
    tipo_servicio_nombre: Optional[str] = None
    id_ocupacion: Optional[int] = None
    fecha: date
    hora_inicio: time
    hora_fin: time
    estado: Literal["reservado", "cumplido", "cancelado"]
    observaciones: Optional[str] = None
    activo: bool
    id_municipio: int
    id_subarea: Optional[int] = None
    fecha_alta: datetime
    fecha_modificacion: datetime


# =============================================================================
# Autoservicio publico (sin JWT) — el ciudadano elige tipo de servicio, dia y
# slot libre. El backend cruza disponibilidad_recurso con ocupaciones.
# =============================================================================
class AgenteDisponibleOut(BaseModel):
    """Agente que atiende un tipo de servicio (vista publica minima)."""
    id_agente: int
    nombre: str


class SlotLibreOut(BaseModel):
    """Un slot horario libre para reservar un turno."""
    id_agente: int
    agente_nombre: str
    fecha: date
    hora_inicio: time
    hora_fin: time


class TurnoPublicoCreate(BaseModel):
    """Reserva de turno por autoservicio. Busca/crea ciudadano por DNI."""
    id_tipo_servicio_turno: int
    id_agente: int
    fecha: date
    hora_inicio: time
    dni: str = Field(..., min_length=6, max_length=20)
    apellido: str = Field(..., min_length=1, max_length=100)
    nombre: str = Field(..., min_length=1, max_length=100)
    telefono: Optional[str] = None
    email: Optional[str] = None
    observaciones: Optional[str] = None


class TurnoPublicoOut(BaseModel):
    """Datos de un turno reservado por autoservicio (incluye token para
    consultar/cancelar despues)."""
    id_turno: int
    token_turno: str
    estado: Literal["reservado", "cumplido", "cancelado"]
    fecha: date
    hora_inicio: time
    hora_fin: time
    tipo_servicio_nombre: Optional[str] = None
    agente_nombre: Optional[str] = None
    ciudadano_apellido: Optional[str] = None
    ciudadano_nombre: Optional[str] = None
    ciudadano_dni: Optional[str] = None
