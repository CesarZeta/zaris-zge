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


# ─── Alta en UN PASO con ficha COMPLETA (decisión 2026-06-12) ─────────────────
# El vecino carga TODA su ficha (con las validaciones canónicas del ciudadano) en la
# página pública. NUNCA se escriben placeholders falsos en la BUC (fecha 1900, CUIL
# inventado): el registro nace completo y válido. Reemplaza al modelo de 2 pasos de la
# Fase 4 (paso 2 "completar ficha" en la app, eliminado).

class AltaCuentaIn(BaseModel):
    municipio_slug: str = Field(..., min_length=1, max_length=20)

    # Identificación
    doc_nro: str = Field(..., min_length=6, max_length=15)   # DNI (digit-only se normaliza en el endpoint)
    cuil: str = Field(..., min_length=10, max_length=15)     # acepta guiones, se valida módulo 11

    # Datos personales
    nombre: str = Field(..., min_length=1, max_length=100)
    apellido: str = Field(..., min_length=1, max_length=100)
    sexo: Literal["HOMBRE", "MUJER", "OTROS"]
    fecha_nac: str = Field(..., description="YYYY-MM-DD")
    id_nacionalidad: int

    # Domicilio (lo completa el buscador OSM en el front; lat/lon opcionales)
    calle: str = Field(..., min_length=1, max_length=200)
    localidad: str = Field(..., min_length=1, max_length=100)
    provincia: str = Field(..., min_length=1, max_length=100)
    latitud: float | None = None
    longitud: float | None = None

    # Contacto + cuenta
    telefono: str = Field(..., min_length=6, max_length=20)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)

    observaciones: str | None = Field(None, max_length=500)

    @field_validator("cuil")
    @classmethod
    def _val_cuil(cls, v: str) -> str:
        return _validar_modulo11(v)


class AltaCuentaOut(BaseModel):
    id_ciudadano: int
    email: str
    verificacion_enviada: bool = True
    mensaje: str = (
        "Tu alta quedó registrada. Te enviamos un correo para verificar tu dirección: "
        "revisá tu casilla (y la carpeta de correo no deseado / spam) y hacé clic en el enlace. "
        "Después de verificar ya podés iniciar sesión con tu DNI y la contraseña que elegiste."
    )


# ─── Activar cuenta de un vecino que YA existe en la BUC ─────────────────────
# El alta pública rechaza DNIs ya registrados (no duplica). Esta vía le permite al
# vecino pre-existente pedir su cuenta de portal: se le manda el mail de activación
# al email que YA figura en la BUC, creando la credencial sobre el MISMO registro.
# Anti-enumeración: SIEMPRE responde 200 con el mismo mensaje, exista o no el DNI.

class ActivarExistenteIn(BaseModel):
    municipio_slug: str = Field(..., min_length=1, max_length=20)
    doc_nro: str = Field(..., min_length=6, max_length=15)


class ActivarExistenteOut(BaseModel):
    enviado: bool = True
    mensaje: str = (
        "Si tus datos figuran en el registro del municipio, te enviamos un correo a la "
        "casilla que tenemos registrada para que actives tu cuenta. Si no te llega, "
        "acercate a una oficina de atención para actualizar tu email."
    )


# Paso 2: completar la ficha real del vecino ya verificado y logueado (JWT scope publico).
# El id_ciudadano sale SIEMPRE del token, nunca del body (no puede editar a terceros).
class CompletarFichaIn(BaseModel):
    cuil: str = Field(..., min_length=10, max_length=15)  # acepta guiones, se valida módulo 11
    sexo: Literal["HOMBRE", "MUJER", "OTROS"]
    fecha_nac: str = Field(..., description="YYYY-MM-DD")
    id_nacionalidad: int

    # Domicilio (lo completa el buscador OSM en el front)
    calle: str = Field(..., min_length=1, max_length=200)
    localidad: str = Field(..., min_length=1, max_length=100)
    provincia: str = Field(..., min_length=1, max_length=100)
    latitud: float | None = None
    longitud: float | None = None

    telefono: str = Field(..., min_length=6, max_length=20)
    observaciones: str | None = Field(None, max_length=500)

    @field_validator("cuil")
    @classmethod
    def _val_cuil(cls, v: str) -> str:
        return _validar_modulo11(v)


class CompletarFichaOut(BaseModel):
    id_ciudadano: int
    ficha_completa: bool = True
    mensaje: str = "Tus datos quedaron guardados."


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
