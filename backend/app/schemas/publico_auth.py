"""
Schemas Pydantic para auth publico de ciudadanos (App Vecinos).
Endpoints bajo /api/v1/publico/auth/* y /api/v1/publico/identidad-municipio.
"""
from pydantic import BaseModel, EmailStr, Field


class CiudadanoBasicoOut(BaseModel):
    id_ciudadano: int
    dni: str
    nombre: str
    apellido: str
    email: str
    estado_validacion: str


class RegistroCiudadanoIn(BaseModel):
    """Body que envia un agente para dar de alta a un ciudadano + crear su credencial."""
    dni: str = Field(..., min_length=7, max_length=8)
    apellido: str = Field(..., min_length=1, max_length=100)
    nombre: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    telefono: str | None = Field(None, max_length=15)


class RegistroCiudadanoOut(BaseModel):
    id_ciudadano: int
    email: str
    activacion_enviada: bool


class ActivarIn(BaseModel):
    token: str
    password: str = Field(..., min_length=8, max_length=72)


class ActivarOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    ciudadano: CiudadanoBasicoOut


class ReenviarActivacionIn(BaseModel):
    dni: str = Field(..., min_length=7, max_length=8)


class LoginCiudadanoIn(BaseModel):
    dni: str = Field(..., min_length=7, max_length=8)
    password: str = Field(..., min_length=1, max_length=72)


class LoginCiudadanoOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    ciudadano: CiudadanoBasicoOut


class RecuperarPasswordIn(BaseModel):
    dni: str = Field(..., min_length=7, max_length=8)


class ResetearPasswordIn(BaseModel):
    token: str
    password: str = Field(..., min_length=8, max_length=72)


class ResetearPasswordOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    ciudadano: CiudadanoBasicoOut


class IdentidadMunicipioOut(BaseModel):
    municipio_nombre: str | None
    municipio_logo_url: str | None
    municipio_descripcion: str | None
    municipio_color_primary: str | None
    municipio_color_accent: str | None


class GenericoOkOut(BaseModel):
    enviado: bool = True
