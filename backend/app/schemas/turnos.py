"""
Schemas Pydantic v2 para el modulo Turnos (mig 45, replanteado en mig 71).

Una PRESTACION (tipo_prestacion) define el recurso fijo (un agente O un lugar
de atencion), su duracion y su clase (atencion de personas vs. reserva de un
espacio). Un turno reserva un bloque de la disponibilidad efectiva de ese
recurso para que un ciudadano realice la prestacion. Estados: reservado,
cumplido, cancelado. El backend mantiene una fila espejo en `ocupaciones`
(tipo='turno') para que el turno aparezca en la grilla del modulo Agenda.
"""
from __future__ import annotations

from datetime import date, time, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


ClasePrestacion = Literal["atencion", "reserva_espacio"]
TipoRecurso = Literal["agente", "espacio"]


# =============================================================================
# tipo_prestacion (catalogo) — ABM en el modulo Turnos (tab Prestaciones)
# =============================================================================
class TipoPrestacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_tipo_prestacion: int
    nombre: str
    descripcion: Optional[str] = None
    clase: ClasePrestacion
    duracion_min: int
    tipo_recurso: Optional[TipoRecurso] = None
    id_agente: Optional[int] = None
    id_espacio: Optional[int] = None
    recurso_nombre: Optional[str] = None
    id_subarea: Optional[int] = None
    activo: bool


class _PrestacionRecursoMixin(BaseModel):
    """Valida que el recurso sea coherente con la clase y que se indique
    exactamente uno de agente/espacio segun tipo_recurso."""

    @model_validator(mode="after")
    def _validar_recurso(self):  # type: ignore[override]
        tr = getattr(self, "tipo_recurso", None)
        ia = getattr(self, "id_agente", None)
        ie = getattr(self, "id_espacio", None)
        clase = getattr(self, "clase", None)
        if tr == "agente" and (ia is None or ie is not None):
            raise ValueError("tipo_recurso='agente' requiere id_agente y no id_espacio")
        if tr == "espacio" and (ie is None or ia is not None):
            raise ValueError("tipo_recurso='espacio' requiere id_espacio y no id_agente")
        if tr is None:
            raise ValueError("Indicar tipo_recurso ('agente' o 'espacio')")
        if clase == "reserva_espacio" and tr != "espacio":
            raise ValueError("La clase 'reserva_espacio' requiere tipo_recurso='espacio'")
        return self


class TipoPrestacionCreate(_PrestacionRecursoMixin):
    nombre: str = Field(..., min_length=1, max_length=150)
    descripcion: Optional[str] = None
    clase: ClasePrestacion = "atencion"
    duracion_min: int = Field(30, gt=0)
    tipo_recurso: TipoRecurso
    id_agente: Optional[int] = None
    id_espacio: Optional[int] = None
    id_municipio: int = 1
    id_subarea: Optional[int] = None


class TipoPrestacionUpdate(_PrestacionRecursoMixin):
    nombre: str = Field(..., min_length=1, max_length=150)
    descripcion: Optional[str] = None
    clase: ClasePrestacion = "atencion"
    duracion_min: int = Field(30, gt=0)
    tipo_recurso: TipoRecurso
    id_agente: Optional[int] = None
    id_espacio: Optional[int] = None
    id_subarea: Optional[int] = None


# =============================================================================
# turnos — el cliente ya NO manda recurso; sale de la prestacion
# =============================================================================
class TurnoCreate(BaseModel):
    id_ciudadano: int
    id_tipo_prestacion: int
    fecha: date
    hora_inicio: time
    hora_fin: Optional[time] = Field(
        None,
        description="Opcional: si se omite se calcula con duracion_min de la prestacion",
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
    """Edicion de un turno en estado 'reservado' (reprogramar). El recurso no
    cambia (es el de la prestacion); si cambia la prestacion se re-resuelve."""
    id_tipo_prestacion: Optional[int] = None
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
    id_agente: Optional[int] = None
    agente_nombre: Optional[str] = None
    id_espacio: Optional[int] = None
    espacio_nombre: Optional[str] = None
    recurso_tipo: Optional[str] = None  # 'agente' | 'espacio'
    recurso_nombre: Optional[str] = None
    id_tipo_prestacion: int
    prestacion_nombre: Optional[str] = None
    prestacion_clase: Optional[str] = None
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
# Autoservicio publico (sin JWT) — el ciudadano elige prestacion, dia y slot.
# El recurso lo trae la prestacion; el backend cruza disponibilidad con
# ocupaciones para calcular los slots libres.
# =============================================================================
class PrestacionPublicaOut(BaseModel):
    """Prestacion publicable: activa y con recurso que tiene disponibilidad."""
    id_tipo_prestacion: int
    nombre: str
    descripcion: Optional[str] = None
    clase: ClasePrestacion
    duracion_min: int
    recurso_nombre: Optional[str] = None


class SlotLibreOut(BaseModel):
    """Un slot horario libre para reservar un turno (recurso de la prestacion)."""
    tipo_recurso: str = "agente"   # 'agente' | 'espacio'
    id_recurso: int
    recurso_nombre: str
    fecha: date
    hora_inicio: time
    hora_fin: time


class TurnoPublicoCreate(BaseModel):
    """Reserva de turno por autoservicio. Busca/crea ciudadano por DNI.
    El recurso lo trae la prestacion (el cliente NO lo manda)."""
    id_tipo_prestacion: int
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
    prestacion_nombre: Optional[str] = None
    recurso_nombre: Optional[str] = None
    ciudadano_apellido: Optional[str] = None
    ciudadano_nombre: Optional[str] = None
    ciudadano_dni: Optional[str] = None
