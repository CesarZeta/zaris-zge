"""
ZARIS API — Modelos ORM del módulo Agenda.
Mapeo de tablas creadas por 03_agenda_areas.sql y 04_agenda_schema.sql.
"""
from sqlalchemy import (
    Column, Integer, String, Boolean, Date, DateTime, Time, SmallInteger,
    Text, ForeignKey, UniqueConstraint, Index, CheckConstraint, func
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class Area(Base):
    __tablename__ = "areas"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    nombre        = Column(String(120), nullable=False)
    descripcion   = Column(Text)
    activo        = Column(Boolean, default=True, nullable=False)
    creado_en     = Column(DateTime(timezone=True), server_default=func.now())
    modificado_en = Column(DateTime(timezone=True), server_default=func.now())


class AgendaClase(Base):
    __tablename__ = "agenda_clase"

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    nombre                = Column(String(80), nullable=False)
    descripcion           = Column(Text)
    visible_ciudadano     = Column(Boolean, default=False)
    requiere_rrhh         = Column(Boolean, default=True)
    requiere_servicio     = Column(Boolean, default=True)
    requiere_lugar        = Column(Boolean, default=False)
    duracion_slot_minutos = Column(Integer, nullable=False, default=30)
    id_area               = Column(Integer, ForeignKey("areas.id"))
    activo                = Column(Boolean, default=True, nullable=False)
    fecha_baja            = Column(Date)
    creado_por            = Column(Integer, ForeignKey("usuarios.id_usuario"))
    creado_en             = Column(DateTime(timezone=True), server_default=func.now())
    modificado_en         = Column(DateTime(timezone=True), server_default=func.now())


class AgendaFeriado(Base):
    __tablename__ = "agenda_feriado"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    fecha       = Column(Date, nullable=False, unique=True)
    descripcion = Column(String(200), nullable=False)
    ambito      = Column(String(20), default="NACIONAL")
    activo      = Column(Boolean, default=True, nullable=False)
    creado_por  = Column(Integer, ForeignKey("usuarios.id_usuario"))
    creado_en   = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("ambito IN ('NACIONAL','PROVINCIAL','MUNICIPAL')", name="ck_feriado_ambito"),
    )


class Servicio(Base):
    __tablename__ = "servicios"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    nombre            = Column(String(120), nullable=False)
    descripcion       = Column(Text)
    id_area           = Column(Integer, ForeignKey("areas.id"))
    capacidad_agentes = Column(Integer, nullable=False, default=1)
    activo            = Column(Boolean, default=True, nullable=False)
    fecha_baja        = Column(Date)
    creado_por        = Column(Integer, ForeignKey("usuarios.id_usuario"))
    creado_en         = Column(DateTime(timezone=True), server_default=func.now())
    modificado_en     = Column(DateTime(timezone=True), server_default=func.now())


class LugarAtencion(Base):
    __tablename__ = "lugares_atencion"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    nombre              = Column(String(120), nullable=False)
    direccion           = Column(String(200))
    es_atencion         = Column(Boolean, default=True)
    capacidad_servicios = Column(Integer, nullable=False, default=1)
    id_area             = Column(Integer, ForeignKey("areas.id"))
    activo              = Column(Boolean, default=True, nullable=False)
    fecha_baja          = Column(Date)
    creado_por          = Column(Integer, ForeignKey("usuarios.id_usuario"))
    creado_en           = Column(DateTime(timezone=True), server_default=func.now())
    modificado_en       = Column(DateTime(timezone=True), server_default=func.now())


class AgendaAgente(Base):
    __tablename__ = "agenda_agente"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario       = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    id_area          = Column(Integer, ForeignKey("areas.id"), nullable=False)
    id_clase         = Column(Integer, ForeignKey("agenda_clase.id"), nullable=False)
    fecha_desde      = Column(Date, nullable=False)
    fecha_hasta      = Column(Date)
    hora_inicio      = Column(Time, nullable=False)
    hora_fin         = Column(Time, nullable=False)
    dias_semana      = Column(SmallInteger, nullable=False, default=31)
    nombre_parametro = Column(String(120))
    observaciones    = Column(Text)
    activo           = Column(Boolean, default=True, nullable=False)
    fecha_baja       = Column(Date)
    creado_por       = Column(Integer, ForeignKey("usuarios.id_usuario"))
    creado_en        = Column(DateTime(timezone=True), server_default=func.now())
    modificado_en    = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("hora_fin > hora_inicio", name="ck_hora_agente"),
        Index("idx_agenda_agente_usuario", "id_usuario"),
        Index("idx_agenda_agente_fechas", "fecha_desde", "fecha_hasta"),
    )

    servicios_agente = relationship("AgendaServicioAgente", back_populates="agenda_agente")


class AgendaServicio(Base):
    __tablename__ = "agenda_servicio"

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    id_servicio           = Column(Integer, ForeignKey("servicios.id"), nullable=False)
    id_area               = Column(Integer, ForeignKey("areas.id"), nullable=False)
    id_clase              = Column(Integer, ForeignKey("agenda_clase.id"), nullable=False)
    fecha_desde           = Column(Date, nullable=False)
    fecha_hasta           = Column(Date)
    hora_inicio           = Column(Time, nullable=False)
    hora_fin              = Column(Time, nullable=False)
    dias_semana           = Column(SmallInteger, nullable=False, default=31)
    duracion_slot_minutos = Column(Integer)
    nombre_parametro      = Column(String(120))
    observaciones         = Column(Text)
    activo                = Column(Boolean, default=True, nullable=False)
    fecha_baja            = Column(Date)
    creado_por            = Column(Integer, ForeignKey("usuarios.id_usuario"))
    creado_en             = Column(DateTime(timezone=True), server_default=func.now())
    modificado_en         = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("hora_fin > hora_inicio", name="ck_hora_servicio"),
        Index("idx_agenda_servicio_fechas", "fecha_desde", "fecha_hasta"),
    )

    agentes_servicio = relationship("AgendaServicioAgente", back_populates="agenda_servicio")
    lugares_servicio = relationship("AgendaLugarServicio", back_populates="agenda_servicio")


class AgendaServicioAgente(Base):
    __tablename__ = "agenda_servicio_agente"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    id_agenda_servicio = Column(Integer, ForeignKey("agenda_servicio.id"), nullable=False)
    id_agenda_agente   = Column(Integer, ForeignKey("agenda_agente.id"), nullable=False)
    activo             = Column(Boolean, default=True)
    creado_en          = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("id_agenda_servicio", "id_agenda_agente", name="uq_servicio_agente"),
    )

    agenda_servicio = relationship("AgendaServicio", back_populates="agentes_servicio")
    agenda_agente   = relationship("AgendaAgente", back_populates="servicios_agente")


class AgendaLugar(Base):
    __tablename__ = "agenda_lugar"

    id                        = Column(Integer, primary_key=True, autoincrement=True)
    id_lugar                  = Column(Integer, ForeignKey("lugares_atencion.id"), nullable=False)
    id_area                   = Column(Integer, ForeignKey("areas.id"), nullable=False)
    id_clase                  = Column(Integer, ForeignKey("agenda_clase.id"), nullable=False)
    independiente_de_servicio = Column(Boolean, default=False)
    fecha_desde               = Column(Date, nullable=False)
    fecha_hasta               = Column(Date)
    hora_inicio               = Column(Time, nullable=False)
    hora_fin                  = Column(Time, nullable=False)
    dias_semana               = Column(SmallInteger, nullable=False, default=31)
    nombre_parametro          = Column(String(120))
    observaciones             = Column(Text)
    activo                    = Column(Boolean, default=True, nullable=False)
    fecha_baja                = Column(Date)
    creado_por                = Column(Integer, ForeignKey("usuarios.id_usuario"))
    creado_en                 = Column(DateTime(timezone=True), server_default=func.now())
    modificado_en             = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("hora_fin > hora_inicio", name="ck_hora_lugar"),
        Index("idx_agenda_lugar_fechas", "fecha_desde", "fecha_hasta"),
    )

    servicios_lugar = relationship("AgendaLugarServicio", back_populates="agenda_lugar")


class AgendaLugarServicio(Base):
    __tablename__ = "agenda_lugar_servicio"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    id_agenda_lugar    = Column(Integer, ForeignKey("agenda_lugar.id"), nullable=False)
    id_agenda_servicio = Column(Integer, ForeignKey("agenda_servicio.id"), nullable=False)
    activo             = Column(Boolean, default=True)
    creado_en          = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("id_agenda_lugar", "id_agenda_servicio", name="uq_lugar_servicio"),
    )

    agenda_lugar    = relationship("AgendaLugar", back_populates="servicios_lugar")
    agenda_servicio = relationship("AgendaServicio", back_populates="lugares_servicio")


class Turno(Base):
    __tablename__ = "turnos"

    id                   = Column(Integer, primary_key=True, autoincrement=True)
    tipo_agenda          = Column(String(10), nullable=False)
    id_agenda_agente     = Column(Integer, ForeignKey("agenda_agente.id"))
    id_agenda_servicio   = Column(Integer, ForeignKey("agenda_servicio.id"))
    id_agenda_lugar      = Column(Integer, ForeignKey("agenda_lugar.id"))
    id_ciudadano         = Column(Integer, ForeignKey("ciudadanos.id_ciudadano"))
    fecha                = Column(Date, nullable=False)
    hora_inicio          = Column(Time, nullable=False)
    hora_fin             = Column(Time, nullable=False)
    estado               = Column(String(15), default="RESERVADO")
    origen_reserva       = Column(String(10), default="OPERADOR")
    reservado_por        = Column(Integer, ForeignKey("usuarios.id_usuario"))
    notificacion_enviada = Column(Boolean, default=False)
    observaciones        = Column(Text)
    activo               = Column(Boolean, default=True, nullable=False)
    fecha_baja           = Column(Date)
    creado_en            = Column(DateTime(timezone=True), server_default=func.now())
    modificado_en        = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("tipo_agenda IN ('AGENTE','SERVICIO','LUGAR')", name="ck_turno_tipo"),
        CheckConstraint("estado IN ('RESERVADO','CONFIRMADO','PRESENTE','AUSENTE','CANCELADO')", name="ck_turno_estado"),
        CheckConstraint("origen_reserva IN ('CIUDADANO','OPERADOR')", name="ck_turno_origen"),
        Index("idx_turnos_fecha", "fecha"),
        Index("idx_turnos_ciudadano", "id_ciudadano"),
    )


class AgendaAusencia(Base):
    __tablename__ = "agenda_ausencia"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario    = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    fecha_desde   = Column(Date, nullable=False)
    fecha_hasta   = Column(Date, nullable=False)
    motivo        = Column(String(200))
    genera_alerta = Column(Boolean, default=True)
    cargado_por   = Column(Integer, ForeignKey("usuarios.id_usuario"))
    activo        = Column(Boolean, default=True, nullable=False)
    creado_en     = Column(DateTime(timezone=True), server_default=func.now())
    modificado_en = Column(DateTime(timezone=True), server_default=func.now())


class AgendaAlerta(Base):
    __tablename__ = "agenda_alerta"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    tipo_alerta        = Column(String(30), nullable=False)
    id_agenda_agente   = Column(Integer, ForeignKey("agenda_agente.id"))
    id_agenda_servicio = Column(Integer, ForeignKey("agenda_servicio.id"))
    id_agenda_lugar    = Column(Integer, ForeignKey("agenda_lugar.id"))
    id_ausencia        = Column(Integer, ForeignKey("agenda_ausencia.id"))
    fecha_desde        = Column(Date)
    fecha_hasta        = Column(Date)
    descripcion        = Column(Text, nullable=False)
    resuelta           = Column(Boolean, default=False)
    resuelta_por       = Column(Integer, ForeignKey("usuarios.id_usuario"))
    resuelta_en        = Column(DateTime(timezone=True))
    creado_en          = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "tipo_alerta IN ('RRHH_AUSENTE','SERVICIO_SIN_RRHH','LUGAR_SIN_SERVICIO','CONFLICTO_DISPONIBILIDAD')",
            name="ck_alerta_tipo"
        ),
        Index("idx_agenda_alerta_resuelta", "resuelta"),
    )
