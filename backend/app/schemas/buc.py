"""
ZARIS API — Schemas Pydantic para el módulo BUC.
Validación de entrada/salida en los endpoints.
"""
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator
import re


# ── Helpers de validación ──────────────────────────────────────

def _validar_modulo11(valor: str) -> str:
    """Valida CUIL/CUIT con algoritmo módulo 11. Retorna el valor limpio (sin guiones)."""
    limpio = re.sub(r"[-\s]", "", valor)
    if not re.match(r"^\d{11}$", limpio):
        raise ValueError("Debe contener 11 dígitos numéricos")

    digitos = [int(d) for d in limpio]
    multiplicadores = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    suma = sum(d * m for d, m in zip(digitos[:10], multiplicadores))
    resto = suma % 11

    if resto == 0:
        esperado = 0
    elif resto == 1:
        # Caso especial: dígito verificador 9 (o 4 para prefijo 27, pero se acepta 9)
        esperado = 9
    else:
        esperado = 11 - resto

    if digitos[10] != esperado:
        raise ValueError(f"Dígito verificador inválido (se esperaba {esperado})")

    return limpio  # guardar sin guiones


def _validar_telefono_arg(valor: str) -> str:
    """Valida teléfono argentino: 10 dígitos sin 0 de área."""
    limpio = re.sub(r"[-\s()]", "", valor)
    if not re.match(r"^\d{10}$", limpio):
        raise ValueError("El teléfono debe contener exactamente 10 dígitos (código de área sin 0 + número)")
    if limpio.startswith("0"):
        raise ValueError("No incluir el 0 del código de área")
    return limpio


def _validar_email_fmt(valor: str) -> str:
    """Valida formato de email."""
    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", valor):
        raise ValueError("Formato de email inválido")
    return valor.lower().strip()


# ═══════════════════════════════════════════════════════════════
# USUARIOS
# ═══════════════════════════════════════════════════════════════

class UsuarioOut(BaseModel):
    id_usuario:   int
    nombre:       str
    nivel_acceso: int
    username:     str
    id_cargo:     Optional[str]
    id_municipio: int
    activo:       bool
    cuil:         Optional[str]
    buc_acceso:   bool
    fecha_alta:   datetime
    fecha_modif:  datetime

    class Config:
        from_attributes = True


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
    telefono: str = Field(..., max_length=15)
    email: str = Field(..., max_length=150)
    emp_chk: bool = False
    observaciones: Optional[str] = Field(None, max_length=500)

    @field_validator("cuil")
    @classmethod
    def validar_cuil(cls, v):
        return _validar_modulo11(v)

    @field_validator("telefono")
    @classmethod
    def validar_telefono(cls, v):
        return _validar_telefono_arg(v)

    @field_validator("email")
    @classmethod
    def validar_email(cls, v):
        return _validar_email_fmt(v)


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
    telefono: Optional[str] = Field(None, max_length=15)
    email: Optional[str] = Field(None, max_length=150)
    emp_chk: Optional[bool] = None
    observaciones: Optional[str] = Field(None, max_length=500)
    modificado_por: Optional[int] = None

    @field_validator("cuil")
    @classmethod
    def validar_cuil(cls, v):
        if v is None:
            return v
        return _validar_modulo11(v)

    @field_validator("telefono")
    @classmethod
    def validar_telefono(cls, v):
        if v is None:
            return v
        return _validar_telefono_arg(v)

    @field_validator("email")
    @classmethod
    def validar_email(cls, v):
        if v is None:
            return v
        return _validar_email_fmt(v)


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
    modificado_por: Optional[int]

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
    telefono: str = Field(..., max_length=15)
    email: str = Field(..., max_length=150)
    observaciones: Optional[str] = Field(None, max_length=500)

    @field_validator("cuit")
    @classmethod
    def validar_cuit(cls, v):
        return _validar_modulo11(v)

    @field_validator("telefono")
    @classmethod
    def validar_telefono(cls, v):
        return _validar_telefono_arg(v)

    @field_validator("email")
    @classmethod
    def validar_email(cls, v):
        return _validar_email_fmt(v)


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
    telefono: Optional[str] = Field(None, max_length=15)
    email: Optional[str] = Field(None, max_length=150)
    observaciones: Optional[str] = Field(None, max_length=500)
    modificado_por: Optional[int] = None

    @field_validator("cuit")
    @classmethod
    def validar_cuit(cls, v):
        if v is None:
            return v
        return _validar_modulo11(v)

    @field_validator("telefono")
    @classmethod
    def validar_telefono(cls, v):
        if v is None:
            return v
        return _validar_telefono_arg(v)

    @field_validator("email")
    @classmethod
    def validar_email(cls, v):
        if v is None:
            return v
        return _validar_email_fmt(v)


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
    modificado_por: Optional[int]

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
