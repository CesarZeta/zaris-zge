"""
ZARIS API — Schemas Pydantic para el módulo BUC.
Validación de entrada/salida en los endpoints.
"""
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator
import re


# ═══════════════════════════════════════════════════════════════
# NACIONALIDADES
# ═══════════════════════════════════════════════════════════════

class NacionalidadOut(BaseModel):
    id: int
    pais: str
    region: str

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════
# TIPO REPRESENTACIÓN
# ═══════════════════════════════════════════════════════════════

class TipoRepresentacionOut(BaseModel):
    id: int
    tipo: str
    descripcion: str

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════
# ACTIVIDADES
# ═══════════════════════════════════════════════════════════════

class ActividadOut(BaseModel):
    id: int
    codigo_clae: int
    descripcion: str
    categoria_tasa: str

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════
# CIUDADANO
# ═══════════════════════════════════════════════════════════════

class CiudadanoBase(BaseModel):
    doc_tipo: str = Field(..., pattern=r"^(DNI|PASAPORTE)$")
    doc_nro: str = Field(..., max_length=10)
    cuil: str = Field(..., max_length=13)
    nombre: str = Field(..., max_length=100)
    apellido: str = Field(..., max_length=100)
    sexo: str = Field(..., pattern=r"^(HOMBRE|MUJER|OTROS)$")
    fecha_nac: date
    id_nacionalidad: int
    calle: Optional[str] = Field(None, max_length=200)
    altura: Optional[str] = Field(None, max_length=20)
    localidad: Optional[str] = Field(None, max_length=100)
    provincia: Optional[str] = Field(None, max_length=100)
    telefono: str = Field(..., max_length=10)
    email: str = Field(..., max_length=150)
    emp_chk: bool = False
    observaciones: Optional[str] = Field(None, max_length=250)

    @field_validator("cuil")
    @classmethod
    def validar_cuil(cls, v):
        limpio = re.sub(r"[-\s]", "", v)
        if not re.match(r"^\d{11}$", limpio):
            raise ValueError("CUIL debe contener 11 digitos")
        return limpio  # guardar sin guiones

    @field_validator("telefono")
    @classmethod
    def validar_telefono(cls, v):
        limpio = re.sub(r"[-\s()]", "", v)
        if not re.match(r"^\d{10}$", limpio):
            raise ValueError("Telefono debe contener 10 digitos")
        if limpio.startswith("0"):
            raise ValueError("No incluir el 0 del codigo de area")
        return limpio

    @field_validator("email")
    @classmethod
    def validar_email(cls, v):
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("Formato de email invalido")
        return v.lower().strip()


class CiudadanoCreate(CiudadanoBase):
    pass


class CiudadanoUpdate(BaseModel):
    """Todos los campos opcionales para update parcial."""
    doc_tipo: Optional[str] = Field(None, pattern=r"^(DNI|PASAPORTE)$")
    doc_nro: Optional[str] = Field(None, max_length=10)
    cuil: Optional[str] = Field(None, max_length=13)
    nombre: Optional[str] = Field(None, max_length=100)
    apellido: Optional[str] = Field(None, max_length=100)
    sexo: Optional[str] = Field(None, pattern=r"^(HOMBRE|MUJER|OTROS)$")
    fecha_nac: Optional[date] = None
    id_nacionalidad: Optional[int] = None
    calle: Optional[str] = Field(None, max_length=200)
    altura: Optional[str] = Field(None, max_length=20)
    localidad: Optional[str] = Field(None, max_length=100)
    provincia: Optional[str] = Field(None, max_length=100)
    telefono: Optional[str] = Field(None, max_length=10)
    email: Optional[str] = Field(None, max_length=150)
    emp_chk: Optional[bool] = None
    observaciones: Optional[str] = Field(None, max_length=250)


class CiudadanoOut(BaseModel):
    id_ciudadano: int
    fecha_alta: datetime
    doc_tipo: str
    doc_nro: str
    cuil: str
    nombre: str
    apellido: str
    sexo: str
    fecha_nac: date
    id_nacionalidad: int
    ren_chk: bool
    calle: Optional[str]
    altura: Optional[str]
    localidad: Optional[str]
    provincia: Optional[str]
    latitud: Optional[float]
    longitud: Optional[float]
    telefono: str
    email: str
    email_chk: bool
    emp_chk: bool
    observaciones: Optional[str]
    fecha_modif: Optional[datetime]
    activo: bool

    class Config:
        from_attributes = True


class CiudadanoConNacionalidad(CiudadanoOut):
    """Ciudadano con datos de nacionalidad incluidos."""
    nacionalidad: Optional[NacionalidadOut] = None


# ═══════════════════════════════════════════════════════════════
# EMPRESA
# ═══════════════════════════════════════════════════════════════

class EmpresaBase(BaseModel):
    cuit: str = Field(..., max_length=13)
    nombre: str = Field(..., max_length=100)
    id_actividad: int
    calle: Optional[str] = Field(None, max_length=200)
    altura: Optional[str] = Field(None, max_length=20)
    localidad: Optional[str] = Field(None, max_length=100)
    provincia: Optional[str] = Field(None, max_length=100)
    telefono: str = Field(..., max_length=10)
    email: str = Field(..., max_length=150)
    observaciones: Optional[str] = Field(None, max_length=250)

    @field_validator("cuit")
    @classmethod
    def validar_cuit(cls, v):
        limpio = re.sub(r"[-\s]", "", v)
        if not re.match(r"^\d{11}$", limpio):
            raise ValueError("CUIT debe contener 11 digitos")
        return limpio  # guardar sin guiones

    @field_validator("telefono")
    @classmethod
    def validar_telefono(cls, v):
        limpio = re.sub(r"[-\s()]", "", v)
        if not re.match(r"^\d{10}$", limpio):
            raise ValueError("Telefono debe contener 10 digitos")
        return limpio

    @field_validator("email")
    @classmethod
    def validar_email(cls, v):
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("Formato de email invalido")
        return v.lower().strip()


class EmpresaCreate(EmpresaBase):
    pass


class EmpresaUpdate(BaseModel):
    cuit: Optional[str] = Field(None, max_length=13)
    nombre: Optional[str] = Field(None, max_length=100)
    id_actividad: Optional[int] = None
    calle: Optional[str] = Field(None, max_length=200)
    altura: Optional[str] = Field(None, max_length=20)
    localidad: Optional[str] = Field(None, max_length=100)
    provincia: Optional[str] = Field(None, max_length=100)
    telefono: Optional[str] = Field(None, max_length=10)
    email: Optional[str] = Field(None, max_length=150)
    observaciones: Optional[str] = Field(None, max_length=250)


class EmpresaOut(BaseModel):
    id_empresa: int
    fecha_alta: datetime
    cuit: str
    nombre: str
    id_actividad: int
    calle: Optional[str]
    altura: Optional[str]
    localidad: Optional[str]
    provincia: Optional[str]
    latitud: Optional[float]
    longitud: Optional[float]
    telefono: str
    email: str
    email_chk: bool
    observaciones: Optional[str]
    fecha_modif: Optional[datetime]
    activo: bool

    class Config:
        from_attributes = True


class EmpresaConActividad(EmpresaOut):
    actividad: Optional[ActividadOut] = None


# ═══════════════════════════════════════════════════════════════
# CIUDADANO-EMPRESA
# ═══════════════════════════════════════════════════════════════

class CiudadanoEmpresaCreate(BaseModel):
    id_ciudadano: int
    id_empresa: int
    id_tipo_representacion: int


class CiudadanoEmpresaOut(BaseModel):
    id: int
    id_ciudadano: int
    id_empresa: int
    id_tipo_representacion: int
    fecha_alta: datetime
    activo: bool

    class Config:
        from_attributes = True
