"""
ZARIS API - Router del modulo Tramites/Expedientes (migraciones 47-50).

Fase 1: endpoints de consulta (GET).
Fase 2: creacion, transiciones, pase, toma, firma, adjuntos, comentario, relacion.

Registro en main.py: ANTES de cualquier router con {param} greedy
(admin_tablas, etc.) para evitar que /tramites/* sea capturado como {tabla}/*.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.schemas.tramites import (
    ComentarioIn,
    DocumentoConFirmasOut,
    DocumentoOut,
    DocumentosOut,
    EstadoOut,
    FirmaDetalleOut,
    FirmaOut,
    FirmarIn,
    IniciadorIn,
    MovimientoOut,
    MovimientosOut,
    PaseIn,
    RechazarFirmaIn,
    RelacionOut,
    RelacionarIn,
    TipoTramiteDetalleOut,
    TipoTramiteListItem,
    TipoTramiteListOut,
    TramiteCreateIn,
    TramiteDetalleOut,
    TramiteListItem,
    TramiteListOut,
    TransicionIn,
    TransicionOut,
    TransicionPermitidaOut,
    TransicionesPermitidasOut,
    CampoOut,
    DocumentoRequeridoOut,
    VersionOut,
)
from app.services.tramites import auth as svc_auth
from app.services.tramites import autorizacion as svc_autorizacion
from app.services.tramites import creacion as svc_creacion
from app.services.tramites import documentos as svc_docs
from app.services.tramites import firmas as svc_firmas
from app.services.tramites import movimientos as svc_mov
from app.services.tramites import numerador as svc_num

router = APIRouter(prefix="/api/v1/tramites", tags=["tramites"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dias_entre(desde: datetime, hasta: datetime | None = None) -> int:
    if hasta is None:
        hasta = datetime.now(timezone.utc)
    delta = hasta - desde.replace(tzinfo=timezone.utc) if desde.tzinfo is None else hasta - desde
    return max(0, delta.days)


# ---------------------------------------------------------------------------
# GET /api/v1/tramites/tipos
# ---------------------------------------------------------------------------

@router.get("/tipos", response_model=TipoTramiteListOut)
async def listar_tipos_tramite(
    iniciador: Optional[str] = Query(None, description="ciudadano | empresa | area_interna"),
    id_municipio: int = Query(1),
    _user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista tipos de tramite publicados para el municipio."""
    where_extra = ""
    params: dict[str, Any] = {"mun": id_municipio}

    if iniciador:
        where_extra = "AND :iniciador = ANY(tt.iniciadores_permitidos)"
        params["iniciador"] = iniciador

    sql = text(f"""
        SELECT
            tt.id_tipo_tramite,
            tt.codigo,
            tt.nombre,
            tt.descripcion,
            tt.prefijo,
            tt.iniciadores_permitidos,
            tt.permite_representante,
            tt.icono,
            tt.color,
            tt.id_version_publicada
        FROM tipo_tramite tt
        WHERE tt.id_municipio = :mun
          AND tt.activo = TRUE
          AND tt.id_version_publicada IS NOT NULL
          {where_extra}
        ORDER BY tt.nombre
    """)

    rows = (await db.execute(sql, params)).fetchall()

    items = [
        TipoTramiteListItem(
            id_tipo_tramite=r.id_tipo_tramite,
            codigo=r.codigo,
            nombre=r.nombre,
            descripcion=r.descripcion,
            prefijo=r.prefijo,
            iniciadores_permitidos=list(r.iniciadores_permitidos or []),
            permite_representante=r.permite_representante,
            icono=r.icono,
            color=r.color,
            id_version_publicada=r.id_version_publicada,
        )
        for r in rows
    ]
    return TipoTramiteListOut(items=items, total=len(items))


# ---------------------------------------------------------------------------
# GET /api/v1/tramites/tipos/{id_tipo_tramite}
# ---------------------------------------------------------------------------

@router.get("/tipos/{id_tipo_tramite}", response_model=TipoTramiteDetalleOut)
async def detalle_tipo_tramite(
    id_tipo_tramite: int,
    _user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Detalle del tipo con su version publicada, campos, estados, transiciones y docs."""
    tipo_row = (await db.execute(
        text("""
            SELECT tt.*, m.codigo_corto
            FROM tipo_tramite tt
            JOIN municipios m ON m.id_municipio = tt.id_municipio
            WHERE tt.id_tipo_tramite = :id AND tt.activo = TRUE
        """),
        {"id": id_tipo_tramite},
    )).fetchone()

    if not tipo_row:
        raise HTTPException(404, "Tipo de tramite no encontrado")

    id_ver = tipo_row.id_version_publicada
    version_out: Optional[VersionOut] = None
    campos_out: list[CampoOut] = []
    estados_out: list[EstadoOut] = []
    transiciones_out: list[TransicionOut] = []
    docs_out: list[DocumentoRequeridoOut] = []

    if id_ver:
        ver_row = (await db.execute(
            text("SELECT * FROM tipo_tramite_version WHERE id_tipo_tramite_version = :id"),
            {"id": id_ver},
        )).fetchone()
        if ver_row:
            version_out = VersionOut(
                id_tipo_tramite_version=ver_row.id_tipo_tramite_version,
                version_num=ver_row.version_num,
                estado=ver_row.estado,
                publicada_en=ver_row.publicada_en,
            )

        campos_rows = (await db.execute(
            text("SELECT * FROM tipo_tramite_campo WHERE id_tipo_tramite_version = :id AND activo = TRUE ORDER BY orden"),
            {"id": id_ver},
        )).fetchall()
        campos_out = [
            CampoOut(
                id_tipo_tramite_campo=r.id_tipo_tramite_campo,
                nombre_interno=r.nombre_interno,
                etiqueta=r.etiqueta,
                tipo_dato=r.tipo_dato,
                obligatorio=r.obligatorio,
                orden=r.orden,
                opciones_jsonb=r.opciones_jsonb,
                validacion_jsonb=r.validacion_jsonb,
                ayuda=r.ayuda,
                visible_en_listado=r.visible_en_listado,
            )
            for r in campos_rows
        ]

        estados_rows = (await db.execute(
            text("SELECT * FROM tipo_tramite_estado WHERE id_tipo_tramite_version = :id AND activo = TRUE ORDER BY orden"),
            {"id": id_ver},
        )).fetchall()
        estados_out = [
            EstadoOut(
                id_tipo_tramite_estado=r.id_tipo_tramite_estado,
                codigo=r.codigo,
                etiqueta=r.etiqueta,
                orden=r.orden,
                es_inicial=r.es_inicial,
                es_final=r.es_final,
                color=r.color,
                oculto_para_iniciador=r.oculto_para_iniciador,
            )
            for r in estados_rows
        ]

        trans_rows = (await db.execute(
            text("SELECT * FROM tipo_tramite_transicion WHERE id_tipo_tramite_version = :id AND activo = TRUE ORDER BY orden"),
            {"id": id_ver},
        )).fetchall()
        transiciones_out = [
            TransicionOut(
                id_tipo_tramite_transicion=r.id_tipo_tramite_transicion,
                id_estado_origen=r.id_estado_origen,
                id_estado_destino=r.id_estado_destino,
                etiqueta_accion=r.etiqueta_accion,
                orden=r.orden,
                requiere_comentario=r.requiere_comentario,
                requiere_adjunto=r.requiere_adjunto,
                quien_puede_jsonb=r.quien_puede_jsonb,
                notifica_iniciador=r.notifica_iniciador,
            )
            for r in trans_rows
        ]

        docs_rows = (await db.execute(
            text("SELECT * FROM tipo_tramite_documento_requerido WHERE id_tipo_tramite_version = :id AND activo = TRUE ORDER BY orden"),
            {"id": id_ver},
        )).fetchall()
        docs_out = [
            DocumentoRequeridoOut(
                id_tipo_tramite_documento_requerido=r.id_tipo_tramite_documento_requerido,
                nombre=r.nombre,
                descripcion=r.descripcion,
                obligatorio=r.obligatorio,
                id_tipo_tramite_estado=r.id_tipo_tramite_estado,
                aporta_quien=r.aporta_quien,
                formatos_permitidos=list(r.formatos_permitidos or []),
                tamano_max_mb=r.tamano_max_mb,
                requiere_firma=r.requiere_firma,
                orden=r.orden,
            )
            for r in docs_rows
        ]

    return TipoTramiteDetalleOut(
        id_tipo_tramite=tipo_row.id_tipo_tramite,
        codigo=tipo_row.codigo,
        nombre=tipo_row.nombre,
        descripcion=tipo_row.descripcion,
        prefijo=tipo_row.prefijo,
        incluye_municipio=tipo_row.incluye_municipio,
        incluye_anio=tipo_row.incluye_anio,
        largo_correlativo=tipo_row.largo_correlativo,
        separador=tipo_row.separador,
        iniciadores_permitidos=list(tipo_row.iniciadores_permitidos or []),
        permite_representante=tipo_row.permite_representante,
        icono=tipo_row.icono,
        color=tipo_row.color,
        version=version_out,
        campos=campos_out,
        estados=estados_out,
        transiciones=transiciones_out,
        documentos_requeridos=docs_out,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/tramites  (bandeja)
# ---------------------------------------------------------------------------

@router.get("", response_model=TramiteListOut)
async def listar_tramites(
    response: Response,
    id_municipio: int = Query(1),
    destinatario_tipo: Optional[str] = Query(None),
    destinatario_id: Optional[int] = Query(None),
    tomado_por: Optional[int] = Query(None),
    sin_tomar: Optional[bool] = Query(None),
    estado_codigo: Optional[str] = Query(None),
    tipo_codigo: Optional[str] = Query(None),
    iniciador_tipo: Optional[str] = Query(None),
    id_ciudadano_iniciador: Optional[int] = Query(None),
    id_empresa_iniciadora: Optional[int] = Query(None),
    numero: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    _user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Bandeja de tramites con filtros combinables."""
    conditions = ["t.id_municipio = :mun", "t.activo = TRUE"]
    params: dict[str, Any] = {"mun": id_municipio, "limit": limit, "offset": offset}

    if destinatario_tipo == "subarea" and destinatario_id:
        conditions.append("t.id_subarea_actual = :dest_id")
        params["dest_id"] = destinatario_id
    elif destinatario_tipo == "equipo" and destinatario_id:
        conditions.append("t.id_equipo_actual = :dest_id")
        params["dest_id"] = destinatario_id

    if tomado_por:
        conditions.append("t.id_agente_tomado_por = :tomado_por")
        params["tomado_por"] = tomado_por

    if sin_tomar is True:
        conditions.append("t.id_agente_tomado_por IS NULL")
    elif sin_tomar is False:
        conditions.append("t.id_agente_tomado_por IS NOT NULL")

    if estado_codigo:
        conditions.append("tte.codigo = :estado_codigo")
        params["estado_codigo"] = estado_codigo

    if tipo_codigo:
        conditions.append("tt.codigo = :tipo_codigo")
        params["tipo_codigo"] = tipo_codigo

    if iniciador_tipo:
        conditions.append("t.iniciador_tipo = :iniciador_tipo")
        params["iniciador_tipo"] = iniciador_tipo

    if id_ciudadano_iniciador:
        conditions.append("t.id_ciudadano_iniciador = :cid")
        params["cid"] = id_ciudadano_iniciador

    if id_empresa_iniciadora:
        conditions.append("t.id_empresa_iniciadora = :eid")
        params["eid"] = id_empresa_iniciadora

    if numero:
        conditions.append("t.numero_expediente = :numero")
        params["numero"] = numero

    if q:
        conditions.append("t.asunto ILIKE :q")
        params["q"] = f"%{q}%"

    if desde:
        conditions.append("t.fecha_alta >= :desde")
        params["desde"] = desde

    if hasta:
        conditions.append("t.fecha_alta < :hasta")
        params["hasta"] = hasta

    where_clause = " AND ".join(conditions)

    count_sql = text(f"""
        SELECT COUNT(*) FROM tramite t
        JOIN tipo_tramite_version ttv ON ttv.id_tipo_tramite_version = t.id_tipo_tramite_version
        JOIN tipo_tramite tt ON tt.id_tipo_tramite = ttv.id_tipo_tramite
        JOIN tipo_tramite_estado tte ON tte.id_tipo_tramite_estado = t.id_tipo_tramite_estado_actual
        WHERE {where_clause}
    """)
    total = (await db.execute(count_sql, params)).scalar() or 0

    rows_sql = text(f"""
        SELECT
            t.id_tramite,
            t.numero_expediente,
            t.asunto,
            tt.codigo AS tipo_codigo,
            tt.nombre AS tipo_nombre,
            tte.codigo AS estado_codigo,
            tte.etiqueta AS estado_etiqueta,
            tte.color AS estado_color,
            t.iniciador_tipo,
            CASE
                WHEN t.iniciador_tipo = 'ciudadano' THEN c.apellido || ', ' || c.nombre
                WHEN t.iniciador_tipo = 'empresa' THEN e.nombre
                WHEN t.iniciador_tipo = 'area_interna' THEN sa_ini.nombre
            END AS iniciador_nombre,
            t.destinatario_actual_tipo,
            CASE
                WHEN t.destinatario_actual_tipo = 'subarea' THEN sa.nombre
                WHEN t.destinatario_actual_tipo = 'equipo' THEN eq.nombre
            END AS destinatario_actual_nombre,
            ag_tom.apellido || ', ' || ag_tom.nombre AS tomado_por_nombre,
            t.tomado_en,
            t.fecha_alta,
            t.fecha_entrada_estado_actual
        FROM tramite t
        JOIN tipo_tramite_version ttv ON ttv.id_tipo_tramite_version = t.id_tipo_tramite_version
        JOIN tipo_tramite tt ON tt.id_tipo_tramite = ttv.id_tipo_tramite
        JOIN tipo_tramite_estado tte ON tte.id_tipo_tramite_estado = t.id_tipo_tramite_estado_actual
        LEFT JOIN ciudadanos c ON c.id_ciudadano = t.id_ciudadano_iniciador
        LEFT JOIN empresas e ON e.id_empresa = t.id_empresa_iniciadora
        LEFT JOIN subarea sa_ini ON sa_ini.id_subarea = t.id_subarea_iniciadora
        LEFT JOIN subarea sa ON sa.id_subarea = t.id_subarea_actual
        LEFT JOIN equipos eq ON eq.id_equipo = t.id_equipo_actual
        LEFT JOIN agentes ag_tom ON ag_tom.id_agente = t.id_agente_tomado_por
        WHERE {where_clause}
        ORDER BY t.fecha_alta DESC
        LIMIT :limit OFFSET :offset
    """)
    rows = (await db.execute(rows_sql, params)).fetchall()

    now = datetime.now(timezone.utc)
    items = [
        TramiteListItem(
            id_tramite=r.id_tramite,
            numero_expediente=r.numero_expediente,
            asunto=r.asunto,
            tipo_codigo=r.tipo_codigo,
            tipo_nombre=r.tipo_nombre,
            estado_codigo=r.estado_codigo,
            estado_etiqueta=r.estado_etiqueta,
            estado_color=r.estado_color,
            iniciador_tipo=r.iniciador_tipo,
            iniciador_nombre=r.iniciador_nombre,
            destinatario_actual_tipo=r.destinatario_actual_tipo,
            destinatario_actual_nombre=r.destinatario_actual_nombre,
            tomado_por_nombre=r.tomado_por_nombre,
            tomado_en=r.tomado_en,
            fecha_alta=r.fecha_alta,
            dias_en_estado_actual=_dias_entre(r.fecha_entrada_estado_actual, now),
        )
        for r in rows
    ]

    response.headers["X-Total-Count"] = str(total)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return TramiteListOut(items=items, total=total, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# GET /api/v1/tramites/{numero_o_id}  (detalle)
# ---------------------------------------------------------------------------

@router.get("/{numero_o_id}", response_model=TramiteDetalleOut)
async def detalle_tramite(
    numero_o_id: str,
    _user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Detalle completo de un tramite. Acepta id numerico o numero_expediente."""
    # Resolver por id o por numero
    if numero_o_id.isdigit():
        where = "t.id_tramite = :ref"
        params: dict[str, Any] = {"ref": int(numero_o_id)}
    else:
        where = "t.numero_expediente = :ref"
        params = {"ref": numero_o_id}

    row = (await db.execute(
        text(f"""
            SELECT
                t.*,
                tt.codigo AS tipo_codigo,
                tt.nombre AS tipo_nombre,
                tt.prefijo AS tipo_prefijo,
                ttv.version_num,
                tte.codigo AS estado_codigo,
                tte.etiqueta AS estado_etiqueta,
                tte.color AS estado_color,
                CASE
                    WHEN t.iniciador_tipo = 'ciudadano' THEN c.apellido || ', ' || c.nombre
                    WHEN t.iniciador_tipo = 'empresa' THEN e.nombre
                    WHEN t.iniciador_tipo = 'area_interna' THEN sa_ini.nombre
                END AS iniciador_nombre,
                CASE
                    WHEN cr.id_ciudadano IS NOT NULL THEN cr.apellido || ', ' || cr.nombre
                END AS representante_nombre,
                CASE
                    WHEN t.destinatario_actual_tipo = 'subarea' THEN sa.nombre
                    WHEN t.destinatario_actual_tipo = 'equipo' THEN eq.nombre
                END AS destinatario_actual_nombre,
                ag_tom.apellido || ', ' || ag_tom.nombre AS tomado_por_nombre
            FROM tramite t
            JOIN tipo_tramite_version ttv ON ttv.id_tipo_tramite_version = t.id_tipo_tramite_version
            JOIN tipo_tramite tt ON tt.id_tipo_tramite = ttv.id_tipo_tramite
            JOIN tipo_tramite_estado tte ON tte.id_tipo_tramite_estado = t.id_tipo_tramite_estado_actual
            LEFT JOIN ciudadanos c ON c.id_ciudadano = t.id_ciudadano_iniciador
            LEFT JOIN empresas e ON e.id_empresa = t.id_empresa_iniciadora
            LEFT JOIN subarea sa_ini ON sa_ini.id_subarea = t.id_subarea_iniciadora
            LEFT JOIN ciudadanos cr ON cr.id_ciudadano = t.id_ciudadano_representante
            LEFT JOIN subarea sa ON sa.id_subarea = t.id_subarea_actual
            LEFT JOIN equipos eq ON eq.id_equipo = t.id_equipo_actual
            LEFT JOIN agentes ag_tom ON ag_tom.id_agente = t.id_agente_tomado_por
            WHERE {where} AND t.activo = TRUE
        """),
        params,
    )).fetchone()

    if not row:
        raise HTTPException(404, "Tramite no encontrado")

    # Ultimo movimiento
    ult_mov = (await db.execute(
        text("""
            SELECT tipo, comentario, fecha_alta
            FROM tramite_movimiento
            WHERE id_tramite = :id AND activo = TRUE
            ORDER BY orden_secuencial DESC LIMIT 1
        """),
        {"id": row.id_tramite},
    )).fetchone()

    # Conteo documentos activos
    cant_docs = (await db.execute(
        text("SELECT COUNT(*) FROM tramite_documento WHERE id_tramite = :id AND activo = TRUE"),
        {"id": row.id_tramite},
    )).scalar() or 0

    # Firmas pendientes
    cant_firmas = (await db.execute(
        text("""
            SELECT COUNT(*) FROM tramite_firma tf
            JOIN tramite_documento td ON td.id_tramite_documento = tf.id_tramite_documento
            WHERE td.id_tramite = :id AND tf.estado = 'pendiente' AND tf.activo = TRUE
        """),
        {"id": row.id_tramite},
    )).scalar() or 0

    # Relaciones
    rel_rows = (await db.execute(
        text("""
            SELECT
                tr.id_tramite_relacion,
                tr.tipo_relacion,
                tr.fecha_alta,
                CASE WHEN tr.id_tramite_a = :id THEN tr.id_tramite_b ELSE tr.id_tramite_a END AS id_tramite_rel,
                t2.numero_expediente AS num_rel,
                t2.asunto AS asunto_rel
            FROM tramite_relacion tr
            JOIN tramite t2 ON t2.id_tramite = CASE WHEN tr.id_tramite_a = :id THEN tr.id_tramite_b ELSE tr.id_tramite_a END
            WHERE (tr.id_tramite_a = :id OR tr.id_tramite_b = :id) AND tr.activo = TRUE
        """),
        {"id": row.id_tramite},
    )).fetchall()

    relaciones = [
        RelacionOut(
            id_tramite_relacion=r.id_tramite_relacion,
            id_tramite_relacionado=r.id_tramite_rel,
            numero_expediente_relacionado=r.num_rel,
            asunto_relacionado=r.asunto_rel,
            tipo_relacion=r.tipo_relacion,
            fecha_alta=r.fecha_alta,
        )
        for r in rel_rows
    ]

    return TramiteDetalleOut(
        id_tramite=row.id_tramite,
        numero_expediente=row.numero_expediente,
        asunto=row.asunto,
        datos_jsonb=row.datos_jsonb,
        iniciador_tipo=row.iniciador_tipo,
        iniciador_nombre=row.iniciador_nombre,
        representante_nombre=row.representante_nombre,
        tipo_codigo=row.tipo_codigo,
        tipo_nombre=row.tipo_nombre,
        tipo_prefijo=row.tipo_prefijo,
        id_tipo_tramite_version=row.id_tipo_tramite_version,
        version_num=row.version_num,
        estado_codigo=row.estado_codigo,
        estado_etiqueta=row.estado_etiqueta,
        estado_color=row.estado_color,
        fecha_entrada_estado_actual=row.fecha_entrada_estado_actual,
        destinatario_actual_tipo=row.destinatario_actual_tipo,
        destinatario_actual_nombre=row.destinatario_actual_nombre,
        tomado_por_nombre=row.tomado_por_nombre,
        tomado_en=row.tomado_en,
        ultimo_movimiento_tipo=ult_mov.tipo if ult_mov else None,
        ultimo_movimiento_comentario=ult_mov.comentario if ult_mov else None,
        ultimo_movimiento_fecha=ult_mov.fecha_alta if ult_mov else None,
        cant_documentos=cant_docs,
        cant_firmas_pendientes=cant_firmas,
        relaciones=relaciones,
        fecha_alta=row.fecha_alta,
        id_municipio=row.id_municipio,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/tramites/{numero_o_id}/movimientos  (timeline)
# ---------------------------------------------------------------------------

@router.get("/{numero_o_id}/movimientos", response_model=MovimientosOut)
async def movimientos_tramite(
    numero_o_id: str,
    _user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Timeline completo de movimientos de un tramite."""
    id_tramite, numero = await _resolver_tramite(numero_o_id, db)

    rows = (await db.execute(
        text("""
            SELECT
                tm.id_tramite_movimiento,
                tm.orden_secuencial,
                tm.tipo,
                tm.id_tipo_tramite_transicion,
                eo.codigo AS estado_origen_codigo,
                eo.etiqueta AS estado_origen_etiqueta,
                ed.codigo AS estado_destino_codigo,
                ed.etiqueta AS estado_destino_etiqueta,
                tm.origen_jsonb,
                tm.destino_jsonb,
                tm.comentario,
                tm.metadata_jsonb,
                ag.apellido || ', ' || ag.nombre AS agente_nombre,
                tm.fecha_alta
            FROM tramite_movimiento tm
            LEFT JOIN tipo_tramite_estado eo ON eo.id_tipo_tramite_estado = tm.id_estado_origen
            LEFT JOIN tipo_tramite_estado ed ON ed.id_tipo_tramite_estado = tm.id_estado_destino
            JOIN agentes ag ON ag.id_agente = tm.id_agente
            WHERE tm.id_tramite = :id AND tm.activo = TRUE
            ORDER BY tm.orden_secuencial
        """),
        {"id": id_tramite},
    )).fetchall()

    movimientos = [
        MovimientoOut(
            id_tramite_movimiento=r.id_tramite_movimiento,
            orden_secuencial=r.orden_secuencial,
            tipo=r.tipo,
            id_tipo_tramite_transicion=r.id_tipo_tramite_transicion,
            estado_origen_codigo=r.estado_origen_codigo,
            estado_origen_etiqueta=r.estado_origen_etiqueta,
            estado_destino_codigo=r.estado_destino_codigo,
            estado_destino_etiqueta=r.estado_destino_etiqueta,
            origen_jsonb=r.origen_jsonb,
            destino_jsonb=r.destino_jsonb,
            comentario=r.comentario,
            metadata_jsonb=r.metadata_jsonb,
            agente_nombre=r.agente_nombre,
            fecha_alta=r.fecha_alta,
        )
        for r in rows
    ]

    return MovimientosOut(numero_expediente=numero, movimientos=movimientos, total=len(movimientos))


# ---------------------------------------------------------------------------
# GET /api/v1/tramites/{numero_o_id}/documentos
# ---------------------------------------------------------------------------

@router.get("/{numero_o_id}/documentos", response_model=DocumentosOut)
async def documentos_tramite(
    numero_o_id: str,
    _user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista de documentos del tramite con sus firmas."""
    id_tramite, numero = await _resolver_tramite(numero_o_id, db)

    doc_rows = (await db.execute(
        text("""
            SELECT *
            FROM tramite_documento
            WHERE id_tramite = :id AND activo = TRUE
            ORDER BY posicion_orden
        """),
        {"id": id_tramite},
    )).fetchall()

    documentos: list[DocumentoOut] = []
    for d in doc_rows:
        firma_rows = (await db.execute(
            text("""
                SELECT
                    tf.id_tramite_firma,
                    tf.rol_intervencion,
                    tf.orden,
                    tf.estado,
                    tf.firmado_en,
                    CASE
                        WHEN tf.id_agente_asignado IS NOT NULL THEN ag.apellido || ', ' || ag.nombre
                        WHEN tf.id_subarea_asignada IS NOT NULL THEN sa.nombre
                        WHEN tf.id_equipo_asignado IS NOT NULL THEN eq.nombre
                    END AS asignado_nombre
                FROM tramite_firma tf
                LEFT JOIN agentes ag ON ag.id_agente = tf.id_agente_asignado
                LEFT JOIN subarea sa ON sa.id_subarea = tf.id_subarea_asignada
                LEFT JOIN equipos eq ON eq.id_equipo = tf.id_equipo_asignado
                WHERE tf.id_tramite_documento = :did AND tf.activo = TRUE
                ORDER BY tf.orden
            """),
            {"did": d.id_tramite_documento},
        )).fetchall()

        firmas = [
            FirmaOut(
                id_tramite_firma=f.id_tramite_firma,
                rol_intervencion=f.rol_intervencion,
                orden=f.orden,
                asignado_nombre=f.asignado_nombre,
                estado=f.estado,
                firmado_en=f.firmado_en,
            )
            for f in firma_rows
        ]

        documentos.append(DocumentoOut(
            id_tramite_documento=d.id_tramite_documento,
            nombre=d.nombre,
            nombre_archivo_original=d.nombre_archivo_original,
            mime_type=d.mime_type,
            tamano_bytes=d.tamano_bytes,
            requiere_firma=d.requiere_firma,
            estado_firma=d.estado_firma,
            posicion_orden=d.posicion_orden,
            firmas=firmas,
            fecha_alta=d.fecha_alta,
        ))

    return DocumentosOut(numero_expediente=numero, documentos=documentos, total=len(documentos))


# ---------------------------------------------------------------------------
# Helper privado: resolver tramite por id o numero
# ---------------------------------------------------------------------------

async def _resolver_tramite(numero_o_id: str, db: AsyncSession) -> tuple[int, str]:
    if numero_o_id.isdigit():
        row = (await db.execute(
            text("SELECT id_tramite, numero_expediente FROM tramite WHERE id_tramite = :ref AND activo = TRUE"),
            {"ref": int(numero_o_id)},
        )).fetchone()
    else:
        row = (await db.execute(
            text("SELECT id_tramite, numero_expediente FROM tramite WHERE numero_expediente = :ref AND activo = TRUE"),
            {"ref": numero_o_id},
        )).fetchone()

    if not row:
        raise HTTPException(404, "Tramite no encontrado")
    return row.id_tramite, row.numero_expediente


async def _cargar_tramite_dict(numero_o_id: str, db: AsyncSession) -> dict:
    """Carga fila de tramite como dict para los helpers de servicios."""
    id_tramite, _ = await _resolver_tramite(numero_o_id, db)
    row = (await db.execute(
        text("SELECT * FROM tramite WHERE id_tramite = :id AND activo = TRUE"),
        {"id": id_tramite},
    )).fetchone()
    if not row:
        raise HTTPException(404, "Tramite no encontrado")
    return dict(row._mapping)


async def _tramite_detalle_out(id_tramite: int, db: AsyncSession) -> TramiteDetalleOut:
    """Reutiliza la logica de detalle para devolver el tramite completo post-mutacion."""
    row = (await db.execute(
        text("""
            SELECT
                t.*,
                tt.codigo AS tipo_codigo, tt.nombre AS tipo_nombre,
                tt.prefijo AS tipo_prefijo,
                ttv.version_num,
                tte.codigo AS estado_codigo, tte.etiqueta AS estado_etiqueta,
                tte.color AS estado_color,
                CASE
                    WHEN t.iniciador_tipo='ciudadano' THEN c.apellido||', '||c.nombre
                    WHEN t.iniciador_tipo='empresa' THEN e.nombre
                    WHEN t.iniciador_tipo='area_interna' THEN sa_ini.nombre
                END AS iniciador_nombre,
                CASE WHEN cr.id_ciudadano IS NOT NULL THEN cr.apellido||', '||cr.nombre END AS representante_nombre,
                CASE
                    WHEN t.destinatario_actual_tipo='subarea' THEN sa.nombre
                    WHEN t.destinatario_actual_tipo='equipo' THEN eq.nombre
                END AS destinatario_actual_nombre,
                ag_tom.apellido||', '||ag_tom.nombre AS tomado_por_nombre
            FROM tramite t
            JOIN tipo_tramite_version ttv ON ttv.id_tipo_tramite_version=t.id_tipo_tramite_version
            JOIN tipo_tramite tt ON tt.id_tipo_tramite=ttv.id_tipo_tramite
            JOIN tipo_tramite_estado tte ON tte.id_tipo_tramite_estado=t.id_tipo_tramite_estado_actual
            LEFT JOIN ciudadanos c ON c.id_ciudadano=t.id_ciudadano_iniciador
            LEFT JOIN empresas e ON e.id_empresa=t.id_empresa_iniciadora
            LEFT JOIN subarea sa_ini ON sa_ini.id_subarea=t.id_subarea_iniciadora
            LEFT JOIN ciudadanos cr ON cr.id_ciudadano=t.id_ciudadano_representante
            LEFT JOIN subarea sa ON sa.id_subarea=t.id_subarea_actual
            LEFT JOIN equipos eq ON eq.id_equipo=t.id_equipo_actual
            LEFT JOIN agentes ag_tom ON ag_tom.id_agente=t.id_agente_tomado_por
            WHERE t.id_tramite=:id AND t.activo=TRUE
        """),
        {"id": id_tramite},
    )).fetchone()

    if not row:
        raise HTTPException(404, "Tramite no encontrado")

    ult_mov = (await db.execute(
        text("SELECT tipo, comentario, fecha_alta FROM tramite_movimiento WHERE id_tramite=:id AND activo=TRUE ORDER BY orden_secuencial DESC LIMIT 1"),
        {"id": id_tramite},
    )).fetchone()
    cant_docs = (await db.execute(text("SELECT COUNT(*) FROM tramite_documento WHERE id_tramite=:id AND activo=TRUE"), {"id": id_tramite})).scalar() or 0
    cant_firmas = (await db.execute(text("""
        SELECT COUNT(*) FROM tramite_firma tf
        JOIN tramite_documento td ON td.id_tramite_documento=tf.id_tramite_documento
        WHERE td.id_tramite=:id AND tf.estado='pendiente' AND tf.activo=TRUE
    """), {"id": id_tramite})).scalar() or 0
    rel_rows = (await db.execute(text("""
        SELECT tr.id_tramite_relacion, tr.tipo_relacion, tr.fecha_alta,
               CASE WHEN tr.id_tramite_a=:id THEN tr.id_tramite_b ELSE tr.id_tramite_a END AS id_tramite_rel,
               t2.numero_expediente AS num_rel, t2.asunto AS asunto_rel
        FROM tramite_relacion tr
        JOIN tramite t2 ON t2.id_tramite=CASE WHEN tr.id_tramite_a=:id THEN tr.id_tramite_b ELSE tr.id_tramite_a END
        WHERE (tr.id_tramite_a=:id OR tr.id_tramite_b=:id) AND tr.activo=TRUE
    """), {"id": id_tramite})).fetchall()

    return TramiteDetalleOut(
        id_tramite=row.id_tramite, numero_expediente=row.numero_expediente,
        asunto=row.asunto, datos_jsonb=row.datos_jsonb,
        iniciador_tipo=row.iniciador_tipo, iniciador_nombre=row.iniciador_nombre,
        representante_nombre=row.representante_nombre,
        tipo_codigo=row.tipo_codigo, tipo_nombre=row.tipo_nombre, tipo_prefijo=row.tipo_prefijo,
        id_tipo_tramite_version=row.id_tipo_tramite_version, version_num=row.version_num,
        estado_codigo=row.estado_codigo, estado_etiqueta=row.estado_etiqueta,
        estado_color=row.estado_color,
        fecha_entrada_estado_actual=row.fecha_entrada_estado_actual,
        destinatario_actual_tipo=row.destinatario_actual_tipo,
        destinatario_actual_nombre=row.destinatario_actual_nombre,
        tomado_por_nombre=row.tomado_por_nombre, tomado_en=row.tomado_en,
        ultimo_movimiento_tipo=ult_mov.tipo if ult_mov else None,
        ultimo_movimiento_comentario=ult_mov.comentario if ult_mov else None,
        ultimo_movimiento_fecha=ult_mov.fecha_alta if ult_mov else None,
        cant_documentos=cant_docs, cant_firmas_pendientes=cant_firmas,
        relaciones=[
            RelacionOut(
                id_tramite_relacion=r.id_tramite_relacion,
                id_tramite_relacionado=r.id_tramite_rel,
                numero_expediente_relacionado=r.num_rel,
                asunto_relacionado=r.asunto_rel,
                tipo_relacion=r.tipo_relacion, fecha_alta=r.fecha_alta,
            ) for r in rel_rows
        ],
        fecha_alta=row.fecha_alta, id_municipio=row.id_municipio,
    )


# ===========================================================================
# FASE 2 — Endpoints de operacion
# ===========================================================================

# ---------------------------------------------------------------------------
# POST /api/v1/tramites  — Crear tramite
# Registrado ANTES de /{numero_o_id} pero el router ya lo hace por orden.
# ---------------------------------------------------------------------------

@router.post("", status_code=201, response_model=TramiteDetalleOut)
async def crear_tramite(
    body: TramiteCreateIn,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    id_usuario = current_user["id_usuario"]
    agente = await svc_auth.resolver_agente_desde_usuario(id_usuario, db)
    if not agente:
        raise HTTPException(403, "El usuario no tiene un agente asociado")

    # Cargar tipo de tramite y version publicada
    tipo_row = (await db.execute(
        text("""
            SELECT tt.*, m.codigo_corto FROM tipo_tramite tt
            JOIN municipios m ON m.id_municipio=tt.id_municipio
            WHERE tt.id_tipo_tramite=:id AND tt.activo=TRUE AND tt.id_municipio=:mun
        """),
        {"id": body.id_tipo_tramite, "mun": body.id_municipio},
    )).fetchone()
    if not tipo_row:
        raise HTTPException(404, "Tipo de tramite no encontrado")
    if not tipo_row.id_version_publicada:
        raise HTTPException(400, "El tipo de tramite no tiene version publicada")

    tipo = dict(tipo_row._mapping)

    # Resolver iniciador
    iniciador_fks = await svc_creacion.resolver_iniciador(
        body.iniciador.model_dump(exclude_none=True),
        tipo, body.id_municipio, db,
    )

    # Validar campos del formulario
    await svc_creacion.validar_campos_contra_tipo(
        body.datos, tipo_row.id_version_publicada, body.id_municipio, db,
    )

    # Estado inicial
    estado_inicial = (await db.execute(
        text("""
            SELECT id_tipo_tramite_estado FROM tipo_tramite_estado
            WHERE id_tipo_tramite_version=:ver AND es_inicial=TRUE AND activo=TRUE
        """),
        {"ver": tipo_row.id_version_publicada},
    )).fetchone()
    if not estado_inicial:
        raise HTTPException(500, "El tipo de tramite no tiene estado inicial configurado")

    # Destinatario inicial = subarea del agente creador
    dest_tipo, dest_id = svc_creacion.determinar_destinatario_inicial(agente)

    # Numero correlativo atomico
    anio = datetime.now(timezone.utc).year
    correlativo = await svc_num.proximo_numero(db, body.id_tipo_tramite, body.id_municipio, anio)
    numero_expediente = svc_num.formatear_numero(
        prefijo=tipo_row.prefijo,
        separador=tipo_row.separador,
        incluye_municipio=tipo_row.incluye_municipio,
        incluye_anio=tipo_row.incluye_anio,
        codigo_municipio=tipo_row.codigo_corto or "",
        anio=anio,
        correlativo=correlativo,
        largo_correlativo=tipo_row.largo_correlativo,
    )

    datos_str = json.dumps(body.datos)

    # INSERT tramite
    t_row = (await db.execute(
        text("""
            INSERT INTO tramite (
                numero_expediente, id_tipo_tramite_version, asunto,
                datos_jsonb, iniciador_tipo,
                id_ciudadano_iniciador, id_empresa_iniciadora,
                id_ciudadano_representante, id_subarea_iniciadora,
                id_agente_iniciador,
                id_tipo_tramite_estado_actual, fecha_entrada_estado_actual,
                destinatario_actual_tipo,
                id_subarea_actual, id_equipo_actual,
                id_municipio,
                id_usuario_alta, id_usuario_modificacion
            ) VALUES (
                :num, :ver, :asunto,
                CAST(:datos AS jsonb), :ini_tipo,
                :cid, :eid, :crep, :sub_ini,
                :ag_ini,
                :estado, NOW(),
                :dest_tipo,
                :dest_sa, :dest_eq,
                :mun,
                :uid, :uid
            )
            RETURNING id_tramite
        """),
        {
            "num": numero_expediente,
            "ver": tipo_row.id_version_publicada,
            "asunto": body.asunto,
            "datos": datos_str,
            "ini_tipo": body.iniciador.tipo,
            "cid": iniciador_fks.get("id_ciudadano_iniciador"),
            "eid": iniciador_fks.get("id_empresa_iniciadora"),
            "crep": iniciador_fks.get("id_ciudadano_representante"),
            "sub_ini": iniciador_fks.get("id_subarea_iniciadora"),
            "ag_ini": agente["id_agente"],
            "estado": estado_inicial.id_tipo_tramite_estado,
            "dest_tipo": dest_tipo,
            "dest_sa": dest_id if dest_tipo == "subarea" else None,
            "dest_eq": dest_id if dest_tipo == "equipo" else None,
            "mun": body.id_municipio,
            "uid": id_usuario,
        },
    )).fetchone()
    id_tramite = t_row.id_tramite

    # Movimiento creacion
    await svc_mov.registrar_movimiento(
        db, id_tramite, "creacion", id_usuario, agente["id_agente"],
        body.id_municipio, request,
        id_estado_destino=estado_inicial.id_tipo_tramite_estado,
        destino_jsonb={"tipo": dest_tipo, "id": dest_id},
        metadata_jsonb={"datos_iniciales": body.datos},
    )
    # Movimiento numeracion
    await svc_mov.registrar_movimiento(
        db, id_tramite, "numeracion", id_usuario, agente["id_agente"],
        body.id_municipio, request,
        metadata_jsonb={"numero_expediente": numero_expediente, "correlativo": correlativo, "anio": anio},
    )

    await db.commit()
    return await _tramite_detalle_out(id_tramite, db)


# ---------------------------------------------------------------------------
# GET /{tramite_ref}/transiciones-permitidas
# IMPORTANTE: debe quedar ANTES de /{numero_o_id} en el router,
# pero como usamos path diferente (/transiciones-permitidas vs sin sufijo)
# FastAPI los distingue correctamente por el sufijo del path.
# ---------------------------------------------------------------------------

@router.get("/{tramite_ref}/transiciones-permitidas", response_model=TransicionesPermitidasOut)
async def transiciones_permitidas(
    tramite_ref: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tramite = await _cargar_tramite_dict(tramite_ref, db)
    agente = await svc_auth.resolver_agente_desde_usuario(current_user["id_usuario"], db)

    estado_row = (await db.execute(
        text("SELECT codigo, etiqueta FROM tipo_tramite_estado WHERE id_tipo_tramite_estado=:id"),
        {"id": tramite["id_tipo_tramite_estado_actual"]},
    )).fetchone()

    transiciones = await svc_autorizacion.listar_transiciones_permitidas(tramite, agente, db)

    tomado_por_mi = (
        agente is not None
        and tramite.get("id_agente_tomado_por") == agente["id_agente"]
    )
    puedo_operar = False
    if agente:
        puede, _ = await svc_auth.agente_puede_operar(agente, tramite)
        puedo_operar = puede

    return TransicionesPermitidasOut(
        id_tramite=tramite["id_tramite"],
        estado_codigo=estado_row.codigo if estado_row else "",
        estado_etiqueta=estado_row.etiqueta if estado_row else "",
        tomado_por_mi=tomado_por_mi,
        puedo_operar=puedo_operar,
        transiciones=[
            TransicionPermitidaOut(
                id_tipo_tramite_transicion=t["id_tipo_tramite_transicion"],
                etiqueta_accion=t["etiqueta_accion"],
                id_estado_destino=t["id_estado_destino"],
                etiqueta_destino=t["etiqueta_destino"],
                requiere_comentario=t["requiere_comentario"],
                requiere_adjunto=t["requiere_adjunto"],
                disponible=t["disponible"],
                motivo_no_disponible=t["motivo_no_disponible"],
            )
            for t in transiciones
        ],
    )


# ---------------------------------------------------------------------------
# POST /{tramite_ref}/tomar
# ---------------------------------------------------------------------------

@router.post("/{tramite_ref}/tomar", response_model=TramiteDetalleOut)
async def tomar_tramite(
    tramite_ref: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agente = await svc_auth.resolver_agente_desde_usuario(current_user["id_usuario"], db)
    if not agente:
        raise HTTPException(403, "El usuario no tiene un agente asociado")

    id_tramite, _ = await _resolver_tramite(tramite_ref, db)

    # Lock pesimista
    tramite = dict((await db.execute(
        text("SELECT * FROM tramite WHERE id_tramite=:id AND activo=TRUE FOR UPDATE"),
        {"id": id_tramite},
    )).fetchone()._mapping)

    puede, motivo = await svc_auth.agente_puede_tomar(agente, tramite)
    if not puede:
        raise HTTPException(409 if tramite.get("id_agente_tomado_por") else 403, motivo)

    await db.execute(
        text("""
            UPDATE tramite SET id_agente_tomado_por=:ag, tomado_en=NOW(),
            fecha_modificacion=NOW(), id_usuario_modificacion=:uid
            WHERE id_tramite=:id
        """),
        {"ag": agente["id_agente"], "uid": current_user["id_usuario"], "id": id_tramite},
    )
    await svc_mov.registrar_movimiento(
        db, id_tramite, "toma", current_user["id_usuario"], agente["id_agente"],
        tramite["id_municipio"], request,
    )
    await db.commit()
    return await _tramite_detalle_out(id_tramite, db)


# ---------------------------------------------------------------------------
# POST /{tramite_ref}/liberar
# ---------------------------------------------------------------------------

@router.post("/{tramite_ref}/liberar", response_model=TramiteDetalleOut)
async def liberar_tramite(
    tramite_ref: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agente = await svc_auth.resolver_agente_desde_usuario(current_user["id_usuario"], db)
    if not agente:
        raise HTTPException(403, "El usuario no tiene un agente asociado")

    id_tramite, _ = await _resolver_tramite(tramite_ref, db)
    tramite = dict((await db.execute(
        text("SELECT * FROM tramite WHERE id_tramite=:id AND activo=TRUE FOR UPDATE"),
        {"id": id_tramite},
    )).fetchone()._mapping)

    tomado_por = tramite.get("id_agente_tomado_por")
    if not tomado_por:
        raise HTTPException(400, "El tramite no esta tomado")
    if tomado_por != agente["id_agente"] and not svc_auth.es_admin(agente["nivel_acceso"]):
        raise HTTPException(403, "Solo el agente que tomo el tramite o un admin puede liberarlo")

    await db.execute(
        text("""
            UPDATE tramite SET id_agente_tomado_por=NULL, tomado_en=NULL,
            fecha_modificacion=NOW(), id_usuario_modificacion=:uid
            WHERE id_tramite=:id
        """),
        {"uid": current_user["id_usuario"], "id": id_tramite},
    )
    await svc_mov.registrar_movimiento(
        db, id_tramite, "liberacion", current_user["id_usuario"], agente["id_agente"],
        tramite["id_municipio"], request,
    )
    await db.commit()
    return await _tramite_detalle_out(id_tramite, db)


# ---------------------------------------------------------------------------
# POST /{tramite_ref}/transicionar
# ---------------------------------------------------------------------------

@router.post("/{tramite_ref}/transicionar", response_model=TramiteDetalleOut)
async def transicionar_tramite(
    tramite_ref: str,
    body: TransicionIn,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agente = await svc_auth.resolver_agente_desde_usuario(current_user["id_usuario"], db)
    if not agente:
        raise HTTPException(403, "El usuario no tiene un agente asociado")

    id_tramite, _ = await _resolver_tramite(tramite_ref, db)
    tramite = dict((await db.execute(
        text("SELECT * FROM tramite WHERE id_tramite=:id AND activo=TRUE FOR UPDATE"),
        {"id": id_tramite},
    )).fetchone()._mapping)

    # Cargar transicion
    trans_row = (await db.execute(
        text("SELECT * FROM tipo_tramite_transicion WHERE id_tipo_tramite_transicion=:id AND activo=TRUE"),
        {"id": body.id_tipo_tramite_transicion},
    )).fetchone()
    if not trans_row:
        raise HTTPException(404, "Transicion no encontrada")
    trans = dict(trans_row._mapping)

    # Validar pertenencia y estado actual
    if trans["id_tipo_tramite_version"] != tramite["id_tipo_tramite_version"]:
        raise HTTPException(400, "La transicion no pertenece a la version del tramite")
    if trans["id_estado_origen"] != tramite["id_tipo_tramite_estado_actual"]:
        raise HTTPException(400, "La transicion no aplica al estado actual del tramite")

    # Permisos
    puede_op, motivo = await svc_auth.agente_puede_operar(agente, tramite)
    if not puede_op:
        raise HTTPException(403, motivo)
    puede_trans, motivo_t = await svc_autorizacion.agente_puede_ejecutar_transicion(agente, trans, tramite)
    if not puede_trans:
        raise HTTPException(403, motivo_t)

    # Comentario requerido
    if trans["requiere_comentario"] and not (body.comentario or "").strip():
        raise HTTPException(400, "Esta transicion requiere un comentario")

    # Adjunto requerido desde el ultimo cambio de estado
    if trans["requiere_adjunto"]:
        ultimo_cambio = (await db.execute(
            text("""
                SELECT fecha_alta FROM tramite_movimiento
                WHERE id_tramite=:id AND tipo IN ('creacion','transicion','cambio_estado') AND activo=TRUE
                ORDER BY orden_secuencial DESC LIMIT 1
            """),
            {"id": id_tramite},
        )).fetchone()
        desde = ultimo_cambio.fecha_alta if ultimo_cambio else datetime.min.replace(tzinfo=timezone.utc)
        tiene_doc = (await db.execute(
            text("""
                SELECT 1 FROM tramite_documento
                WHERE id_tramite=:id AND activo=TRUE AND fecha_alta >= :desde LIMIT 1
            """),
            {"id": id_tramite, "desde": desde},
        )).fetchone()
        if not tiene_doc:
            raise HTTPException(400, "Esta transicion requiere adjuntar al menos un documento en el estado actual")

    id_estado_origen = tramite["id_tipo_tramite_estado_actual"]
    id_estado_destino = trans["id_estado_destino"]

    # Verificar estado destino es_final
    estado_destino_row = (await db.execute(
        text("SELECT es_final FROM tipo_tramite_estado WHERE id_tipo_tramite_estado=:id"),
        {"id": id_estado_destino},
    )).fetchone()
    es_final = estado_destino_row.es_final if estado_destino_row else False

    # Calcular nuevo destinatario
    dest_auto = trans.get("destino_automatico_jsonb")
    nuevo_dest_tipo = tramite.get("destinatario_actual_tipo")
    nuevo_dest_sa = tramite.get("id_subarea_actual")
    nuevo_dest_eq = tramite.get("id_equipo_actual")
    liberar_toma = es_final

    if dest_auto:
        nuevo_dest_tipo = dest_auto.get("tipo", "subarea")
        dest_auto_id = dest_auto.get("id")
        nuevo_dest_sa = dest_auto_id if nuevo_dest_tipo == "subarea" else None
        nuevo_dest_eq = dest_auto_id if nuevo_dest_tipo == "equipo" else None
        liberar_toma = True

    update_params: dict[str, Any] = {
        "estado": id_estado_destino,
        "dest_tipo": nuevo_dest_tipo,
        "dest_sa": nuevo_dest_sa,
        "dest_eq": nuevo_dest_eq,
        "tomado": None if liberar_toma else tramite.get("id_agente_tomado_por"),
        "tomado_en": None if liberar_toma else tramite.get("tomado_en"),
        "uid": current_user["id_usuario"],
        "id": id_tramite,
    }
    await db.execute(
        text("""
            UPDATE tramite SET
                id_tipo_tramite_estado_actual=:estado,
                fecha_entrada_estado_actual=NOW(),
                destinatario_actual_tipo=:dest_tipo,
                id_subarea_actual=:dest_sa,
                id_equipo_actual=:dest_eq,
                id_agente_tomado_por=:tomado,
                tomado_en=:tomado_en,
                fecha_modificacion=NOW(),
                id_usuario_modificacion=:uid
            WHERE id_tramite=:id
        """),
        update_params,
    )

    orig_jsonb = {"tipo": tramite.get("destinatario_actual_tipo"), "id": tramite.get("id_subarea_actual") or tramite.get("id_equipo_actual")}
    dest_jsonb = {"tipo": nuevo_dest_tipo, "id": nuevo_dest_sa or nuevo_dest_eq}

    await svc_mov.registrar_movimiento(
        db, id_tramite, "transicion", current_user["id_usuario"], agente["id_agente"],
        tramite["id_municipio"], request,
        id_tipo_tramite_transicion=body.id_tipo_tramite_transicion,
        id_estado_origen=id_estado_origen,
        id_estado_destino=id_estado_destino,
        origen_jsonb=orig_jsonb if dest_auto else None,
        destino_jsonb=dest_jsonb if dest_auto else None,
        comentario=body.comentario,
    )
    await db.commit()
    return await _tramite_detalle_out(id_tramite, db)


# ---------------------------------------------------------------------------
# POST /{tramite_ref}/pase
# ---------------------------------------------------------------------------

@router.post("/{tramite_ref}/pase", response_model=TramiteDetalleOut)
async def pase_tramite(
    tramite_ref: str,
    body: PaseIn,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agente = await svc_auth.resolver_agente_desde_usuario(current_user["id_usuario"], db)
    if not agente:
        raise HTTPException(403, "El usuario no tiene un agente asociado")

    id_tramite, _ = await _resolver_tramite(tramite_ref, db)
    tramite = dict((await db.execute(
        text("SELECT * FROM tramite WHERE id_tramite=:id AND activo=TRUE FOR UPDATE"),
        {"id": id_tramite},
    )).fetchone()._mapping)

    puede, motivo = await svc_auth.agente_puede_operar(agente, tramite)
    if not puede:
        raise HTTPException(403, motivo)

    if body.destinatario_tipo == "subarea":
        dest_row = (await db.execute(
            text("SELECT id_subarea FROM subarea WHERE id_subarea=:id AND activo=TRUE AND id_municipio=:mun LIMIT 1"),
            {"id": body.destinatario_id, "mun": tramite["id_municipio"]},
        )).fetchone()
        if not dest_row:
            raise HTTPException(404, f"Subarea {body.destinatario_id} no encontrada")
        nuevo_sa, nuevo_eq = body.destinatario_id, None
    elif body.destinatario_tipo == "equipo":
        dest_row = (await db.execute(
            text("SELECT id_equipo FROM equipos WHERE id_equipo=:id AND activo=TRUE AND id_municipio=:mun LIMIT 1"),
            {"id": body.destinatario_id, "mun": tramite["id_municipio"]},
        )).fetchone()
        if not dest_row:
            raise HTTPException(404, f"Equipo {body.destinatario_id} no encontrado")
        nuevo_sa, nuevo_eq = None, body.destinatario_id
    else:
        raise HTTPException(400, "destinatario_tipo debe ser 'subarea' o 'equipo'")

    orig_jsonb = {"tipo": tramite.get("destinatario_actual_tipo"), "id": tramite.get("id_subarea_actual") or tramite.get("id_equipo_actual")}
    dest_jsonb = {"tipo": body.destinatario_tipo, "id": body.destinatario_id}

    await db.execute(
        text("""
            UPDATE tramite SET
                destinatario_actual_tipo=:dt, id_subarea_actual=:sa, id_equipo_actual=:eq,
                id_agente_tomado_por=NULL, tomado_en=NULL,
                fecha_modificacion=NOW(), id_usuario_modificacion=:uid
            WHERE id_tramite=:id
        """),
        {"dt": body.destinatario_tipo, "sa": nuevo_sa, "eq": nuevo_eq, "uid": current_user["id_usuario"], "id": id_tramite},
    )
    await svc_mov.registrar_movimiento(
        db, id_tramite, "pase", current_user["id_usuario"], agente["id_agente"],
        tramite["id_municipio"], request,
        origen_jsonb=orig_jsonb, destino_jsonb=dest_jsonb,
        comentario=body.comentario,
    )
    await db.commit()
    return await _tramite_detalle_out(id_tramite, db)


# ---------------------------------------------------------------------------
# POST /{tramite_ref}/comentar
# ---------------------------------------------------------------------------

@router.post("/{tramite_ref}/comentar", status_code=201)
async def comentar_tramite(
    tramite_ref: str,
    body: ComentarioIn,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agente = await svc_auth.resolver_agente_desde_usuario(current_user["id_usuario"], db)
    if not agente:
        raise HTTPException(403, "El usuario no tiene un agente asociado")

    id_tramite, _ = await _resolver_tramite(tramite_ref, db)
    tramite = dict((await db.execute(
        text("SELECT t.*, tte.permite_comentar FROM tramite t JOIN tipo_tramite_estado tte ON tte.id_tipo_tramite_estado=t.id_tipo_tramite_estado_actual WHERE t.id_tramite=:id AND t.activo=TRUE"),
        {"id": id_tramite},
    )).fetchone()._mapping)

    if not tramite.get("permite_comentar", True):
        raise HTTPException(400, "El estado actual no permite comentar")

    mov = await svc_mov.registrar_movimiento(
        db, id_tramite, "comentario", current_user["id_usuario"], agente["id_agente"],
        tramite["id_municipio"], request,
        comentario=body.comentario,
    )
    await db.commit()
    return mov


# ---------------------------------------------------------------------------
# POST /{tramite_ref}/documentos  — Adjuntar archivo (multipart)
# ---------------------------------------------------------------------------

@router.post("/{tramite_ref}/documentos", status_code=201, response_model=DocumentoConFirmasOut)
async def adjuntar_documento(
    tramite_ref: str,
    request: Request,
    file: UploadFile = File(...),
    id_tipo_tramite_documento_requerido: Optional[int] = Form(None),
    nombre: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agente = await svc_auth.resolver_agente_desde_usuario(current_user["id_usuario"], db)
    if not agente:
        raise HTTPException(403, "El usuario no tiene un agente asociado")

    id_tramite, _ = await _resolver_tramite(tramite_ref, db)
    tramite = dict((await db.execute(
        text("""
            SELECT t.*, tte.permite_adjuntar
            FROM tramite t
            JOIN tipo_tramite_estado tte ON tte.id_tipo_tramite_estado=t.id_tipo_tramite_estado_actual
            WHERE t.id_tramite=:id AND t.activo=TRUE FOR UPDATE
        """),
        {"id": id_tramite},
    )).fetchone()._mapping)

    puede, motivo = await svc_auth.agente_puede_operar(agente, tramite)
    if not puede:
        raise HTTPException(403, motivo)
    if not tramite.get("permite_adjuntar", True):
        raise HTTPException(400, "El estado actual no permite adjuntar documentos")

    # Cargar doc requerido si viene
    doc_req: dict | None = None
    if id_tipo_tramite_documento_requerido:
        dr = (await db.execute(
            text("SELECT * FROM tipo_tramite_documento_requerido WHERE id_tipo_tramite_documento_requerido=:id AND activo=TRUE"),
            {"id": id_tipo_tramite_documento_requerido},
        )).fetchone()
        if not dr:
            raise HTTPException(404, "Documento requerido no encontrado")
        if dr.id_tipo_tramite_version != tramite["id_tipo_tramite_version"]:
            raise HTTPException(400, "El documento requerido no pertenece a la version de este tramite")
        doc_req = dict(dr._mapping)

    await svc_docs.validar_archivo_mock(file, doc_req)

    anio = datetime.now(timezone.utc).year
    # Numero expediente para el path
    num_exp = (await db.execute(
        text("SELECT numero_expediente FROM tramite WHERE id_tramite=:id"),
        {"id": id_tramite},
    )).scalar()

    nombre_logico = nombre or (Path(file.filename or "archivo").stem)
    info = await svc_docs.guardar_archivo_mock(file, num_exp, anio, nombre_logico)
    posicion = await svc_docs.obtener_proxima_posicion(id_tramite, db)

    requiere_firma = bool(doc_req and doc_req.get("requiere_firma"))
    estado_firma = "pendiente" if requiere_firma else "no_requiere"

    doc_row = (await db.execute(
        text("""
            INSERT INTO tramite_documento (
                id_tramite, id_tipo_tramite_documento_requerido,
                nombre, nombre_archivo_original,
                storage_path, mime_type, tamano_bytes, hash_sha256,
                requiere_firma, estado_firma, posicion_orden,
                id_agente_subio, id_municipio,
                id_usuario_alta, id_usuario_modificacion
            ) VALUES (
                :tramite, :doc_req,
                :nombre, :nombre_orig,
                :path, :mime, :tamano, :hash,
                :req_firma, :est_firma, :pos,
                :ag, :mun,
                :uid, :uid
            )
            RETURNING id_tramite_documento, fecha_alta
        """),
        {
            "tramite": id_tramite,
            "doc_req": id_tipo_tramite_documento_requerido,
            "nombre": nombre or info["nombre_archivo_original"],
            "nombre_orig": info["nombre_archivo_original"],
            "path": info["storage_path"],
            "mime": info["mime_type"],
            "tamano": info["tamano_bytes"],
            "hash": info["hash_sha256"],
            "req_firma": requiere_firma,
            "est_firma": estado_firma,
            "pos": posicion,
            "ag": agente["id_agente"],
            "mun": tramite["id_municipio"],
            "uid": current_user["id_usuario"],
        },
    )).fetchone()

    # Crear firmas pendientes si aplica
    ids_firmas: list[int] = []
    if requiere_firma and doc_req:
        ids_firmas = await svc_docs.crear_firmas_pendientes(
            doc_row.id_tramite_documento, doc_req, db,
            current_user["id_usuario"], tramite["id_municipio"],
        )

    await svc_mov.registrar_movimiento(
        db, id_tramite, "adjunto", current_user["id_usuario"], agente["id_agente"],
        tramite["id_municipio"], request,
        metadata_jsonb={
            "id_tramite_documento": doc_row.id_tramite_documento,
            "nombre": info["nombre_archivo_original"],
            "hash_sha256": info["hash_sha256"],
            "tamano_bytes": info["tamano_bytes"],
            "requiere_firma": requiere_firma,
        },
    )
    await db.commit()

    # Cargar firmas para el response
    firma_rows = (await db.execute(
        text("""
            SELECT tf.id_tramite_firma, tf.rol_intervencion, tf.orden,
                   tf.estado, tf.firmado_en,
                   CASE
                     WHEN tf.id_agente_asignado IS NOT NULL THEN ag.apellido||', '||ag.nombre
                     WHEN tf.id_subarea_asignada IS NOT NULL THEN sa.nombre
                     WHEN tf.id_equipo_asignado IS NOT NULL THEN eq.nombre
                   END AS asignado_nombre
            FROM tramite_firma tf
            LEFT JOIN agentes ag ON ag.id_agente=tf.id_agente_asignado
            LEFT JOIN subarea sa ON sa.id_subarea=tf.id_subarea_asignada
            LEFT JOIN equipos eq ON eq.id_equipo=tf.id_equipo_asignado
            WHERE tf.id_tramite_documento=:did AND tf.activo=TRUE ORDER BY tf.orden
        """),
        {"did": doc_row.id_tramite_documento},
    )).fetchall()

    return DocumentoConFirmasOut(
        id_tramite_documento=doc_row.id_tramite_documento,
        nombre=nombre or info["nombre_archivo_original"],
        nombre_archivo_original=info["nombre_archivo_original"],
        mime_type=info["mime_type"],
        tamano_bytes=info["tamano_bytes"],
        hash_sha256=info["hash_sha256"],
        requiere_firma=requiere_firma,
        estado_firma=estado_firma,
        posicion_orden=posicion,
        firmas=[FirmaOut(id_tramite_firma=f.id_tramite_firma, rol_intervencion=f.rol_intervencion, orden=f.orden, asignado_nombre=f.asignado_nombre, estado=f.estado, firmado_en=f.firmado_en) for f in firma_rows],
        fecha_alta=doc_row.fecha_alta,
    )


# ---------------------------------------------------------------------------
# GET /{tramite_ref}/documentos/{id_doc}/contenido — Descargar archivo
# ---------------------------------------------------------------------------

@router.get("/{tramite_ref}/documentos/{id_doc}/contenido")
async def descargar_documento(
    tramite_ref: str,
    id_doc: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    id_tramite, _ = await _resolver_tramite(tramite_ref, db)
    doc = (await db.execute(
        text("SELECT * FROM tramite_documento WHERE id_tramite_documento=:id AND id_tramite=:tid AND activo=TRUE"),
        {"id": id_doc, "tid": id_tramite},
    )).fetchone()
    if not doc:
        raise HTTPException(404, "Documento no encontrado")

    ruta = svc_docs.ruta_absoluta_mock(doc.storage_path)
    if not ruta.exists():
        raise HTTPException(500, "Archivo no encontrado en disco")

    return FileResponse(
        path=str(ruta),
        media_type=doc.mime_type,
        filename=doc.nombre_archivo_original,
        content_disposition_type="inline",
    )


# ---------------------------------------------------------------------------
# POST /{tramite_ref}/documentos/{id_doc}/firmar
# ---------------------------------------------------------------------------

@router.post("/{tramite_ref}/documentos/{id_doc}/firmar", response_model=FirmaDetalleOut)
async def firmar_documento(
    tramite_ref: str,
    id_doc: int,
    body: FirmarIn,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agente = await svc_auth.resolver_agente_desde_usuario(current_user["id_usuario"], db)
    if not agente:
        raise HTTPException(403, "El usuario no tiene un agente asociado")

    id_tramite, _ = await _resolver_tramite(tramite_ref, db)
    doc = (await db.execute(
        text("SELECT * FROM tramite_documento WHERE id_tramite_documento=:id AND id_tramite=:tid AND activo=TRUE"),
        {"id": id_doc, "tid": id_tramite},
    )).fetchone()
    if not doc:
        raise HTTPException(404, "Documento no encontrado")

    firma_row = (await db.execute(
        text("SELECT * FROM tramite_firma WHERE id_tramite_firma=:id AND activo=TRUE FOR UPDATE"),
        {"id": body.id_tramite_firma},
    )).fetchone()
    if not firma_row:
        raise HTTPException(404, "Firma no encontrada")
    if firma_row.id_tramite_documento != id_doc:
        raise HTTPException(400, "La firma no corresponde a este documento")

    firma = dict(firma_row._mapping)
    puede, motivo = await svc_firmas.agente_puede_firmar(agente, firma)
    if not puede:
        raise HTTPException(403, motivo)

    hash_actual = await svc_firmas.verificar_integridad_documento(dict(doc._mapping))
    resultado = await svc_firmas.marcar_firma(
        body.id_tramite_firma, agente, request, hash_actual, db, current_user["id_usuario"],
    )
    estado_firma_doc = await svc_firmas.actualizar_estado_firma_documento(id_doc, db)

    await svc_mov.registrar_movimiento(
        db, id_tramite, "firma_realizada", current_user["id_usuario"], agente["id_agente"],
        doc.id_municipio, request,
        metadata_jsonb={
            "id_tramite_firma": body.id_tramite_firma,
            "id_tramite_documento": id_doc,
            "rol_intervencion": firma.get("rol_intervencion"),
        },
    )
    await db.commit()
    return FirmaDetalleOut(
        id_tramite_firma=resultado["id_tramite_firma"],
        estado=resultado["estado"],
        firmado_en=resultado["firmado_en"],
        hash_documento_firmado=resultado["hash_documento_firmado"],
        estado_firma_documento=estado_firma_doc,
    )


# ---------------------------------------------------------------------------
# POST /{tramite_ref}/documentos/{id_doc}/rechazar-firma
# ---------------------------------------------------------------------------

@router.post("/{tramite_ref}/documentos/{id_doc}/rechazar-firma", response_model=FirmaDetalleOut)
async def rechazar_firma_documento(
    tramite_ref: str,
    id_doc: int,
    body: RechazarFirmaIn,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agente = await svc_auth.resolver_agente_desde_usuario(current_user["id_usuario"], db)
    if not agente:
        raise HTTPException(403, "El usuario no tiene un agente asociado")

    id_tramite, _ = await _resolver_tramite(tramite_ref, db)
    doc = (await db.execute(
        text("SELECT id_municipio FROM tramite_documento WHERE id_tramite_documento=:id AND id_tramite=:tid AND activo=TRUE"),
        {"id": id_doc, "tid": id_tramite},
    )).fetchone()
    if not doc:
        raise HTTPException(404, "Documento no encontrado")

    firma_row = (await db.execute(
        text("SELECT * FROM tramite_firma WHERE id_tramite_firma=:id AND activo=TRUE FOR UPDATE"),
        {"id": body.id_tramite_firma},
    )).fetchone()
    if not firma_row:
        raise HTTPException(404, "Firma no encontrada")
    if firma_row.id_tramite_documento != id_doc:
        raise HTTPException(400, "La firma no corresponde a este documento")

    firma = dict(firma_row._mapping)
    puede, motivo = await svc_firmas.agente_puede_firmar(agente, firma)
    if not puede:
        raise HTTPException(403, motivo)

    await db.execute(
        text("""
            UPDATE tramite_firma SET
                estado='rechazado', motivo_rechazo=:motivo, rechazado_en=NOW(),
                fecha_modificacion=NOW(), id_usuario_modificacion=:uid
            WHERE id_tramite_firma=:fid
        """),
        {"motivo": body.motivo, "uid": current_user["id_usuario"], "fid": body.id_tramite_firma},
    )
    estado_firma_doc = await svc_firmas.actualizar_estado_firma_documento(id_doc, db)
    await svc_mov.registrar_movimiento(
        db, id_tramite, "firma_rechazada", current_user["id_usuario"], agente["id_agente"],
        doc.id_municipio, request,
        metadata_jsonb={"id_tramite_firma": body.id_tramite_firma, "id_tramite_documento": id_doc, "motivo": body.motivo},
    )
    await db.commit()
    return FirmaDetalleOut(
        id_tramite_firma=body.id_tramite_firma,
        estado="rechazado",
        firmado_en=None,
        hash_documento_firmado=None,
        estado_firma_documento=estado_firma_doc,
    )


# ---------------------------------------------------------------------------
# POST /{tramite_ref}/relacionar
# ---------------------------------------------------------------------------

@router.post("/{tramite_ref}/relacionar", status_code=201, response_model=RelacionOut)
async def relacionar_tramites(
    tramite_ref: str,
    body: RelacionarIn,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agente = await svc_auth.resolver_agente_desde_usuario(current_user["id_usuario"], db)
    if not agente:
        raise HTTPException(403, "El usuario no tiene un agente asociado")

    id_tramite_a, num_a = await _resolver_tramite(tramite_ref, db)
    tramite_a = dict((await db.execute(
        text("SELECT * FROM tramite WHERE id_tramite=:id AND activo=TRUE FOR UPDATE"),
        {"id": id_tramite_a},
    )).fetchone()._mapping)

    tramite_b = (await db.execute(
        text("SELECT id_tramite, numero_expediente, asunto, id_municipio FROM tramite WHERE id_tramite=:id AND activo=TRUE"),
        {"id": body.id_tramite_b},
    )).fetchone()
    if not tramite_b:
        raise HTTPException(404, "Tramite B no encontrado")
    if tramite_b.id_municipio != tramite_a["id_municipio"]:
        raise HTTPException(400, "Los tramites deben pertenecer al mismo municipio")

    puede, motivo = await svc_auth.agente_puede_operar(agente, tramite_a)
    if not puede:
        raise HTTPException(403, motivo)

    id_a, id_b = sorted([id_tramite_a, body.id_tramite_b])

    try:
        rel_row = (await db.execute(
            text("""
                INSERT INTO tramite_relacion (
                    id_tramite_a, id_tramite_b, tipo_relacion, id_agente_creador,
                    comentario, id_municipio,
                    id_usuario_alta, id_usuario_modificacion
                ) VALUES (
                    :a, :b, 'asociacion_simple', :ag,
                    :comentario, :mun,
                    :uid, :uid
                )
                RETURNING id_tramite_relacion, tipo_relacion, fecha_alta
            """),
            {
                "a": id_a, "b": id_b,
                "ag": agente["id_agente"],
                "comentario": body.comentario,
                "mun": tramite_a["id_municipio"],
                "uid": current_user["id_usuario"],
            },
        )).fetchone()
    except Exception as exc:
        if "unique" in str(exc).lower():
            raise HTTPException(409, "Los tramites ya estan relacionados")
        raise

    meta = {"id_tramite_relacionado": body.id_tramite_b, "tipo": "asociacion_simple"}
    meta_b = {"id_tramite_relacionado": id_tramite_a, "tipo": "asociacion_simple"}

    await svc_mov.registrar_movimiento(
        db, id_tramite_a, "relacion", current_user["id_usuario"], agente["id_agente"],
        tramite_a["id_municipio"], request, metadata_jsonb=meta,
    )
    await svc_mov.registrar_movimiento(
        db, body.id_tramite_b, "relacion", current_user["id_usuario"], agente["id_agente"],
        tramite_b.id_municipio, request, metadata_jsonb=meta_b,
    )

    await db.commit()
    return RelacionOut(
        id_tramite_relacion=rel_row.id_tramite_relacion,
        id_tramite_relacionado=body.id_tramite_b,
        numero_expediente_relacionado=tramite_b.numero_expediente,
        asunto_relacionado=tramite_b.asunto,
        tipo_relacion=rel_row.tipo_relacion,
        fecha_alta=rel_row.fecha_alta,
    )
