"""
ZARIS API — Endpoints CRUD genéricos para tablas administrativas.
Prefijo: /api/v1/admin/
"""
import logging
from datetime import date, time
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user

router = APIRouter(tags=["Admin Tablas"])
logger = logging.getLogger("zaris.admin_tablas")

# ─── Registro de tablas ────────────────────────────────────────────────────────
# pk: columna de clave primaria
# cols: columnas editables (excluye pk y timestamps estándar)
# fecha_mod: nombre del campo de última modificación (varía por tabla)
# exclude: columnas a ocultar en respuestas (ej: password_hash)

TABLE_CONFIG: dict[str, dict] = {
    "area": {
        "pk": "id_area",
        "cols": ["nombre", "descripcion"],
        "fecha_mod": "fecha_modificacion",
    },
    "subarea": {
        "pk": "id_subarea",
        "cols": ["nombre", "descripcion", "id_area"],
        "fecha_mod": "fecha_modificacion",
    },
    "tipo_usuario": {
        "pk": "id_tipo_usuario",
        "cols": ["nombre", "descripcion"],
        "fecha_mod": "fecha_modificacion",
    },
    "cargos": {
        "pk": "id_cargo",
        "cols": ["nombre", "descripcion"],
        "fecha_mod": "fecha_modificacion",
    },
    "usuarios": {
        "pk": "id_usuario",
        "cols": ["nombre", "nivel_acceso", "username", "cuil", "buc_acceso", "id_tipo_usuario", "id_subarea"],
        "fecha_mod": "fecha_modif",
        "exclude": ["password_hash"],
    },
    "agentes": {
        "pk": "id_agente",
        "cols": ["nombre", "apellido", "legajo", "email", "telefono", "id_cargo", "id_subarea"],
        "fecha_mod": "fecha_modificacion",
    },
    "equipos": {
        "pk": "id_equipo",
        "cols": ["nombre", "descripcion", "id_subarea", "dias_semana", "hora_inicio", "hora_fin"],
        "fecha_mod": "fecha_modificacion",
        "col_types": {"hora_inicio": "time", "hora_fin": "time"},
    },
    "equipo_usuarios": {
        "pk": "id_equipo_usuario",
        "cols": ["id_equipo", "id_usuario", "rol"],
        "fecha_mod": "fecha_modificacion",
    },
    "servicios": {
        "pk": "id",
        "cols": ["nombre", "descripcion", "id_area", "id_usuario_responsable", "capacidad_agentes",
                 "dias_semana", "hora_inicio", "hora_fin"],
        "fecha_mod": "modificado_en",
        "col_types": {"hora_inicio": "time", "hora_fin": "time"},
    },
    # ── Tablas de Agenda (sin campos estándar de auditoría)
    "areas": {
        "pk": "id",
        "cols": ["nombre", "descripcion"],
        "fecha_mod": "modificado_en",
        "has_audit": False,
    },
    "lugares_atencion": {
        "pk": "id",
        "cols": ["nombre", "direccion", "es_atencion", "capacidad_servicios", "id_area"],
        "fecha_mod": "modificado_en",
        "has_audit": False,
    },
    "agenda_clase": {
        "pk": "id",
        "cols": [
            "nombre", "descripcion", "visible_ciudadano", "requiere_rrhh",
            "requiere_servicio", "requiere_lugar", "duracion_slot_minutos", "id_area",
        ],
        "fecha_mod": "modificado_en",
        "has_audit": False,
    },
    "agenda_feriado": {
        "pk": "id",
        "cols": ["fecha", "descripcion", "ambito"],
        "fecha_mod": None,
        "has_audit": False,
        "col_types": {"fecha": "date"},
    },
    # ── Reclamos
    "estado_reclamo": {
        "pk": "id_estado_reclamo",
        "cols": ["nombre", "descripcion", "color", "es_final", "orden"],
        "fecha_mod": "fecha_modificacion",
        "has_audit": False,
    },
    "estado_ot": {
        "pk": "id_estado_ot",
        "cols": ["nombre", "descripcion", "color", "es_final", "orden"],
        "fecha_mod": "fecha_modificacion",
        "has_audit": False,
    },
    "equipo_agentes": {
        "pk": "id_equipo_agente",
        "cols": ["id_equipo", "id_agente"],
        "fecha_mod": "fecha_modificacion",
    },
    "tipo_reclamo": {
        "pk": "id_tipo_reclamo",
        "cols": ["nombre", "descripcion", "id_area", "id_subarea", "sla_dias", "audit"],
        "fecha_mod": "fecha_modificacion",
    },
    "configuracion_general": {
        "pk": "id_config",
        "cols": ["clave", "valor", "tipo", "descripcion"],
        "fecha_mod": "fecha_modificacion",
        "has_audit": False,
    },
    # ── Tablas BUC — ahora con auditoría y baja lógica
    "actividades": {
        "pk": "id",
        "cols": ["codigo_clae", "descripcion", "categoria_tasa"],
        "fecha_mod": "fecha_modificacion",
    },
    "tipo_representacion": {
        "pk": "id",
        "cols": ["tipo", "descripcion"],
        "fecha_mod": "fecha_modificacion",
    },
    "nacionalidades": {
        "pk": "id",
        "cols": ["pais", "region"],
        "fecha_mod": "fecha_modificacion",
    },
}

ALLOWED_TABLES = set(TABLE_CONFIG.keys())


def _get_config(tabla: str) -> dict:
    if tabla not in ALLOWED_TABLES:
        raise HTTPException(status_code=404, detail=f"Tabla '{tabla}' no administrable")
    return TABLE_CONFIG[tabla]


def _row_to_dict(row: Any, exclude: list[str]) -> dict:
    """Convierte un Row de SQLAlchemy a dict, omitiendo columnas sensibles."""
    d = dict(row._mapping)
    for col in exclude:
        d.pop(col, None)
    # Serializar TIME/DATE a string para JSON
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            d[k] = str(v)
    return d


def _coerce_types(data: dict, col_types: dict) -> None:
    """Convierte strings a tipos nativos de Python requeridos por asyncpg."""
    for col, typ in col_types.items():
        if col not in data or data[col] is None:
            continue
        val = data[col]
        if not isinstance(val, str):
            continue
        if typ == "date":
            data[col] = date.fromisoformat(val)
        elif typ == "time":
            h, m = val.split(":")[:2]
            data[col] = time(int(h), int(m))


# ─── GET /{tabla} — listar activos ────────────────────────────────────────────

@router.get("/{tabla}")
async def listar(
    tabla: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    cfg = _get_config(tabla)
    pk = cfg["pk"]
    exclude = cfg.get("exclude", [])
    where = "WHERE activo = TRUE" if cfg.get("has_activo", True) else ""
    stmt = text(f"SELECT * FROM {tabla} {where} ORDER BY {pk}")
    result = await db.execute(stmt)
    rows = result.fetchall()
    return [_row_to_dict(r, exclude) for r in rows]


# ─── GET /{tabla}/{id} — obtener uno ──────────────────────────────────────────

@router.get("/{tabla}/{id}")
async def obtener(
    tabla: str,
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    cfg = _get_config(tabla)
    pk = cfg["pk"]
    exclude = cfg.get("exclude", [])
    stmt = text(f"SELECT * FROM {tabla} WHERE {pk} = :id")
    result = await db.execute(stmt, {"id": id})
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Registro {id} no encontrado en {tabla}")
    return _row_to_dict(row, exclude)


# ─── POST /{tabla} — crear ────────────────────────────────────────────────────

@router.post("/{tabla}", status_code=201)
async def crear(
    tabla: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    cfg = _get_config(tabla)
    allowed = cfg["cols"]
    exclude = cfg.get("exclude", [])

    data = {k: v for k, v in body.items() if k in allowed}
    if not data:
        raise HTTPException(status_code=422, detail="No se recibieron campos válidos")

    if cfg.get("has_audit", True):
        data["id_usuario_alta"] = current_user["id_usuario"]

    if cfg.get("has_activo", True) and "activo" not in data:
        data["activo"] = True

    col_types = cfg.get("col_types", {})
    _coerce_types(data, col_types)
    cols = ", ".join(data.keys())
    vals = ", ".join(f":{k}" for k in data.keys())
    stmt = text(f"INSERT INTO {tabla} ({cols}) VALUES ({vals}) RETURNING *")
    try:
        result = await db.execute(stmt, data)
        await db.commit()
        row = result.fetchone()
        return _row_to_dict(row, exclude)
    except Exception as e:
        await db.rollback()
        logger.error("Error al crear en %s: %s", tabla, e)
        raise HTTPException(status_code=400, detail=str(e))


# ─── PUT /{tabla}/{id} — editar ───────────────────────────────────────────────

@router.put("/{tabla}/{id}")
async def editar(
    tabla: str,
    id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    cfg = _get_config(tabla)
    pk = cfg["pk"]
    allowed = cfg["cols"]
    fecha_mod = cfg["fecha_mod"]
    exclude = cfg.get("exclude", [])

    data = {k: v for k, v in body.items() if k in allowed}
    if not data:
        raise HTTPException(status_code=422, detail="No se recibieron campos válidos")

    if cfg.get("has_audit", True):
        data["id_usuario_modificacion"] = current_user["id_usuario"]
    col_types = cfg.get("col_types", {})
    _coerce_types(data, col_types)
    sets = ", ".join(f"{k} = :{k}" for k in data.keys())
    fecha_extra = f", {fecha_mod} = NOW()" if fecha_mod else ""
    stmt = text(
        f"UPDATE {tabla} SET {sets}{fecha_extra} "
        f"WHERE {pk} = :__id RETURNING *"
    )
    try:
        result = await db.execute(stmt, {**data, "__id": id})
        await db.commit()
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Registro {id} no encontrado en {tabla}")
        return _row_to_dict(row, exclude)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Error al editar en %s id=%s: %s", tabla, id, e)
        raise HTTPException(status_code=400, detail=str(e))


# ─── DELETE /{tabla}/{id} — baja lógica ───────────────────────────────────────

@router.delete("/{tabla}/{id}")
async def baja_logica(
    tabla: str,
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    cfg = _get_config(tabla)
    pk = cfg["pk"]
    fecha_mod = cfg["fecha_mod"]
    if not cfg.get("has_activo", True):
        raise HTTPException(
            status_code=400,
            detail=f"La tabla '{tabla}' no soporta baja lógica (sin campo activo)"
        )
    parts: list[str] = ["activo = FALSE"]
    params: dict = {"id": id}
    if fecha_mod:
        parts.append(f"{fecha_mod} = NOW()")
    if cfg.get("has_audit", True):
        parts.append("id_usuario_modificacion = :uid")
        params["uid"] = current_user["id_usuario"]
    stmt = text(f"UPDATE {tabla} SET {', '.join(parts)} WHERE {pk} = :id RETURNING {pk}")
    try:
        result = await db.execute(stmt, params)
        await db.commit()
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Registro {id} no encontrado en {tabla}")
        return {"ok": True, pk: id}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Error al dar de baja en %s id=%s: %s", tabla, id, e)
        raise HTTPException(status_code=400, detail=str(e))
