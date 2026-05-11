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


# =============================================================================
# Migraciones 30-34 (sub-fase 1.A del modulo Agenda nuevo)
# Mapping de las tablas nuevas. Las legacy de arriba se mantienen como estaban.
# =============================================================================
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB


class Municipio(Base):
    __tablename__ = "municipios"
    __table_args__ = {"extend_existing": True}

    id_municipio             = Column(Integer, primary_key=True, autoincrement=True)
    nombre                   = Column(String(120), nullable=False)
    provincia                = Column(String(80))
    activo                   = Column(Boolean, default=True, nullable=False)
    fecha_alta               = Column(DateTime(timezone=True), server_default=func.now())
    fecha_modificacion       = Column(DateTime(timezone=True), server_default=func.now())
    id_usuario_alta          = Column(Integer, ForeignKey("usuarios.id_usuario"))
    id_usuario_modificacion  = Column(Integer, ForeignKey("usuarios.id_usuario"))


class EstadoEvento(Base):
    __tablename__ = "estado_evento"

    id_estado_evento         = Column(Integer, primary_key=True, autoincrement=True)
    codigo                   = Column(String(20), unique=True, nullable=False)
    descripcion              = Column(String(120))
    orden                    = Column(Integer)
    activo                   = Column(Boolean, default=True, nullable=False)
    id_municipio             = Column(Integer, ForeignKey("municipios.id_municipio"), nullable=False, default=1)
    fecha_alta               = Column(DateTime(timezone=True), server_default=func.now())
    fecha_modificacion       = Column(DateTime(timezone=True), server_default=func.now())
    id_usuario_alta          = Column(Integer, ForeignKey("usuarios.id_usuario"))
    id_usuario_modificacion  = Column(Integer, ForeignKey("usuarios.id_usuario"))


class EstadoReserva(Base):
    __tablename__ = "estado_reserva"

    id_estado_reserva        = Column(Integer, primary_key=True, autoincrement=True)
    codigo                   = Column(String(20), unique=True, nullable=False)
    descripcion              = Column(String(120))
    orden                    = Column(Integer)
    activo                   = Column(Boolean, default=True, nullable=False)
    id_municipio             = Column(Integer, ForeignKey("municipios.id_municipio"), nullable=False, default=1)
    fecha_alta               = Column(DateTime(timezone=True), server_default=func.now())
    fecha_modificacion       = Column(DateTime(timezone=True), server_default=func.now())
    id_usuario_alta          = Column(Integer, ForeignKey("usuarios.id_usuario"))
    id_usuario_modificacion  = Column(Integer, ForeignKey("usuarios.id_usuario"))


class Evento(Base):
    __tablename__ = "eventos"

    id_evento                = Column(Integer, primary_key=True, autoincrement=True)
    nombre                   = Column(String(200), nullable=False)
    descripcion              = Column(Text)
    id_subarea               = Column(Integer, ForeignKey("subarea.id_subarea"))
    fecha                    = Column(Date, nullable=False)
    hora_inicio              = Column(Time, nullable=False)
    hora_fin                 = Column(Time, nullable=False)
    capacidad_ciudadanos     = Column(Integer, nullable=False, default=1)
    cantidad_encargados      = Column(Integer, nullable=False, default=0)
    tipo_qr                  = Column(String(10), nullable=False, default="ninguno")
    admite_autoservicio      = Column(Boolean, nullable=False, default=False)
    id_estado_evento         = Column(Integer, ForeignKey("estado_evento.id_estado_evento"), nullable=False)
    activo                   = Column(Boolean, default=True, nullable=False)
    id_municipio             = Column(Integer, ForeignKey("municipios.id_municipio"), nullable=False, default=1)
    fecha_alta               = Column(DateTime(timezone=True), server_default=func.now())
    fecha_modificacion       = Column(DateTime(timezone=True), server_default=func.now())
    id_usuario_alta          = Column(Integer, ForeignKey("usuarios.id_usuario"))
    id_usuario_modificacion  = Column(Integer, ForeignKey("usuarios.id_usuario"))

    __table_args__ = (
        CheckConstraint("tipo_qr IN ('nominal','generico','ninguno')", name="ck_eventos_tipo_qr"),
        CheckConstraint("hora_fin > hora_inicio",                       name="ck_eventos_horario"),
        CheckConstraint("capacidad_ciudadanos >= 0",                    name="ck_eventos_capacidad"),
        CheckConstraint("cantidad_encargados  >= 0",                    name="ck_eventos_encargados"),
        Index("idx_eventos_fecha_mun", "fecha", "id_municipio"),
        Index("idx_eventos_subarea",   "id_subarea"),
        Index("idx_eventos_estado",    "id_estado_evento"),
    )


class EventoEncargado(Base):
    __tablename__ = "evento_encargados"

    id_evento_encargado      = Column(Integer, primary_key=True, autoincrement=True)
    id_evento                = Column(Integer, ForeignKey("eventos.id_evento", ondelete="CASCADE"), nullable=False)
    tipo_recurso             = Column(String(10), nullable=False)
    id_recurso               = Column(Integer, nullable=False)
    activo                   = Column(Boolean, default=True, nullable=False)
    id_municipio             = Column(Integer, ForeignKey("municipios.id_municipio"), nullable=False, default=1)
    fecha_alta               = Column(DateTime(timezone=True), server_default=func.now())
    fecha_modificacion       = Column(DateTime(timezone=True), server_default=func.now())
    id_usuario_alta          = Column(Integer, ForeignKey("usuarios.id_usuario"))
    id_usuario_modificacion  = Column(Integer, ForeignKey("usuarios.id_usuario"))

    __table_args__ = (
        CheckConstraint("tipo_recurso IN ('agente','equipo')", name="ck_evt_enc_tipo_recurso"),
        UniqueConstraint("id_evento", "tipo_recurso", "id_recurso", name="uq_evt_enc"),
        Index("idx_evt_enc_evento",  "id_evento"),
        Index("idx_evt_enc_recurso", "tipo_recurso", "id_recurso"),
    )


class EventoReserva(Base):
    __tablename__ = "evento_reservas"

    id_evento_reserva        = Column(Integer, primary_key=True, autoincrement=True)
    id_evento                = Column(Integer, ForeignKey("eventos.id_evento", ondelete="CASCADE"), nullable=False)
    id_ciudadano             = Column(Integer, ForeignKey("ciudadanos.id_ciudadano"), nullable=False)
    id_estado_reserva        = Column(Integer, ForeignKey("estado_reserva.id_estado_reserva"), nullable=False)
    origen                   = Column(String(15), nullable=False)
    qr_codigo                = Column(String(255))
    activo                   = Column(Boolean, default=True, nullable=False)
    id_municipio             = Column(Integer, ForeignKey("municipios.id_municipio"), nullable=False, default=1)
    fecha_alta               = Column(DateTime(timezone=True), server_default=func.now())
    fecha_modificacion       = Column(DateTime(timezone=True), server_default=func.now())
    id_usuario_alta          = Column(Integer, ForeignKey("usuarios.id_usuario"))
    id_usuario_modificacion  = Column(Integer, ForeignKey("usuarios.id_usuario"))

    __table_args__ = (
        CheckConstraint("origen IN ('backoffice','autoservicio')", name="ck_evt_res_origen"),
        Index("idx_evt_res_evento",    "id_evento"),
        Index("idx_evt_res_ciudadano", "id_ciudadano"),
        Index("idx_evt_res_estado",    "id_estado_reserva"),
    )


class Ocupacion(Base):
    __tablename__ = "ocupaciones"

    id_ocupacion             = Column(Integer, primary_key=True, autoincrement=True)
    tipo                     = Column(String(10), nullable=False)
    tipo_recurso             = Column(String(10), nullable=False)
    id_recurso               = Column(Integer, nullable=False)
    fecha                    = Column(Date, nullable=False)
    hora_inicio              = Column(Time, nullable=False)
    hora_fin                 = Column(Time, nullable=False)
    id_orden_trabajo         = Column(Integer, ForeignKey("ordenes_trabajo.id_ot"))
    id_evento                = Column(Integer, ForeignKey("eventos.id_evento"))
    id_ciudadano             = Column(Integer, ForeignKey("ciudadanos.id_ciudadano"))
    duracion_aplicada_min    = Column(Integer)
    rol_en_evento            = Column(String(50))
    motivo                   = Column(Text)
    activo                   = Column(Boolean, default=True, nullable=False)
    id_municipio             = Column(Integer, ForeignKey("municipios.id_municipio"), nullable=False, default=1)
    fecha_alta               = Column(DateTime(timezone=True), server_default=func.now())
    fecha_modificacion       = Column(DateTime(timezone=True), server_default=func.now())
    id_usuario_alta          = Column(Integer, ForeignKey("usuarios.id_usuario"))
    id_usuario_modificacion  = Column(Integer, ForeignKey("usuarios.id_usuario"))

    __table_args__ = (
        CheckConstraint("tipo IN ('ot','evento','turno')",            name="ck_ocup_tipo"),
        CheckConstraint("tipo_recurso IN ('agente','equipo')",        name="ck_ocup_tipo_recurso"),
        CheckConstraint("hora_fin > hora_inicio",                     name="ck_ocup_horario"),
        CheckConstraint(
            "(tipo='ot'     AND id_orden_trabajo IS NOT NULL AND id_evento IS NULL    AND id_ciudadano IS NULL) "
            "OR (tipo='evento' AND id_evento        IS NOT NULL AND id_orden_trabajo IS NULL AND id_ciudadano IS NULL) "
            "OR (tipo='turno'  AND id_ciudadano     IS NOT NULL AND id_evento IS NULL    AND id_orden_trabajo IS NULL)",
            name="ck_ocupacion_consistencia"
        ),
        Index("idx_ocup_recurso_fecha", "tipo_recurso", "id_recurso", "fecha"),
        Index("idx_ocup_mun_fecha",     "id_municipio", "fecha"),
        Index("idx_ocup_tipo",          "tipo"),
    )


class ConflictoLog(Base):
    __tablename__ = "conflictos_log"

    id_conflicto             = Column(Integer, primary_key=True, autoincrement=True)
    fecha_deteccion          = Column(DateTime(timezone=True), server_default=func.now())
    tipo_recurso             = Column(String(10), nullable=False)
    id_recurso               = Column(Integer, nullable=False)
    id_ocupacion_origen      = Column(Integer, ForeignKey("ocupaciones.id_ocupacion"))
    id_ocupacion_conflicto   = Column(Integer, ForeignKey("ocupaciones.id_ocupacion"))
    resuelto                 = Column(Boolean, default=False, nullable=False)
    observaciones            = Column(Text)
    id_municipio             = Column(Integer, ForeignKey("municipios.id_municipio"), nullable=False, default=1)
    fecha_alta               = Column(DateTime(timezone=True), server_default=func.now())
    id_usuario_alta          = Column(Integer, ForeignKey("usuarios.id_usuario"))

    __table_args__ = (
        CheckConstraint("tipo_recurso IN ('agente','equipo')", name="ck_conf_tipo_recurso"),
    )


class AgendaAuditLog(Base):
    __tablename__ = "agenda_audit_log"

    id_audit                 = Column(Integer, primary_key=True, autoincrement=True)
    fecha                    = Column(DateTime(timezone=True), server_default=func.now())
    id_usuario               = Column(Integer, ForeignKey("usuarios.id_usuario"))
    entidad                  = Column(String(20), nullable=False)
    id_entidad               = Column(Integer, nullable=False)
    accion                   = Column(String(20), nullable=False)
    datos_anteriores         = Column(JSONB)
    datos_nuevos             = Column(JSONB)
    id_municipio             = Column(Integer, ForeignKey("municipios.id_municipio"), nullable=False, default=1)
    fecha_alta               = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("entidad IN ('evento','ocupacion','reserva')",            name="ck_audit_entidad"),
        CheckConstraint("accion  IN ('crear','modificar','cancelar','asignar')",  name="ck_audit_accion"),
    )
