"""
ZARIS API — Modelos ORM del módulo Reclamos (v1.2).
"""
from sqlalchemy import (
    Column, Integer, String, Boolean, Text, DateTime,
    ForeignKey, Index, CheckConstraint, func
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class Equipo(Base):
    """Stub para que SQLAlchemy resuelva las FKs a equipos.id_equipo."""
    __tablename__ = "equipos"
    __table_args__ = {"extend_existing": True}

    id_equipo = Column(Integer, primary_key=True, autoincrement=True)


class Reclamo(Base):
    __tablename__ = "reclamos"

    id_reclamo          = Column(Integer, primary_key=True, autoincrement=True)
    nro_reclamo         = Column(String(20), unique=True, nullable=True)
    id_ciudadano        = Column(Integer, ForeignKey("ciudadanos.id_ciudadano", ondelete="RESTRICT"), nullable=True)
    id_tipo_reclamo     = Column(Integer, ForeignKey("tipo_reclamo.id_tipo_reclamo", ondelete="SET NULL"), nullable=True)
    id_area             = Column(Integer, ForeignKey("area.id_area", ondelete="SET NULL"), nullable=True)
    descripcion         = Column(Text, nullable=False)
    domicilio_reclamo   = Column(String(300), nullable=True)
    prioridad           = Column(String(10), nullable=False, default="Media")
    estado              = Column(String(30), nullable=False, default="Sin asignar")
    id_agente_asignado  = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    id_reclamo_padre    = Column(Integer, ForeignKey("reclamos.id_reclamo", ondelete="SET NULL"), nullable=True)
    observaciones       = Column(Text, nullable=True)
    activo              = Column(Boolean, nullable=False, default=True)
    id_municipio        = Column(Integer, nullable=True)
    id_subarea          = Column(Integer, nullable=True)
    fecha_alta          = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_modificacion  = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    id_usuario_alta     = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    id_usuario_modificacion = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        CheckConstraint("prioridad IN ('Alta','Media','Baja')", name="ck_reclamo_prioridad"),
        CheckConstraint(
            "estado IN ('Sin asignar','En gestión','En espera','En auditoría','Resuelto','Cancelado')",
            name="ck_reclamo_estado"
        ),
        Index("idx_reclamos_ciudadano", "id_ciudadano"),
        Index("idx_reclamos_area", "id_area"),
        Index("idx_reclamos_estado", "estado"),
        Index("idx_reclamos_fecha_alta", "fecha_alta"),
        Index("idx_reclamos_padre", "id_reclamo_padre"),
    )

    historial = relationship("ReclamoHistorial", back_populates="reclamo",
                             cascade="all, delete-orphan", order_by="ReclamoHistorial.fecha_alta")
    ordenes   = relationship("OrdenTrabajo", back_populates="reclamo",
                             foreign_keys="OrdenTrabajo.id_reclamo")


class ReclamoHistorial(Base):
    __tablename__ = "reclamo_historial"

    id_historial    = Column(Integer, primary_key=True, autoincrement=True)
    id_reclamo      = Column(Integer, ForeignKey("reclamos.id_reclamo", ondelete="CASCADE"), nullable=False)
    accion          = Column(String(100), nullable=False)
    estado_anterior = Column(String(30), nullable=True)
    estado_nuevo    = Column(String(30), nullable=True)
    nota            = Column(Text, nullable=True)
    fecha_alta      = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    id_usuario_alta = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("idx_reclamo_hist_reclamo", "id_reclamo"),
    )

    reclamo = relationship("Reclamo", back_populates="historial")


class TipoReclamo(Base):
    __tablename__ = "tipo_reclamo"

    id_tipo_reclamo     = Column(Integer, primary_key=True, autoincrement=True)
    nombre              = Column(String(200), nullable=False)
    descripcion         = Column(Text, nullable=True)
    id_area             = Column(Integer, ForeignKey("area.id_area", ondelete="SET NULL"), nullable=True)
    id_subarea          = Column(Integer, ForeignKey("subarea.id_subarea", ondelete="SET NULL"), nullable=True)
    sla_dias            = Column(Integer, default=5)
    audit               = Column(Boolean, nullable=False, default=False)
    activo              = Column(Boolean, nullable=False, default=True)
    id_municipio        = Column(Integer, nullable=True)
    fecha_alta          = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_modificacion  = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    id_usuario_alta     = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    id_usuario_modificacion = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("idx_tipo_reclamo_area", "id_area"),
        Index("idx_tipo_reclamo_subarea", "id_subarea"),
    )


class EstadoOT(Base):
    __tablename__ = "estado_ot"

    id_estado_ot    = Column(Integer, primary_key=True, autoincrement=True)
    nombre          = Column(String(100), nullable=False, unique=True)
    descripcion     = Column(Text, nullable=True)
    color           = Column(String(20), nullable=True)
    es_final        = Column(Boolean, nullable=False, default=False)
    orden           = Column(Integer, nullable=False, default=0)
    activo          = Column(Boolean, nullable=False, default=True)
    id_municipio    = Column(Integer, nullable=True)
    fecha_alta      = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_modificacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class OrdenTrabajo(Base):
    __tablename__ = "ordenes_trabajo"

    id_ot                   = Column(Integer, primary_key=True, autoincrement=True)
    nro_ot                  = Column(String(20), unique=True, nullable=True)
    id_reclamo              = Column(Integer, ForeignKey("reclamos.id_reclamo", ondelete="RESTRICT"), nullable=False)
    id_estado               = Column(Integer, ForeignKey("estado_ot.id_estado_ot", ondelete="RESTRICT"), nullable=False)
    id_agente               = Column(Integer, ForeignKey("agentes.id_agente", ondelete="SET NULL"), nullable=True)
    id_equipo               = Column(Integer, ForeignKey("equipos.id_equipo", ondelete="SET NULL"), nullable=True)
    es_auditoria            = Column(Boolean, nullable=False, default=False)
    resultado_auditoria     = Column(String(20), nullable=True)
    observaciones_auditoria = Column(Text, nullable=True)
    id_ot_origen            = Column(Integer, ForeignKey("ordenes_trabajo.id_ot", ondelete="SET NULL"), nullable=True)
    id_supervisor_asigna    = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="RESTRICT"), nullable=False)
    fecha_creacion          = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_cierre            = Column(DateTime(timezone=True), nullable=True)
    observaciones           = Column(Text, nullable=True)
    activo                  = Column(Boolean, nullable=False, default=True)
    id_municipio            = Column(Integer, nullable=True)
    id_subarea              = Column(Integer, nullable=True)
    fecha_alta              = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_modificacion      = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    id_usuario_alta         = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    id_usuario_modificacion = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        CheckConstraint("resultado_auditoria IN ('aprobada','rechazada')", name="ck_ot_resultado"),
        Index("idx_ot_reclamo",   "id_reclamo"),
        Index("idx_ot_agente",    "id_agente"),
        Index("idx_ot_equipo",    "id_equipo"),
        Index("idx_ot_estado",    "id_estado"),
        Index("idx_ot_auditoria", "es_auditoria"),
    )

    reclamo = relationship("Reclamo", back_populates="ordenes",
                           foreign_keys=[id_reclamo])


class EquipoAgente(Base):
    __tablename__ = "equipo_agentes"

    id_equipo_agente    = Column(Integer, primary_key=True, autoincrement=True)
    id_equipo           = Column(Integer, ForeignKey("equipos.id_equipo", ondelete="CASCADE"), nullable=False)
    id_agente           = Column(Integer, ForeignKey("agentes.id_agente", ondelete="CASCADE"), nullable=False)
    activo              = Column(Boolean, nullable=False, default=True)
    id_municipio        = Column(Integer, nullable=True)
    id_subarea          = Column(Integer, nullable=True)
    fecha_alta          = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_modificacion  = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    id_usuario_alta     = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    id_usuario_modificacion = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("idx_ea_equipo", "id_equipo"),
        Index("idx_ea_agente", "id_agente"),
    )


class ConfiguracionGeneral(Base):
    __tablename__ = "configuracion_general"

    id_config           = Column(Integer, primary_key=True, autoincrement=True)
    clave               = Column(String(100), nullable=False, unique=True)
    valor               = Column(Text, nullable=False)
    tipo                = Column(String(20), nullable=False, default="string")
    descripcion         = Column(Text, nullable=True)
    activo              = Column(Boolean, nullable=False, default=True)
    fecha_alta          = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_modificacion  = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
