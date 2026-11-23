"""Schemas de la app de agentes: relevamientos (mig 141) y control de entradas.

Plan: PLAN_APP_AGENTES_RECLAMOS_ENTRADAS.md.
"""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

FUENTES_GEO = ("pin_manual", "geocoding_osm", "gps_dispositivo")


class RelevamientoIn(BaseModel):
    id_tipo_reclamo: int = Field(..., ge=1, le=2_147_483_647)
    descripcion: str = Field(..., max_length=2000)
    direccion: str = Field(..., max_length=300)
    latitud: Optional[float] = Field(None, ge=-90, le=90)
    longitud: Optional[float] = Field(None, ge=-180, le=180)
    fuente_geolocalizacion: Optional[Literal["pin_manual", "geocoding_osm", "gps_dispositivo"]] = None

    @field_validator("descripcion")
    @classmethod
    def _descripcion(cls, v: str) -> str:
        v = (v or "").strip()
        if len(v) < 5:
            raise ValueError("La descripción debe tener al menos 5 caracteres")
        return v

    @field_validator("direccion")
    @classmethod
    def _direccion(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("La dirección es obligatoria")
        return v

    @model_validator(mode="after")
    def _coordenadas(self) -> "RelevamientoIn":
        if (self.latitud is None) != (self.longitud is None):
            raise ValueError("Latitud y longitud van juntas")
        return self


class RelevamientoCreadoOut(BaseModel):
    id_reclamo: int
    nro_reclamo: str
    estado: str


class RelevamientoItemOut(BaseModel):
    id_reclamo: int
    nro_reclamo: str
    estado: str
    tipo: Optional[str] = None
    descripcion: str
    direccion: Optional[str] = None
    fecha_alta: datetime


class RelevamientoHistorialOut(BaseModel):
    accion: str
    estado_anterior: Optional[str] = None
    estado_nuevo: Optional[str] = None
    fecha: datetime


class RelevamientoDetalleOut(RelevamientoItemOut):
    remitente: Optional[str] = None  # persona (ficha) de quien lo cargó
    gestion: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    resolucion: Optional[str] = None
    fecha_cierre: Optional[datetime] = None
    historial: list[RelevamientoHistorialOut] = []


class AcreditarQRPuertaIn(BaseModel):
    qr_codigo: str = Field(..., max_length=200)


class ReservaPuertaOut(BaseModel):
    id_evento_reserva: int
    id_evento: int
    evento: str
    fecha: date
    hora_inicio: Optional[time] = None
    hora_fin: Optional[time] = None
    espacio: Optional[str] = None
    ciudadano: Optional[str] = None


class AcreditarQRPuertaOut(BaseModel):
    resultado: Literal["acreditada", "ya_acreditada", "cancelada", "otra_fecha", "no_encontrada"]
    acreditada_en: Optional[datetime] = None
    reserva: Optional[ReservaPuertaOut] = None


class EntradaValidadaOut(BaseModel):
    numero: int  # id de la reserva: el número de la entrada
    registrada_en: datetime
    persona: Optional[str] = None
    documento: Optional[str] = None
    evento: str


class EventoHoyOut(BaseModel):
    id_evento: int
    nombre: str
    fecha: date
    hora_inicio: Optional[time] = None
    hora_fin: Optional[time] = None
    espacio: Optional[str] = None
    reservas: int
    acreditadas: int
    soy_encargado: bool
