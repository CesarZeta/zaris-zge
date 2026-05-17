"""
Schemas Pydantic v2 para el modulo Tramites/Expedientes (migraciones 47-50).

Fase 1: solo lectura.
Fase 2: creacion, transicion, pase, toma, firma, adjuntos, comentario, relacion.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, field_validator


# ---------------------------------------------------------------------------
# Schemas auxiliares reutilizables
# ---------------------------------------------------------------------------

class ActorRef(BaseModel):
    """Referencia denormalizada a un actor (subarea, equipo, agente, ciudadano)."""
    tipo: str
    id: int
    nombre: str


# ---------------------------------------------------------------------------
# Catalogo: tipo_tramite
# ---------------------------------------------------------------------------

class TipoTramiteListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_tipo_tramite: int
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    prefijo: str
    iniciadores_permitidos: list[str]
    permite_representante: bool
    icono: Optional[str] = None
    color: Optional[str] = None
    id_version_publicada: Optional[int] = None


class TipoTramiteListOut(BaseModel):
    items: list[TipoTramiteListItem]
    total: int


class VersionOut(BaseModel):
    id_tipo_tramite_version: int
    version_num: int
    estado: str
    publicada_en: Optional[datetime] = None


class CampoOut(BaseModel):
    id_tipo_tramite_campo: int
    nombre_interno: str
    etiqueta: str
    tipo_dato: str
    obligatorio: bool
    orden: int
    opciones_jsonb: Optional[Any] = None
    validacion_jsonb: Optional[Any] = None
    ayuda: Optional[str] = None
    visible_en_listado: bool


class EstadoOut(BaseModel):
    id_tipo_tramite_estado: int
    codigo: str
    etiqueta: str
    orden: int
    es_inicial: bool
    es_final: bool
    color: Optional[str] = None
    oculto_para_iniciador: bool


class TransicionOut(BaseModel):
    id_tipo_tramite_transicion: int
    id_estado_origen: int
    id_estado_destino: int
    etiqueta_accion: str
    orden: int
    requiere_comentario: bool
    requiere_adjunto: bool
    quien_puede_jsonb: Any
    notifica_iniciador: bool


class DocumentoRequeridoOut(BaseModel):
    id_tipo_tramite_documento_requerido: int
    nombre: str
    descripcion: Optional[str] = None
    obligatorio: bool
    id_tipo_tramite_estado: Optional[int] = None
    aporta_quien: str
    formatos_permitidos: list[str]
    tamano_max_mb: int
    requiere_firma: bool
    orden: int


class TipoTramiteDetalleOut(BaseModel):
    id_tipo_tramite: int
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    prefijo: str
    incluye_municipio: bool
    incluye_anio: bool
    largo_correlativo: int
    separador: str
    iniciadores_permitidos: list[str]
    permite_representante: bool
    icono: Optional[str] = None
    color: Optional[str] = None
    version: Optional[VersionOut] = None
    campos: list[CampoOut] = []
    estados: list[EstadoOut] = []
    transiciones: list[TransicionOut] = []
    documentos_requeridos: list[DocumentoRequeridoOut] = []


# ---------------------------------------------------------------------------
# Instancias: tramite (bandeja y detalle)
# ---------------------------------------------------------------------------

class TramiteListItem(BaseModel):
    id_tramite: int
    numero_expediente: str
    asunto: str
    tipo_codigo: str
    tipo_nombre: str
    estado_codigo: str
    estado_etiqueta: str
    estado_color: Optional[str] = None
    iniciador_tipo: str
    iniciador_nombre: Optional[str] = None
    destinatario_actual_tipo: Optional[str] = None
    destinatario_actual_nombre: Optional[str] = None
    tomado_por_nombre: Optional[str] = None
    tomado_en: Optional[datetime] = None
    fecha_alta: datetime
    dias_en_estado_actual: int


class TramiteListOut(BaseModel):
    items: list[TramiteListItem]
    total: int
    limit: int
    offset: int


class RelacionOut(BaseModel):
    id_tramite_relacion: int
    id_tramite_relacionado: int
    numero_expediente_relacionado: str
    asunto_relacionado: str
    tipo_relacion: str
    fecha_alta: datetime


class TramiteDetalleOut(BaseModel):
    id_tramite: int
    numero_expediente: str
    asunto: str
    datos_jsonb: Any
    iniciador_tipo: str
    iniciador_nombre: Optional[str] = None
    representante_nombre: Optional[str] = None
    tipo_codigo: str
    tipo_nombre: str
    tipo_prefijo: str
    id_tipo_tramite_version: int
    version_num: int
    estado_codigo: str
    estado_etiqueta: str
    estado_color: Optional[str] = None
    fecha_entrada_estado_actual: datetime
    destinatario_actual_tipo: Optional[str] = None
    destinatario_actual_nombre: Optional[str] = None
    tomado_por_nombre: Optional[str] = None
    tomado_en: Optional[datetime] = None
    ultimo_movimiento_tipo: Optional[str] = None
    ultimo_movimiento_comentario: Optional[str] = None
    ultimo_movimiento_fecha: Optional[datetime] = None
    cant_documentos: int
    cant_firmas_pendientes: int
    relaciones: list[RelacionOut] = []
    fecha_alta: datetime
    id_municipio: int


# ---------------------------------------------------------------------------
# Movimientos (timeline)
# ---------------------------------------------------------------------------

class MovimientoOut(BaseModel):
    id_tramite_movimiento: int
    orden_secuencial: int
    tipo: str
    id_tipo_tramite_transicion: Optional[int] = None
    estado_origen_codigo: Optional[str] = None
    estado_origen_etiqueta: Optional[str] = None
    estado_destino_codigo: Optional[str] = None
    estado_destino_etiqueta: Optional[str] = None
    origen_jsonb: Optional[Any] = None
    destino_jsonb: Optional[Any] = None
    comentario: Optional[str] = None
    metadata_jsonb: Optional[Any] = None
    agente_nombre: str
    fecha_alta: datetime


class MovimientosOut(BaseModel):
    numero_expediente: str
    movimientos: list[MovimientoOut]
    total: int


# ---------------------------------------------------------------------------
# Documentos
# ---------------------------------------------------------------------------

class FirmaOut(BaseModel):
    id_tramite_firma: int
    rol_intervencion: str
    orden: int
    asignado_nombre: Optional[str] = None
    estado: str
    firmado_en: Optional[datetime] = None


class DocumentoOut(BaseModel):
    id_tramite_documento: int
    nombre: str
    nombre_archivo_original: str
    mime_type: str
    tamano_bytes: int
    requiere_firma: bool
    estado_firma: str
    posicion_orden: int
    firmas: list[FirmaOut] = []
    fecha_alta: datetime


class DocumentosOut(BaseModel):
    numero_expediente: str
    documentos: list[DocumentoOut]
    total: int


# ---------------------------------------------------------------------------
# Schemas de entrada — Fase 2
# ---------------------------------------------------------------------------

class IniciadorIn(BaseModel):
    tipo: str  # ciudadano | empresa | area_interna
    id_ciudadano: Optional[int] = None
    id_empresa: Optional[int] = None
    id_ciudadano_representante: Optional[int] = None
    id_subarea: Optional[int] = None


class TramiteCreateIn(BaseModel):
    id_tipo_tramite: int
    asunto: str
    iniciador: IniciadorIn
    datos: dict[str, Any] = {}
    id_municipio: int = 1

    @field_validator("asunto")
    @classmethod
    def asunto_no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El asunto no puede estar vacio")
        return v


class TransicionIn(BaseModel):
    id_tipo_tramite_transicion: int
    comentario: Optional[str] = None


class PaseIn(BaseModel):
    destinatario_tipo: str  # subarea | equipo
    destinatario_id: int
    comentario: Optional[str] = None


class ComentarioIn(BaseModel):
    comentario: str

    @field_validator("comentario")
    @classmethod
    def comentario_valido(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El comentario no puede estar vacio")
        if len(v) > 5000:
            raise ValueError("El comentario no puede superar los 5000 caracteres")
        return v


class FirmarIn(BaseModel):
    id_tramite_firma: int
    comentario: Optional[str] = None


class RechazarFirmaIn(BaseModel):
    id_tramite_firma: int
    motivo: str

    @field_validator("motivo")
    @classmethod
    def motivo_no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El motivo de rechazo no puede estar vacio")
        return v


class RelacionarIn(BaseModel):
    id_tramite_b: int
    comentario: Optional[str] = None


# ---------------------------------------------------------------------------
# Schemas de salida adicionales — Fase 2
# ---------------------------------------------------------------------------

class TransicionPermitidaOut(BaseModel):
    id_tipo_tramite_transicion: int
    etiqueta_accion: str
    id_estado_destino: int
    etiqueta_destino: str
    requiere_comentario: bool
    requiere_adjunto: bool
    disponible: bool
    motivo_no_disponible: Optional[str] = None


class TransicionesPermitidasOut(BaseModel):
    id_tramite: int
    estado_codigo: str
    estado_etiqueta: str
    tomado_por_mi: bool
    puedo_operar: bool
    transiciones: list[TransicionPermitidaOut]


class DocumentoConFirmasOut(BaseModel):
    id_tramite_documento: int
    nombre: str
    nombre_archivo_original: str
    mime_type: str
    tamano_bytes: int
    hash_sha256: str
    requiere_firma: bool
    estado_firma: str
    posicion_orden: int
    firmas: list[FirmaOut] = []
    fecha_alta: datetime


class FirmaDetalleOut(BaseModel):
    id_tramite_firma: int
    estado: str
    firmado_en: Optional[datetime] = None
    hash_documento_firmado: Optional[str] = None
    estado_firma_documento: str
