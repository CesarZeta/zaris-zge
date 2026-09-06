"""
ZARIS API - Router de espacios de agenda (mig 40).

CRUD del catalogo `espacios_agenda` + N:M `espacio_agentes`. Convive con el
modulo Agenda y se monta bajo el mismo prefix /api/v1/agenda para que el
frontend del modulo lo consuma como sub-recurso.

Permisos: nivel 1-2 (admin/supervisor) puede mutar; cualquier nivel autenticado
puede leer (mismo criterio que catalogos de agenda).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.schemas.agenda_v2 import (
    EspacioAgendaCreate,
    EspacioAgendaOut,
    EspacioAgendaUpdate,
    EspacioAgenteCreate,
    EspacioAgenteOut,
)
from app.services.agenda import subarea_del_usuario


router = APIRouter(prefix="/api/v1/agenda/espacios", tags=["agenda-espacios"])


def _require_admin(user: dict) -> None:
    """Solo nivel 1 (admin) o 2 (supervisor) puede mutar el catalogo."""
    if int(user.get("nivel_acceso", 99)) > 2:
        raise HTTPException(403, "Permiso insuficiente (requiere nivel <= 2)")


async def _subarea_scope_nivel2(db: AsyncSession, user: dict) -> Optional[int]:
    """Scope-subarea 2026-07-18 (hallazgo [18]) — espejo de _subarea_scope_mutacion
    de agenda_v2, acotado a este router (solo nivel <= 2 llega a mutar).
    None para nivel 1 (admin sin scope); para nivel 2 devuelve la subarea de su
    agente vinculado (regla 1:1 §39, via subarea_del_usuario — NUNCA
    usuarios.id_subarea). Fail-closed: supervisor sin subarea resoluble => 403
    accionable."""
    if int(user.get("nivel_acceso", 99)) != 2:
        return None
    sub = await subarea_del_usuario(db, int(user["id_usuario"]))
    if sub is None:
        raise HTTPException(
            status_code=403,
            detail=(
                "Tu usuario no tiene una subárea asignada en su perfil de agente. "
                "Pedile a un administrador que la configure desde Maestros → Usuarios."
            ),
        )
    return sub


async def _validar_scope_espacio(db: AsyncSession, user: dict, id_espacio: int) -> Optional[int]:
    """Scope-subarea 2026-07-18 — el supervisor (nivel 2) solo gestiona espacios
    de su subarea. Espacio con id_subarea NULL = compartido: lo gestiona un
    administrador. Espacio inexistente NO corta aca (el 404 lo da el handler).
    Devuelve la subarea del supervisor (None = sin scope) para checks
    adicionales del caller."""
    sub = await _subarea_scope_nivel2(db, user)
    if sub is None:
        return None
    row = (await db.execute(text(
        "SELECT id_subarea FROM espacios_agenda WHERE id_espacio = :id"
    ), {"id": id_espacio})).mappings().first()
    if row is None:
        return sub
    if row["id_subarea"] is None:
        raise HTTPException(403, "Los espacios compartidos los gestiona un administrador.")
    if int(row["id_subarea"]) != sub:
        raise HTTPException(403, "El espacio pertenece a otra subárea.")
    return sub


async def _espacio_to_out(db: AsyncSession, id_espacio: int, incluir_agentes: bool = True) -> Optional[dict[str, Any]]:
    row = (await db.execute(text("""
        SELECT e.id_espacio, e.nombre, e.descripcion, e.direccion, e.latitud, e.longitud,
               e.capacidad_personas,
               e.atendido, e.id_subarea, s.nombre AS subarea_nombre, e.prefijo_colero,
               e.activo, e.id_municipio, e.fecha_alta, e.fecha_modificacion
        FROM espacios_agenda e
        LEFT JOIN subarea s ON s.id_subarea = e.id_subarea
        WHERE e.id_espacio = :id
    """), {"id": id_espacio})).mappings().first()
    if not row:
        return None
    out = dict(row)
    out["agentes_vinculados"] = []
    out["cant_agentes"] = 0
    if incluir_agentes:
        out["agentes_vinculados"] = await _listar_agentes_espacio(db, id_espacio)
        out["cant_agentes"] = len(out["agentes_vinculados"])
    return out


async def _listar_agentes_espacio(db: AsyncSession, id_espacio: int) -> list[dict[str, Any]]:
    rows = (await db.execute(text("""
        SELECT ea.id_espacio_agente, ea.id_espacio, ea.id_agente,
               COALESCE(a.apellido, '') || ', ' || COALESCE(a.nombre, '') AS agente_nombre,
               ea.activo, ea.fecha_alta
        FROM espacio_agentes ea
        JOIN agentes a ON a.id_agente = ea.id_agente
        WHERE ea.id_espacio = :id AND ea.activo = TRUE
        ORDER BY a.apellido, a.nombre
    """), {"id": id_espacio})).mappings().all()
    return [dict(r) for r in rows]


# =============================================================================
# CRUD espacios
# =============================================================================
@router.get("", response_model=list[EspacioAgendaOut])
async def listar_espacios(
    id_municipio: int = 1,
    atendido: Optional[bool] = Query(None, description="True=solo atendidos, False=solo desatendidos, omitir=ambos"),
    activo: bool = True,
    q: Optional[str] = Query(None, description="Texto libre sobre nombre/direccion"),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    where = ["e.id_municipio = :m", "e.activo = :ac"]
    params: dict[str, Any] = {"m": id_municipio, "ac": activo}
    if atendido is not None:
        where.append("e.atendido = :at"); params["at"] = atendido
    if q:
        where.append("(e.nombre ILIKE :q OR COALESCE(e.direccion,'') ILIKE :q)")
        params["q"] = f"%{q}%"
    where_sql = " AND ".join(where)
    rows = (await db.execute(text(f"""
        SELECT e.id_espacio, e.nombre, e.descripcion, e.direccion, e.latitud, e.longitud,
               e.capacidad_personas,
               e.atendido, e.id_subarea, s.nombre AS subarea_nombre, e.prefijo_colero,
               e.activo, e.id_municipio, e.fecha_alta, e.fecha_modificacion,
               (SELECT COUNT(*) FROM espacio_agentes ea
                 WHERE ea.id_espacio = e.id_espacio AND ea.activo = TRUE) AS cant_agentes
        FROM espacios_agenda e
        LEFT JOIN subarea s ON s.id_subarea = e.id_subarea
        WHERE {where_sql}
        ORDER BY e.nombre
    """), params)).mappings().all()
    # Listado liviano: no incluir agentes vinculados (es n+1, lo trae /detalle).
    # Si traemos solo el conteo agregado (cant_agentes) para que el frontend
    # pueda marcar espacios atendidos sin agentes.
    out = []
    for r in rows:
        d = dict(r)
        d["agentes_vinculados"] = []
        out.append(d)
    return out


@router.post("", response_model=EspacioAgendaOut, status_code=201)
async def crear_espacio(
    payload: EspacioAgendaCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_admin(user)
    # Scope-subarea 2026-07-18: el supervisor solo crea espacios de su subarea.
    sub = await _subarea_scope_nivel2(db, user)
    if sub is not None:
        if payload.id_subarea is None:
            raise HTTPException(403, "Los espacios compartidos (sin subárea) los crea un administrador.")
        if payload.id_subarea != sub:
            raise HTTPException(403, "Solo podés crear espacios de tu subárea.")
    row = (await db.execute(text("""
        INSERT INTO espacios_agenda (
            nombre, descripcion, direccion, latitud, longitud, capacidad_personas, atendido,
            id_subarea, prefijo_colero, id_municipio, id_usuario_alta, id_usuario_modificacion
        ) VALUES (
            :nombre, :descripcion, :direccion, :latitud, :longitud, :capacidad, :atendido,
            :id_sa, :prefijo, :id_mun, :uid, :uid
        )
        RETURNING id_espacio
    """), {
        "nombre": payload.nombre,
        "descripcion": payload.descripcion,
        "direccion": payload.direccion,
        "latitud": payload.latitud,
        "longitud": payload.longitud,
        "capacidad": payload.capacidad_personas,
        "atendido": payload.atendido,
        "id_sa": payload.id_subarea,
        "prefijo": payload.prefijo_colero,
        "id_mun": payload.id_municipio,
        "uid": user["id_usuario"],
    })).first()
    await db.commit()
    out = await _espacio_to_out(db, int(row[0]))
    if out is None:
        raise HTTPException(500, "Espacio creado pero no se pudo releer")
    return out


@router.get("/{id_espacio}", response_model=EspacioAgendaOut)
async def detalle_espacio(
    id_espacio: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    out = await _espacio_to_out(db, id_espacio)
    if out is None:
        raise HTTPException(404, "Espacio no encontrado")
    return out


@router.put("/{id_espacio}", response_model=EspacioAgendaOut)
async def actualizar_espacio(
    id_espacio: int,
    payload: EspacioAgendaUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_admin(user)
    row = (await db.execute(text("SELECT 1 FROM espacios_agenda WHERE id_espacio = :id"), {"id": id_espacio})).first()
    if not row:
        raise HTTPException(404, "Espacio no encontrado")
    # Scope-subarea 2026-07-18: solo espacios de la subarea del supervisor.
    sub = await _validar_scope_espacio(db, user, id_espacio)

    sets = []
    params: dict[str, Any] = {"id": id_espacio, "uid": user["id_usuario"]}
    data = payload.model_dump(exclude_unset=True)
    # El supervisor tampoco puede mover el espacio fuera de su subarea (a otra
    # subarea o a compartido/NULL) via este PUT.
    if sub is not None and "id_subarea" in data and data["id_subarea"] != sub:
        raise HTTPException(403, "Solo podés asignar el espacio a tu propia subárea.")
    # prefijo_colero (mig 105): ya viene normalizado/validado por el schema (3 alfanumericos o None).
    for col in ("nombre", "descripcion", "direccion", "latitud", "longitud", "capacidad_personas", "atendido", "id_subarea", "prefijo_colero", "activo"):
        if col in data:
            sets.append(f"{col} = :{col}")
            params[col] = data[col]
    if not sets:
        # Nada que actualizar — devolver estado actual.
        out = await _espacio_to_out(db, id_espacio)
        return out  # type: ignore

    sets.append("fecha_modificacion = NOW()")
    sets.append("id_usuario_modificacion = :uid")
    await db.execute(text(f"UPDATE espacios_agenda SET {', '.join(sets)} WHERE id_espacio = :id"), params)
    await db.commit()
    out = await _espacio_to_out(db, id_espacio)
    if out is None:
        raise HTTPException(500, "Espacio actualizado pero no se pudo releer")
    return out


@router.delete("/{id_espacio}", status_code=204)
async def eliminar_espacio(
    id_espacio: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Soft-delete: activo = FALSE. Tambien soft-deletea espacio_agentes asociados."""
    _require_admin(user)
    row = (await db.execute(text("SELECT 1 FROM espacios_agenda WHERE id_espacio = :id AND activo = TRUE"), {"id": id_espacio})).first()
    if not row:
        raise HTTPException(404, "Espacio no encontrado o ya inactivo")
    # Scope-subarea 2026-07-18: solo espacios de la subarea del supervisor.
    await _validar_scope_espacio(db, user, id_espacio)
    await db.execute(text("""
        UPDATE espacios_agenda
        SET activo = FALSE, fecha_modificacion = NOW(), id_usuario_modificacion = :uid
        WHERE id_espacio = :id
    """), {"id": id_espacio, "uid": user["id_usuario"]})
    await db.execute(text("""
        UPDATE espacio_agentes
        SET activo = FALSE, fecha_modificacion = NOW(), id_usuario_modificacion = :uid
        WHERE id_espacio = :id AND activo = TRUE
    """), {"id": id_espacio, "uid": user["id_usuario"]})
    await db.commit()


# =============================================================================
# N:M espacio <-> agente
# =============================================================================
@router.get("/{id_espacio}/agentes", response_model=list[EspacioAgenteOut])
async def listar_agentes_de_espacio(
    id_espacio: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    return await _listar_agentes_espacio(db, id_espacio)


@router.post("/{id_espacio}/agentes", response_model=EspacioAgenteOut, status_code=201)
async def vincular_agente_a_espacio(
    id_espacio: int,
    payload: EspacioAgenteCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_admin(user)
    # Validar existencia
    esp = (await db.execute(text("SELECT 1 FROM espacios_agenda WHERE id_espacio = :id AND activo = TRUE"), {"id": id_espacio})).first()
    if not esp:
        raise HTTPException(404, "Espacio no encontrado o inactivo")
    ag = (await db.execute(text("SELECT 1 FROM agentes WHERE id_agente = :id AND activo = TRUE"), {"id": payload.id_agente})).first()
    if not ag:
        raise HTTPException(404, "Agente no encontrado o inactivo")
    # Scope-subarea 2026-07-18: scope SOLO por el ESPACIO. NO se valida la
    # subarea del agente vinculado: los espacios atendidos se atienden con
    # agentes de varias subareas POR DISENO.
    await _validar_scope_espacio(db, user, id_espacio)

    # Reactivar si existe inactivo, sino INSERT.
    existe = (await db.execute(text("""
        SELECT id_espacio_agente, activo FROM espacio_agentes
        WHERE id_espacio = :ie AND id_agente = :ia
    """), {"ie": id_espacio, "ia": payload.id_agente})).mappings().first()
    if existe:
        if existe["activo"]:
            raise HTTPException(409, "Agente ya vinculado a este espacio")
        await db.execute(text("""
            UPDATE espacio_agentes
            SET activo = TRUE, fecha_modificacion = NOW(), id_usuario_modificacion = :uid
            WHERE id_espacio_agente = :id
        """), {"id": existe["id_espacio_agente"], "uid": user["id_usuario"]})
        id_ea = int(existe["id_espacio_agente"])
    else:
        row = (await db.execute(text("""
            INSERT INTO espacio_agentes (id_espacio, id_agente, id_usuario_alta, id_usuario_modificacion)
            VALUES (:ie, :ia, :uid, :uid)
            RETURNING id_espacio_agente
        """), {"ie": id_espacio, "ia": payload.id_agente, "uid": user["id_usuario"]})).first()
        id_ea = int(row[0])

    await db.commit()
    rows = (await db.execute(text("""
        SELECT ea.id_espacio_agente, ea.id_espacio, ea.id_agente,
               COALESCE(a.apellido, '') || ', ' || COALESCE(a.nombre, '') AS agente_nombre,
               ea.activo, ea.fecha_alta
        FROM espacio_agentes ea
        JOIN agentes a ON a.id_agente = ea.id_agente
        WHERE ea.id_espacio_agente = :id
    """), {"id": id_ea})).mappings().first()
    if not rows:
        raise HTTPException(500, "Vinculo creado pero no se pudo releer")
    return dict(rows)


@router.delete("/{id_espacio}/agentes/{id_espacio_agente}", status_code=204)
async def desvincular_agente_de_espacio(
    id_espacio: int,
    id_espacio_agente: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_admin(user)
    row = (await db.execute(text("""
        SELECT 1 FROM espacio_agentes
        WHERE id_espacio_agente = :id AND id_espacio = :ie AND activo = TRUE
    """), {"id": id_espacio_agente, "ie": id_espacio})).first()
    if not row:
        raise HTTPException(404, "Vinculo no encontrado o ya inactivo")
    # Scope-subarea 2026-07-18: scope SOLO por el ESPACIO (misma regla que el POST).
    await _validar_scope_espacio(db, user, id_espacio)
    await db.execute(text("""
        UPDATE espacio_agentes
        SET activo = FALSE, fecha_modificacion = NOW(), id_usuario_modificacion = :uid
        WHERE id_espacio_agente = :id
    """), {"id": id_espacio_agente, "uid": user["id_usuario"]})
    await db.commit()
