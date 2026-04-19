"""
ZARIS API — Schemas Pydantic para el módulo Agenda.
"""
from datetime import date, datetime, time
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════
# ÁREA
# ═══════════════════════════════════════════════════════════════

class AreaCreate(BaseModel):
    nombre: str = Field(..., max_length=120)
    descripcion: Optional[str] = None


class AreaUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=120)
    descripcion: Optional[str] = None
    activo: Optional[bool] = None


class AreaOut(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str]
    activo: bool
    creado_en: Optional[datetime]
    modificado_en: Optional[datetime]

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════
# CLASE DE AGENDA
# ═══════════════════════════════════════════════════════════════

class AgendaClaseCreate(BaseModel):
    nombre: str = Field(..., max_length=80)
    descripcion: Optional[str] = None
    visible_ciudadano: bool = False
    requiere_rrhh: bool = True
    requiere_servicio: bool = True
    requiere_lugar: bool = False
    duracion_slot_minutos: int = Field(30, ge=5, le=480)
    id_area: Optional[int] = None
    creado_por: Optional[int] = None


class AgendaClaseUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=80)
    descripcion: Optional[str] = None
    visible_ciudadano: Optional[bool] = None
    requiere_rrhh: Optional[bool] = None
    requiere_servicio: Optional[bool] = None
    requiere_lugar: Optional[bool] = None
    duracion_slot_minutos: Optional[int] = Field(None, ge=5, le=480)
    id_area: Optional[int] = None
    activo: Optional[bool] = None
    fecha_baja: Optional[date] = None


class AgendaClaseOut(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str]
    visible_ciudadano: bool
    requiere_rrhh: bool
    requiere_servicio: bool
    requiere_lugar: bool
    duracion_slot_minutos: int
    id_area: Optional[int]
    activo: bool
    fecha_baja: Optional[date]
    creado_en: Optional[datetime]
    modificado_en: Optional[datetime]

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════
# FERIADO
# ═══════════════════════════════════════════════════════════════

class AgendaFeriadoCreate(BaseModel):
    fecha: date
    descripcion: str = Field(..., max_length=200)
    ambito: Literal["NACIONAL", "PROVINCIAL", "MUNICIPAL"] = "NACIONAL"
    creado_por: Optional[int] = None


class AgendaFeriadoUpdate(BaseModel):
    descripcion: Optional[str] = Field(None, max_length=200)
    ambito: Optional[Literal["NACIONAL", "PROVINCIAL", "MUNICIPAL"]] = None
    activo: Optional[bool] = None


class AgendaFeriadoOut(BaseModel):
    id: int
    fecha: date
    descripcion: str
    ambito: str
    activo: bool
    creado_en: Optional[datetime]

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════
# SERVICIO
# ═══════════════════════════════════════════════════════════════

class ServicioCreate(BaseModel):
    nombre: str = Field(..., max_length=120)
    descripcion: Optional[str] = None
    id_area: Optional[int] = None
    capacidad_agentes: int = Field(1, ge=1)
    creado_por: Optional[int] = None


class ServicioUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=120)
    descripcion: Optional[str] = None
    id_area: Optional[int] = None
    capacidad_agentes: Optional[int] = Field(None, ge=1)
    activo: Optional[bool] = None
    fecha_baja: Optional[date] = None


class ServicioOut(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str]
    id_area: Optional[int]
    capacidad_agentes: int
    activo: bool
    fecha_baja: Optional[date]
    creado_en: Optional[datetime]
    modificado_en: Optional[datetime]

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════
# LUGAR DE ATENCIÓN
# ═══════════════════════════════════════════════════════════════

class LugarAtencionCreate(BaseModel):
    nombre: str = Field(..., max_length=120)
    direccion: Optional[str] = Field(None, max_length=200)
    es_atencion: bool = True
    capacidad_servicios: int = Field(1, ge=1)
    id_area: Optional[int] = None
    creado_por: Optional[int] = None


class LugarAtencionUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=120)
    direccion: Optional[str] = Field(None, max_length=200)
    es_atencion: Optional[bool] = None
    capacidad_servicios: Optional[int] = Field(None, ge=1)
    id_area: Optional[int] = None
    activo: Optional[bool] = None
    fecha_baja: Optional[date] = None


class LugarAtencionOut(BaseModel):
    id: int
    nombre: str
    direccion: Optional[str]
    es_atencion: bool
    capacidad_servicios: int
    id_area: Optional[int]
    activo: bool
    fecha_baja: Optional[date]
    creado_en: Optional[datetime]
    modificado_en: Optional[datetime]

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════
# AGENDA AGENTE
# ═══════════════════════════════════════════════════════════════

class AgendaAgenteCreate(BaseModel):
    id_usuario: int
    id_area: int
    id_clase: int
    fecha_desde: date
    fecha_hasta: Optional[date] = None
    hora_inicio: time
    hora_fin: time
    dias_semana: int = Field(31, ge=1, le=127)
    nombre_parametro: Optional[str] = Field(None, max_length=120)
    observaciones: Optional[str] = None
    creado_por: Optional[int] = None


class AgendaAgenteUpdate(BaseModel):
    id_area: Optional[int] = None
    id_clase: Optional[int] = None
    fecha_desde: Optional[date] = None
    fecha_hasta: Optional[date] = None
    hora_inicio: Optional[time] = None
    hora_fin: Optional[time] = None
    dias_semana: Optional[int] = Field(None, ge=1, le=127)
    nombre_parametro: Optional[str] = Field(None, max_length=120)
    observaciones: Optional[str] = None
    activo: Optional[bool] = None
    fecha_baja: Optional[date] = None


class AgendaAgenteOut(BaseModel):
    id: int
    id_usuario: int
    id_area: int
    id_clase: int
    fecha_desde: date
    fecha_hasta: Optional[date]
    hora_inicio: time
    hora_fin: time
    dias_semana: int
    nombre_parametro: Optional[str]
    observaciones: Optional[str]
    activo: bool
    fecha_baja: Optional[date]
    creado_por: Optional[int]
    creado_en: Optional[datetime]
    modificado_en: Optional[datetime]

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════
# AGENDA SERVICIO
# ═══════════════════════════════════════════════════════════════

class AgendaServicioCreate(BaseModel):
    id_servicio: int
    id_area: int
    id_clase: int
    fecha_desde: date
    fecha_hasta: Optional[date] = None
    hora_inicio: time
    hora_fin: time
    dias_semana: int = Field(31, ge=1, le=127)
    duracion_slot_minutos: Optional[int] = Field(None, ge=5, le=480)
    nombre_parametro: Optional[str] = Field(None, max_length=120)
    observaciones: Optional[str] = None
    ids_agenda_agente: Optional[List[int]] = None
    creado_por: Optional[int] = None


class AgendaServicioUpdate(BaseModel):
    id_servicio: Optional[int] = None
    id_area: Optional[int] = None
    id_clase: Optional[int] = None
    fecha_desde: Optional[date] = None
    fecha_hasta: Optional[date] = None
    hora_inicio: Optional[time] = None
    hora_fin: Optional[time] = None
    dias_semana: Optional[int] = Field(None, ge=1, le=127)
    duracion_slot_minutos: Optional[int] = Field(None, ge=5, le=480)
    nombre_parametro: Optional[str] = Field(None, max_length=120)
    observaciones: Optional[str] = None
    activo: Optional[bool] = None
    fecha_baja: Optional[date] = None


class AgendaServicioOut(BaseModel):
    id: int
    id_servicio: int
    id_area: int
    id_clase: int
    fecha_desde: date
    fecha_hasta: Optional[date]
    hora_inicio: time
    hora_fin: time
    dias_semana: int
    duracion_slot_minutos: Optional[int]
    nombre_parametro: Optional[str]
    observaciones: Optional[str]
    activo: bool
    fecha_baja: Optional[date]
    creado_por: Optional[int]
    creado_en: Optional[datetime]
    modificado_en: Optional[datetime]

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════
# AGENDA LUGAR
# ═══════════════════════════════════════════════════════════════

class AgendaLugarCreate(BaseModel):
    id_lugar: int
    id_area: int
    id_clase: int
    independiente_de_servicio: bool = False
    fecha_desde: date
    fecha_hasta: Optional[date] = None
    hora_inicio: time
    hora_fin: time
    dias_semana: int = Field(31, ge=1, le=127)
    nombre_parametro: Optional[str] = Field(None, max_length=120)
    observaciones: Optional[str] = None
    ids_agenda_servicio: Optional[List[int]] = None
    creado_por: Optional[int] = None


class AgendaLugarUpdate(BaseModel):
    id_lugar: Optional[int] = None
    id_area: Optional[int] = None
    id_clase: Optional[int] = None
    independiente_de_servicio: Optional[bool] = None
    fecha_desde: Optional[date] = None
    fecha_hasta: Optional[date] = None
    hora_inicio: Optional[time] = None
    hora_fin: Optional[time] = None
    dias_semana: Optional[int] = Field(None, ge=1, le=127)
    nombre_parametro: Optional[str] = Field(None, max_length=120)
    observaciones: Optional[str] = None
    activo: Optional[bool] = None
    fecha_baja: Optional[date] = None


class AgendaLugarOut(BaseModel):
    id: int
    id_lugar: int
    id_area: int
    id_clase: int
    independiente_de_servicio: bool
    fecha_desde: date
    fecha_hasta: Optional[date]
    hora_inicio: time
    hora_fin: time
    dias_semana: int
    nombre_parametro: Optional[str]
    observaciones: Optional[str]
    activo: bool
    fecha_baja: Optional[date]
    creado_por: Optional[int]
    creado_en: Optional[datetime]
    modificado_en: Optional[datetime]

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════
# TURNO
# ═══════════════════════════════════════════════════════════════

class TurnoCreate(BaseModel):
    tipo_agenda: Literal["AGENTE", "SERVICIO", "LUGAR"]
    id_agenda_agente: Optional[int] = None
    id_agenda_servicio: Optional[int] = None
    id_agenda_lugar: Optional[int] = None
    id_ciudadano: Optional[int] = None
    fecha: date
    hora_inicio: time
    hora_fin: time
    origen_reserva: Literal["CIUDADANO", "OPERADOR"] = "OPERADOR"
    reservado_por: Optional[int] = None
    observaciones: Optional[str] = None


class TurnoEstadoUpdate(BaseModel):
    estado: Literal["RESERVADO", "CONFIRMADO", "PRESENTE", "AUSENTE", "CANCELADO"]


class TurnoOut(BaseModel):
    id: int
    tipo_agenda: str
    id_agenda_agente: Optional[int]
    id_agenda_servicio: Optional[int]
    id_agenda_lugar: Optional[int]
    id_ciudadano: Optional[int]
    fecha: date
    hora_inicio: time
    hora_fin: time
    estado: str
    origen_reserva: str
    reservado_por: Optional[int]
    notificacion_enviada: bool
    observaciones: Optional[str]
    activo: bool
    creado_en: Optional[datetime]
    modificado_en: Optional[datetime]

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════
# AUSENCIA
# ═══════════════════════════════════════════════════════════════

class AgendaAusenciaCreate(BaseModel):
    id_usuario: int
    fecha_desde: date
    fecha_hasta: date
    motivo: Optional[str] = Field(None, max_length=200)
    genera_alerta: bool = True
    cargado_por: Optional[int] = None


class AgendaAusenciaOut(BaseModel):
    id: int
    id_usuario: int
    fecha_desde: date
    fecha_hasta: date
    motivo: Optional[str]
    genera_alerta: bool
    cargado_por: Optional[int]
    activo: bool
    creado_en: Optional[datetime]
    modificado_en: Optional[datetime]

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════
# ALERTA
# ═══════════════════════════════════════════════════════════════

class AgendaAlertaOut(BaseModel):
    id: int
    tipo_alerta: str
    id_agenda_agente: Optional[int]
    id_agenda_servicio: Optional[int]
    id_agenda_lugar: Optional[int]
    id_ausencia: Optional[int]
    fecha_desde: Optional[date]
    fecha_hasta: Optional[date]
    descripcion: str
    resuelta: bool
    resuelta_por: Optional[int]
    resuelta_en: Optional[datetime]
    creado_en: Optional[datetime]

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════
# CALENDARIO
# ═══════════════════════════════════════════════════════════════

class SlotCalendario(BaseModel):
    hora_inicio: time
    hora_fin: time
    disponible: bool
    turnos_count: int
    es_feriado: bool


class DiaCalendario(BaseModel):
    fecha: date
    es_feriado: bool
    feriado_descripcion: Optional[str]
    slots_totales: int
    slots_ocupados: int
    estado: Literal["disponible", "parcial", "ocupado", "feriado", "fuera"]


class CalendarioMesOut(BaseModel):
    anio: int
    mes: int
    dias: List[DiaCalendario]


class CalendarioDiaOut(BaseModel):
    fecha: date
    es_feriado: bool
    feriado_descripcion: Optional[str]
    slots: List[SlotCalendario]
