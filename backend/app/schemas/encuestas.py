"""
Schemas Pydantic v2 para el modulo Encuestas (CSAT) — migracion 57.

Create / Update / Out por cada tabla. Los campos de auditoria del estandar §10
(id_usuario_alta/modificacion, id_municipio, etc.) los inyecta el backend desde
el JWT — no vienen del cliente, por eso no estan en los schemas Create/Update.

Fase 1: solo modelos + schemas. Los endpoints van en el prompt 2.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# encuesta_plantilla
# ---------------------------------------------------------------------------

class EncuestaPlantillaBase(BaseModel):
    nombre: str = Field(max_length=100)
    descripcion: Optional[str] = None
    version: str = Field(default="1.0", max_length=20)
    tipo: str = Field(max_length=30)  # reclamos | tramites | turnos


class EncuestaPlantillaCreate(EncuestaPlantillaBase):
    pass


class EncuestaPlantillaUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, max_length=100)
    descripcion: Optional[str] = None
    version: Optional[str] = Field(default=None, max_length=20)
    tipo: Optional[str] = Field(default=None, max_length=30)
    activo: Optional[bool] = None


class EncuestaPlantillaOut(EncuestaPlantillaBase):
    model_config = ConfigDict(from_attributes=True)

    id_encuesta_plantilla: int
    activo: bool
    id_municipio: Optional[int] = None
    id_subarea: Optional[int] = None
    fecha_alta: datetime
    fecha_modificacion: datetime


# ---------------------------------------------------------------------------
# encuesta_pregunta
# ---------------------------------------------------------------------------

class EncuestaPreguntaBase(BaseModel):
    id_plantilla: int
    texto: str
    tipo: str = Field(max_length=20)   # likert5 | texto_libre | si_no | multiple
    orden: int
    rama: str = Field(max_length=20)   # todos | satisfechos | neutrales | insatisfechos
    obligatoria: bool = True


class EncuestaPreguntaCreate(EncuestaPreguntaBase):
    pass


class EncuestaPreguntaUpdate(BaseModel):
    texto: Optional[str] = None
    tipo: Optional[str] = Field(default=None, max_length=20)
    orden: Optional[int] = None
    rama: Optional[str] = Field(default=None, max_length=20)
    obligatoria: Optional[bool] = None
    activo: Optional[bool] = None


class EncuestaPreguntaOut(EncuestaPreguntaBase):
    model_config = ConfigDict(from_attributes=True)

    id_encuesta_pregunta: int
    activo: bool
    fecha_alta: datetime
    fecha_modificacion: datetime


# ---------------------------------------------------------------------------
# encuesta_opcion
# ---------------------------------------------------------------------------

class EncuestaOpcionBase(BaseModel):
    id_pregunta: int
    texto: str = Field(max_length=200)
    valor: str = Field(max_length=50)
    orden: int


class EncuestaOpcionCreate(EncuestaOpcionBase):
    pass


class EncuestaOpcionUpdate(BaseModel):
    texto: Optional[str] = Field(default=None, max_length=200)
    valor: Optional[str] = Field(default=None, max_length=50)
    orden: Optional[int] = None
    activo: Optional[bool] = None


class EncuestaOpcionOut(EncuestaOpcionBase):
    model_config = ConfigDict(from_attributes=True)

    id_encuesta_opcion: int
    activo: bool
    fecha_alta: datetime
    fecha_modificacion: datetime


# ---------------------------------------------------------------------------
# encuesta_envio
# ---------------------------------------------------------------------------

class EncuestaEnvioBase(BaseModel):
    id_plantilla: int
    id_ciudadano: int
    id_reclamo: int
    email_destino_snapshot: str = Field(max_length=150)
    fecha_expiracion: datetime


class EncuestaEnvioCreate(EncuestaEnvioBase):
    pass


class EncuestaEnvioUpdate(BaseModel):
    fecha_envio: Optional[datetime] = None
    fecha_apertura: Optional[datetime] = None
    fecha_completada: Optional[datetime] = None
    estado: Optional[str] = Field(default=None, max_length=20)
    intentos_envio: Optional[int] = None
    ultimo_error_envio: Optional[str] = None
    activo: Optional[bool] = None


class EncuestaEnvioOut(EncuestaEnvioBase):
    model_config = ConfigDict(from_attributes=True)

    id_encuesta_envio: int
    token_unico: UUID
    fecha_envio: Optional[datetime] = None
    fecha_apertura: Optional[datetime] = None
    fecha_completada: Optional[datetime] = None
    estado: str
    intentos_envio: int
    ultimo_error_envio: Optional[str] = None
    activo: bool
    fecha_alta: datetime
    fecha_modificacion: datetime


# ---------------------------------------------------------------------------
# encuesta_respuesta
# ---------------------------------------------------------------------------

class EncuestaRespuestaBase(BaseModel):
    id_envio: int
    clasificacion_inicial: int = Field(ge=1, le=5)
    rama_seguida: str = Field(max_length=20)  # satisfechos | neutrales | insatisfechos
    tiempo_completado_seg: Optional[int] = None
    solicita_contacto: bool = False
    ip_origen: Optional[str] = Field(default=None, max_length=45)


class EncuestaRespuestaCreate(EncuestaRespuestaBase):
    pass


class EncuestaRespuestaUpdate(BaseModel):
    solicita_contacto: Optional[bool] = None
    activo: Optional[bool] = None


class EncuestaRespuestaOut(EncuestaRespuestaBase):
    model_config = ConfigDict(from_attributes=True)

    id_encuesta_respuesta: int
    atendida: bool = False
    atendida_por: Optional[int] = None
    fecha_atendida: Optional[datetime] = None
    activo: bool
    fecha_alta: datetime
    fecha_modificacion: datetime


# ---------------------------------------------------------------------------
# encuesta_respuesta_detalle
# ---------------------------------------------------------------------------

class EncuestaRespuestaDetalleBase(BaseModel):
    id_respuesta: int
    id_pregunta: int
    valor_numerico: Optional[int] = None
    valor_texto: Optional[str] = None
    id_opcion_seleccionada: Optional[int] = None


class EncuestaRespuestaDetalleCreate(EncuestaRespuestaDetalleBase):
    pass


class EncuestaRespuestaDetalleUpdate(BaseModel):
    valor_numerico: Optional[int] = None
    valor_texto: Optional[str] = None
    id_opcion_seleccionada: Optional[int] = None
    activo: Optional[bool] = None


class EncuestaRespuestaDetalleOut(EncuestaRespuestaDetalleBase):
    model_config = ConfigDict(from_attributes=True)

    id_encuesta_respuesta_detalle: int
    activo: bool
    fecha_alta: datetime
    fecha_modificacion: datetime


# ---------------------------------------------------------------------------
# Composiciones para endpoints admin (fase 2C)
# ---------------------------------------------------------------------------

class EncuestaPreguntaConOpcionesOut(EncuestaPreguntaOut):
    """Pregunta con sus opciones anidadas (para el detalle de plantilla)."""
    opciones: list[EncuestaOpcionOut] = []


class EncuestaPlantillaDetalleOut(EncuestaPlantillaOut):
    """Plantilla + preguntas anidadas + opciones dentro de cada pregunta."""
    preguntas: list[EncuestaPreguntaConOpcionesOut] = []


class EncuestaEnvioConRespuestaOut(EncuestaEnvioOut):
    """Detalle de envio; si tiene respuesta, va anidada con sus detalles."""
    respuesta: Optional[EncuestaRespuestaOut] = None
    detalles_respuesta: list[EncuestaRespuestaDetalleOut] = []


class DispararEncuestaIn(BaseModel):
    id_reclamo: int


# --- Pendientes de contacto (incluye datos del ciudadano + reclamo) ---

class RespuestaPendienteContactoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_encuesta_respuesta: int
    id_encuesta_envio: int
    clasificacion_inicial: int
    rama_seguida: str
    fecha_respuesta: Optional[datetime] = None  # = encuesta_respuesta.fecha_alta
    atendida: bool
    # contexto del reclamo
    id_reclamo: int
    nro_reclamo: Optional[str] = None
    # contexto del ciudadano (para que el agente lo contacte)
    id_ciudadano: int
    ciudadano_nombre: Optional[str] = None
    ciudadano_apellido: Optional[str] = None
    ciudadano_email: Optional[str] = None
    ciudadano_telefono: Optional[str] = None


# --- Dashboard ---

class DashboardPeriodoOut(BaseModel):
    desde: date
    hasta: date


class DashboardDistribucionItem(BaseModel):
    clasificacion: int
    count: int


class DashboardResumenOut(BaseModel):
    periodo: DashboardPeriodoOut
    csat_promedio: float
    tasa_respuesta_pct: float
    pct_insatisfechos: float
    alertas_contacto_pendientes: int
    total_enviadas: int
    total_completadas: int
    distribucion: list[DashboardDistribucionItem]


class DashboardPorAreaItem(BaseModel):
    id_area: Optional[int] = None
    nombre_area: Optional[str] = None
    total_respuestas: int
    csat_promedio: float


class DashboardEvolucionItem(BaseModel):
    anio_mes: str          # 'YYYY-MM'
    csat_promedio: float
    total_respuestas: int


class DashboardComentarioItem(BaseModel):
    id_envio: int
    fecha_respuesta: Optional[datetime] = None
    clasificacion_inicial: int
    comentario: str
