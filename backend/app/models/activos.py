"""
Modelos de activos físicos del municipio (luminarias, semáforos, espacios verdes, etc.).
"""
from sqlalchemy import Column, Integer, String, Boolean, Text, Numeric, DateTime, ForeignKey, Index, func
from app.core.database import Base


class TipoActivo(Base):
    __tablename__ = "tipos_activo"

    id_tipo_activo     = Column(Integer, primary_key=True, autoincrement=True)
    nombre             = Column(String(150), nullable=False, unique=True)
    descripcion        = Column(Text, nullable=True)
    icono              = Column(String(50), nullable=True)
    requiere_ciudadano = Column(Boolean, nullable=False, default=False)
    activo             = Column(Boolean, nullable=False, default=True)
    fecha_alta         = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_modificacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    id_usuario_alta    = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    id_usuario_modificacion = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)


class Activo(Base):
    __tablename__ = "activos"

    id_activo        = Column(Integer, primary_key=True, autoincrement=True)
    codigo_unico     = Column(String(50), unique=True, nullable=True)
    id_tipo_activo   = Column(Integer, ForeignKey("tipos_activo.id_tipo_activo", ondelete="RESTRICT"), nullable=False)
    descripcion      = Column(Text, nullable=True)
    direccion        = Column(String(300), nullable=True)
    id_localidad     = Column(Integer, ForeignKey("localidades.id_localidad", ondelete="SET NULL"), nullable=True)
    latitud          = Column(Numeric(10, 7), nullable=True)
    longitud         = Column(Numeric(10, 7), nullable=True)
    metros_cuadrados = Column(Numeric(10, 2), nullable=True)
    activo           = Column(Boolean, nullable=False, default=True)
    id_municipio     = Column(Integer, nullable=True)
    id_subarea       = Column(Integer, nullable=True)
    fecha_alta       = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_modificacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    id_usuario_alta  = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)
    id_usuario_modificacion = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("idx_activos_tipo",       "id_tipo_activo"),
        Index("idx_activos_localidad",  "id_localidad"),
        Index("idx_activos_codigo",     "codigo_unico"),
        Index("idx_activos_lat_lon",    "latitud", "longitud"),
    )
