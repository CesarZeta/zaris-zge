"""
ZARIS API - Modelos ORM del modulo Tramites/Expedientes.
Schema actual = migraciones 47 (catalogos), 48 (instancias), 49 (indices).

12 tablas:
  Catalogos: tipo_tramite, tipo_tramite_version, tipo_tramite_campo,
             tipo_tramite_estado, tipo_tramite_transicion,
             tipo_tramite_documento_requerido, tipo_tramite_numerador
  Instancias: tramite, tramite_movimiento, tramite_documento,
              tramite_firma, tramite_relacion
"""
from sqlalchemy import (
    Column, Integer, SmallInteger, BigInteger, String, Boolean,
    Text, ForeignKey, UniqueConstraint, CheckConstraint, func,
    ARRAY
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMPTZ
from sqlalchemy.types import CHAR

from app.core.database import Base


# ---------------------------------------------------------------------------
# Catalogos (versionados)
# ---------------------------------------------------------------------------

class TipoTramite(Base):
    __tablename__ = "tipo_tramite"
    __table_args__ = {"extend_existing": True}

    id_tipo_tramite           = Column(Integer, primary_key=True, autoincrement=True)
    codigo                    = Column(String(50), nullable=False)
    nombre                    = Column(String(200), nullable=False)
    descripcion               = Column(Text)
    prefijo                   = Column(String(20), nullable=False)
    incluye_municipio         = Column(Boolean, nullable=False, default=True)
    incluye_anio              = Column(Boolean, nullable=False, default=True)
    largo_correlativo         = Column(SmallInteger, nullable=False, default=4)
    separador                 = Column(CHAR(1), nullable=False, default='-')
    correlativo_reinicia_anual = Column(Boolean, nullable=False, default=True)
    iniciadores_permitidos    = Column(ARRAY(String), nullable=False)
    permite_representante     = Column(Boolean, nullable=False, default=False)
    id_version_publicada      = Column(Integer, ForeignKey("tipo_tramite_version.id_tipo_tramite_version", deferrable=True, initially="DEFERRED"))
    icono                     = Column(String(50))
    color                     = Column(String(7))
    activo                    = Column(Boolean, nullable=False, default=True)
    id_municipio              = Column(Integer, ForeignKey("municipios.id_municipio"), nullable=False)
    fecha_alta                = Column(TIMESTAMPTZ, nullable=False, server_default=func.now())
    fecha_modificacion        = Column(TIMESTAMPTZ, nullable=False, server_default=func.now())


class TipoTramiteVersion(Base):
    __tablename__ = "tipo_tramite_version"
    __table_args__ = {"extend_existing": True}

    id_tipo_tramite_version   = Column(Integer, primary_key=True, autoincrement=True)
    id_tipo_tramite           = Column(Integer, ForeignKey("tipo_tramite.id_tipo_tramite"), nullable=False)
    version_num               = Column(SmallInteger, nullable=False)
    estado                    = Column(String(20), nullable=False)
    publicada_en              = Column(TIMESTAMPTZ)
    id_agente_publicador      = Column(Integer, ForeignKey("agentes.id_agente"))
    activo                    = Column(Boolean, nullable=False, default=True)
    id_municipio              = Column(Integer, ForeignKey("municipios.id_municipio"), nullable=False)
    fecha_alta                = Column(TIMESTAMPTZ, nullable=False, server_default=func.now())
    fecha_modificacion        = Column(TIMESTAMPTZ, nullable=False, server_default=func.now())


class TipoTramiteCampo(Base):
    __tablename__ = "tipo_tramite_campo"
    __table_args__ = {"extend_existing": True}

    id_tipo_tramite_campo     = Column(Integer, primary_key=True, autoincrement=True)
    id_tipo_tramite_version   = Column(Integer, ForeignKey("tipo_tramite_version.id_tipo_tramite_version"), nullable=False)
    nombre_interno            = Column(String(50), nullable=False)
    etiqueta                  = Column(String(200), nullable=False)
    tipo_dato                 = Column(String(30), nullable=False)
    obligatorio               = Column(Boolean, nullable=False, default=False)
    orden                     = Column(SmallInteger, nullable=False)
    opciones_jsonb            = Column(JSONB)
    validacion_jsonb          = Column(JSONB)
    ayuda                     = Column(Text)
    visible_en_listado        = Column(Boolean, nullable=False, default=False)
    activo                    = Column(Boolean, nullable=False, default=True)
    id_municipio              = Column(Integer, ForeignKey("municipios.id_municipio"), nullable=False)
    fecha_alta                = Column(TIMESTAMPTZ, nullable=False, server_default=func.now())
    fecha_modificacion        = Column(TIMESTAMPTZ, nullable=False, server_default=func.now())


class TipoTramiteEstado(Base):
    __tablename__ = "tipo_tramite_estado"
    __table_args__ = {"extend_existing": True}

    id_tipo_tramite_estado    = Column(Integer, primary_key=True, autoincrement=True)
    id_tipo_tramite_version   = Column(Integer, ForeignKey("tipo_tramite_version.id_tipo_tramite_version"), nullable=False)
    codigo                    = Column(String(50), nullable=False)
    etiqueta                  = Column(String(200), nullable=False)
    descripcion               = Column(Text)
    color                     = Column(String(7), default='#6b7280')
    orden                     = Column(SmallInteger, nullable=False)
    es_inicial                = Column(Boolean, nullable=False, default=False)
    es_final                  = Column(Boolean, nullable=False, default=False)
    permite_adjuntar          = Column(Boolean, nullable=False, default=True)
    permite_comentar          = Column(Boolean, nullable=False, default=True)
    oculto_para_iniciador     = Column(Boolean, nullable=False, default=False)
    activo                    = Column(Boolean, nullable=False, default=True)
    id_municipio              = Column(Integer, ForeignKey("municipios.id_municipio"), nullable=False)
    fecha_alta                = Column(TIMESTAMPTZ, nullable=False, server_default=func.now())
    fecha_modificacion        = Column(TIMESTAMPTZ, nullable=False, server_default=func.now())


class TipoTramiteTransicion(Base):
    __tablename__ = "tipo_tramite_transicion"
    __table_args__ = {"extend_existing": True}

    id_tipo_tramite_transicion = Column(Integer, primary_key=True, autoincrement=True)
    id_tipo_tramite_version   = Column(Integer, ForeignKey("tipo_tramite_version.id_tipo_tramite_version"), nullable=False)
    id_estado_origen          = Column(Integer, ForeignKey("tipo_tramite_estado.id_tipo_tramite_estado"), nullable=False)
    id_estado_destino         = Column(Integer, ForeignKey("tipo_tramite_estado.id_tipo_tramite_estado"), nullable=False)
    etiqueta_accion           = Column(String(200), nullable=False)
    orden                     = Column(SmallInteger, nullable=False, default=0)
    quien_puede_jsonb         = Column(JSONB, nullable=False, default={})
    requiere_comentario       = Column(Boolean, nullable=False, default=False)
    requiere_adjunto          = Column(Boolean, nullable=False, default=False)
    destino_automatico_jsonb  = Column(JSONB)
    notifica_iniciador        = Column(Boolean, nullable=False, default=True)
    activo                    = Column(Boolean, nullable=False, default=True)
    id_municipio              = Column(Integer, ForeignKey("municipios.id_municipio"), nullable=False)
    fecha_alta                = Column(TIMESTAMPTZ, nullable=False, server_default=func.now())
    fecha_modificacion        = Column(TIMESTAMPTZ, nullable=False, server_default=func.now())


class TipoTramiteDocumentoRequerido(Base):
    __tablename__ = "tipo_tramite_documento_requerido"
    __table_args__ = {"extend_existing": True}

    id_tipo_tramite_documento_requerido = Column(Integer, primary_key=True, autoincrement=True)
    id_tipo_tramite_version   = Column(Integer, ForeignKey("tipo_tramite_version.id_tipo_tramite_version"), nullable=False)
    id_tipo_tramite_estado    = Column(Integer, ForeignKey("tipo_tramite_estado.id_tipo_tramite_estado"))
    nombre                    = Column(String(200), nullable=False)
    descripcion               = Column(Text)
    obligatorio               = Column(Boolean, nullable=False, default=True)
    formatos_permitidos       = Column(ARRAY(String), nullable=False)
    tamano_max_mb             = Column(SmallInteger, nullable=False, default=10)
    requiere_firma            = Column(Boolean, nullable=False, default=False)
    firmantes_jsonb           = Column(JSONB)
    aporta_quien              = Column(String(20), nullable=False, default='iniciador')
    orden                     = Column(SmallInteger, nullable=False, default=0)
    activo                    = Column(Boolean, nullable=False, default=True)
    id_municipio              = Column(Integer, ForeignKey("municipios.id_municipio"), nullable=False)
    fecha_alta                = Column(TIMESTAMPTZ, nullable=False, server_default=func.now())
    fecha_modificacion        = Column(TIMESTAMPTZ, nullable=False, server_default=func.now())


class TipoTramiteNumerador(Base):
    __tablename__ = "tipo_tramite_numerador"
    __table_args__ = (
        UniqueConstraint("id_tipo_tramite", "anio", "id_municipio"),
        {"extend_existing": True},
    )

    id_tipo_tramite           = Column(Integer, ForeignKey("tipo_tramite.id_tipo_tramite"), primary_key=True)
    anio                      = Column(SmallInteger, primary_key=True)
    id_municipio              = Column(Integer, ForeignKey("municipios.id_municipio"), primary_key=True)
    ultimo_numero             = Column(Integer, nullable=False, default=0)
    activo                    = Column(Boolean, nullable=False, default=True)
    fecha_alta                = Column(TIMESTAMPTZ, nullable=False, server_default=func.now())
    fecha_modificacion        = Column(TIMESTAMPTZ, nullable=False, server_default=func.now())


# ---------------------------------------------------------------------------
# Instancias
# ---------------------------------------------------------------------------

class Tramite(Base):
    __tablename__ = "tramite"
    __table_args__ = {"extend_existing": True}

    id_tramite                       = Column(Integer, primary_key=True, autoincrement=True)
    numero_expediente                = Column(String(60), nullable=False)
    id_tipo_tramite_version          = Column(Integer, ForeignKey("tipo_tramite_version.id_tipo_tramite_version"), nullable=False)
    asunto                           = Column(String(500), nullable=False)
    datos_jsonb                      = Column(JSONB, nullable=False, default={})

    iniciador_tipo                   = Column(String(20), nullable=False)
    id_ciudadano_iniciador           = Column(Integer, ForeignKey("ciudadanos.id_ciudadano"))
    id_empresa_iniciadora            = Column(Integer, ForeignKey("empresas.id_empresa"))
    id_ciudadano_representante       = Column(Integer, ForeignKey("ciudadanos.id_ciudadano"))
    id_subarea_iniciadora            = Column(Integer, ForeignKey("subarea.id_subarea"))
    id_agente_iniciador              = Column(Integer, ForeignKey("agentes.id_agente"), nullable=False)

    id_tipo_tramite_estado_actual    = Column(Integer, ForeignKey("tipo_tramite_estado.id_tipo_tramite_estado"), nullable=False)
    fecha_entrada_estado_actual      = Column(TIMESTAMPTZ, nullable=False, server_default=func.now())

    destinatario_actual_tipo         = Column(String(20))
    id_subarea_actual                = Column(Integer, ForeignKey("subarea.id_subarea"))
    id_equipo_actual                 = Column(Integer, ForeignKey("equipos.id_equipo"))
    id_agente_tomado_por             = Column(Integer, ForeignKey("agentes.id_agente"))
    tomado_en                        = Column(TIMESTAMPTZ)

    activo                           = Column(Boolean, nullable=False, default=True)
    id_municipio                     = Column(Integer, ForeignKey("municipios.id_municipio"), nullable=False)
    fecha_alta                       = Column(TIMESTAMPTZ, nullable=False, server_default=func.now())
    fecha_modificacion               = Column(TIMESTAMPTZ, nullable=False, server_default=func.now())


class TramiteMovimiento(Base):
    __tablename__ = "tramite_movimiento"
    __table_args__ = {"extend_existing": True}

    id_tramite_movimiento        = Column(BigInteger, primary_key=True, autoincrement=True)
    id_tramite                   = Column(Integer, ForeignKey("tramite.id_tramite"), nullable=False)
    orden_secuencial             = Column(Integer, nullable=False)
    tipo                         = Column(String(30), nullable=False)
    id_tipo_tramite_transicion   = Column(Integer, ForeignKey("tipo_tramite_transicion.id_tipo_tramite_transicion"))
    id_estado_origen             = Column(Integer, ForeignKey("tipo_tramite_estado.id_tipo_tramite_estado"))
    id_estado_destino            = Column(Integer, ForeignKey("tipo_tramite_estado.id_tipo_tramite_estado"))
    origen_jsonb                 = Column(JSONB)
    destino_jsonb                = Column(JSONB)
    comentario                   = Column(Text)
    metadata_jsonb               = Column(JSONB)
    id_agente                    = Column(Integer, ForeignKey("agentes.id_agente"), nullable=False)
    ip                           = Column(String(45))
    user_agent                   = Column(Text)
    activo                       = Column(Boolean, nullable=False, default=True)
    id_municipio                 = Column(Integer, ForeignKey("municipios.id_municipio"), nullable=False)
    fecha_alta                   = Column(TIMESTAMPTZ, nullable=False, server_default=func.now())
    fecha_modificacion           = Column(TIMESTAMPTZ, nullable=False, server_default=func.now())


class TramiteDocumento(Base):
    __tablename__ = "tramite_documento"
    __table_args__ = {"extend_existing": True}

    id_tramite_documento         = Column(Integer, primary_key=True, autoincrement=True)
    id_tramite                   = Column(Integer, ForeignKey("tramite.id_tramite"), nullable=False)
    id_tipo_tramite_documento_requerido = Column(Integer, ForeignKey("tipo_tramite_documento_requerido.id_tipo_tramite_documento_requerido"))
    nombre                       = Column(String(300), nullable=False)
    nombre_archivo_original      = Column(String(300), nullable=False)
    storage_path                 = Column(String(500), nullable=False)
    mime_type                    = Column(String(100), nullable=False)
    tamano_bytes                 = Column(BigInteger, nullable=False)
    hash_sha256                  = Column(String(64), nullable=False)
    requiere_firma               = Column(Boolean, nullable=False, default=False)
    estado_firma                 = Column(String(20), nullable=False, default='no_requiere')
    posicion_orden               = Column(Integer, nullable=False)
    id_agente_subio              = Column(Integer, ForeignKey("agentes.id_agente"), nullable=False)
    activo                       = Column(Boolean, nullable=False, default=True)
    id_municipio                 = Column(Integer, ForeignKey("municipios.id_municipio"), nullable=False)
    fecha_alta                   = Column(TIMESTAMPTZ, nullable=False, server_default=func.now())
    fecha_modificacion           = Column(TIMESTAMPTZ, nullable=False, server_default=func.now())


class TramiteFirma(Base):
    __tablename__ = "tramite_firma"
    __table_args__ = {"extend_existing": True}

    id_tramite_firma             = Column(Integer, primary_key=True, autoincrement=True)
    id_tramite_documento         = Column(Integer, ForeignKey("tramite_documento.id_tramite_documento"), nullable=False)
    rol_intervencion             = Column(String(20), nullable=False)
    orden                        = Column(SmallInteger, nullable=False)
    id_agente_asignado           = Column(Integer, ForeignKey("agentes.id_agente"))
    id_subarea_asignada          = Column(Integer, ForeignKey("subarea.id_subarea"))
    id_equipo_asignado           = Column(Integer, ForeignKey("equipos.id_equipo"))
    estado                       = Column(String(20), nullable=False, default='pendiente')
    id_agente_firmante           = Column(Integer, ForeignKey("agentes.id_agente"))
    firmado_en                   = Column(TIMESTAMPTZ)
    ip_firma                     = Column(String(45))
    user_agent_firma             = Column(Text)
    hash_documento_firmado       = Column(String(64))
    motivo_rechazo               = Column(Text)
    rechazado_en                 = Column(TIMESTAMPTZ)
    proveedor_externo            = Column(String(50))
    evidencia_externa_jsonb      = Column(JSONB)
    activo                       = Column(Boolean, nullable=False, default=True)
    id_municipio                 = Column(Integer, ForeignKey("municipios.id_municipio"), nullable=False)
    fecha_alta                   = Column(TIMESTAMPTZ, nullable=False, server_default=func.now())
    fecha_modificacion           = Column(TIMESTAMPTZ, nullable=False, server_default=func.now())


class TramiteRelacion(Base):
    __tablename__ = "tramite_relacion"
    __table_args__ = {"extend_existing": True}

    id_tramite_relacion          = Column(Integer, primary_key=True, autoincrement=True)
    id_tramite_a                 = Column(Integer, ForeignKey("tramite.id_tramite"), nullable=False)
    id_tramite_b                 = Column(Integer, ForeignKey("tramite.id_tramite"), nullable=False)
    tipo_relacion                = Column(String(20), nullable=False)
    id_agente_creador            = Column(Integer, ForeignKey("agentes.id_agente"), nullable=False)
    comentario                   = Column(Text)
    activo                       = Column(Boolean, nullable=False, default=True)
    id_municipio                 = Column(Integer, ForeignKey("municipios.id_municipio"), nullable=False)
    fecha_alta                   = Column(TIMESTAMPTZ, nullable=False, server_default=func.now())
    fecha_modificacion           = Column(TIMESTAMPTZ, nullable=False, server_default=func.now())
