"""
Schemas Pydantic para el ALTA PÚBLICA de vecinos (autoregistro).

Endpoints bajo /api/v1/publico/alta/*. A diferencia de publico_auth.py (donde el alta
la hace un agente municipal), acá el ciudadano se da de alta él mismo desde una URL
pública diferenciada por municipio (slug validado, mono-tenant §38).

Paridad de campos con el alta oficial del backoffice (módulos React ciudadanos/empresas):
datos personales completos + domicilio normalizado por OSM (calle/localidad/provincia +
lat/lon). CUIL/CUIT reales con validación de dígito verificador (módulo 11), reusando el
validador del BUC.

Flujo:
  1. GET  /identidad?m=<slug>      -> branding del municipio para el header.
  2. GET  /actividades?m=<slug>    -> catálogo de actividades (select de empresa).
  3. GET  /geo/buscar?m=&q=        -> geocoding OSM público (autocompletado de domicilio).
  4. POST /ciudadano               -> crea ciudadano + credencial (cuenta) en una tx. Mail.
  5. POST /empresa                 -> (requiere ciudadano) empresa + vínculo + credencial. Mail.
  6. GET  /verificar?token=        -> marca verificado (ciudadano o empresa) y activa la cuenta.
"""
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.buc import _validar_modulo11


# ─── Identidad del municipio (header de la página pública) ───────────────────

class IdentidadAltaOut(BaseModel):
    municipio_slug: str
    municipio_nombre: str
    municipio_logo_url: str | None = None
    municipio_color_primary: str | None = None
    municipio_color_accent: str | None = None


# ─── Alta de ciudadano (paridad con el alta oficial) ─────────────────────────

class AltaCiudadanoIn(BaseModel):
    municipio_slug: str = Field(..., min_length=1, max_length=20)

    # Identificación
    doc_tipo: Literal["DNI", "PASAPORTE"] = "DNI"
    doc_nro: str = Field(..., min_length=6, max_length=15)
    cuil: str = Field(..., min_length=10, max_length=15)  # acepta guiones, se valida módulo 11

    # Datos personales
    nombre: str = Field(..., min_length=1, max_length=100)
    apellido: str = Field(..., min_length=1, max_length=100)
    sexo: Literal["HOMBRE", "MUJER", "OTROS"]
    fecha_nac: str = Field(..., description="YYYY-MM-DD")
    id_nacionalidad: int

    # Domicilio (lo completa el buscador OSM en el front)
    calle: str = Field(..., min_length=1, max_length=200)
    localidad: str = Field(..., min_length=1, max_length=100)
    provincia: str = Field(..., min_length=1, max_length=100)
    latitud: float | None = None
    longitud: float | None = None

    # Contacto
    telefono: str = Field(..., min_length=6, max_length=20)
    email: EmailStr

    # Cuenta
    password: str = Field(..., min_length=8, max_length=72)

    # Opcional
    observaciones: str | None = Field(None, max_length=500)

    @field_validator("cuil")
    @classmethod
    def _val_cuil(cls, v: str) -> str:
        return _validar_modulo11(v)


class AltaCiudadanoOut(BaseModel):
    id_ciudadano: int
    email: str
    verificacion_enviada: bool = True
    mensaje: str = (
        "Te enviamos un correo para verificar tu alta. "
        "Revisá tu casilla (y la carpeta de correo no deseado / spam) y hacé clic en el enlace."
    )


# ─── Alta de empresa (requiere ciudadano ya creado) ──────────────────────────

class AltaEmpresaIn(BaseModel):
    municipio_slug: str = Field(..., min_length=1, max_length=20)
    id_ciudadano: int  # el ciudadano que la da de alta (representante)

    cuit: str = Field(..., min_length=10, max_length=15)  # acepta guiones, se valida módulo 11
    razon_social: str = Field(..., min_length=1, max_length=200)
    id_actividad: int

    # Domicilio (OSM)
    calle: str = Field(..., min_length=1, max_length=200)
    localidad: str = Field(..., min_length=1, max_length=100)
    provincia: str = Field(..., min_length=1, max_length=100)
    latitud: float | None = None
    longitud: float | None = None

    # Contacto
    telefono: str = Field(..., min_length=6, max_length=20)
    email: EmailStr

    observaciones: str | None = Field(None, max_length=500)
    id_tipo_representacion: int = 1  # default: Representante Legal

    @field_validator("cuit")
    @classmethod
    def _val_cuit(cls, v: str) -> str:
        return _validar_modulo11(v)


class AltaEmpresaOut(BaseModel):
    id_empresa: int
    email: str
    verificacion_enviada: bool = True
    mensaje: str = (
        "Te enviamos un correo a la casilla de la empresa para verificar el alta. "
        "Revisá la bandeja de entrada y la carpeta de spam."
    )
