"""
Router publico del modulo Turnos — endpoints sin JWT para autoservicio
(replanteado en mig 71).

El ciudadano elige una PRESTACION (que ya define el recurso fijo: un agente o
un lugar de atencion) y un slot libre. El backend calcula los slots cruzando la
disponibilidad efectiva del recurso de la prestacion con sus ocupaciones.

Flujo del ciudadano:
  1. GET    /api/v1/turnos/publico/prestaciones          -> elige la prestacion
  2. GET    /api/v1/turnos/publico/slots?id_tipo_prestacion= -> elige dia y hora
  3. POST   /api/v1/turnos/publico/reservar              -> crea el turno
  4. GET    /api/v1/turnos/publico/turno/{token}         -> consulta despues
  5. DELETE /api/v1/turnos/publico/turno/{token}         -> cancela

Validaciones del POST /reservar:
  - prestacion activa con recurso valido
  - el slot pedido cae dentro de la disponibilidad efectiva del recurso ese dia
  - el slot no se solapa con ninguna ocupacion existente del recurso
  - el ciudadano (por DNI) no tiene otro turno no-cancelado el mismo dia
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, time, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.utils.request_helpers import get_real_ip
from app.middleware.rate_limit import check_rate_limit
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.turnos import (
    PantallaColeroOut,
    PrestacionPublicaOut,
    SlotLibreOut,
    TurnoPublicoCreate,
    TurnoPublicoOut,
)
from app.services.agenda import (
    advisory_lock_tx,
    buscar_o_crear_ciudadano_por_dni,
    disponibilidad_efectiva,
    turnos_respeta_disponibilidad,
)
from app.utils.fechas import ahora_local, hoy_local


router = APIRouter(prefix="/api/v1/turnos/publico", tags=["turnos-publico"])
logger = logging.getLogger("zaris.turnos_publico")

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)

DIAS_VENTANA_DEFAULT = 14
DIAS_VENTANA_MAX = 30


def _validate_uuid(token: str) -> None:
    if not UUID_RE.match(token):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Turno no encontrado")


def _slots_de_rango(
    rango_ini: time, rango_fin: time, duracion_min: int,
) -> list[tuple[time, time]]:
    """Parte un rango horario en slots consecutivos de `duracion_min`.
    Descarta el ultimo slot si no entra completo."""
    out: list[tuple[time, time]] = []
    cursor = datetime.combine(date.min, rango_ini)
    fin = datetime.combine(date.min, rango_fin)
    paso = timedelta(minutes=duracion_min)
    while cursor + paso <= fin:
        out.append((cursor.time(), (cursor + paso).time()))
        cursor += paso
    return out


def _solapa(a_ini: time, a_fin: time, b_ini: time, b_fin: time) -> bool:
    return a_ini < b_fin and a_fin > b_ini


async def _resolver_prestacion(
    db: AsyncSession, id_tipo_prestacion: int,
) -> dict[str, Any]:
    """Devuelve la prestacion activa con su recurso resuelto, o 404."""
    prest = (await db.execute(text("""
        SELECT tp.id_tipo_prestacion, tp.tipo_recurso, tp.id_agente, tp.id_espacio,
               tp.duracion_min, tp.id_espacio_ubicacion,
               CASE WHEN tp.tipo_recurso = 'espacio' THEN e.nombre
                    ELSE COALESCE(a.apellido, '') || ', ' || COALESCE(a.nombre, '') END AS recurso_nombre,
               tp.id_subarea
        FROM tipo_prestacion tp
        LEFT JOIN agentes         a ON a.id_agente  = tp.id_agente
        LEFT JOIN espacios_agenda e ON e.id_espacio = tp.id_espacio
        WHERE tp.id_tipo_prestacion = :id AND tp.activo = TRUE
    """), {"id": id_tipo_prestacion})).mappings().first()
    if not prest:
        raise HTTPException(404, "Prestacion no encontrada o inactiva")
    tr = prest["tipo_recurso"]
    id_recurso = prest["id_agente"] if tr == "agente" else prest["id_espacio"]
    if id_recurso is None:
        raise HTTPException(422, "La prestacion no tiene un recurso valido asignado")
    # Ubicacion de atencion (mig 103): la de la prestacion o, si el recurso es
    # un espacio, ese mismo espacio. Se copia al turno en TODAS las vias.
    id_ubicacion = prest["id_espacio_ubicacion"]
    if id_ubicacion is None and tr == "espacio":
        id_ubicacion = int(id_recurso)
    return {
        "tipo_recurso": tr,
        "id_recurso": int(id_recurso),
        "recurso_nombre": prest["recurso_nombre"],
        "duracion_min": int(prest["duracion_min"]),
        "id_subarea": prest["id_subarea"],
        "id_espacio_ubicacion": id_ubicacion,
    }


# =============================================================================
# 1. Prestaciones publicables
# =============================================================================
@router.get("/prestaciones", response_model=list[PrestacionPublicaOut])
async def listar_prestaciones_publico(
    id_municipio: int = 1,
    db: AsyncSession = Depends(get_db),
):
    """Prestaciones activas cuyo recurso tiene disponibilidad cargada. Una
    prestacion sin disponibilidad no genera slots, asi que no se ofrece."""
    rows = (await db.execute(text("""
        SELECT tp.id_tipo_prestacion, tp.nombre, tp.descripcion, tp.clase, tp.duracion_min,
               CASE WHEN tp.tipo_recurso = 'espacio' THEN e.nombre
                    ELSE COALESCE(a.apellido, '') || ', ' || COALESCE(a.nombre, '') END AS recurso_nombre
        FROM tipo_prestacion tp
        LEFT JOIN agentes         a ON a.id_agente  = tp.id_agente
        LEFT JOIN espacios_agenda e ON e.id_espacio = tp.id_espacio
        WHERE tp.activo = TRUE AND tp.id_municipio = :m
          AND (
            -- recurso agente con disponibilidad propia
            (tp.tipo_recurso = 'agente' AND EXISTS (
              SELECT 1 FROM disponibilidad_recurso d
              WHERE d.tipo_recurso = 'agente' AND d.id_recurso = tp.id_agente AND d.activo = TRUE
            ))
            OR
            -- recurso espacio: desatendido con disponibilidad propia, o atendido
            -- con al menos un agente vinculado con disponibilidad.
            (tp.tipo_recurso = 'espacio' AND (
              EXISTS (
                SELECT 1 FROM disponibilidad_recurso d
                WHERE d.tipo_recurso = 'espacio' AND d.id_recurso = tp.id_espacio AND d.activo = TRUE
              )
              OR EXISTS (
                SELECT 1 FROM espacio_agentes ea
                JOIN disponibilidad_recurso d
                  ON d.tipo_recurso = 'agente' AND d.id_recurso = ea.id_agente AND d.activo = TRUE
                WHERE ea.id_espacio = tp.id_espacio AND ea.activo = TRUE
              )
            ))
          )
        ORDER BY tp.nombre
    """), {"m": id_municipio})).mappings().all()
    return [dict(r) for r in rows]


# =============================================================================
# 2. Slots libres de la prestacion
# =============================================================================
async def _slots_libres_recurso(
    db: AsyncSession,
    tipo_recurso: str,
    id_recurso: int,
    recurso_nombre: str,
    duracion_min: int,
    fecha: date,
) -> list[dict[str, Any]]:
    """Slots libres de un recurso para una fecha: parte su disponibilidad
    efectiva en bloques de `duracion_min` y descarta los que se solapan con una
    ocupacion existente del mismo recurso. Para HOY descarta ademas los slots
    cuyo inicio ya paso (hora local del municipio, no UTC del server)."""
    ahora = ahora_local()
    if fecha < ahora.date():
        return []
    hora_corte = ahora.time() if fecha == ahora.date() else None

    rangos = await disponibilidad_efectiva(db, tipo_recurso, id_recurso, fecha)
    if not rangos:
        return []

    ocup = (await db.execute(text("""
        SELECT hora_inicio, hora_fin
        FROM ocupaciones
        WHERE activo = TRUE AND tipo_recurso = :tr AND id_recurso = :ir AND fecha = :f
    """), {"tr": tipo_recurso, "ir": id_recurso, "f": fecha})).mappings().all()
    ocupadas = [(o["hora_inicio"], o["hora_fin"]) for o in ocup]

    out: list[dict[str, Any]] = []
    for r in rangos:
        for (s_ini, s_fin) in _slots_de_rango(r["hora_inicio"], r["hora_fin"], duracion_min):
            if hora_corte is not None and s_ini <= hora_corte:
                continue
            if any(_solapa(s_ini, s_fin, o_ini, o_fin) for (o_ini, o_fin) in ocupadas):
                continue
            out.append({
                "tipo_recurso": tipo_recurso,
                "id_recurso": id_recurso,
                "recurso_nombre": recurso_nombre,
                "fecha": fecha,
                "hora_inicio": s_ini,
                "hora_fin": s_fin,
            })
    return out


@router.get("/slots", response_model=list[SlotLibreOut])
async def listar_slots_publico(
    id_tipo_prestacion: int = Query(..., description="Prestacion: define recurso + duracion"),
    fecha_desde: Optional[date] = Query(None, description="Default: hoy"),
    dias: int = Query(DIAS_VENTANA_DEFAULT, ge=1, le=DIAS_VENTANA_MAX),
    db: AsyncSession = Depends(get_db),
):
    """Slots libres del recurso de la prestacion en una ventana de `dias`."""
    prest = await _resolver_prestacion(db, id_tipo_prestacion)
    desde = fecha_desde or date.today()
    out: list[dict[str, Any]] = []
    for offset in range(dias):
        f = desde + timedelta(days=offset)
        out.extend(await _slots_libres_recurso(
            db, prest["tipo_recurso"], prest["id_recurso"],
            prest["recurso_nombre"] or "", prest["duracion_min"], f,
        ))
    return out


# =============================================================================
# 3. Reservar turno
# =============================================================================
async def _turno_publico_out(db: AsyncSession, id_turno: int) -> Optional[dict[str, Any]]:
    row = (await db.execute(text("""
        SELECT t.id_turno, CAST(t.token_turno AS TEXT) AS token_turno,
               t.estado, t.fecha, t.hora_inicio, t.hora_fin,
               tp.nombre AS prestacion_nombre,
               CASE WHEN t.id_espacio IS NOT NULL THEN e.nombre
                    ELSE COALESCE(a.apellido, '') || ', ' || COALESCE(a.nombre, '') END AS recurso_nombre,
               c.apellido AS ciudadano_apellido,
               c.nombre   AS ciudadano_nombre,
               c.doc_nro  AS ciudadano_dni
        FROM turnos t
        LEFT JOIN tipo_prestacion tp ON tp.id_tipo_prestacion = t.id_tipo_prestacion
        LEFT JOIN agentes         a  ON a.id_agente            = t.id_agente
        LEFT JOIN espacios_agenda e  ON e.id_espacio           = t.id_espacio
        LEFT JOIN ciudadanos      c  ON c.id_ciudadano         = t.id_ciudadano
        WHERE t.id_turno = :id
    """), {"id": id_turno})).mappings().first()
    return dict(row) if row else None


@router.post(
    "/reservar",
    response_model=TurnoPublicoOut,
    status_code=201,
    responses={409: {"description": "Slot ocupado, fuera de disponibilidad o turno duplicado (anti-carrera mig 95)"}},
)
async def reservar_turno_publico(
    payload: TurnoPublicoCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Crea un turno por autoservicio. El recurso lo trae la prestacion.
    Busca/crea el ciudadano por DNI."""
    # Rate limit anónimo: evita que un script cree turnos/ciudadanos en masa.
    # Clave prefijada por flujo (§5) para no compartir bucket con otros endpoints.
    check_rate_limit(f"turnopub:{get_real_ip(request)}", max_requests=10, window_seconds=60)
    prest = await _resolver_prestacion(db, payload.id_tipo_prestacion)
    tipo_recurso = prest["tipo_recurso"]
    id_recurso = prest["id_recurso"]
    duracion_min = prest["duracion_min"]
    id_subarea = prest["id_subarea"]

    ahora = ahora_local()
    if payload.fecha < ahora.date() or (
        payload.fecha == ahora.date() and payload.hora_inicio <= ahora.time()
    ):
        raise HTTPException(422, "No se puede reservar un turno en el pasado")

    hora_inicio = payload.hora_inicio
    hora_fin = (datetime.combine(payload.fecha, hora_inicio)
                + timedelta(minutes=duracion_min)).time()
    if hora_fin <= hora_inicio:
        raise HTTPException(422, "La duracion de la prestacion excede el dia")

    # Anti-carrera (mig 95): serializa las reservas concurrentes del mismo
    # recurso+dia ANTES de los checks. Orden de locks fijo en todas las vias:
    # recurso -> dni (dentro del helper) -> ciudadano-dia.
    await advisory_lock_tx(db, f"turno:{tipo_recurso}:{id_recurso}:{payload.fecha}")

    if await turnos_respeta_disponibilidad(db):
        rangos = await disponibilidad_efectiva(db, tipo_recurso, id_recurso, payload.fecha)
        dentro = any(
            r["hora_inicio"] <= hora_inicio and hora_fin <= r["hora_fin"]
            for r in rangos
        )
        if not dentro:
            raise HTTPException(409, "El horario solicitado no esta dentro de la disponibilidad del recurso")

    solapado = await db.scalar(text("""
        SELECT 1 FROM ocupaciones
        WHERE activo = TRUE AND tipo_recurso = :tr AND id_recurso = :ir AND fecha = :f
          AND hora_inicio < :hf AND hora_fin > :hi
        LIMIT 1
    """), {"tr": tipo_recurso, "ir": id_recurso, "f": payload.fecha, "hi": hora_inicio, "hf": hora_fin})
    if solapado:
        raise HTTPException(409, "El horario solicitado ya no esta disponible")

    try:
        ciu = await buscar_o_crear_ciudadano_por_dni(
            db,
            dni=payload.dni,
            apellido=payload.apellido,
            nombre=payload.nombre,
            telefono=payload.telefono,
            email=payload.email,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    # Anti-carrera de la regla "1 turno por dia": mismo ciudadano reservando en
    # paralelo contra DOS recursos distintos el mismo dia (el lock de recurso no
    # lo cubre). Mismo orden de adquisicion en publico_turnos_vecino.py.
    await advisory_lock_tx(db, f"turnodia:{int(ciu['id_ciudadano'])}:{payload.fecha}")

    dup = await db.scalar(text("""
        SELECT 1 FROM turnos
        WHERE id_ciudadano = :ic AND fecha = :f AND activo = TRUE AND estado <> 'cancelado'
        LIMIT 1
    """), {"ic": int(ciu["id_ciudadano"]), "f": payload.fecha})
    if dup:
        raise HTTPException(409, "El ciudadano ya tiene un turno reservado para ese dia")

    id_agente_turno = id_recurso if tipo_recurso == "agente" else None
    id_espacio_turno = id_recurso if tipo_recurso == "espacio" else None

    # UNIQUE parcial de slot (mig 95): red de contencion si otra via inserta
    # el mismo slot pese al lock -> 409 en lugar de doble reserva.
    try:
        id_ocupacion = await db.scalar(text("""
            INSERT INTO ocupaciones (
                tipo, tipo_recurso, id_recurso, fecha, hora_inicio, hora_fin,
                id_ciudadano, motivo, id_municipio, id_usuario_alta
            ) VALUES (
                'turno', :tr, :ir, :f, :hi, :hf, :ic, :mot, 1, NULL
            )
            RETURNING id_ocupacion
        """), {
            "tr": tipo_recurso, "ir": id_recurso, "f": payload.fecha,
            "hi": hora_inicio, "hf": hora_fin, "ic": int(ciu["id_ciudadano"]),
            "mot": f"Turno (autoservicio): {payload.observaciones}" if payload.observaciones else "Turno (autoservicio)",
        })

        row = (await db.execute(text("""
            INSERT INTO turnos (
                id_ciudadano, id_agente, id_espacio, id_espacio_ubicacion,
                id_tipo_prestacion, id_ocupacion,
                fecha, hora_inicio, hora_fin, estado, observaciones,
                origen, id_municipio, id_subarea
            ) VALUES (
                :ic, :ia, :ie, :iu, :itp, :iocup,
                :f, :hi, :hf, 'reservado', :obs,
                'autoservicio', 1, :isa
            )
            RETURNING id_turno, CAST(token_turno AS TEXT) AS token_turno
        """), {
            "ic": int(ciu["id_ciudadano"]), "ia": id_agente_turno, "ie": id_espacio_turno,
            "iu": prest["id_espacio_ubicacion"],
            "itp": payload.id_tipo_prestacion, "iocup": id_ocupacion,
            "f": payload.fecha, "hi": hora_inicio, "hf": hora_fin,
            "obs": payload.observaciones, "isa": id_subarea,
        })).mappings().first()
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "El horario solicitado ya no esta disponible")

    out = await _turno_publico_out(db, int(row["id_turno"]))
    if out is None:
        raise HTTPException(500, "Turno creado pero no se pudo releer")
    return out


# =============================================================================
# 4 + 5. Consultar / cancelar por token
# =============================================================================
async def _turno_por_token(db: AsyncSession, token: str) -> Optional[dict[str, Any]]:
    _validate_uuid(token)
    row = (await db.execute(text("""
        SELECT t.id_turno, CAST(t.token_turno AS TEXT) AS token_turno,
               t.id_ocupacion, t.estado, t.fecha, t.hora_inicio, t.hora_fin, t.activo,
               tp.nombre AS prestacion_nombre,
               CASE WHEN t.id_espacio IS NOT NULL THEN e.nombre
                    ELSE COALESCE(a.apellido, '') || ', ' || COALESCE(a.nombre, '') END AS recurso_nombre,
               c.apellido AS ciudadano_apellido,
               c.nombre   AS ciudadano_nombre,
               c.doc_nro  AS ciudadano_dni
        FROM turnos t
        LEFT JOIN tipo_prestacion tp ON tp.id_tipo_prestacion = t.id_tipo_prestacion
        LEFT JOIN agentes         a  ON a.id_agente            = t.id_agente
        LEFT JOIN espacios_agenda e  ON e.id_espacio           = t.id_espacio
        LEFT JOIN ciudadanos      c  ON c.id_ciudadano         = t.id_ciudadano
        WHERE t.token_turno = CAST(:t AS UUID)
    """), {"t": token})).mappings().first()
    return dict(row) if row else None


@router.get("/turno/{token_turno}", response_model=TurnoPublicoOut)
async def obtener_turno_publico(
    token_turno: str,
    db: AsyncSession = Depends(get_db),
):
    t = await _turno_por_token(db, token_turno)
    if not t or not t["activo"]:
        raise HTTPException(404, "Turno no encontrado")
    return t


@router.delete("/turno/{token_turno}", response_model=TurnoPublicoOut)
async def cancelar_turno_publico(
    token_turno: str,
    db: AsyncSession = Depends(get_db),
):
    """Cancela el turno del ciudadano y libera la ocupacion espejo."""
    t = await _turno_por_token(db, token_turno)
    if not t or not t["activo"]:
        raise HTTPException(404, "Turno no encontrado")
    if t["estado"] == "cancelado":
        return t  # idempotente
    if t["estado"] != "reservado":
        raise HTTPException(409, f"No se puede cancelar un turno '{t['estado']}'")

    # CAS de estado (mig 95): no pisar un cumplir concurrente del backoffice.
    res = await db.execute(text("""
        UPDATE turnos SET estado = 'cancelado', fecha_modificacion = NOW()
        WHERE id_turno = :id AND estado = 'reservado'
    """), {"id": int(t["id_turno"])})
    if res.rowcount == 0:
        await db.rollback()
        t2 = await _turno_por_token(db, token_turno)
        if t2 and t2["estado"] == "cancelado":
            return t2  # idempotente
        raise HTTPException(409, f"No se puede cancelar un turno '{t2['estado'] if t2 else '?'}'")
    if t["id_ocupacion"]:
        await db.execute(text("""
            UPDATE ocupaciones SET activo = FALSE, fecha_modificacion = NOW()
            WHERE id_ocupacion = :io
        """), {"io": int(t["id_ocupacion"])})
    await db.commit()

    out = await _turno_por_token(db, token_turno)
    return out  # type: ignore


# =============================================================================
# Pantalla del colero (mig 105, F3 plan ATENCION) — TV de la sala de espera.
#
# Va en ESTE router (publico, sin auth y registrado ANTES de turnos_router en
# main.py) y no como `/turnos/pantalla/{token}` dentro del router autenticado:
# abrir un hueco sin `Depends(get_current_user)` ahi seria fragil ante un guard
# futuro a nivel router, que ademas no se puede anular por handler
# ([[reference_fastapi_router_dependencies_no_override]]).
#
# PRIVACIDAD (decision de Cesar 2026-09-01): la pantalla es un monitor a la
# vista de cualquiera en la sala. Muestra SOLO numero + "Nombre I." — nunca
# apellido completo, DNI, prestacion, agente ni id de turno. La proyeccion se
# hace EN SQL para que no haya forma de que un campo sensible viaje al cliente.
# =============================================================================
@router.get("/pantalla/{token_pantalla}", response_model=PantallaColeroOut)
async def pantalla_colero(
    token_pantalla: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Estado del colero de una ubicacion, para la TV de la sala (sin auth).

    La pantalla la refresca un polling corto, por eso el rate limit es mas
    holgado que el de reservas y usa **prefijo propio** (`pantalla:`): sin el,
    compartiria bucket por IP con los otros endpoints publicos y una TV
    consumiria el cupo de las reservas de esa misma IP (§5).
    """
    check_rate_limit(f"pantalla:{get_real_ip(request)}", max_requests=60, window_seconds=60)

    espacio = (await db.execute(text("""
        SELECT id_espacio, nombre FROM espacios_agenda
         WHERE token_pantalla = CAST(:tok AS uuid) AND activo = TRUE
    """), {"tok": token_pantalla})).mappings().first()
    if not espacio:
        raise HTTPException(404, "Pantalla no encontrada")

    hoy = hoy_local()

    # Una sola pasada: el ultimo llamado de cada turno del dia con numero.
    # `nombre_display` se arma en SQL (ver nota de privacidad arriba).
    filas = (await db.execute(text("""
        SELECT t.numero_diario AS numero,
               TRIM(COALESCE(c.nombre, '')) ||
                   CASE WHEN COALESCE(c.apellido, '') <> ''
                        THEN ' ' || UPPER(LEFT(TRIM(c.apellido), 1)) || '.'
                        ELSE '' END AS nombre_display,
               ll.puesto, ll.llamado_en,
               t.estado
          FROM turnos t
          JOIN LATERAL (
              SELECT l.llamado_en, l.puesto FROM turno_llamado l
               WHERE l.id_turno = t.id_turno AND l.activo = TRUE
               ORDER BY l.llamado_en DESC LIMIT 1
          ) ll ON TRUE
          LEFT JOIN ciudadanos c ON c.id_ciudadano = t.id_ciudadano
         WHERE t.id_espacio_ubicacion = :ie
           AND t.fecha = CAST(:f AS date)
           AND t.activo = TRUE
           AND t.numero_diario IS NOT NULL
         ORDER BY ll.llamado_en DESC
         LIMIT 12
    """), {"ie": espacio["id_espacio"], "f": hoy})).mappings().all()

    llamando: list[dict[str, Any]] = []
    previos: list[dict[str, Any]] = []
    for f in filas:
        item = {
            "numero": f["numero"],
            "nombre_display": (f["nombre_display"] or "").strip() or "—",
            "puesto": f["puesto"],
            "llamado_en": f["llamado_en"],
        }
        # "Llamando" = los que siguen en estado llamado (nadie los cerro aun).
        if f["estado"] == "llamado" and len(llamando) < 3:
            llamando.append(item)
        elif len(previos) < 8:
            previos.append(item)

    return {
        "ubicacion_nombre": espacio["nombre"],
        "fecha": hoy,
        "llamando": llamando,
        "previos": previos,
    }
