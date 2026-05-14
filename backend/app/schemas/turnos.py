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
