"""
ZARIS API - Modelos ORM para auth publico de ciudadanos (App Vecinos).

Mapeo directo a las tablas creadas por mig 53:
- ciudadano_credencial: 1:1 con ciudadanos, password + tokens de activacion/recovery + lockout
- ciudadano_canal_preferido: preferencias multi-canal (solo email se usa en MVP)
- ciudadano_push_subscription: placeholder Web Push (no se consume en esta etapa)

Estilo Column 1.x para mantener consistencia con app/models/buc.py y resto del proyecto.
"""
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey,
    UniqueConstraint, Index, Text, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class CiudadanoCredencial(Base):
    __tablename__ = "ciudadano_credencial"

    id_ciudadano_credencial = Column(Integer, primary_key=True, autoincrement=True)
    id_ciudadano = Column(
        Integer,
        ForeignKey("ciudadanos.id_ciudadano", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Credenciales
    password_hash = Column(String(255), nullable=True)

    # Activacion inicial
    token_activacion = Column(UUID(as_uuid=True), nullable=True)
    token_activacion_expira = Column(DateTime(timezone=True), nullable=True)
    activado = Column(Boolean, nullable=False, default=False)
    activado_en = Column(DateTime(timezone=True), nullable=True)

    # Recovery
    token_recovery = Column(UUID(as_uuid=True), nullable=True)
    token_recovery_expira = Column(DateTime(timezone=True), nullable=True)

    # Anti-abuso de reenvios
    fecha_ultimo_email_activacion = Column(DateTime(timezone=True), nullable=True)
    fecha_ultimo_email_recovery = Column(DateTime(timezone=True), nullable=True)

    # Lockout
    intentos_fallidos = Column(Integer, nullable=False, default=0)
    bloqueada_hasta = Column(DateTime(timezone=True), nullable=True)
    fecha_ultimo_login = Column(DateTime(timezone=True), nullable=True)
    fecha_ultimo_cambio_password = Column(DateTime(timezone=True), nullable=True)

    # Estandar §10
    activo = Column(Boolean, nullable=False, default=True)
    id_municipio = Column(Integer, nullable=True)
    id_subarea = Column(Integer, nullable=True)
    fecha_alta = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_modificacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    id_usuario_alta = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    id_usuario_modificacion = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("idx_ciudadano_credencial_token_activacion", "token_activacion",
              postgresql_where=token_activacion.isnot(None)),
        Index("idx_ciudadano_credencial_token_recovery", "token_recovery",
              postgresql_where=token_recovery.isnot(None)),
    )


class CiudadanoCanalPreferido(Base):
    __tablename__ = "ciudadano_canal_preferido"

    id_ciudadano_canal_preferido = Column(Integer, primary_key=True, autoincrement=True)
    id_ciudadano = Column(
        Integer,
        ForeignKey("ciudadanos.id_ciudadano", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Canales (todos preparados, solo email se usa en MVP)
    canal_email = Column(Boolean, nullable=False, default=True)
    canal_push = Column(Boolean, nullable=False, default=True)
    canal_whatsapp = Column(Boolean, nullable=False, default=False)
    canal_sms = Column(Boolean, nullable=False, default=False)

    # Estandar §10
    activo = Column(Boolean, nullable=False, default=True)
    id_municipio = Column(Integer, nullable=True)
    id_subarea = Column(Integer, nullable=True)
    fecha_alta = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_modificacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    id_usuario_alta = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    id_usuario_modificacion = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)


class CiudadanoPushSubscription(Base):
    """Placeholder Web Push. No se consume todavia (Etapa 5)."""
    __tablename__ = "ciudadano_push_subscription"

    id_ciudadano_push_subscription = Column(Integer, primary_key=True, autoincrement=True)
    id_ciudadano = Column(
        Integer,
        ForeignKey("ciudadanos.id_ciudadano", ondelete="CASCADE"),
        nullable=False,
    )

    endpoint = Column(Text, nullable=False)
    p256dh = Column(Text, nullable=False)
    auth_secret = Column(Text, nullable=False)
    user_agent = Column(Text, nullable=True)

    # Estandar §10
    activo = Column(Boolean, nullable=False, default=True)
    id_municipio = Column(Integer, nullable=True)
    id_subarea = Column(Integer, nullable=True)
    fecha_alta = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_modificacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    id_usuario_alta = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    id_usuario_modificacion = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        UniqueConstraint("id_ciudadano", "endpoint", name="uq_ciudadano_push_endpoint"),
    )
