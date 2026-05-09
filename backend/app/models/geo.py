"""
Modelos de geografía: provincias → partidos → localidades.
"""
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from app.core.database import Base


class Provincia(Base):
    __tablename__ = "provincias"

    id_provincia = Column(Integer, primary_key=True, autoincrement=True)
    nombre       = Column(String(100), nullable=False, unique=True)
    iso_code     = Column(String(10), nullable=True)
    activo       = Column(Boolean, nullable=False, default=True)


class Partido(Base):
    __tablename__ = "partidos"

    id_partido   = Column(Integer, primary_key=True, autoincrement=True)
    id_provincia = Column(Integer, ForeignKey("provincias.id_provincia", ondelete="RESTRICT"), nullable=False)
    nombre       = Column(String(150), nullable=False)
    activo       = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("id_provincia", "nombre", name="uq_partido_provincia_nombre"),
        Index("idx_partidos_provincia", "id_provincia"),
    )


class Localidad(Base):
    __tablename__ = "localidades"

    id_localidad  = Column(Integer, primary_key=True, autoincrement=True)
    id_partido    = Column(Integer, ForeignKey("partidos.id_partido", ondelete="RESTRICT"), nullable=False)
    nombre        = Column(String(150), nullable=False)
    codigo_postal = Column(String(8), nullable=True)
    activo        = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("id_partido", "nombre", name="uq_localidad_partido_nombre"),
        Index("idx_localidades_partido", "id_partido"),
        Index("idx_localidades_nombre",  "nombre"),
    )
