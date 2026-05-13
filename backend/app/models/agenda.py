"""
ZARIS API - Modelos ORM del modulo Agenda.
Schema actual = migraciones 30-34 (modelo nuevo: eventos, reservas, ocupaciones,
conflictos, audit) + 39 (limpieza legacy: agenda_clase + agenda_feriado
estandarizados al estandar de campos de auditoria, ausencias_agente nueva).

Las tablas legacy (agenda_agente, agenda_servicio, agenda_lugar,
agenda_servicio_agente, agenda_lugar_servicio, agenda_ausencia, agenda_alerta,
turnos, areas) fueron dropeadas en migracion 39.
"""
from sqlalchemy import (
    Column, Integer, String, Boolean, Date, DateTime, Time,
    Text, ForeignKey, UniqueConstraint, Index, CheckConstraint, func
)
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


# ---------------------------------------------------------------------------
# Maestros simples (servicios + lugares) - sobreviven a la limpieza legacy
# pero ya NO tienen FK a areas (mig 39 limpio el id_area en NULL y dropeo el FK).
# ---------------------------------------------------------------------------
class Servicio(Base):
    __tablename__ = "servicios"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    nombre            = Column(String(120), nullable=False)
    descripcion       = Column(Text)
    id_area           = Column(Integer)  # FK a `areas` legacy dropeada en mig 39
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
    id_area             = Column(Integer)  # FK a `areas` legacy dropeada en mig 39
    activo              = Column(Boolean, default=True, nullable=False)
    fecha_baja          = Column(Date)
    creado_por          = Column(Integer, ForeignKey("usuarios.id_usuario"))
    creado_en           = Column(DateTime(timezone=True), server_default=func.now())
    modificado_en       = Column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# agenda_clase + agenda_feriado - estandarizados en mig 39
# ---------------------------------------------------------------------------
class AgendaClase(Base):
    __tablename__ = "agenda_clase"

    id_agenda_clase         = Column(Integer, primary_key=True, autoincrement=True)
    nombre                  = Column(String(80), nullable=False)
    descripcion             = Column(Text)
    visible_ciudadano       = Column(Boolean, default=False)
    requiere_rrhh           = Column(Boolean, default=True)
    requiere_servicio       = Column(Boolean, default=True)
    requiere_lugar          = Column(Boolean, default=False)
    duracion_slot_minutos   = Column(Integer, nullable=False, default=30)
    activo                  = Column(Boolean, default=True, nullable=False)
    id_municipio            = Column(Integer)
    id_subarea              = Column(Integer)
    fecha_alta              = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fecha_modificacion      = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    id_usuario_alta         = Column(Integer, ForeignKey("usuarios.id_usuario"))
    id_usuario_modificacion = Column(Integer, ForeignKey("usuarios.id_usuario"))


class AgendaFeriado(Base):
    __tablename__ = "agenda_feriado"

    id_agenda_feriado       = Column(Integer, primary_key=True, autoincrement=True)
    fecha                   = Column(Date, nullable=False, unique=True)
    descripcion             = Column(String(200), nullable=False)
    ambito                  = Column(String(20), default="NACIONAL")
    activo                  = Column(Boolean, default=True, nullable=False)
    id_municipio            = Column(Integer)
    id_subarea              = Column(Integer)
    fecha_alta              = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fecha_modificacion      = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    id_usuario_alta         = Column(Integer, ForeignKey("usuarios.id_usuario"))
    id_usuario_modificacion = Column(Integer, ForeignKey("usuarios.id_usuario"))

    __table_args__ = (
        CheckConstraint(
            "ambito IN ('NACIONAL','PROVINCIAL','MUNICIPAL')",
            name="ck_feriado_ambito",
        ),
    )


# ---------------------------------------------------------------------------
# ausencias_agente - nueva en mig 39 (reemplaza agenda_ausencia)
# ---------------------------------------------------------------------------
class AusenciaAgente(Base):
    __tablename__ = "ausencias_agente"

    id_ausencia_agente      = Column(Integer, primary_key=True, autoincrement=True)
    id_agente               = Column(Integer, ForeignKey("agentes.id_agente", ondelete="CASCADE"), nullable=False)
    fecha_desde             = Column(Date, nullable=False)
    fecha_hasta             = Column(Date, nullable=False)
    motivo                  = Column(String(200))
    activo                  = Column(Boolean, default=True, nullable=False)
    id_municipio            = Column(Integer)
    id_subarea              = Column(Integer)
    fecha_alta              = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fecha_modificacion      = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    id_usuario_alta         = Column(Integer, ForeignKey("usuarios.id_usuario"))
    id_usuario_modificacion = Column(Integer, ForeignKey("usuarios.id_usuario"))

    __table_args__ = (
        CheckConstraint("fecha_hasta >= fecha_desde", name="ck_ausencia_agente_rango"),
        Index("idx_ausencias_agente_id_agente", "id_agente"),
        Index("idx_ausencias_agente_fechas", "fecha_desde", "fecha_hasta"),
        Index("idx_ausencias_agente_activo", "activo"),
    )


# ===========================================================================
# Migraciones 30-34 (modulo Agenda nuevo)
# ===========================================================================
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
