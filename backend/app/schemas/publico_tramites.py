"""Schemas del portal del vecino para trámites (spec 2026-11-21 §5.1, §5.3)."""
from __future__ import annotations

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
