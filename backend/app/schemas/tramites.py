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


# ---------------------------------------------------------------------------
# Schemas Admin Catalogo (CRUD de tipo_tramite y sub-tablas)
# ---------------------------------------------------------------------------

INICIADORES_VALIDOS = {"ciudadano", "empresa", "area_interna"}
TIPO_DATO_VALIDOS = {
    "texto", "texto_largo", "numero", "decimal", "fecha", "fecha_hora",
    "booleano", "seleccion", "seleccion_multiple", "ciudadano", "empresa",
    "agente", "subarea", "equipo", "archivo", "moneda", "direccion",
}
APORTA_QUIEN_VALIDOS = {"iniciador", "oficina_actual", "cualquiera"}


class TipoTramiteCreateIn(BaseModel):
    """Crea un nuevo tipo + v1 borrador automaticamente."""
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    prefijo: str
    iniciadores_permitidos: list[str]
    permite_representante: bool = False
    incluye_municipio: bool = True
    incluye_anio: bool = True
    largo_correlativo: int = 4
    separador: str = "-"
    correlativo_reinicia_anual: bool = True
    icono: Optional[str] = None
    color: Optional[str] = None
    id_municipio: int = 1

    @field_validator("codigo", "nombre", "prefijo")
    @classmethod
    def no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Campo obligatorio")
        return v

    @field_validator("iniciadores_permitidos")
    @classmethod
    def iniciadores_validos(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("Debe haber al menos un iniciador permitido")
        invalidos = set(v) - INICIADORES_VALIDOS
        if invalidos:
            raise ValueError(f"Iniciadores invalidos: {invalidos}. Validos: {INICIADORES_VALIDOS}")
        return v

    @field_validator("largo_correlativo")
    @classmethod
    def largo_correlativo_valido(cls, v: int) -> int:
        if not 1 <= v <= 8:
            raise ValueError("largo_correlativo debe estar entre 1 y 8")
        return v

    @field_validator("separador")
    @classmethod
    def separador_un_char(cls, v: str) -> str:
        if len(v) != 1:
            raise ValueError("separador debe ser un solo caracter")
        return v


class TipoTramiteUpdateIn(BaseModel):
    """Actualiza datos identitarios del tipo (NO afectan circuito)."""
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    prefijo: Optional[str] = None
    iniciadores_permitidos: Optional[list[str]] = None
    permite_representante: Optional[bool] = None
    incluye_municipio: Optional[bool] = None
    incluye_anio: Optional[bool] = None
    largo_correlativo: Optional[int] = None
    separador: Optional[str] = None
    correlativo_reinicia_anual: Optional[bool] = None
    icono: Optional[str] = None
    color: Optional[str] = None

    @field_validator("iniciadores_permitidos")
    @classmethod
    def iniciadores_validos_opt(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is None:
            return None
        if not v:
            raise ValueError("Debe haber al menos un iniciador permitido")
        invalidos = set(v) - INICIADORES_VALIDOS
        if invalidos:
            raise ValueError(f"Iniciadores invalidos: {invalidos}")
        return v


class CampoIn(BaseModel):
    nombre_interno: str
    etiqueta: str
    tipo_dato: str
    obligatorio: bool = False
    orden: int = 0
    opciones_jsonb: Optional[Any] = None
    validacion_jsonb: Optional[Any] = None
    ayuda: Optional[str] = None
    visible_en_listado: bool = False

    @field_validator("nombre_interno")
    @classmethod
    def nombre_interno_valido(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("nombre_interno obligatorio")
        # snake_case-ish: solo letras, numeros y _; max 50
        import re
        if not re.match(r"^[a-z][a-z0-9_]{0,49}$", v):
            raise ValueError("nombre_interno debe ser snake_case (a-z, 0-9, _), empezar con letra, max 50")
        return v

    @field_validator("tipo_dato")
    @classmethod
    def tipo_dato_valido(cls, v: str) -> str:
        if v not in TIPO_DATO_VALIDOS:
            raise ValueError(f"tipo_dato invalido. Validos: {sorted(TIPO_DATO_VALIDOS)}")
        return v


class CampoUpdateIn(BaseModel):
    etiqueta: Optional[str] = None
    tipo_dato: Optional[str] = None
    obligatorio: Optional[bool] = None
    orden: Optional[int] = None
    opciones_jsonb: Optional[Any] = None
    validacion_jsonb: Optional[Any] = None
    ayuda: Optional[str] = None
    visible_en_listado: Optional[bool] = None

    @field_validator("tipo_dato")
    @classmethod
    def tipo_dato_valido(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if v not in TIPO_DATO_VALIDOS:
            raise ValueError(f"tipo_dato invalido. Validos: {sorted(TIPO_DATO_VALIDOS)}")
        return v


class EstadoIn(BaseModel):
    codigo: str
    etiqueta: str
    descripcion: Optional[str] = None
    color: Optional[str] = None
    orden: int = 0
    es_inicial: bool = False
    es_final: bool = False
    permite_adjuntar: bool = True
    permite_comentar: bool = True
    oculto_para_iniciador: bool = False

    @field_validator("codigo")
    @classmethod
    def codigo_valido(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("codigo obligatorio")
        import re
        if not re.match(r"^[a-z][a-z0-9_]{0,49}$", v):
            raise ValueError("codigo debe ser snake_case")
        return v


class EstadoUpdateIn(BaseModel):
    etiqueta: Optional[str] = None
    descripcion: Optional[str] = None
    color: Optional[str] = None
    orden: Optional[int] = None
    es_inicial: Optional[bool] = None
    es_final: Optional[bool] = None
    permite_adjuntar: Optional[bool] = None
    permite_comentar: Optional[bool] = None
    oculto_para_iniciador: Optional[bool] = None


class TransicionIn2(BaseModel):
    """Para CRUD del catalogo. Distinto a TransicionIn que es para EJECUTAR una transicion."""
    id_estado_origen: int
    id_estado_destino: int
    etiqueta_accion: str
    orden: int = 0
    quien_puede_jsonb: Optional[Any] = None  # dict; default {}
    requiere_comentario: bool = False
    requiere_adjunto: bool = False
    destino_automatico_jsonb: Optional[Any] = None
    notifica_iniciador: bool = True


class TransicionUpdateIn(BaseModel):
    id_estado_origen: Optional[int] = None
    id_estado_destino: Optional[int] = None
    etiqueta_accion: Optional[str] = None
    orden: Optional[int] = None
    quien_puede_jsonb: Optional[Any] = None
    requiere_comentario: Optional[bool] = None
    requiere_adjunto: Optional[bool] = None
    destino_automatico_jsonb: Optional[Any] = None
    notifica_iniciador: Optional[bool] = None


class DocumentoRequeridoIn(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    id_tipo_tramite_estado: Optional[int] = None
    obligatorio: bool = True
    formatos_permitidos: list[str] = ["pdf", "jpg", "png"]
    tamano_max_mb: int = 10
    requiere_firma: bool = False
    firmantes_jsonb: Optional[Any] = None
    aporta_quien: str = "iniciador"
    orden: int = 0

    @field_validator("aporta_quien")
    @classmethod
    def aporta_quien_valido(cls, v: str) -> str:
        if v not in APORTA_QUIEN_VALIDOS:
            raise ValueError(f"aporta_quien invalido. Validos: {sorted(APORTA_QUIEN_VALIDOS)}")
        return v


class DocumentoRequeridoUpdateIn(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    id_tipo_tramite_estado: Optional[int] = None
    obligatorio: Optional[bool] = None
    formatos_permitidos: Optional[list[str]] = None
    tamano_max_mb: Optional[int] = None
    requiere_firma: Optional[bool] = None
    firmantes_jsonb: Optional[Any] = None
    aporta_quien: Optional[str] = None
    orden: Optional[int] = None

    @field_validator("aporta_quien")
    @classmethod
    def aporta_quien_valido_opt(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if v not in APORTA_QUIEN_VALIDOS:
            raise ValueError(f"aporta_quien invalido. Validos: {sorted(APORTA_QUIEN_VALIDOS)}")
        return v


class TipoTramiteAdminOut(BaseModel):
    """Devuelve el tipo + sus versiones."""
    id_tipo_tramite: int
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    prefijo: str
    iniciadores_permitidos: list[str]
    permite_representante: bool
    incluye_municipio: bool
    incluye_anio: bool
    largo_correlativo: int
    separador: str
    correlativo_reinicia_anual: bool
    icono: Optional[str] = None
    color: Optional[str] = None
    activo: bool
    id_version_publicada: Optional[int] = None
    versiones: list[VersionOut] = []


class VersionAdminOut(BaseModel):
    id_tipo_tramite_version: int
    id_tipo_tramite: int
    version_num: int
    estado: str
    publicada_en: Optional[datetime] = None
    activo: bool
    cant_tramites: int = 0
