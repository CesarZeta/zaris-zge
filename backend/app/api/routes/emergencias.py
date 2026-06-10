"""
ZARIS API - Modulo Emergencias (COM).

Fase 2: catalogos de lectura (plan seccion 4.1).
Fase 3: contactos eventuales (4.2), busqueda unificada de denunciantes (4.3)
        y eventos con FSM + log append-only (4.4).

Permisos: guard JWT a nivel router (patron s39 — get_current_user rechaza
scope publico). Catalogos: cualquier autenticado. Contactos/eventos:
nivel <= 3 (operador+); el operador (nivel 3) con subarea asignada queda
scopeado a su subarea; admin/supervisor (<=2) y operador sin subarea ven todo.
"""
from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db

router = APIRouter(
    prefix="/api/v1/emergencias",
    tags=["emergencias"],
    dependencies=[Depends(get_current_user)],
)


# =============================================================================
# Schemas (lectura)
# =============================================================================
class OrganismoOut(BaseModel):
    id_emergencia_organismo_derivacion: int
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    telefono_contacto: Optional[str] = None
    es_municipal: bool
    activo: bool


class CanalOut(BaseModel):
    id_emergencia_canal_ingreso: int
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    requiere_operador: bool
    activo: bool


class PrioridadOut(BaseModel):
    id_emergencia_prioridad: int
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    sla_minutos_arribo: int
    color_token: str
    orden_visual: int
    activo: bool


class EstadoOut(BaseModel):
    id_emergencia_estado: int
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    es_inicial: bool
    es_terminal: bool
    es_terminal_positivo: bool
    orden_visual: int
    activo: bool


class TipoOut(BaseModel):
    id_emergencia_tipo: int
    id_subarea: int
    subarea_nombre: Optional[str] = None
    codigo_oficial: Optional[int] = None
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    id_prioridad_default: int
    prioridad_codigo: Optional[str] = None
    id_organismo_derivacion_default: Optional[int] = None
    organismo_default_codigo: Optional[str] = None
    requiere_911: bool
    es_emergencia: bool
    activo: bool


class SubtipoOut(BaseModel):
    id_emergencia_subtipo: int
    id_tipo: int
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    id_prioridad_override: Optional[int] = None
    prioridad_override_codigo: Optional[str] = None
    activo: bool


# =============================================================================
# Catalogos simples
# =============================================================================
@router.get("/organismos", response_model=list[OrganismoOut])
async def listar_organismos(
    activo: Optional[bool] = Query(True),
    db: AsyncSession = Depends(get_db),
) -> Any:
    rows = (await db.execute(text("""
        SELECT id_emergencia_organismo_derivacion, codigo, nombre, descripcion,
               telefono_contacto, es_municipal, activo
        FROM emergencia_organismo_derivacion
        WHERE (CAST(:activo AS boolean) IS NULL OR activo = :activo)
        ORDER BY nombre
    """), {"activo": activo})).mappings().all()
    return [dict(r) for r in rows]


@router.get("/canales", response_model=list[CanalOut])
async def listar_canales(
    activo: Optional[bool] = Query(True),
    db: AsyncSession = Depends(get_db),
) -> Any:
    rows = (await db.execute(text("""
        SELECT id_emergencia_canal_ingreso, codigo, nombre, descripcion,
               requiere_operador, activo
        FROM emergencia_canal_ingreso
        WHERE (CAST(:activo AS boolean) IS NULL OR activo = :activo)
        ORDER BY nombre
    """), {"activo": activo})).mappings().all()
    return [dict(r) for r in rows]


@router.get("/prioridades", response_model=list[PrioridadOut])
async def listar_prioridades(
    activo: Optional[bool] = Query(True),
    db: AsyncSession = Depends(get_db),
) -> Any:
    rows = (await db.execute(text("""
        SELECT id_emergencia_prioridad, codigo, nombre, descripcion,
               sla_minutos_arribo, color_token, orden_visual, activo
        FROM emergencia_prioridad
        WHERE (CAST(:activo AS boolean) IS NULL OR activo = :activo)
        ORDER BY orden_visual
    """), {"activo": activo})).mappings().all()
    return [dict(r) for r in rows]


@router.get("/estados", response_model=list[EstadoOut])
async def listar_estados(
    activo: Optional[bool] = Query(True),
    db: AsyncSession = Depends(get_db),
) -> Any:
    rows = (await db.execute(text("""
        SELECT id_emergencia_estado, codigo, nombre, descripcion,
               es_inicial, es_terminal, es_terminal_positivo, orden_visual, activo
        FROM emergencia_estado
        WHERE (CAST(:activo AS boolean) IS NULL OR activo = :activo)
        ORDER BY orden_visual
    """), {"activo": activo})).mappings().all()
    return [dict(r) for r in rows]


# =============================================================================
# Tipos y subtipos
# =============================================================================
_SELECT_TIPOS = """
    SELECT t.id_emergencia_tipo, t.id_subarea, s.nombre AS subarea_nombre,
           t.codigo_oficial, t.codigo, t.nombre, t.descripcion,
           t.id_prioridad_default, p.codigo AS prioridad_codigo,
           t.id_organismo_derivacion_default, o.codigo AS organismo_default_codigo,
           t.requiere_911, t.es_emergencia, t.activo
    FROM emergencia_tipo t
    JOIN subarea s ON s.id_subarea = t.id_subarea
    JOIN emergencia_prioridad p ON p.id_emergencia_prioridad = t.id_prioridad_default
    LEFT JOIN emergencia_organismo_derivacion o
           ON o.id_emergencia_organismo_derivacion = t.id_organismo_derivacion_default
"""


@router.get("/tipos", response_model=list[TipoOut])
async def listar_tipos(
    id_subarea: Optional[int] = Query(None),
    activo: Optional[bool] = Query(True),
    db: AsyncSession = Depends(get_db),
) -> Any:
    rows = (await db.execute(text(_SELECT_TIPOS + """
        WHERE (CAST(:id_subarea AS integer) IS NULL OR t.id_subarea = :id_subarea)
          AND (CAST(:activo AS boolean) IS NULL OR t.activo = :activo)
        ORDER BY t.nombre
    """), {"id_subarea": id_subarea, "activo": activo})).mappings().all()
    return [dict(r) for r in rows]


_SELECT_SUBTIPOS = """
    SELECT st.id_emergencia_subtipo, st.id_tipo, st.codigo, st.nombre,
           st.descripcion, st.id_prioridad_override,
           p.codigo AS prioridad_override_codigo, st.activo
    FROM emergencia_subtipo st
    LEFT JOIN emergencia_prioridad p
           ON p.id_emergencia_prioridad = st.id_prioridad_override
"""


@router.get("/tipos/{id_tipo}/subtipos", response_model=list[SubtipoOut])
async def listar_subtipos_de_tipo(
    id_tipo: int,
    activo: Optional[bool] = Query(True),
    db: AsyncSession = Depends(get_db),
) -> Any:
    existe = (await db.execute(text(
        "SELECT 1 FROM emergencia_tipo WHERE id_emergencia_tipo = :id"
    ), {"id": id_tipo})).scalar()
    if not existe:
        raise HTTPException(404, "Tipo de emergencia no encontrado")
    rows = (await db.execute(text(_SELECT_SUBTIPOS + """
        WHERE st.id_tipo = :id_tipo
          AND (CAST(:activo AS boolean) IS NULL OR st.activo = :activo)
        ORDER BY st.nombre
    """), {"id_tipo": id_tipo, "activo": activo})).mappings().all()
    return [dict(r) for r in rows]


@router.get("/subtipos", response_model=list[SubtipoOut])
async def listar_subtipos(
    id_tipo: Optional[int] = Query(None),
    activo: Optional[bool] = Query(True),
    db: AsyncSession = Depends(get_db),
) -> Any:
    rows = (await db.execute(text(_SELECT_SUBTIPOS + """
        WHERE (CAST(:id_tipo AS integer) IS NULL OR st.id_tipo = :id_tipo)
          AND (CAST(:activo AS boolean) IS NULL OR st.activo = :activo)
        ORDER BY st.id_tipo, st.nombre
    """), {"id_tipo": id_tipo, "activo": activo})).mappings().all()
    return [dict(r) for r in rows]


# =============================================================================
# FASE 3 — Helpers de permisos, estados y log
# =============================================================================
def _solo_digitos(s: Optional[str]) -> str:
    return re.sub(r"\D", "", s or "")


def _require_operador(user: dict) -> None:
    if int(user.get("nivel_acceso", 99)) > 3:
        raise HTTPException(403, "Permiso insuficiente (requiere nivel <= 3)")


async def _subarea_usuario(db: AsyncSession, id_usuario: int) -> Optional[int]:
    return (await db.execute(text(
        "SELECT id_subarea FROM usuarios WHERE id_usuario = :id"
    ), {"id": id_usuario})).scalar()


async def _check_scope_subarea(db: AsyncSession, user: dict, id_subarea_evento: int) -> None:
    """Operador (nivel 3) con subarea asignada solo opera eventos de su subarea.
    Admin/supervisor (<=2) exentos. Operador sin subarea: fail-open (s27)."""
    if int(user.get("nivel_acceso", 99)) <= 2:
        return
    propia = await _subarea_usuario(db, user["id_usuario"])
    if propia is not None and propia != id_subarea_evento:
        raise HTTPException(403, "El evento pertenece a otra subarea")


async def _filtro_scope_subarea(db: AsyncSession, user: dict) -> Optional[int]:
    """Devuelve la subarea a la que limitar listados (None = sin limite)."""
    if int(user.get("nivel_acceso", 99)) <= 2:
        return None
    return await _subarea_usuario(db, user["id_usuario"])


# FSM de estados (espeja el panel de acciones del plan seccion 5.3).
# RESUELTO/DESESTIMADO solo via POST /cerrar; DERIVADO solo via POST /derivar.
TRANSICIONES: dict[str, set[str]] = {
    "PENDIENTE": {"EN_PREPARACION", "DERIVADO", "DESESTIMADO"},
    "EN_PREPARACION": {"EN_CAMINO", "DERIVADO", "DESESTIMADO"},
    "EN_CAMINO": {"EN_SITIO", "DERIVADO"},
    "EN_SITIO": {"RESUELTO", "DERIVADO"},
    "DERIVADO": {"EN_SITIO", "RESUELTO"},
    "RESUELTO": set(),
    "DESESTIMADO": set(),
}


async def _estado_por_codigo(db: AsyncSession, codigo: str) -> dict:
    row = (await db.execute(text("""
        SELECT id_emergencia_estado, codigo, es_terminal, es_terminal_positivo
        FROM emergencia_estado WHERE codigo = :c AND activo
    """), {"c": codigo})).mappings().first()
    if not row:
        raise HTTPException(422, f"Estado '{codigo}' inexistente o inactivo")
    return dict(row)


async def _evento_for_update(db: AsyncSession, id_evento: int) -> dict:
    row = (await db.execute(text("""
        SELECT e.*, est.codigo AS estado_codigo, est.es_terminal
        FROM emergencia_evento e
        JOIN emergencia_estado est ON est.id_emergencia_estado = e.id_estado
        WHERE e.id_emergencia_evento = :id AND e.activo
        FOR UPDATE OF e
    """), {"id": id_evento})).mappings().first()
    if not row:
        raise HTTPException(404, "Evento no encontrado")
    return dict(row)


async def _registrar_log(
    db: AsyncSession,
    id_evento: int,
    id_usuario: Optional[int],
    tipo_accion: str,
    estado_anterior: Optional[str] = None,
    estado_nuevo: Optional[str] = None,
    payload: Optional[dict] = None,
    observaciones: Optional[str] = None,
    id_municipio: Optional[int] = None,
) -> None:
    await db.execute(text("""
        INSERT INTO emergencia_log
            (id_evento, id_usuario, tipo_accion, estado_anterior, estado_nuevo,
             payload_json, observaciones, id_municipio)
        VALUES (:e, :u, :t, :ea, :en, CAST(:p AS jsonb), :o, :m)
    """), {
        "e": id_evento, "u": id_usuario, "t": tipo_accion,
        "ea": estado_anterior, "en": estado_nuevo,
        "p": json.dumps(payload) if payload is not None else None,
        "o": observaciones, "m": id_municipio,
    })


# =============================================================================
# FASE 3 — Schemas
# =============================================================================
class ContactoEventualCreate(BaseModel):
    dni: str = Field(..., min_length=6, max_length=15)
    nombre_apellido: str = Field(..., min_length=3, max_length=150)
    telefono: str = Field(..., min_length=6, max_length=30)
    direccion: str = Field(..., min_length=3, max_length=300)
    contacto_alt_nombre: Optional[str] = Field(None, max_length=150)
    contacto_alt_telefono: Optional[str] = Field(None, max_length=30)
    observaciones: Optional[str] = None
    id_municipio: Optional[int] = None


class ContactoEventualUpdate(BaseModel):
    nombre_apellido: Optional[str] = Field(None, min_length=3, max_length=150)
    telefono: Optional[str] = Field(None, min_length=6, max_length=30)
    direccion: Optional[str] = Field(None, min_length=3, max_length=300)
    contacto_alt_nombre: Optional[str] = Field(None, max_length=150)
    contacto_alt_telefono: Optional[str] = Field(None, max_length=30)
    observaciones: Optional[str] = None


class ContactoEventualOut(BaseModel):
    id_emergencia_contacto_eventual: int
    dni: str
    nombre_apellido: str
    telefono: str
    direccion: str
    contacto_alt_nombre: Optional[str] = None
    contacto_alt_telefono: Optional[str] = None
    convertido_a_buc: bool
    id_ciudadano_buc_destino: Optional[int] = None
    observaciones: Optional[str] = None
    activo: bool
    fecha_alta: Any = None


class PromoverBucIn(BaseModel):
    # vincular a un ciudadano existente...
    id_ciudadano: Optional[int] = None
    # ...o crear uno nuevo (apellido + nombre + email obligatorios en ese caso)
    apellido: Optional[str] = Field(None, max_length=100)
    nombre: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=150)


class EventoCreate(BaseModel):
    id_subarea: int
    id_tipo: int
    id_subtipo: Optional[int] = None
    id_prioridad: Optional[int] = None      # autocompleta del subtipo/tipo si no viene
    id_canal_ingreso: int
    denunciante_anonimo: bool = False
    id_ciudadano_buc: Optional[int] = None
    id_contacto_eventual: Optional[int] = None
    direccion_evento: str = Field(..., min_length=3, max_length=300)
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    referencia_ubicacion: Optional[str] = Field(None, max_length=300)
    observaciones_recepcion: Optional[str] = None
    audio_grabacion_url: Optional[str] = None
    id_municipio: Optional[int] = None


class EventoUpdate(BaseModel):
    id_tipo: Optional[int] = None
    id_subtipo: Optional[int] = None
    id_prioridad: Optional[int] = None
    direccion_evento: Optional[str] = Field(None, min_length=3, max_length=300)
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    referencia_ubicacion: Optional[str] = Field(None, max_length=300)
    observaciones_recepcion: Optional[str] = None
    audio_grabacion_url: Optional[str] = None


class CambiarEstadoIn(BaseModel):
    nuevo_estado: str
    observaciones: Optional[str] = None


class DerivarIn(BaseModel):
    id_organismo: int
    observaciones: Optional[str] = None


class CerrarIn(BaseModel):
    veracidad: Literal["CONFIRMADA", "FALSA_ALARMA", "NO_VERIFICABLE"]
    terminal_positivo: bool
    observaciones_cierre: Optional[str] = None


class NotaIn(BaseModel):
    observaciones: str = Field(..., min_length=1)


# =============================================================================
# FASE 3 — Contactos eventuales (4.2)
# =============================================================================
_SELECT_CONTACTO = """
    SELECT id_emergencia_contacto_eventual, dni, nombre_apellido, telefono,
           direccion, contacto_alt_nombre, contacto_alt_telefono,
           convertido_a_buc, id_ciudadano_buc_destino, observaciones,
           activo, fecha_alta
    FROM emergencia_contacto_eventual
"""


@router.get("/contactos-eventuales", response_model=list[ContactoEventualOut])
async def buscar_contactos_eventuales(
    dni: Optional[str] = Query(None),
    telefono: Optional[str] = Query(None),
    nombre: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    _require_operador(user)
    criterios = [c for c in (dni, telefono, nombre) if c]
    if len(criterios) != 1:
        raise HTTPException(422, "Indicar exactamente un criterio: dni, telefono o nombre")
    where, params = _where_contacto(dni, telefono, nombre)
    rows = (await db.execute(text(
        _SELECT_CONTACTO + where + " ORDER BY nombre_apellido LIMIT 20"
    ), params)).mappings().all()
    return [dict(r) for r in rows]


def _where_contacto(dni, telefono, nombre):
    base = " WHERE activo AND NOT convertido_a_buc AND "
    if dni:
        return base + "dni = :v", {"v": _solo_digitos(dni)}
    if telefono:
        return base + "regexp_replace(telefono, '\\D', '', 'g') = :v", {"v": _solo_digitos(telefono)}
    tokens = [t for t in (nombre or "").split() if t]
    conds, params = [], {}
    for i, t in enumerate(tokens):
        conds.append(f"nombre_apellido ILIKE :t{i}")
        params[f"t{i}"] = f"%{t}%"
    return base + "(" + " AND ".join(conds) + ")", params


@router.post("/contactos-eventuales", response_model=ContactoEventualOut, status_code=201)
async def crear_contacto_eventual(
    body: ContactoEventualCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    _require_operador(user)
    dni = _solo_digitos(body.dni)
    if len(dni) < 6:
        raise HTTPException(422, "DNI invalido (minimo 6 digitos)")
    dup = (await db.execute(text("""
        SELECT id_emergencia_contacto_eventual FROM emergencia_contacto_eventual
        WHERE dni = :dni AND activo AND NOT convertido_a_buc
    """), {"dni": dni})).scalar()
    if dup:
        raise HTTPException(409, f"Ya existe un contacto eventual activo con DNI {dni} (id {dup})")
    row = (await db.execute(text("""
        INSERT INTO emergencia_contacto_eventual
            (dni, nombre_apellido, telefono, direccion, contacto_alt_nombre,
             contacto_alt_telefono, observaciones, activo, id_municipio, id_usuario_alta)
        VALUES (:dni, :na, :tel, :dir, :can, :cat, :obs, TRUE, :mun, :ua)
        RETURNING id_emergencia_contacto_eventual
    """), {
        "dni": dni, "na": body.nombre_apellido.strip(),
        "tel": _solo_digitos(body.telefono), "dir": body.direccion.strip(),
        "can": body.contacto_alt_nombre,
        "cat": _solo_digitos(body.contacto_alt_telefono) or None,
        "obs": body.observaciones, "mun": body.id_municipio,
        "ua": user["id_usuario"],
    })).scalar()
    await db.commit()
    return await _contacto_out(db, row)


async def _contacto_out(db: AsyncSession, id_contacto: int) -> dict:
    row = (await db.execute(text(
        _SELECT_CONTACTO + " WHERE id_emergencia_contacto_eventual = :id"
    ), {"id": id_contacto})).mappings().first()
    if not row:
        raise HTTPException(404, "Contacto eventual no encontrado")
    return dict(row)


@router.get("/contactos-eventuales/{id_contacto}", response_model=ContactoEventualOut)
async def detalle_contacto_eventual(
    id_contacto: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    _require_operador(user)
    return await _contacto_out(db, id_contacto)


@router.patch("/contactos-eventuales/{id_contacto}", response_model=ContactoEventualOut)
async def editar_contacto_eventual(
    id_contacto: int,
    body: ContactoEventualUpdate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    _require_operador(user)
    actual = await _contacto_out(db, id_contacto)
    if actual["convertido_a_buc"]:
        raise HTTPException(422, "El contacto ya fue promovido a BUC; editar el ciudadano en Padrones")
    cambios = body.model_dump(exclude_unset=True)
    if not cambios:
        return actual
    if "telefono" in cambios and cambios["telefono"]:
        cambios["telefono"] = _solo_digitos(cambios["telefono"])
    if "contacto_alt_telefono" in cambios and cambios["contacto_alt_telefono"]:
        cambios["contacto_alt_telefono"] = _solo_digitos(cambios["contacto_alt_telefono"])
    sets = ", ".join(f"{k} = :{k}" for k in cambios)
    await db.execute(text(f"""
        UPDATE emergencia_contacto_eventual
        SET {sets}, fecha_modificacion = NOW(), id_usuario_modificacion = :um
        WHERE id_emergencia_contacto_eventual = :id
    """), {**cambios, "um": user["id_usuario"], "id": id_contacto})
    await db.commit()
    return await _contacto_out(db, id_contacto)


@router.post("/contactos-eventuales/{id_contacto}/promover-a-buc")
async def promover_contacto_a_buc(
    id_contacto: int,
    body: PromoverBucIn,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    _require_operador(user)
    contacto = await _contacto_out(db, id_contacto)
    if contacto["convertido_a_buc"]:
        raise HTTPException(409, "El contacto ya fue promovido a BUC")

    creado = False
    if body.id_ciudadano:
        id_ciudadano = (await db.execute(text(
            "SELECT id_ciudadano FROM ciudadanos WHERE id_ciudadano = :id AND activo"
        ), {"id": body.id_ciudadano})).scalar()
        if not id_ciudadano:
            raise HTTPException(422, "El ciudadano indicado no existe o esta inactivo")
    else:
        # si ya hay un ciudadano activo con ese DNI, se vincula automaticamente
        id_ciudadano = (await db.execute(text("""
            SELECT id_ciudadano FROM ciudadanos
            WHERE regexp_replace(doc_nro, '\\D', '', 'g') = :dni AND activo
            ORDER BY id_ciudadano LIMIT 1
        """), {"dni": contacto["dni"]})).scalar()
        if not id_ciudadano:
            if not (body.apellido and body.nombre and body.email):
                raise HTTPException(
                    422, "Para crear el ciudadano en BUC se requieren apellido, nombre y email")
            cuil = "20" + contacto["dni"].zfill(8) + "9"
            dup_cuil = (await db.execute(text(
                "SELECT id_ciudadano FROM ciudadanos WHERE cuil = :c"
            ), {"c": cuil})).scalar()
            if dup_cuil:
                raise HTTPException(409, "Colision de CUIL placeholder; vincular por id_ciudadano")
            id_ciudadano = (await db.execute(text("""
                INSERT INTO ciudadanos
                    (doc_tipo, doc_nro, cuil, apellido, nombre, sexo, fecha_nac,
                     id_nacionalidad, ren_chk, calle, telefono, email, email_chk,
                     emp_chk, activo, estado_validacion, ficha_completa, id_usuario_alta)
                VALUES ('DNI', :dni, :cuil, :ape, :nom, 'OTROS', CAST('1900-01-01' AS date),
                        1, FALSE, :calle, :tel, :email, FALSE,
                        FALSE, TRUE, 'verificado', FALSE, :ua)
                RETURNING id_ciudadano
            """), {
                "dni": contacto["dni"], "cuil": cuil,
                "ape": body.apellido.strip(), "nom": body.nombre.strip(),
                "calle": contacto["direccion"], "tel": contacto["telefono"],
                "email": body.email.strip(), "ua": user["id_usuario"],
            })).scalar()
            creado = True

    # reasignar eventos previos del contacto al ciudadano BUC
    eventos = (await db.execute(text("""
        UPDATE emergencia_evento
        SET id_ciudadano_buc = :c, id_contacto_eventual = NULL,
            fecha_modificacion = NOW(), id_usuario_modificacion = :um
        WHERE id_contacto_eventual = :ct
        RETURNING id_emergencia_evento
    """), {"c": id_ciudadano, "um": user["id_usuario"], "ct": id_contacto})).scalars().all()
    for id_ev in eventos:
        await _registrar_log(
            db, id_ev, user["id_usuario"], "PROMOCION_BUC",
            payload={"id_contacto_eventual": id_contacto, "id_ciudadano": id_ciudadano},
            observaciones="Contacto eventual promovido a ciudadano BUC")

    await db.execute(text("""
        UPDATE emergencia_contacto_eventual
        SET convertido_a_buc = TRUE, id_ciudadano_buc_destino = :c,
            fecha_modificacion = NOW(), id_usuario_modificacion = :um
        WHERE id_emergencia_contacto_eventual = :id
    """), {"c": id_ciudadano, "um": user["id_usuario"], "id": id_contacto})
    await db.commit()
    return {
        "id_ciudadano": id_ciudadano,
        "ciudadano_creado": creado,
        "eventos_reasignados": len(eventos),
    }


# =============================================================================
# FASE 3 — Busqueda unificada de denunciante (4.3)
# =============================================================================
@router.get("/denunciantes/buscar")
async def buscar_denunciante(
    dni: Optional[str] = Query(None),
    telefono: Optional[str] = Query(None),
    nombre: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    _require_operador(user)
    criterios = [("dni", dni), ("telefono", telefono), ("nombre", nombre)]
    activos = [(k, v) for k, v in criterios if v]
    if len(activos) != 1:
        raise HTTPException(422, "Indicar exactamente un criterio: dni, telefono o nombre")
    criterio, valor = activos[0]

    # 1) BUC
    if criterio == "dni":
        where, params = "regexp_replace(doc_nro, '\\D', '', 'g') = :v", {"v": _solo_digitos(valor)}
    elif criterio == "telefono":
        where, params = "regexp_replace(telefono, '\\D', '', 'g') = :v", {"v": _solo_digitos(valor)}
    else:
        tokens = [t for t in valor.split() if t]
        conds, params = [], {}
        for i, t in enumerate(tokens):
            conds.append(f"(apellido ILIKE :t{i} OR nombre ILIKE :t{i})")
            params[f"t{i}"] = f"%{t}%"
        where = " AND ".join(conds)
    buc = (await db.execute(text(f"""
        SELECT id_ciudadano, apellido, nombre, doc_nro, cuil, telefono, email,
               calle, altura, localidad
        FROM ciudadanos WHERE activo AND {where}
        ORDER BY apellido, nombre LIMIT 20
    """), params)).mappings().all()
    if buc:
        return {"origen": "BUC", "matches": [dict(r) for r in buc]}

    # 2) contactos eventuales
    where_ev, params_ev = _where_contacto(
        dni if criterio == "dni" else None,
        telefono if criterio == "telefono" else None,
        nombre if criterio == "nombre" else None,
    )
    ev = (await db.execute(text(
        _SELECT_CONTACTO + where_ev + " ORDER BY nombre_apellido LIMIT 20"
    ), params_ev)).mappings().all()
    if ev:
        return {"origen": "EVENTUAL", "matches": [dict(r) for r in ev]}

    # 3) no existe
    return {"origen": "NUEVO", "criterio": criterio, "valor": valor}


# =============================================================================
# FASE 3 — Eventos (4.4)
# =============================================================================
_SELECT_EVENTO = """
    SELECT e.id_emergencia_evento, e.numero_operativo, e.id_subarea,
           s.nombre AS subarea_nombre,
           e.id_tipo, t.codigo AS tipo_codigo, t.nombre AS tipo_nombre,
           e.id_subtipo, st.codigo AS subtipo_codigo, st.nombre AS subtipo_nombre,
           e.id_prioridad, p.codigo AS prioridad_codigo, p.color_token AS prioridad_color_token,
           p.sla_minutos_arribo,
           e.id_estado, est.codigo AS estado_codigo, est.nombre AS estado_nombre,
           est.es_terminal, est.es_terminal_positivo,
           e.id_canal_ingreso, can.codigo AS canal_codigo,
           e.id_organismo_derivacion, org.codigo AS organismo_codigo,
           org.nombre AS organismo_nombre,
           e.id_operador_receptor,
           e.denunciante_anonimo, e.id_ciudadano_buc, e.id_contacto_eventual,
           CASE
             WHEN e.denunciante_anonimo THEN 'Anonimo'
             WHEN e.id_ciudadano_buc IS NOT NULL THEN c.apellido || ', ' || c.nombre
             WHEN e.id_contacto_eventual IS NOT NULL THEN ce.nombre_apellido
           END AS denunciante_nombre,
           e.direccion_evento, e.latitud, e.longitud, e.referencia_ubicacion,
           e.audio_grabacion_url, e.observaciones_recepcion, e.observaciones_cierre,
           e.veracidad, e.fecha_hora_recepcion, e.fecha_hora_despacho,
           e.fecha_hora_arribo, e.fecha_hora_cierre, e.activo
    FROM emergencia_evento e
    JOIN subarea s ON s.id_subarea = e.id_subarea
    JOIN emergencia_tipo t ON t.id_emergencia_tipo = e.id_tipo
    LEFT JOIN emergencia_subtipo st ON st.id_emergencia_subtipo = e.id_subtipo
    JOIN emergencia_prioridad p ON p.id_emergencia_prioridad = e.id_prioridad
    JOIN emergencia_estado est ON est.id_emergencia_estado = e.id_estado
    JOIN emergencia_canal_ingreso can ON can.id_emergencia_canal_ingreso = e.id_canal_ingreso
    LEFT JOIN emergencia_organismo_derivacion org
         ON org.id_emergencia_organismo_derivacion = e.id_organismo_derivacion
    LEFT JOIN ciudadanos c ON c.id_ciudadano = e.id_ciudadano_buc
    LEFT JOIN emergencia_contacto_eventual ce
         ON ce.id_emergencia_contacto_eventual = e.id_contacto_eventual
"""


async def _evento_out(db: AsyncSession, id_evento: int) -> dict:
    row = (await db.execute(text(
        _SELECT_EVENTO + " WHERE e.id_emergencia_evento = :id"
    ), {"id": id_evento})).mappings().first()
    if not row:
        raise HTTPException(404, "Evento no encontrado")
    return dict(row)


@router.post("/eventos", status_code=201)
async def crear_evento(
    body: EventoCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    _require_operador(user)

    tipo = (await db.execute(text("""
        SELECT id_emergencia_tipo, id_subarea, id_prioridad_default,
               id_organismo_derivacion_default
        FROM emergencia_tipo WHERE id_emergencia_tipo = :id AND activo
    """), {"id": body.id_tipo})).mappings().first()
    if not tipo:
        raise HTTPException(422, "Tipo de emergencia inexistente o inactivo")
    if tipo["id_subarea"] != body.id_subarea:
        raise HTTPException(422, "El tipo no pertenece a la subarea indicada")

    id_prioridad = body.id_prioridad
    if body.id_subtipo is not None:
        subtipo = (await db.execute(text("""
            SELECT id_emergencia_subtipo, id_prioridad_override
            FROM emergencia_subtipo
            WHERE id_emergencia_subtipo = :id AND id_tipo = :t AND activo
        """), {"id": body.id_subtipo, "t": body.id_tipo})).mappings().first()
        if not subtipo:
            raise HTTPException(422, "El subtipo no pertenece al tipo indicado o esta inactivo")
        if id_prioridad is None:
            id_prioridad = subtipo["id_prioridad_override"]
    if id_prioridad is None:
        id_prioridad = tipo["id_prioridad_default"]

    canal_ok = (await db.execute(text("""
        SELECT 1 FROM emergencia_canal_ingreso
        WHERE id_emergencia_canal_ingreso = :id AND activo
    """), {"id": body.id_canal_ingreso})).scalar()
    if not canal_ok:
        raise HTTPException(422, "Canal de ingreso inexistente o inactivo")

    # denunciante: anonimo XOR (ciudadano BUC XOR contacto eventual)
    if body.denunciante_anonimo:
        if body.id_ciudadano_buc or body.id_contacto_eventual:
            raise HTTPException(422, "Denunciante anonimo no admite ciudadano ni contacto")
    else:
        if bool(body.id_ciudadano_buc) == bool(body.id_contacto_eventual):
            raise HTTPException(
                422, "Indicar exactamente uno: id_ciudadano_buc o id_contacto_eventual")
        if body.id_ciudadano_buc:
            ok = (await db.execute(text(
                "SELECT 1 FROM ciudadanos WHERE id_ciudadano = :id AND activo"
            ), {"id": body.id_ciudadano_buc})).scalar()
            if not ok:
                raise HTTPException(422, "Ciudadano BUC inexistente o inactivo")
        else:
            ok = (await db.execute(text("""
                SELECT 1 FROM emergencia_contacto_eventual
                WHERE id_emergencia_contacto_eventual = :id AND activo AND NOT convertido_a_buc
            """), {"id": body.id_contacto_eventual})).scalar()
            if not ok:
                raise HTTPException(422, "Contacto eventual inexistente, inactivo o ya promovido")

    estado = await _estado_por_codigo(db, "PENDIENTE")
    id_evento = (await db.execute(text("""
        INSERT INTO emergencia_evento
            (id_subarea, id_tipo, id_subtipo, id_prioridad, id_estado,
             id_canal_ingreso, id_organismo_derivacion, id_operador_receptor,
             denunciante_anonimo, id_ciudadano_buc, id_contacto_eventual,
             direccion_evento, latitud, longitud, referencia_ubicacion,
             audio_grabacion_url, observaciones_recepcion,
             activo, id_municipio, id_usuario_alta)
        VALUES (:sub, :tipo, :stipo, :prio, :est, :canal, :org, :oper,
                :anon, :ciu, :cont, :dir, :lat, :lon, :ref, :audio, :obs,
                TRUE, :mun, :ua)
        RETURNING id_emergencia_evento
    """), {
        "sub": body.id_subarea, "tipo": body.id_tipo, "stipo": body.id_subtipo,
        "prio": id_prioridad, "est": estado["id_emergencia_estado"],
        "canal": body.id_canal_ingreso,
        "org": tipo["id_organismo_derivacion_default"],
        "oper": user["id_usuario"], "anon": body.denunciante_anonimo,
        "ciu": body.id_ciudadano_buc, "cont": body.id_contacto_eventual,
        "dir": body.direccion_evento.strip(), "lat": body.latitud,
        "lon": body.longitud, "ref": body.referencia_ubicacion,
        "audio": body.audio_grabacion_url, "obs": body.observaciones_recepcion,
        "mun": body.id_municipio, "ua": user["id_usuario"],
    })).scalar()

    await _registrar_log(
        db, id_evento, user["id_usuario"], "CREACION",
        estado_nuevo="PENDIENTE",
        payload={"id_canal_ingreso": body.id_canal_ingreso},
        observaciones=body.observaciones_recepcion,
        id_municipio=body.id_municipio)
    await db.commit()
    return await _evento_out(db, id_evento)


@router.get("/eventos/abiertos")
async def listar_eventos_abiertos(
    id_subarea: Optional[int] = Query(None),
    id_prioridad: Optional[int] = Query(None),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    _require_operador(user)
    scope = await _filtro_scope_subarea(db, user)
    rows = (await db.execute(text(_SELECT_EVENTO + """
        WHERE e.activo AND NOT est.es_terminal
          AND (CAST(:sub AS integer) IS NULL OR e.id_subarea = :sub)
          AND (CAST(:prio AS integer) IS NULL OR e.id_prioridad = :prio)
          AND (CAST(:scope AS integer) IS NULL OR e.id_subarea = :scope)
        ORDER BY p.orden_visual ASC, e.fecha_hora_recepcion DESC
    """), {"sub": id_subarea, "prio": id_prioridad, "scope": scope})).mappings().all()
    return [dict(r) for r in rows]


@router.get("/eventos")
async def listar_eventos(
    response: Response,
    estado: Optional[str] = Query(None, description="codigo de estado"),
    id_subarea: Optional[int] = Query(None),
    id_prioridad: Optional[int] = Query(None),
    q: Optional[str] = Query(None, description="numero operativo o direccion"),
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    _require_operador(user)
    scope = await _filtro_scope_subarea(db, user)
    where = """
        WHERE e.activo
          AND (CAST(:estado AS text) IS NULL OR est.codigo = :estado)
          AND (CAST(:sub AS integer) IS NULL OR e.id_subarea = :sub)
          AND (CAST(:prio AS integer) IS NULL OR e.id_prioridad = :prio)
          AND (CAST(:q AS text) IS NULL
               OR e.numero_operativo ILIKE '%' || :q || '%'
               OR e.direccion_evento ILIKE '%' || :q || '%')
          AND (CAST(:fd AS date) IS NULL OR e.fecha_hora_recepcion >= CAST(:fd AS date))
          AND (CAST(:fh AS date) IS NULL
               OR e.fecha_hora_recepcion < CAST(:fh AS date) + INTERVAL '1 day')
          AND (CAST(:scope AS integer) IS NULL OR e.id_subarea = :scope)
    """
    params = {"estado": estado, "sub": id_subarea, "prio": id_prioridad,
              "q": q, "fd": fecha_desde, "fh": fecha_hasta, "scope": scope}
    total = (await db.execute(text(f"""
        SELECT count(*) FROM emergencia_evento e
        JOIN emergencia_estado est ON est.id_emergencia_estado = e.id_estado
        {where}
    """), params)).scalar()
    rows = (await db.execute(text(
        _SELECT_EVENTO + where +
        " ORDER BY e.fecha_hora_recepcion DESC LIMIT :limit OFFSET :offset"
    ), {**params, "limit": limit, "offset": offset})).mappings().all()
    response.headers["X-Total-Count"] = str(total)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return [dict(r) for r in rows]


@router.get("/eventos/{id_evento}")
async def detalle_evento(
    id_evento: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    _require_operador(user)
    out = await _evento_out(db, id_evento)
    await _check_scope_subarea(db, user, out["id_subarea"])
    # datos completos del denunciante para el tab correspondiente
    if out["id_ciudadano_buc"]:
        ciu = (await db.execute(text("""
            SELECT id_ciudadano, apellido, nombre, doc_nro, cuil, telefono, email,
                   calle, altura, localidad
            FROM ciudadanos WHERE id_ciudadano = :id
        """), {"id": out["id_ciudadano_buc"]})).mappings().first()
        out["denunciante"] = dict(ciu) if ciu else None
    elif out["id_contacto_eventual"]:
        out["denunciante"] = await _contacto_out(db, out["id_contacto_eventual"])
    else:
        out["denunciante"] = None
    return out


@router.patch("/eventos/{id_evento}")
async def editar_evento(
    id_evento: int,
    body: EventoUpdate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    _require_operador(user)
    ev = await _evento_for_update(db, id_evento)
    await _check_scope_subarea(db, user, ev["id_subarea"])
    if ev["es_terminal"]:
        raise HTTPException(422, "El evento esta en estado terminal; no admite edicion")

    cambios = body.model_dump(exclude_unset=True)
    if not cambios:
        return await _evento_out(db, id_evento)

    # cambio de tipo: debe pertenecer a la misma subarea del evento
    if "id_tipo" in cambios and cambios["id_tipo"] != ev["id_tipo"]:
        tipo = (await db.execute(text("""
            SELECT id_subarea FROM emergencia_tipo
            WHERE id_emergencia_tipo = :id AND activo
        """), {"id": cambios["id_tipo"]})).mappings().first()
        if not tipo:
            raise HTTPException(422, "Tipo de emergencia inexistente o inactivo")
        if tipo["id_subarea"] != ev["id_subarea"]:
            raise HTTPException(422, "El tipo nuevo pertenece a otra subarea")
        if "id_subtipo" not in cambios:
            cambios["id_subtipo"] = None   # el subtipo viejo ya no aplica
    if cambios.get("id_subtipo") is not None:
        id_tipo_final = cambios.get("id_tipo", ev["id_tipo"])
        ok = (await db.execute(text("""
            SELECT 1 FROM emergencia_subtipo
            WHERE id_emergencia_subtipo = :id AND id_tipo = :t AND activo
        """), {"id": cambios["id_subtipo"], "t": id_tipo_final})).scalar()
        if not ok:
            raise HTTPException(422, "El subtipo no pertenece al tipo del evento")
    if "id_prioridad" in cambios:
        ok = (await db.execute(text("""
            SELECT 1 FROM emergencia_prioridad
            WHERE id_emergencia_prioridad = :id AND activo
        """), {"id": cambios["id_prioridad"]})).scalar()
        if not ok:
            raise HTTPException(422, "Prioridad inexistente o inactiva")

    sets = ", ".join(f"{k} = :{k}" for k in cambios)
    await db.execute(text(f"""
        UPDATE emergencia_evento
        SET {sets}, fecha_modificacion = NOW(), id_usuario_modificacion = :um
        WHERE id_emergencia_evento = :id
    """), {**cambios, "um": user["id_usuario"], "id": id_evento})

    estado_actual = ev["estado_codigo"]
    if "id_tipo" in cambios and cambios["id_tipo"] != ev["id_tipo"]:
        await _registrar_log(db, id_evento, user["id_usuario"], "CAMBIO_TIPO",
                             estado_anterior=estado_actual, estado_nuevo=estado_actual,
                             payload={"de": ev["id_tipo"], "a": cambios["id_tipo"]})
    if "id_subtipo" in cambios and cambios["id_subtipo"] != ev["id_subtipo"]:
        await _registrar_log(db, id_evento, user["id_usuario"], "CAMBIO_SUBTIPO",
                             estado_anterior=estado_actual, estado_nuevo=estado_actual,
                             payload={"de": ev["id_subtipo"], "a": cambios["id_subtipo"]})
    if "id_prioridad" in cambios and cambios["id_prioridad"] != ev["id_prioridad"]:
        await _registrar_log(db, id_evento, user["id_usuario"], "CAMBIO_PRIORIDAD",
                             estado_anterior=estado_actual, estado_nuevo=estado_actual,
                             payload={"de": ev["id_prioridad"], "a": cambios["id_prioridad"]})
    otros = [k for k in cambios
             if k not in ("id_tipo", "id_subtipo", "id_prioridad")]
    if otros:
        await _registrar_log(db, id_evento, user["id_usuario"], "NOTA",
                             estado_anterior=estado_actual, estado_nuevo=estado_actual,
                             payload={"campos_modificados": otros},
                             observaciones="Edicion de datos del evento")
    await db.commit()
    return await _evento_out(db, id_evento)


async def _aplicar_cambio_estado(
    db: AsyncSession,
    ev: dict,
    user: dict,
    codigo_destino: str,
    observaciones: Optional[str],
    tipo_accion: str = "CAMBIO_ESTADO",
    extra_sets: str = "",
    extra_params: Optional[dict] = None,
    payload: Optional[dict] = None,
) -> None:
    actual = ev["estado_codigo"]
    if codigo_destino not in TRANSICIONES.get(actual, set()):
        alcanzables = sorted(TRANSICIONES.get(actual, set()))
        raise HTTPException(
            422, f"Transicion invalida {actual} -> {codigo_destino}. "
                 f"Alcanzables: {', '.join(alcanzables) or 'ninguno (estado terminal)'}")
    destino = await _estado_por_codigo(db, codigo_destino)

    sets = ["id_estado = :nuevo_estado",
            "fecha_modificacion = NOW()", "id_usuario_modificacion = :um"]
    params = {"nuevo_estado": destino["id_emergencia_estado"],
              "um": user["id_usuario"], "id": ev["id_emergencia_evento"]}
    if codigo_destino == "EN_CAMINO":
        sets.append("fecha_hora_despacho = COALESCE(fecha_hora_despacho, NOW())")
    if codigo_destino == "EN_SITIO":
        sets.append("fecha_hora_arribo = COALESCE(fecha_hora_arribo, NOW())")
    if destino["es_terminal"]:
        sets.append("fecha_hora_cierre = COALESCE(fecha_hora_cierre, NOW())")
    if extra_sets:
        sets.append(extra_sets)
        params.update(extra_params or {})

    await db.execute(text(f"""
        UPDATE emergencia_evento SET {', '.join(sets)}
        WHERE id_emergencia_evento = :id
    """), params)
    await _registrar_log(
        db, ev["id_emergencia_evento"], user["id_usuario"], tipo_accion,
        estado_anterior=actual, estado_nuevo=codigo_destino,
        payload=payload, observaciones=observaciones,
        id_municipio=ev.get("id_municipio"))


@router.post("/eventos/{id_evento}/cambiar-estado")
async def cambiar_estado_evento(
    id_evento: int,
    body: CambiarEstadoIn,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    _require_operador(user)
    destino = body.nuevo_estado.strip().upper()
    if destino in ("RESUELTO", "DESESTIMADO"):
        raise HTTPException(422, "Los cierres van por POST /eventos/{id}/cerrar (exigen veracidad)")
    if destino == "DERIVADO":
        raise HTTPException(422, "La derivacion va por POST /eventos/{id}/derivar (exige organismo)")
    ev = await _evento_for_update(db, id_evento)
    await _check_scope_subarea(db, user, ev["id_subarea"])
    await _aplicar_cambio_estado(db, ev, user, destino, body.observaciones)
    await db.commit()
    return await _evento_out(db, id_evento)


@router.post("/eventos/{id_evento}/derivar")
async def derivar_evento(
    id_evento: int,
    body: DerivarIn,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    _require_operador(user)
    org = (await db.execute(text("""
        SELECT id_emergencia_organismo_derivacion, codigo, nombre
        FROM emergencia_organismo_derivacion
        WHERE id_emergencia_organismo_derivacion = :id AND activo
    """), {"id": body.id_organismo})).mappings().first()
    if not org:
        raise HTTPException(422, "Organismo de derivacion inexistente o inactivo")
    ev = await _evento_for_update(db, id_evento)
    await _check_scope_subarea(db, user, ev["id_subarea"])
    await _aplicar_cambio_estado(
        db, ev, user, "DERIVADO", body.observaciones,
        tipo_accion="DERIVACION",
        extra_sets="id_organismo_derivacion = :org",
        extra_params={"org": body.id_organismo},
        payload={"id_organismo": body.id_organismo, "organismo": org["codigo"]})
    await db.commit()
    return await _evento_out(db, id_evento)


@router.post("/eventos/{id_evento}/cerrar")
async def cerrar_evento(
    id_evento: int,
    body: CerrarIn,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    _require_operador(user)
    ev = await _evento_for_update(db, id_evento)
    await _check_scope_subarea(db, user, ev["id_subarea"])
    destino = "RESUELTO" if body.terminal_positivo else "DESESTIMADO"
    await _aplicar_cambio_estado(
        db, ev, user, destino, body.observaciones_cierre,
        tipo_accion="CIERRE",
        extra_sets="veracidad = :ver, observaciones_cierre = :oc",
        extra_params={"ver": body.veracidad, "oc": body.observaciones_cierre},
        payload={"veracidad": body.veracidad, "terminal_positivo": body.terminal_positivo})
    await db.commit()
    return await _evento_out(db, id_evento)


@router.post("/eventos/{id_evento}/marcar-en-sitio")
async def marcar_en_sitio(
    id_evento: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    _require_operador(user)
    ev = await _evento_for_update(db, id_evento)
    await _check_scope_subarea(db, user, ev["id_subarea"])
    await _aplicar_cambio_estado(db, ev, user, "EN_SITIO", None)
    await db.commit()
    return await _evento_out(db, id_evento)


@router.post("/eventos/{id_evento}/agregar-nota", status_code=201)
async def agregar_nota_evento(
    id_evento: int,
    body: NotaIn,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    _require_operador(user)
    ev = await _evento_for_update(db, id_evento)
    await _check_scope_subarea(db, user, ev["id_subarea"])
    await _registrar_log(
        db, id_evento, user["id_usuario"], "NOTA",
        estado_anterior=ev["estado_codigo"], estado_nuevo=ev["estado_codigo"],
        observaciones=body.observaciones)
    await db.commit()
    return {"ok": True}


@router.get("/eventos/{id_evento}/log")
async def log_evento(
    id_evento: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    _require_operador(user)
    ev = await _evento_out(db, id_evento)
    await _check_scope_subarea(db, user, ev["id_subarea"])
    rows = (await db.execute(text("""
        SELECT l.id_emergencia_log, l.id_evento, l.id_usuario,
               u.nombre AS usuario_nombre,
               l.fecha_hora, l.tipo_accion, l.estado_anterior, l.estado_nuevo,
               l.payload_json, l.observaciones
        FROM emergencia_log l
        LEFT JOIN usuarios u ON u.id_usuario = l.id_usuario
        WHERE l.id_evento = :id
        ORDER BY l.fecha_hora ASC, l.id_emergencia_log ASC
    """), {"id": id_evento})).mappings().all()
    return [dict(r) for r in rows]
