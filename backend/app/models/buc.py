"""
ZARIS API — Modelos ORM del módulo BUC (Base Única de Ciudadanos).
Mapeo directo a las tablas creadas por 00_deploy_buc.sql y migraciones posteriores.
"""
from sqlalchemy import (
    Column, Integer, String, Boolean, Date, DateTime,
    Numeric, ForeignKey, UniqueConstraint, Index, func, CheckConstraint
)
from sqlalchemy.orm import relationship

from app.core.database import Base


# ── Tabla Usuarios ────────────────────────────────────────────

class Usuario(Base):
    __tablename__ = "usuarios"

    id_usuario    = Column(Integer, primary_key=True, autoincrement=True)
    nombre        = Column(String(150), nullable=False)
    nivel_acceso  = Column(Integer, nullable=False, default=3)
    username      = Column(String(50), nullable=False, unique=True)
    email         = Column(String(150), nullable=True)
    password_hash = Column(String(255), nullable=False)
    id_cargo      = Column(String(100))
    id_municipio  = Column(Integer, nullable=False, default=377)
    activo        = Column(Boolean, nullable=False, default=True)
    cuil          = Column(String(11))
    buc_acceso    = Column(Boolean, nullable=False, default=False)
    fecha_alta    = Column(DateTime, nullable=False, server_default=func.now())
    fecha_modif   = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("nivel_acceso BETWEEN 1 AND 4", name="ck_usuarios_nivel"),
        Index("idx_usuarios_username", "username"),
    )

    # Relaciones inversas (registros modificados por este usuario)
    ciudadanos_modificados = relationship("Ciudadano", back_populates="modificado_por_usuario",
                                          foreign_keys="Ciudadano.modificado_por")
    empresas_modificadas   = relationship("Empresa", back_populates="modificado_por_usuario",
                                          foreign_keys="Empresa.modificado_por")


# ── Tablas de Referencia ──────────────────────────────────────

class Nacionalidad(Base):
    __tablename__ = "nacionalidades"

    id                      = Column(Integer, primary_key=True, autoincrement=True)
    pais                    = Column(String(100), nullable=False)
    region                  = Column(String(50), nullable=False)
    activo                  = Column(Boolean, nullable=False, default=True)
    id_municipio            = Column(Integer, nullable=True)
    id_subarea              = Column(Integer, nullable=True)
    fecha_alta              = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_modificacion      = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    id_usuario_alta         = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    id_usuario_modificacion = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)

    ciudadanos = relationship("Ciudadano", back_populates="nacionalidad")


class TipoRepresentacion(Base):
    __tablename__ = "tipo_representacion"

    id                      = Column(Integer, primary_key=True, autoincrement=True)
    tipo                    = Column(String(50), nullable=False)
    descripcion             = Column(String(200), nullable=False)
    activo                  = Column(Boolean, nullable=False, default=True)
    id_municipio            = Column(Integer, nullable=True)
    id_subarea              = Column(Integer, nullable=True)
    fecha_alta              = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_modificacion      = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    id_usuario_alta         = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    id_usuario_modificacion = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)

    relaciones = relationship("CiudadanoEmpresa", back_populates="tipo_representacion")


class Actividad(Base):
    __tablename__ = "actividades"

    id                      = Column(Integer, primary_key=True, autoincrement=True)
    codigo_clae             = Column(Integer, nullable=False)
    descripcion             = Column(String(200), nullable=False)
    categoria_tasa          = Column(String(50), nullable=False)
    activo                  = Column(Boolean, nullable=False, default=True)
    id_municipio            = Column(Integer, nullable=True)
    id_subarea              = Column(Integer, nullable=True)
    fecha_alta              = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_modificacion      = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    id_usuario_alta         = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    id_usuario_modificacion = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)

    empresas = relationship("Empresa", back_populates="actividad")


# ── Tablas Principales ────────────────────────────────────────

class Ciudadano(Base):
    __tablename__ = "ciudadanos"

    id_ciudadano   = Column(Integer, primary_key=True, autoincrement=True)
    fecha_alta     = Column(DateTime, nullable=False, server_default=func.now())
    doc_tipo       = Column(String(10), nullable=False)
    doc_nro        = Column(String(10), nullable=False)
    cuil           = Column(String(13), nullable=False, unique=True)
    nombre         = Column(String(100), nullable=False)
    apellido       = Column(String(100), nullable=False)
    sexo           = Column(String(10), nullable=False)
    fecha_nac      = Column(Date, nullable=False)
    id_nacionalidad = Column(Integer, ForeignKey("nacionalidades.id"), nullable=False)
    ren_chk        = Column(Boolean, nullable=False, default=False)
    calle          = Column(String(200))
    altura         = Column(String(20))
    localidad      = Column(String(100))
    provincia      = Column(String(100))
    latitud        = Column(Numeric(10, 7))
    longitud       = Column(Numeric(10, 7))
    telefono       = Column(String(15), nullable=False)
    email          = Column(String(150), nullable=False)
    email_chk      = Column(Boolean, nullable=False, default=False)
    emp_chk        = Column(Boolean, nullable=False, default=False)
    observaciones           = Column(String(500))
    # legacy: campo original de última modificación
    fecha_modif             = Column(DateTime)
    activo                  = Column(Boolean, nullable=False, default=True)
    modificado_por          = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    # campos estándar agregados en migración 20
    id_municipio            = Column(Integer, nullable=True)
    id_subarea              = Column(Integer, nullable=True)
    fecha_modificacion      = Column(DateTime(timezone=True), nullable=True)
    id_usuario_alta         = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    id_usuario_modificacion = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        UniqueConstraint("doc_tipo", "doc_nro", name="uq_ciudadano_doc"),
        Index("idx_ciudadano_email", "email"),
        Index("idx_ciudadano_apellido", "apellido"),
    )

    nacionalidad           = relationship("Nacionalidad", back_populates="ciudadanos")
    empresas               = relationship("CiudadanoEmpresa", back_populates="ciudadano")
    modificado_por_usuario = relationship("Usuario", back_populates="ciudadanos_modificados",
                                          foreign_keys=[modificado_por])


class Empresa(Base):
    __tablename__ = "empresas"

    id_empresa     = Column(Integer, primary_key=True, autoincrement=True)
    fecha_alta     = Column(DateTime, nullable=False, server_default=func.now())
    cuit           = Column(String(13), nullable=False, unique=True)
    nombre         = Column(String(100), nullable=False)
    id_actividad   = Column(Integer, ForeignKey("actividades.id"), nullable=False)
    calle          = Column(String(200))
    altura         = Column(String(20))
    localidad      = Column(String(100))
    provincia      = Column(String(100))
    latitud        = Column(Numeric(10, 7))
    longitud       = Column(Numeric(10, 7))
    telefono       = Column(String(15), nullable=False)
    email          = Column(String(150), nullable=False)
    email_chk      = Column(Boolean, nullable=False, default=False)
    observaciones           = Column(String(500))
    # legacy: campo original de última modificación
    fecha_modif             = Column(DateTime)
    activo                  = Column(Boolean, nullable=False, default=True)
    modificado_por          = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    # campos estándar agregados en migración 20
    id_municipio            = Column(Integer, nullable=True)
    id_subarea              = Column(Integer, nullable=True)
    id_usuario_alta         = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    id_usuario_modificacion = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("idx_empresa_email", "email"),
        Index("idx_empresa_nombre", "nombre"),
    )

    actividad              = relationship("Actividad", back_populates="empresas")
    ciudadanos             = relationship("CiudadanoEmpresa", back_populates="empresa")
    modificado_por_usuario = relationship("Usuario", back_populates="empresas_modificadas",
                                          foreign_keys=[modificado_por])


# ── Tabla Intermedia ──────────────────────────────────────────

class CiudadanoEmpresa(Base):
    __tablename__ = "ciudadano_empresa"

    id                     = Column(Integer, primary_key=True, autoincrement=True)
    id_ciudadano           = Column(Integer, ForeignKey("ciudadanos.id_ciudadano"), nullable=False)
    id_empresa             = Column(Integer, ForeignKey("empresas.id_empresa"), nullable=False)
    id_tipo_representacion = Column(Integer, ForeignKey("tipo_representacion.id"), nullable=False)
    fecha_alta             = Column(DateTime, nullable=False, server_default=func.now())
    activo                 = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint(
            "id_ciudadano", "id_empresa", "id_tipo_representacion",
            name="uq_ciudadano_empresa_tipo"
        ),
    )

    ciudadano           = relationship("Ciudadano", back_populates="empresas")
    empresa             = relationship("Empresa", back_populates="ciudadanos")
    tipo_representacion = relationship("TipoRepresentacion", back_populates="relaciones")
