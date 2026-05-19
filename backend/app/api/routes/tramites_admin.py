"""
ZARIS API - Router admin del catalogo de Tramites.

CRUD de:
- tipo_tramite (POST/PUT/DELETE)
- tipo_tramite_version (crear borrador, publicar, archivar)
- tipo_tramite_campo
- tipo_tramite_estado
- tipo_tramite_transicion
- tipo_tramite_documento_requerido

Permisos: nivel_acceso <= 2 (Admin + Supervisor) para todas las mutaciones.
Borrado: soft-delete (activo=FALSE) siempre. Coherente con regla §5.

IMPORTANTE: registrar en main.py BAJO /api/v1/admin/tramites para que NO
choque con /api/v1/tramites (router de instancias) ni con admin_tablas
({tabla} greedy).
"""
from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.schemas.tramites import (
    CampoIn,
    CampoOut,
    CampoUpdateIn,
    DocumentoRequeridoIn,
    DocumentoRequeridoOut,
    DocumentoRequeridoUpdateIn,
    EstadoIn,
    EstadoOut,
    EstadoUpdateIn,
    TipoTramiteAdminOut,
    TipoTramiteCreateIn,
    TipoTramiteUpdateIn,
    TransicionIn2,
    TransicionOut,
    TransicionUpdateIn,
    VersionAdminOut,
    VersionOut,
)
from app.services.tramites import auth as svc_auth
from app.services.tramites import versionado as svc_ver

router = APIRouter(prefix="/api/v1/admin/tramites", tags=["tramites-admin"])


# ---------------------------------------------------------------------------
# Helpers de permiso
# ---------------------------------------------------------------------------

async def _require_admin_supervisor(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Solo Admin (1) o Supervisor (2) pueden tocar el catalogo."""
    nivel = user.get("nivel_acceso", 99)
    if nivel > 2:
        raise HTTPException(403, "Solo Admin o Supervisor pueden modificar el catalogo de tramites")
    return user


async def _resolver_agente_publicador(user: dict, db: AsyncSession) -> Optional[int]:
    """Devuelve id_agente del usuario, o None si no tiene agente asociado."""
    info = await svc_auth.resolver_agente_desde_usuario(user["id_usuario"], db)
    return info["id_agente"] if info else None


# ---------------------------------------------------------------------------
# tipo_tramite CRUD
# ---------------------------------------------------------------------------

@router.post("/tipos", status_code=201, response_model=TipoTramiteAdminOut)
async def crear_tipo_tramite(
    body: TipoTramiteCreateIn,
    user: dict = Depends(_require_admin_supervisor),
    db: AsyncSession = Depends(get_db),
):
    """Crea tipo + v1 en borrador (sin estructura, hay que agregar estados/campos despues)."""
    # 1. Validar codigo unico para el municipio
    existe = (await db.execute(
        text("SELECT 1 FROM tipo_tramite WHERE codigo = :c AND id_municipio = :m"),
        {"c": body.codigo, "m": body.id_municipio},
    )).fetchone()
    if existe:
        raise HTTPException(409, f"Ya existe un tipo con codigo '{body.codigo}' en este municipio")

    # 2. Insertar tipo
    nuevo_tipo_id = (await db.execute(
        text("""
            INSERT INTO tipo_tramite
                (codigo, nombre, descripcion, prefijo, incluye_municipio, incluye_anio,
                 largo_correlativo, separador, correlativo_reinicia_anual,
                 iniciadores_permitidos, permite_representante, icono, color,
                 activo, id_municipio)
            VALUES (:cod, :nom, :desc, :pre, :imun, :ian, :lc, :sep, :cra,
                    :ini, :pr, :ico, :col, TRUE, :mun)
            RETURNING id_tipo_tramite
        """),
        {
            "cod": body.codigo, "nom": body.nombre, "desc": body.descripcion,
            "pre": body.prefijo, "imun": body.incluye_municipio,
            "ian": body.incluye_anio, "lc": body.largo_correlativo,
            "sep": body.separador, "cra": body.correlativo_reinicia_anual,
            "ini": body.iniciadores_permitidos, "pr": body.permite_representante,
            "ico": body.icono, "col": body.color, "mun": body.id_municipio,
        },
    )).scalar_one()

    # 3. Crear v1 borrador
    await db.execute(
        text("""
            INSERT INTO tipo_tramite_version
                (id_tipo_tramite, version_num, estado, activo, id_municipio)
            VALUES (:tt, 1, 'borrador', TRUE, :mun)
        """),
        {"tt": nuevo_tipo_id, "mun": body.id_municipio},
    )

    await db.commit()
    return await _detalle_tipo_admin(db, int(nuevo_tipo_id))


@router.put("/tipos/{id_tipo_tramite}", response_model=TipoTramiteAdminOut)
async def actualizar_tipo_tramite(
    id_tipo_tramite: int,
    body: TipoTramiteUpdateIn,
    user: dict = Depends(_require_admin_supervisor),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza datos identitarios del tipo (NO toca circuito)."""
    fila = (await db.execute(
        text("SELECT 1 FROM tipo_tramite WHERE id_tipo_tramite = :id"),
        {"id": id_tipo_tramite},
    )).fetchone()
    if not fila:
        raise HTTPException(404, "Tipo de tramite no encontrado")

    sets: list[str] = []
    params: dict[str, Any] = {"id": id_tipo_tramite}
    for field in ("nombre", "descripcion", "prefijo", "permite_representante",
                  "incluye_municipio", "incluye_anio", "largo_correlativo",
                  "separador", "correlativo_reinicia_anual", "icono", "color"):
        val = getattr(body, field)
        if val is not None:
            sets.append(f"{field} = :{field}")
            params[field] = val

    if body.iniciadores_permitidos is not None:
        sets.append("iniciadores_permitidos = :iniciadores_permitidos")
        params["iniciadores_permitidos"] = body.iniciadores_permitidos

    if not sets:
        raise HTTPException(422, "No hay campos para actualizar")

    sets.append("fecha_modificacion = NOW()")
    await db.execute(
        text(f"UPDATE tipo_tramite SET {', '.join(sets)} WHERE id_tipo_tramite = :id"),
        params,
    )
    await db.commit()
    return await _detalle_tipo_admin(db, id_tipo_tramite)


@router.delete("/tipos/{id_tipo_tramite}", status_code=204)
async def eliminar_tipo_tramite(
    id_tipo_tramite: int,
    user: dict = Depends(_require_admin_supervisor),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete: activo=FALSE. Si tiene tramites activos asociados, rechaza."""
    fila = (await db.execute(
        text("SELECT 1 FROM tipo_tramite WHERE id_tipo_tramite = :id AND activo = TRUE"),
        {"id": id_tipo_tramite},
    )).fetchone()
    if not fila:
        raise HTTPException(404, "Tipo no encontrado o ya inactivo")

    # Verificar instancias activas
    n = (await db.execute(
        text("""
            SELECT COUNT(*) AS n FROM tramite t
            JOIN tipo_tramite_version ttv ON ttv.id_tipo_tramite_version = t.id_tipo_tramite_version
            WHERE ttv.id_tipo_tramite = :id AND t.activo = TRUE
        """),
        {"id": id_tipo_tramite},
    )).scalar_one()
    if int(n) > 0:
        raise HTTPException(409, f"No se puede desactivar: hay {n} tramite(s) activo(s) de este tipo")

    await db.execute(
        text("UPDATE tipo_tramite SET activo = FALSE, fecha_modificacion = NOW() WHERE id_tipo_tramite = :id"),
        {"id": id_tipo_tramite},
    )
    await db.commit()


@router.get("/tipos/{id_tipo_tramite}/admin", response_model=TipoTramiteAdminOut)
async def detalle_tipo_admin(
    id_tipo_tramite: int,
    user: dict = Depends(_require_admin_supervisor),
    db: AsyncSession = Depends(get_db),
):
    """Detalle admin: incluye TODAS las versiones (borradores, archivadas, publicada)."""
    return await _detalle_tipo_admin(db, id_tipo_tramite)


async def _detalle_tipo_admin(db: AsyncSession, id_tipo_tramite: int) -> TipoTramiteAdminOut:
    tipo = (await db.execute(
        text("""
            SELECT id_tipo_tramite, codigo, nombre, descripcion, prefijo,
                   iniciadores_permitidos, permite_representante,
                   incluye_municipio, incluye_anio, largo_correlativo, separador,
                   correlativo_reinicia_anual, icono, color, activo,
                   id_version_publicada
            FROM tipo_tramite WHERE id_tipo_tramite = :id
        """),
        {"id": id_tipo_tramite},
    )).fetchone()
    if not tipo:
        raise HTTPException(404, "Tipo no encontrado")

    versiones = (await db.execute(
        text("""
            SELECT id_tipo_tramite_version, version_num, estado, publicada_en
            FROM tipo_tramite_version
            WHERE id_tipo_tramite = :id AND activo = TRUE
            ORDER BY version_num
        """),
        {"id": id_tipo_tramite},
    )).fetchall()

    return TipoTramiteAdminOut(
        id_tipo_tramite=tipo.id_tipo_tramite,
        codigo=tipo.codigo, nombre=tipo.nombre, descripcion=tipo.descripcion,
        prefijo=tipo.prefijo,
        iniciadores_permitidos=list(tipo.iniciadores_permitidos or []),
        permite_representante=tipo.permite_representante,
        incluye_municipio=tipo.incluye_municipio,
        incluye_anio=tipo.incluye_anio,
        largo_correlativo=tipo.largo_correlativo,
        separador=tipo.separador,
        correlativo_reinicia_anual=tipo.correlativo_reinicia_anual,
        icono=tipo.icono, color=tipo.color, activo=tipo.activo,
        id_version_publicada=tipo.id_version_publicada,
        versiones=[
            VersionOut(
                id_tipo_tramite_version=v.id_tipo_tramite_version,
                version_num=v.version_num,
                estado=v.estado,
                publicada_en=v.publicada_en,
            )
            for v in versiones
        ],
    )


# ---------------------------------------------------------------------------
# Detalle de version (cualquier estado, no solo publicada)
# ---------------------------------------------------------------------------

@router.get("/versiones/{id_version}")
async def detalle_version(
    id_version: int,
    user: dict = Depends(_require_admin_supervisor),
    db: AsyncSession = Depends(get_db),
):
    """
    Devuelve el contenido completo de una version (campos, estados, transiciones,
    documentos requeridos). Funciona para borrador / publicada / archivada — a
    diferencia de GET /api/v1/tramites/tipos/{id} (Fase 1) que solo trae la
    publicada.
    """
    ver = await svc_ver.cargar_version(db, id_version)
    cant_tramites = await svc_ver.version_tiene_tramites(db, id_version)

    campos = (await db.execute(
        text("""
            SELECT id_tipo_tramite_campo, nombre_interno, etiqueta, tipo_dato,
                   obligatorio, orden, opciones_jsonb, validacion_jsonb,
                   ayuda, visible_en_listado
            FROM tipo_tramite_campo
            WHERE id_tipo_tramite_version = :v AND activo = TRUE
            ORDER BY orden, id_tipo_tramite_campo
        """),
        {"v": id_version},
    )).fetchall()
    estados = (await db.execute(
        text("""
            SELECT id_tipo_tramite_estado, codigo, etiqueta, descripcion, color,
                   orden, es_inicial, es_final, permite_adjuntar, permite_comentar,
                   oculto_para_iniciador
            FROM tipo_tramite_estado
            WHERE id_tipo_tramite_version = :v AND activo = TRUE
            ORDER BY orden, id_tipo_tramite_estado
        """),
        {"v": id_version},
    )).fetchall()
    transiciones = (await db.execute(
        text("""
            SELECT id_tipo_tramite_transicion, id_estado_origen, id_estado_destino,
                   etiqueta_accion, orden, quien_puede_jsonb,
                   requiere_comentario, requiere_adjunto,
                   destino_automatico_jsonb, notifica_iniciador
            FROM tipo_tramite_transicion
            WHERE id_tipo_tramite_version = :v AND activo = TRUE
            ORDER BY orden, id_tipo_tramite_transicion
        """),
        {"v": id_version},
    )).fetchall()
    docs = (await db.execute(
        text("""
            SELECT id_tipo_tramite_documento_requerido, nombre, descripcion,
                   id_tipo_tramite_estado, obligatorio, formatos_permitidos,
                   tamano_max_mb, requiere_firma, firmantes_jsonb,
                   aporta_quien, orden
            FROM tipo_tramite_documento_requerido
            WHERE id_tipo_tramite_version = :v AND activo = TRUE
            ORDER BY orden, id_tipo_tramite_documento_requerido
        """),
        {"v": id_version},
    )).fetchall()

    return {
        "id_tipo_tramite_version": ver["id_tipo_tramite_version"],
        "id_tipo_tramite": ver["id_tipo_tramite"],
        "version_num": ver["version_num"],
        "estado": ver["estado"],
        "publicada_en": ver["publicada_en"],
        "cant_tramites": cant_tramites,
        "campos": [dict(r._mapping) for r in campos],
        "estados": [dict(r._mapping) for r in estados],
        "transiciones": [dict(r._mapping) for r in transiciones],
        "documentos_requeridos": [dict(r._mapping) for r in docs],
    }


# ---------------------------------------------------------------------------
# Versiones (crear borrador, publicar, archivar)
# ---------------------------------------------------------------------------

@router.post("/tipos/{id_tipo_tramite}/versiones", status_code=201, response_model=VersionAdminOut)
async def crear_borrador(
    id_tipo_tramite: int,
    user: dict = Depends(_require_admin_supervisor),
    db: AsyncSession = Depends(get_db),
):
    """
    Crea una nueva version en borrador.
    - Si hay version publicada anterior, copia su estructura.
    - Falla si ya existe un borrador abierto.
    """
    tipo = (await db.execute(
        text("SELECT id_municipio FROM tipo_tramite WHERE id_tipo_tramite = :id AND activo = TRUE"),
        {"id": id_tipo_tramite},
    )).fetchone()
    if not tipo:
        raise HTTPException(404, "Tipo no encontrado o inactivo")

    id_ag = await _resolver_agente_publicador(user, db)
    nuevo_id = await svc_ver.crear_borrador_desde_publicada(
        db, id_tipo_tramite, tipo.id_municipio, id_ag
    )
    await db.commit()

    ver = await svc_ver.cargar_version(db, nuevo_id)
    return VersionAdminOut(**ver, cant_tramites=0)


@router.post("/versiones/{id_version}/publicar", response_model=VersionAdminOut)
async def publicar(
    id_version: int,
    user: dict = Depends(_require_admin_supervisor),
    db: AsyncSession = Depends(get_db),
):
    """Publica una version (debe estar en borrador y tener >= 1 estado inicial + >= 1 final)."""
    id_ag = await _resolver_agente_publicador(user, db)
    ver = await svc_ver.publicar_version(db, id_version, id_ag)
    await db.commit()
    n = await svc_ver.version_tiene_tramites(db, id_version)
    return VersionAdminOut(**ver, cant_tramites=n)


@router.post("/versiones/{id_version}/archivar", response_model=VersionAdminOut)
async def archivar(
    id_version: int,
    user: dict = Depends(_require_admin_supervisor),
    db: AsyncSession = Depends(get_db),
):
    """Archiva una version publicada (deja al tipo sin version publicada hasta que se publique otra)."""
    ver = await svc_ver.cargar_version(db, id_version)
    if ver["estado"] == "archivado":
        raise HTTPException(409, "La version ya esta archivada")

    if ver["estado"] == "borrador":
        # Si es borrador, simplemente desactivar (soft-delete)
        await db.execute(
            text("UPDATE tipo_tramite_version SET activo = FALSE, fecha_modificacion = NOW() WHERE id_tipo_tramite_version = :v"),
            {"v": id_version},
        )
    else:
        await db.execute(
            text("UPDATE tipo_tramite_version SET estado = 'archivado', fecha_modificacion = NOW() WHERE id_tipo_tramite_version = :v"),
            {"v": id_version},
        )
        # Si era la publicada, limpiar el puntero del tipo
        await db.execute(
            text("""
                UPDATE tipo_tramite SET id_version_publicada = NULL, fecha_modificacion = NOW()
                WHERE id_tipo_tramite = :tt AND id_version_publicada = :v
            """),
            {"tt": ver["id_tipo_tramite"], "v": id_version},
        )

    await db.commit()
    ver2 = await svc_ver.cargar_version(db, id_version)
    n = await svc_ver.version_tiene_tramites(db, id_version)
    return VersionAdminOut(**ver2, cant_tramites=n)


# ---------------------------------------------------------------------------
# tipo_tramite_campo CRUD
# ---------------------------------------------------------------------------

@router.post("/versiones/{id_version}/campos", status_code=201, response_model=CampoOut)
async def crear_campo(
    id_version: int,
    body: CampoIn,
    user: dict = Depends(_require_admin_supervisor),
    db: AsyncSession = Depends(get_db),
):
    ver = await svc_ver.asegurar_editable(db, id_version)
    # Validar nombre_interno unico
    existe = (await db.execute(
        text("SELECT 1 FROM tipo_tramite_campo WHERE id_tipo_tramite_version = :v AND nombre_interno = :n AND activo = TRUE"),
        {"v": id_version, "n": body.nombre_interno},
    )).fetchone()
    if existe:
        raise HTTPException(409, f"Ya existe un campo activo con nombre_interno '{body.nombre_interno}' en esta version")

    new_id = (await db.execute(
        text("""
            INSERT INTO tipo_tramite_campo
                (id_tipo_tramite_version, nombre_interno, etiqueta, tipo_dato,
                 obligatorio, orden, opciones_jsonb, validacion_jsonb, ayuda,
                 visible_en_listado, activo, id_municipio)
            VALUES (:v, :ni, :et, :td, :ob, :or, CAST(:op AS jsonb), CAST(:va AS jsonb),
                    :ay, :vl, TRUE, :mun)
            RETURNING id_tipo_tramite_campo
        """),
        {
            "v": id_version, "ni": body.nombre_interno, "et": body.etiqueta,
            "td": body.tipo_dato, "ob": body.obligatorio, "or": body.orden,
            "op": json.dumps(body.opciones_jsonb) if body.opciones_jsonb is not None else None,
            "va": json.dumps(body.validacion_jsonb) if body.validacion_jsonb is not None else None,
            "ay": body.ayuda, "vl": body.visible_en_listado, "mun": ver["id_municipio"],
        },
    )).scalar_one()
    await db.commit()
    return await _campo_out(db, int(new_id))


@router.put("/campos/{id_campo}", response_model=CampoOut)
async def actualizar_campo(
    id_campo: int,
    body: CampoUpdateIn,
    user: dict = Depends(_require_admin_supervisor),
    db: AsyncSession = Depends(get_db),
):
    fila = (await db.execute(
        text("SELECT id_tipo_tramite_version FROM tipo_tramite_campo WHERE id_tipo_tramite_campo = :id"),
        {"id": id_campo},
    )).fetchone()
    if not fila:
        raise HTTPException(404, "Campo no encontrado")
    await svc_ver.asegurar_editable(db, fila.id_tipo_tramite_version)

    sets: list[str] = []
    params: dict[str, Any] = {"id": id_campo}
    for field in ("etiqueta", "tipo_dato", "obligatorio", "orden", "ayuda", "visible_en_listado"):
        val = getattr(body, field)
        if val is not None:
            sets.append(f"{field} = :{field}")
            params[field] = val

    if body.opciones_jsonb is not None:
        sets.append("opciones_jsonb = CAST(:opciones_jsonb AS jsonb)")
        params["opciones_jsonb"] = json.dumps(body.opciones_jsonb)
    if body.validacion_jsonb is not None:
        sets.append("validacion_jsonb = CAST(:validacion_jsonb AS jsonb)")
        params["validacion_jsonb"] = json.dumps(body.validacion_jsonb)

    if not sets:
        raise HTTPException(422, "No hay campos para actualizar")

    sets.append("fecha_modificacion = NOW()")
    await db.execute(text(f"UPDATE tipo_tramite_campo SET {', '.join(sets)} WHERE id_tipo_tramite_campo = :id"), params)
    await db.commit()
    return await _campo_out(db, id_campo)


@router.delete("/campos/{id_campo}", status_code=204)
async def eliminar_campo(
    id_campo: int,
    user: dict = Depends(_require_admin_supervisor),
    db: AsyncSession = Depends(get_db),
):
    fila = (await db.execute(
        text("SELECT id_tipo_tramite_version FROM tipo_tramite_campo WHERE id_tipo_tramite_campo = :id AND activo = TRUE"),
        {"id": id_campo},
    )).fetchone()
    if not fila:
        raise HTTPException(404, "Campo no encontrado o ya inactivo")
    await svc_ver.asegurar_editable(db, fila.id_tipo_tramite_version)
    await db.execute(
        text("UPDATE tipo_tramite_campo SET activo = FALSE, fecha_modificacion = NOW() WHERE id_tipo_tramite_campo = :id"),
        {"id": id_campo},
    )
    await db.commit()


async def _campo_out(db: AsyncSession, id_campo: int) -> CampoOut:
    r = (await db.execute(
        text("SELECT * FROM tipo_tramite_campo WHERE id_tipo_tramite_campo = :id"),
        {"id": id_campo},
    )).fetchone()
    return CampoOut(
        id_tipo_tramite_campo=r.id_tipo_tramite_campo,
        nombre_interno=r.nombre_interno, etiqueta=r.etiqueta, tipo_dato=r.tipo_dato,
        obligatorio=r.obligatorio, orden=r.orden,
        opciones_jsonb=r.opciones_jsonb, validacion_jsonb=r.validacion_jsonb,
        ayuda=r.ayuda, visible_en_listado=r.visible_en_listado,
    )


# ---------------------------------------------------------------------------
# tipo_tramite_estado CRUD
# ---------------------------------------------------------------------------

@router.post("/versiones/{id_version}/estados", status_code=201, response_model=EstadoOut)
async def crear_estado(
    id_version: int,
    body: EstadoIn,
    user: dict = Depends(_require_admin_supervisor),
    db: AsyncSession = Depends(get_db),
):
    ver = await svc_ver.asegurar_editable(db, id_version)
    # codigo unico
    existe = (await db.execute(
        text("SELECT 1 FROM tipo_tramite_estado WHERE id_tipo_tramite_version = :v AND codigo = :c AND activo = TRUE"),
        {"v": id_version, "c": body.codigo},
    )).fetchone()
    if existe:
        raise HTTPException(409, f"Ya existe un estado con codigo '{body.codigo}' en esta version")

    # si es_inicial=TRUE, no debe haber otro inicial activo
    if body.es_inicial:
        otro = (await db.execute(
            text("SELECT 1 FROM tipo_tramite_estado WHERE id_tipo_tramite_version = :v AND es_inicial = TRUE AND activo = TRUE"),
            {"v": id_version},
        )).fetchone()
        if otro:
            raise HTTPException(409, "Ya existe un estado inicial en esta version. Desmarcalo primero.")

    new_id = (await db.execute(
        text("""
            INSERT INTO tipo_tramite_estado
                (id_tipo_tramite_version, codigo, etiqueta, descripcion, color,
                 orden, es_inicial, es_final, permite_adjuntar, permite_comentar,
                 oculto_para_iniciador, activo, id_municipio)
            VALUES (:v, :c, :e, :d, :col, :o, :ei, :ef, :pa, :pc, :opi, TRUE, :mun)
            RETURNING id_tipo_tramite_estado
        """),
        {
            "v": id_version, "c": body.codigo, "e": body.etiqueta,
            "d": body.descripcion, "col": body.color, "o": body.orden,
            "ei": body.es_inicial, "ef": body.es_final,
            "pa": body.permite_adjuntar, "pc": body.permite_comentar,
            "opi": body.oculto_para_iniciador, "mun": ver["id_municipio"],
        },
    )).scalar_one()
    await db.commit()
    return await _estado_out(db, int(new_id))


@router.put("/estados/{id_estado}", response_model=EstadoOut)
async def actualizar_estado(
    id_estado: int,
    body: EstadoUpdateIn,
    user: dict = Depends(_require_admin_supervisor),
    db: AsyncSession = Depends(get_db),
):
    fila = (await db.execute(
        text("SELECT id_tipo_tramite_version, es_inicial FROM tipo_tramite_estado WHERE id_tipo_tramite_estado = :id"),
        {"id": id_estado},
    )).fetchone()
    if not fila:
        raise HTTPException(404, "Estado no encontrado")
    await svc_ver.asegurar_editable(db, fila.id_tipo_tramite_version)

    # Si va a marcar es_inicial=TRUE y no es ya el inicial, validar unicidad
    if body.es_inicial and not fila.es_inicial:
        otro = (await db.execute(
            text("""
                SELECT 1 FROM tipo_tramite_estado
                WHERE id_tipo_tramite_version = :v AND es_inicial = TRUE
                  AND activo = TRUE AND id_tipo_tramite_estado != :id
            """),
            {"v": fila.id_tipo_tramite_version, "id": id_estado},
        )).fetchone()
        if otro:
            raise HTTPException(409, "Ya existe otro estado inicial en esta version")

    sets: list[str] = []
    params: dict[str, Any] = {"id": id_estado}
    for field in ("etiqueta", "descripcion", "color", "orden", "es_inicial",
                  "es_final", "permite_adjuntar", "permite_comentar",
                  "oculto_para_iniciador"):
        val = getattr(body, field)
        if val is not None:
            sets.append(f"{field} = :{field}")
            params[field] = val

    if not sets:
        raise HTTPException(422, "No hay campos para actualizar")
    sets.append("fecha_modificacion = NOW()")
    await db.execute(text(f"UPDATE tipo_tramite_estado SET {', '.join(sets)} WHERE id_tipo_tramite_estado = :id"), params)
    await db.commit()
    return await _estado_out(db, id_estado)


@router.delete("/estados/{id_estado}", status_code=204)
async def eliminar_estado(
    id_estado: int,
    user: dict = Depends(_require_admin_supervisor),
    db: AsyncSession = Depends(get_db),
):
    fila = (await db.execute(
        text("SELECT id_tipo_tramite_version FROM tipo_tramite_estado WHERE id_tipo_tramite_estado = :id AND activo = TRUE"),
        {"id": id_estado},
    )).fetchone()
    if not fila:
        raise HTTPException(404, "Estado no encontrado o ya inactivo")
    await svc_ver.asegurar_editable(db, fila.id_tipo_tramite_version)

    # Si tiene transiciones activas, rechazar
    n = (await db.execute(
        text("""
            SELECT COUNT(*) AS n FROM tipo_tramite_transicion
            WHERE (id_estado_origen = :id OR id_estado_destino = :id) AND activo = TRUE
        """),
        {"id": id_estado},
    )).scalar_one()
    if int(n) > 0:
        raise HTTPException(409, f"No se puede desactivar: hay {n} transicion(es) activa(s) que lo referencian")

    await db.execute(
        text("UPDATE tipo_tramite_estado SET activo = FALSE, fecha_modificacion = NOW() WHERE id_tipo_tramite_estado = :id"),
        {"id": id_estado},
    )
    await db.commit()


async def _estado_out(db: AsyncSession, id_estado: int) -> EstadoOut:
    r = (await db.execute(
        text("SELECT * FROM tipo_tramite_estado WHERE id_tipo_tramite_estado = :id"),
        {"id": id_estado},
    )).fetchone()
    return EstadoOut(
        id_tipo_tramite_estado=r.id_tipo_tramite_estado,
        codigo=r.codigo, etiqueta=r.etiqueta, orden=r.orden,
        es_inicial=r.es_inicial, es_final=r.es_final, color=r.color,
        oculto_para_iniciador=r.oculto_para_iniciador,
    )


# ---------------------------------------------------------------------------
# tipo_tramite_transicion CRUD
# ---------------------------------------------------------------------------

@router.post("/versiones/{id_version}/transiciones", status_code=201, response_model=TransicionOut)
async def crear_transicion(
    id_version: int,
    body: TransicionIn2,
    user: dict = Depends(_require_admin_supervisor),
    db: AsyncSession = Depends(get_db),
):
    ver = await svc_ver.asegurar_editable(db, id_version)

    # Validar que ambos estados pertenezcan a esta version
    estados = (await db.execute(
        text("""
            SELECT id_tipo_tramite_estado FROM tipo_tramite_estado
            WHERE id_tipo_tramite_estado IN (:o, :d)
              AND id_tipo_tramite_version = :v AND activo = TRUE
        """),
        {"o": body.id_estado_origen, "d": body.id_estado_destino, "v": id_version},
    )).fetchall()
    ids_validos = {e.id_tipo_tramite_estado for e in estados}
    if body.id_estado_origen not in ids_validos or body.id_estado_destino not in ids_validos:
        raise HTTPException(422, "Origen y destino deben ser estados activos de esta version")

    new_id = (await db.execute(
        text("""
            INSERT INTO tipo_tramite_transicion
                (id_tipo_tramite_version, id_estado_origen, id_estado_destino,
                 etiqueta_accion, orden, quien_puede_jsonb,
                 requiere_comentario, requiere_adjunto,
                 destino_automatico_jsonb, notifica_iniciador,
                 activo, id_municipio)
            VALUES (:v, :ori, :dst, :eti, :ord, CAST(:qp AS jsonb), :rc, :ra,
                    CAST(:da AS jsonb), :ni, TRUE, :mun)
            RETURNING id_tipo_tramite_transicion
        """),
        {
            "v": id_version, "ori": body.id_estado_origen, "dst": body.id_estado_destino,
            "eti": body.etiqueta_accion, "ord": body.orden,
            "qp": json.dumps(body.quien_puede_jsonb) if body.quien_puede_jsonb is not None else "{}",
            "rc": body.requiere_comentario, "ra": body.requiere_adjunto,
            "da": json.dumps(body.destino_automatico_jsonb) if body.destino_automatico_jsonb is not None else None,
            "ni": body.notifica_iniciador, "mun": ver["id_municipio"],
        },
    )).scalar_one()
    await db.commit()
    return await _transicion_out(db, int(new_id))


@router.put("/transiciones/{id_trans}", response_model=TransicionOut)
async def actualizar_transicion(
    id_trans: int,
    body: TransicionUpdateIn,
    user: dict = Depends(_require_admin_supervisor),
    db: AsyncSession = Depends(get_db),
):
    fila = (await db.execute(
        text("SELECT id_tipo_tramite_version FROM tipo_tramite_transicion WHERE id_tipo_tramite_transicion = :id"),
        {"id": id_trans},
    )).fetchone()
    if not fila:
        raise HTTPException(404, "Transicion no encontrada")
    await svc_ver.asegurar_editable(db, fila.id_tipo_tramite_version)

    # Si se cambia origen/destino, validar que pertenezcan a la version
    if body.id_estado_origen is not None or body.id_estado_destino is not None:
        ids_a_validar = []
        if body.id_estado_origen is not None:
            ids_a_validar.append(body.id_estado_origen)
        if body.id_estado_destino is not None:
            ids_a_validar.append(body.id_estado_destino)
        validos = (await db.execute(
            text("""
                SELECT id_tipo_tramite_estado FROM tipo_tramite_estado
                WHERE id_tipo_tramite_estado = ANY(:ids)
                  AND id_tipo_tramite_version = :v AND activo = TRUE
            """),
            {"ids": ids_a_validar, "v": fila.id_tipo_tramite_version},
        )).fetchall()
        if len(validos) != len(set(ids_a_validar)):
            raise HTTPException(422, "Algun estado origen/destino no pertenece a la version o esta inactivo")

    sets: list[str] = []
    params: dict[str, Any] = {"id": id_trans}
    for field in ("id_estado_origen", "id_estado_destino", "etiqueta_accion",
                  "orden", "requiere_comentario", "requiere_adjunto",
                  "notifica_iniciador"):
        val = getattr(body, field)
        if val is not None:
            sets.append(f"{field} = :{field}")
            params[field] = val

    if body.quien_puede_jsonb is not None:
        sets.append("quien_puede_jsonb = CAST(:quien_puede_jsonb AS jsonb)")
        params["quien_puede_jsonb"] = json.dumps(body.quien_puede_jsonb)
    if body.destino_automatico_jsonb is not None:
        sets.append("destino_automatico_jsonb = CAST(:destino_automatico_jsonb AS jsonb)")
        params["destino_automatico_jsonb"] = json.dumps(body.destino_automatico_jsonb)

    if not sets:
        raise HTTPException(422, "No hay campos para actualizar")
    sets.append("fecha_modificacion = NOW()")
    await db.execute(text(f"UPDATE tipo_tramite_transicion SET {', '.join(sets)} WHERE id_tipo_tramite_transicion = :id"), params)
    await db.commit()
    return await _transicion_out(db, id_trans)


@router.delete("/transiciones/{id_trans}", status_code=204)
async def eliminar_transicion(
    id_trans: int,
    user: dict = Depends(_require_admin_supervisor),
    db: AsyncSession = Depends(get_db),
):
    fila = (await db.execute(
        text("SELECT id_tipo_tramite_version FROM tipo_tramite_transicion WHERE id_tipo_tramite_transicion = :id AND activo = TRUE"),
        {"id": id_trans},
    )).fetchone()
    if not fila:
        raise HTTPException(404, "Transicion no encontrada o ya inactiva")
    await svc_ver.asegurar_editable(db, fila.id_tipo_tramite_version)
    await db.execute(
        text("UPDATE tipo_tramite_transicion SET activo = FALSE, fecha_modificacion = NOW() WHERE id_tipo_tramite_transicion = :id"),
        {"id": id_trans},
    )
    await db.commit()


async def _transicion_out(db: AsyncSession, id_trans: int) -> TransicionOut:
    r = (await db.execute(
        text("SELECT * FROM tipo_tramite_transicion WHERE id_tipo_tramite_transicion = :id"),
        {"id": id_trans},
    )).fetchone()
    return TransicionOut(
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


# ---------------------------------------------------------------------------
# tipo_tramite_documento_requerido CRUD
# ---------------------------------------------------------------------------

@router.post("/versiones/{id_version}/documentos-requeridos", status_code=201, response_model=DocumentoRequeridoOut)
async def crear_documento_requerido(
    id_version: int,
    body: DocumentoRequeridoIn,
    user: dict = Depends(_require_admin_supervisor),
    db: AsyncSession = Depends(get_db),
):
    ver = await svc_ver.asegurar_editable(db, id_version)
    # Si se referencia estado, validar que pertenezca a la version
    if body.id_tipo_tramite_estado is not None:
        ok = (await db.execute(
            text("""
                SELECT 1 FROM tipo_tramite_estado
                WHERE id_tipo_tramite_estado = :e AND id_tipo_tramite_version = :v AND activo = TRUE
            """),
            {"e": body.id_tipo_tramite_estado, "v": id_version},
        )).fetchone()
        if not ok:
            raise HTTPException(422, "El estado referenciado no pertenece a esta version o esta inactivo")

    new_id = (await db.execute(
        text("""
            INSERT INTO tipo_tramite_documento_requerido
                (id_tipo_tramite_version, id_tipo_tramite_estado, nombre, descripcion,
                 obligatorio, formatos_permitidos, tamano_max_mb, requiere_firma,
                 firmantes_jsonb, aporta_quien, orden, activo, id_municipio)
            VALUES (:v, :est, :nom, :desc, :obl, :for, :tam, :rf,
                    CAST(:fj AS jsonb), :aq, :ord, TRUE, :mun)
            RETURNING id_tipo_tramite_documento_requerido
        """),
        {
            "v": id_version, "est": body.id_tipo_tramite_estado, "nom": body.nombre,
            "desc": body.descripcion, "obl": body.obligatorio,
            "for": body.formatos_permitidos, "tam": body.tamano_max_mb,
            "rf": body.requiere_firma,
            "fj": json.dumps(body.firmantes_jsonb) if body.firmantes_jsonb is not None else None,
            "aq": body.aporta_quien, "ord": body.orden, "mun": ver["id_municipio"],
        },
    )).scalar_one()
    await db.commit()
    return await _doc_req_out(db, int(new_id))


@router.put("/documentos-requeridos/{id_doc}", response_model=DocumentoRequeridoOut)
async def actualizar_documento_requerido(
    id_doc: int,
    body: DocumentoRequeridoUpdateIn,
    user: dict = Depends(_require_admin_supervisor),
    db: AsyncSession = Depends(get_db),
):
    fila = (await db.execute(
        text("SELECT id_tipo_tramite_version FROM tipo_tramite_documento_requerido WHERE id_tipo_tramite_documento_requerido = :id"),
        {"id": id_doc},
    )).fetchone()
    if not fila:
        raise HTTPException(404, "Documento requerido no encontrado")
    await svc_ver.asegurar_editable(db, fila.id_tipo_tramite_version)

    if body.id_tipo_tramite_estado is not None:
        ok = (await db.execute(
            text("""
                SELECT 1 FROM tipo_tramite_estado
                WHERE id_tipo_tramite_estado = :e AND id_tipo_tramite_version = :v AND activo = TRUE
            """),
            {"e": body.id_tipo_tramite_estado, "v": fila.id_tipo_tramite_version},
        )).fetchone()
        if not ok:
            raise HTTPException(422, "El estado referenciado no pertenece a esta version")

    sets: list[str] = []
    params: dict[str, Any] = {"id": id_doc}
    for field in ("nombre", "descripcion", "id_tipo_tramite_estado", "obligatorio",
                  "tamano_max_mb", "requiere_firma", "aporta_quien", "orden"):
        val = getattr(body, field)
        if val is not None:
            sets.append(f"{field} = :{field}")
            params[field] = val

    if body.formatos_permitidos is not None:
        sets.append("formatos_permitidos = :formatos_permitidos")
        params["formatos_permitidos"] = body.formatos_permitidos
    if body.firmantes_jsonb is not None:
        sets.append("firmantes_jsonb = CAST(:firmantes_jsonb AS jsonb)")
        params["firmantes_jsonb"] = json.dumps(body.firmantes_jsonb)

    if not sets:
        raise HTTPException(422, "No hay campos para actualizar")
    sets.append("fecha_modificacion = NOW()")
    await db.execute(text(f"UPDATE tipo_tramite_documento_requerido SET {', '.join(sets)} WHERE id_tipo_tramite_documento_requerido = :id"), params)
    await db.commit()
    return await _doc_req_out(db, id_doc)


@router.delete("/documentos-requeridos/{id_doc}", status_code=204)
async def eliminar_documento_requerido(
    id_doc: int,
    user: dict = Depends(_require_admin_supervisor),
    db: AsyncSession = Depends(get_db),
):
    fila = (await db.execute(
        text("SELECT id_tipo_tramite_version FROM tipo_tramite_documento_requerido WHERE id_tipo_tramite_documento_requerido = :id AND activo = TRUE"),
        {"id": id_doc},
    )).fetchone()
    if not fila:
        raise HTTPException(404, "Documento requerido no encontrado o ya inactivo")
    await svc_ver.asegurar_editable(db, fila.id_tipo_tramite_version)
    await db.execute(
        text("UPDATE tipo_tramite_documento_requerido SET activo = FALSE, fecha_modificacion = NOW() WHERE id_tipo_tramite_documento_requerido = :id"),
        {"id": id_doc},
    )
    await db.commit()


async def _doc_req_out(db: AsyncSession, id_doc: int) -> DocumentoRequeridoOut:
    r = (await db.execute(
        text("SELECT * FROM tipo_tramite_documento_requerido WHERE id_tipo_tramite_documento_requerido = :id"),
        {"id": id_doc},
    )).fetchone()
    return DocumentoRequeridoOut(
        id_tipo_tramite_documento_requerido=r.id_tipo_tramite_documento_requerido,
        nombre=r.nombre, descripcion=r.descripcion, obligatorio=r.obligatorio,
        id_tipo_tramite_estado=r.id_tipo_tramite_estado,
        aporta_quien=r.aporta_quien,
        formatos_permitidos=list(r.formatos_permitidos or []),
        tamano_max_mb=r.tamano_max_mb,
        requiere_firma=r.requiere_firma, orden=r.orden,
    )
