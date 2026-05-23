"""
ZARIS API — Modelos ORM del modulo Encuestas (CSAT) — migracion 57.

Encuestas de satisfaccion disparadas al cierre de reclamos. Encuesta estandar
ZARIS (no editable por municipio en v1), con ramificacion condicional segun la
satisfaccion inicial (1-5).

Jerarquia:
    EncuestaPlantilla 1-N EncuestaPregunta 1-N EncuestaOpcion
    EncuestaEnvio 1-1 EncuestaRespuesta 1-N EncuestaRespuestaDetalle

Convenciones:
    - PK estilo id_<tabla> (§5/§28).
    - Estandar §10 completo (incluye id_usuario_alta/modificacion).
    - id_municipio/id_subarea INTEGER nullable, sin FK fisica ("FK futura" §10).
    - BUC obligatoria (§2): id_ciudadano es FK fisica a ciudadanos(id_ciudadano).
"""
from sqlalchemy import (
    Column, Integer, SmallInteger, String, Boolean, Text, DateTime,
    ForeignKey, Index, CheckConstraint, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class EncuestaPlantilla(Base):
    __tablename__ = "encuesta_plantilla"

    id_encuesta_plantilla = Column(Integer, primary_key=True, autoincrement=True)
    nombre                = Column(String(100), nullable=False)
    descripcion           = Column(Text, nullable=True)
    version               = Column(String(20), nullable=False, default="1.0")
    tipo                  = Column(String(30), nullable=False)
    # estandar §10
    activo                  = Column(Boolean, nullable=False, default=True)
    id_municipio            = Column(Integer, nullable=True)
    id_subarea              = Column(Integer, nullable=True)
    fecha_alta              = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_modificacion      = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    id_usuario_alta         = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    id_usuario_modificacion = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)

    preguntas = relationship(
        "EncuestaPregunta", back_populates="plantilla", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "tipo IN ('reclamos','tramites','turnos')",
            name="ck_encuesta_plantilla_tipo",
        ),
    )


class EncuestaPregunta(Base):
    __tablename__ = "encuesta_pregunta"

    id_encuesta_pregunta = Column(Integer, primary_key=True, autoincrement=True)
    id_plantilla         = Column(Integer, ForeignKey("encuesta_plantilla.id_encuesta_plantilla", ondelete="CASCADE"), nullable=False)
    texto                = Column(Text, nullable=False)
    tipo                 = Column(String(20), nullable=False)
    orden                = Column(Integer, nullable=False)
    rama                 = Column(String(20), nullable=False)
    obligatoria          = Column(Boolean, nullable=False, default=True)
    # estandar §10
    activo                  = Column(Boolean, nullable=False, default=True)
    id_municipio            = Column(Integer, nullable=True)
    id_subarea              = Column(Integer, nullable=True)
    fecha_alta              = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_modificacion      = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    id_usuario_alta         = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    id_usuario_modificacion = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)

    plantilla = relationship("EncuestaPlantilla", back_populates="preguntas")
    opciones  = relationship(
        "EncuestaOpcion", back_populates="pregunta", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "tipo IN ('likert5','texto_libre','si_no','multiple')",
            name="ck_encuesta_pregunta_tipo",
        ),
        CheckConstraint(
            "rama IN ('todos','satisfechos','neutrales','insatisfechos')",
            name="ck_encuesta_pregunta_rama",
        ),
        Index("idx_encuesta_pregunta_plantilla", "id_plantilla"),
    )


class EncuestaOpcion(Base):
    __tablename__ = "encuesta_opcion"

    id_encuesta_opcion = Column(Integer, primary_key=True, autoincrement=True)
    id_pregunta        = Column(Integer, ForeignKey("encuesta_pregunta.id_encuesta_pregunta", ondelete="CASCADE"), nullable=False)
    texto              = Column(String(200), nullable=False)
    valor              = Column(String(50), nullable=False)
    orden              = Column(Integer, nullable=False)
    # estandar §10
    activo                  = Column(Boolean, nullable=False, default=True)
    id_municipio            = Column(Integer, nullable=True)
    id_subarea              = Column(Integer, nullable=True)
    fecha_alta              = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_modificacion      = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    id_usuario_alta         = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    id_usuario_modificacion = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)

    pregunta = relationship("EncuestaPregunta", back_populates="opciones")

    __table_args__ = (
        Index("idx_encuesta_opcion_pregunta", "id_pregunta"),
    )


class EncuestaEnvio(Base):
    __tablename__ = "encuesta_envio"

    id_encuesta_envio      = Column(Integer, primary_key=True, autoincrement=True)
    id_plantilla           = Column(Integer, ForeignKey("encuesta_plantilla.id_encuesta_plantilla", ondelete="RESTRICT"), nullable=False)
    # BUC obligatoria (§2): FK fisica al ciudadano
    id_ciudadano           = Column(Integer, ForeignKey("ciudadanos.id_ciudadano", ondelete="RESTRICT"), nullable=False)
    id_reclamo             = Column(Integer, ForeignKey("reclamos.id_reclamo", ondelete="RESTRICT"), nullable=False)
    token_unico            = Column(UUID(as_uuid=True), nullable=False, server_default=func.gen_random_uuid())
    email_destino_snapshot = Column(String(150), nullable=False)
    fecha_envio            = Column(DateTime(timezone=True), nullable=True)
    fecha_apertura         = Column(DateTime(timezone=True), nullable=True)
    fecha_completada       = Column(DateTime(timezone=True), nullable=True)
    fecha_expiracion       = Column(DateTime(timezone=True), nullable=False)
    estado                 = Column(String(20), nullable=False, default="pendiente")
    intentos_envio         = Column(SmallInteger, nullable=False, default=0)
    ultimo_error_envio     = Column(Text, nullable=True)
    # estandar §10
    activo                  = Column(Boolean, nullable=False, default=True)
    id_municipio            = Column(Integer, nullable=True)
    id_subarea              = Column(Integer, nullable=True)
    fecha_alta              = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_modificacion      = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    id_usuario_alta         = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    id_usuario_modificacion = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)

    respuesta = relationship(
        "EncuestaRespuesta", back_populates="envio", uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "estado IN ('pendiente','enviada','abierta','completada','expirada','error_envio')",
            name="ck_encuesta_envio_estado",
        ),
        Index("idx_encuesta_envio_token", "token_unico", unique=True),
        Index("idx_encuesta_envio_reclamo", "id_reclamo"),
        Index("idx_encuesta_envio_estado", "estado", "fecha_expiracion"),
    )


class EncuestaRespuesta(Base):
    __tablename__ = "encuesta_respuesta"

    id_encuesta_respuesta = Column(Integer, primary_key=True, autoincrement=True)
    id_envio              = Column(Integer, ForeignKey("encuesta_envio.id_encuesta_envio", ondelete="CASCADE"), nullable=False, unique=True)
    clasificacion_inicial = Column(SmallInteger, nullable=False)
    rama_seguida          = Column(String(20), nullable=False)
    tiempo_completado_seg = Column(Integer, nullable=True)
    solicita_contacto     = Column(Boolean, nullable=False, default=False)
    ip_origen             = Column(String(45), nullable=True)
    # Tracking de atencion al vecino que solicito contacto (mig 58)
    atendida              = Column(Boolean, nullable=False, default=False)
    atendida_por          = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    fecha_atendida        = Column(DateTime(timezone=True), nullable=True)
    # estandar §10
    activo                  = Column(Boolean, nullable=False, default=True)
    id_municipio            = Column(Integer, nullable=True)
    id_subarea              = Column(Integer, nullable=True)
    fecha_alta              = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_modificacion      = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    id_usuario_alta         = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    id_usuario_modificacion = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)

    envio   = relationship("EncuestaEnvio", back_populates="respuesta")
    detalle = relationship(
        "EncuestaRespuestaDetalle", back_populates="respuesta",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "clasificacion_inicial BETWEEN 1 AND 5",
            name="ck_encuesta_respuesta_clasificacion",
        ),
        CheckConstraint(
            "rama_seguida IN ('satisfechos','neutrales','insatisfechos')",
            name="ck_encuesta_respuesta_rama",
        ),
    )


class EncuestaRespuestaDetalle(Base):
    __tablename__ = "encuesta_respuesta_detalle"

    id_encuesta_respuesta_detalle = Column(Integer, primary_key=True, autoincrement=True)
    id_respuesta           = Column(Integer, ForeignKey("encuesta_respuesta.id_encuesta_respuesta", ondelete="CASCADE"), nullable=False)
    id_pregunta            = Column(Integer, ForeignKey("encuesta_pregunta.id_encuesta_pregunta", ondelete="RESTRICT"), nullable=False)
    valor_numerico         = Column(SmallInteger, nullable=True)
    valor_texto            = Column(Text, nullable=True)
    id_opcion_seleccionada = Column(Integer, ForeignKey("encuesta_opcion.id_encuesta_opcion", ondelete="SET NULL"), nullable=True)
    # estandar §10
    activo                  = Column(Boolean, nullable=False, default=True)
    id_municipio            = Column(Integer, nullable=True)
    id_subarea              = Column(Integer, nullable=True)
    fecha_alta              = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_modificacion      = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    id_usuario_alta         = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    id_usuario_modificacion = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)

    respuesta = relationship("EncuestaRespuesta", back_populates="detalle")

    __table_args__ = (
        Index("idx_encuesta_resp_detalle_respuesta", "id_respuesta"),
        Index("idx_encuesta_resp_detalle_pregunta", "id_pregunta"),
    )
