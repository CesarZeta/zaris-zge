"""Schemas del portal del vecino para trámites (spec 2026-11-21 §5.1, §5.3)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class TipoOfrecidoOut(BaseModel):
    id_tipo_tramite: int
    nombre: str
    descripcion: Optional[str] = None
    exige_identidad_validada: bool
    puede_iniciar: bool
    motivo_no_puede: Optional[str] = None


class CampoPublicoOut(BaseModel):
    nombre_interno: str
    etiqueta: str
    tipo_dato: str
    obligatorio: bool
    opciones: Optional[Any] = None
    ayuda: Optional[str] = None
    orden: int
    # Reglas extra del campo, con el significado de `_validar_escalar` (services/tramites/creacion.py):
    # {min, max} = largo en texto/dirección y valor en numero/moneda; {regex} en texto. null si no tiene.
    validacion: Optional[dict] = None


class DocumentoAltaOut(BaseModel):
    id_documento_requerido: int
    nombre: str
    descripcion: Optional[str] = None
    obligatorio: bool
    formatos_permitidos: list[str] = []
    tamano_max_mb: Optional[int] = None
    cantidad_max_archivos: int = 1


class TipoOfrecidoDetalleOut(TipoOfrecidoOut):
    campos: list[CampoPublicoOut]
    documentos: list[DocumentoAltaOut]


class AltaTramiteOut(BaseModel):
    id_tramite: int
    numero_expediente: str


# ── Ver mis trámites (spec §5.4, §5.5) ──────────────────────────────────────

class MiTramiteOut(BaseModel):
    id_tramite: int
    numero_expediente: str
    tipo_nombre: str
    estado_etiqueta: str
    estado_color: Optional[str] = None
    resultado: str
    fecha_alta: datetime
    tiene_pedido_abierto: bool
    documentos_pendientes: int


class DatoTramiteOut(BaseModel):
    etiqueta: str
    valor: str


class DocumentoSubidoOut(BaseModel):
    id_tramite_documento: int
    nombre: str
    fecha_alta: datetime
    binario_purgado: bool


class DocumentoPasoOut(DocumentoAltaOut):
    subidos: int = 0


class PedidoAbiertoOut(BaseModel):
    id_tramite_pedido: int
    texto: str
    pide_archivo: bool
    fecha_pedido: datetime


class HistorialItemOut(BaseModel):
    fecha: datetime
    texto: str


class MiTramiteDetalleOut(MiTramiteOut):
    datos: list[DatoTramiteOut]
    documentos: list[DocumentoSubidoOut]
    documentos_del_paso: list[DocumentoPasoOut]
    pedido_abierto: Optional[PedidoAbiertoOut] = None
    historial: list[HistorialItemOut]


class DocumentosSubidosOut(BaseModel):
    subidos: int


class RespuestaPedidoOut(BaseModel):
    respondido: bool
