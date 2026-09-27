"""
Modelo de `usuario_push_subscription` (mig 108, 2026-09-26) — suscripciones
Web Push de USUARIOS INTERNOS (App de agentes `zaris-agentes`).

Espejo de CiudadanoPushSubscription (models/ciudadano_credencial.py) clavado a
`usuarios`. Los routers usan SQL crudo; el modelo existe para que la tabla
figure en la metadata (§20) y como documentación del shape.
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func

from app.core.database import Base


class UsuarioPushSubscription(Base):
    __tablename__ = "usuario_push_subscription"
    __table_args__ = (
        UniqueConstraint("id_usuario", "endpoint", name="usuario_push_subscription_id_usuario_endpoint_key"),
        {"extend_existing": True},
    )

    id_usuario_push_subscription = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario = Column(
        Integer,
        ForeignKey("usuarios.id_usuario", ondelete="CASCADE"),
        nullable=False,
    )

    endpoint = Column(Text, nullable=False)
    p256dh = Column(Text, nullable=False)
    auth_secret = Column(Text, nullable=False)
    user_agent = Column(Text, nullable=True)

    # Estándar §10
    activo = Column(Boolean, nullable=False, default=True)
    id_municipio = Column(Integer, nullable=True)
    id_subarea = Column(Integer, nullable=True)
    fecha_alta = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_modificacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    id_usuario_alta = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    id_usuario_modificacion = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
