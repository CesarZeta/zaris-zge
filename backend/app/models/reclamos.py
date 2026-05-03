"""
ZARIS API — Modelos ORM del módulo Reclamos.
Tabla transaccional de reclamos + historial de cambios de estado.
Las tablas de área y subárea se toman de los maestros generales (area/subarea).
"""
from sqlalchemy import (
    Column, Integer, String, Boolean, Text, DateTime,
    ForeignKey, Index, CheckConstraint, func
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class Reclamo(Base):
    __tablename__ = "reclamos"

    id_reclamo       = Column(Integer, primary_key=True, autoincrement=True)
    nro_reclamo      = Column(String(20), unique=True, nullable=True)
    id_ciudadano     = Column(Integer, ForeignKey("ciudadanos.id_ciudadano", ondelete="RESTRICT"), nullable=True)
    id_tipo_reclamo  = Column(Integer, ForeignKey("tipo_reclamo.id_tipo_reclamo", ondelete="SET NULL"), nullable=True)
    id_area          = Column(Integer, ForeignKey("area.id_area", ondelete="SET NULL"), nullable=True)
    descripcion      = Column(Text, nullable=False)
    domicilio_reclamo = Column(String(300), nullable=True)
    prioridad        = Column(String(10), nullable=False, default="Media")
    estado           = Column(String(30), nullable=False, default="Ingresado")
    id_agente_asignado = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    observaciones    = Column(Text, nullable=True)
    activo           = Column(Boolean, nullable=False, default=True)
    id_municipio     = Column(Integer, nullable=True)
    id_subarea       = Column(Integer, nullable=True)
    fecha_alta       = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_modificacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    id_usuario_alta  = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    id_usuario_modificacion = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        CheckConstraint("prioridad IN ('Alta','Media','Baja')", name="ck_reclamo_prioridad"),
        CheckConstraint(
            "estado IN ('Ingresado','En revisión','En gestión','Resuelto','Rechazado','Cerrado')",
            name="ck_reclamo_estado"
        ),
        Index("idx_reclamos_ciudadano", "id_ciudadano"),
        Index("idx_reclamos_area", "id_area"),
        Index("idx_reclamos_estado", "estado"),
        Index("idx_reclamos_fecha_alta", "fecha_alta"),
    )

    historial = relationship("ReclamoHistorial", back_populates="reclamo",
                             cascade="all, delete-orphan", order_by="ReclamoHistorial.fecha_alta")


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

    id_tipo_reclamo  = Column(Integer, primary_key=True, autoincrement=True)
    nombre           = Column(String(200), nullable=False)
    descripcion      = Column(Text, nullable=True)
    id_area          = Column(Integer, ForeignKey("area.id_area", ondelete="SET NULL"), nullable=True)
    sla_dias         = Column(Integer, default=5)
    activo           = Column(Boolean, nullable=False, default=True)
    id_municipio     = Column(Integer, nullable=True)
    id_subarea       = Column(Integer, nullable=True)
    fecha_alta       = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_modificacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    id_usuario_alta  = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    id_usuario_modificacion = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("idx_tipo_reclamo_area", "id_area"),
    )

    reclamos = relationship("Reclamo", foreign_keys=[Reclamo.id_tipo_reclamo],
                            primaryjoin="TipoReclamo.id_tipo_reclamo == Reclamo.id_tipo_reclamo")
