"""
ZARIS API - RECLAMOS del vecino (autoservicio desde la cuenta del ciudadano).

Bajo /api/v1/publico/reclamos/*. Guard get_current_ciudadano (JWT scope 'publico').

El vecino crea/ve reclamos A SU PROPIO NOMBRE: el id_ciudadano SIEMPRE sale del
token, nunca del body, así no puede operar sobre reclamos de terceros. Es la paridad
de acciones de un operador (call center) actuando en su nombre, acotada a sus datos
(ver project_usuario_vs_ciudadano_modelo).

Sin migración: reusa columnas existentes. El reclamo del vecino va con:
  - id_usuario_alta = NULL (no es un usuarios interno; columna nullable, verificado prod)
  - canal_origen = 'app_movil' (el CHECK lo acepta) para que el backoffice distinga el origen
  - estado inicial 'Sin asignar' (igual que el alta del operador)

v1 NO incluye: cambiar estado, cancelar, subreclamos, adjuntos, empresa/prioridad/
observaciones internas (eso es del backoffice u otra etapa).
"""
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_ciudadano
from app.core.config import settings
from app.core.database import get_db
from app.middleware.rate_limit import check_rate_limit
from app.utils.request_helpers import get_real_ip
from app.api.routes.geo import geocodificar_direccion, localidad_desde_coords, reverse_geocodificar
from app.services.email import enviar_mail_confirmacion_reclamo_ciudadano
from app.services.cuenta_vecino import _municipio_branding
from app.services.autoasignacion import autoasignar_reclamo

logger = logging.getLogger("zaris.publico_reclamos")

router = APIRouter(prefix="/api/v1/publico/reclamos", tags=["publico-reclamos"])

CANAL_VECINO = "app_movil"


def _to_dict(row) -> dict:
    d = dict(row._mapping)
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


# ─── GET /publico/reclamos/catalogo/tipos ────────────────────────────────────

@router.get("/catalogo/tipos")
async def catalogo_tipos_publico(
    q: Optional[str] = Query(None, description="Filtro por nombre (ILIKE)"),
    limit: int = Query(500, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
):
    """Tipos de reclamo activos para poblar el formulario del vecino.
    Solo datos no sensibles (id, nombre, sla, subárea). El área se deriva de
    subarea.id_area (mig 27 eliminó tipo_reclamo.id_area)."""
    cond = ["tr.activo = TRUE", "tr.id_municipio = :mun"]
    params: dict = {"lim": limit, "mun": current["id_municipio"]}
    if q and q.strip():
        cond.append("tr.nombre ILIKE :q")
        params["q"] = f"%{q.strip()}%"

    result = await db.execute(text(f"""
        SELECT tr.id_tipo_reclamo, tr.nombre, tr.sla_dias,
               tr.id_subarea, s.nombre AS subarea_nombre
        FROM tipo_reclamo tr
        LEFT JOIN subarea s ON s.id_subarea = tr.id_subarea
        WHERE {' AND '.join(cond)}
        ORDER BY tr.nombre
        LIMIT :lim
    """), params)
    return [_to_dict(r) for r in result.fetchall()]


# ─── GET /publico/reclamos/geo/buscar ────────────────────────────────────────

@router.get("/geo/buscar")
async def geo_buscar_vecino(
    request: Request,
    q: str = Query(..., min_length=3, description="Texto a geocodificar"),
    limit: int = Query(5, ge=1, le=10),
    current: dict = Depends(get_current_ciudadano),
):
    """Geocoding OSM para el buscador de domicilio del reclamo del vecino logueado.
    Reusa la lógica de filtrado de POIs de geo.py (solo_direcciones=True). El vecino
    geocodifica su propia dirección; scope 'publico' (no 'agente'). Rate-limit por IP
    además del rate-limit global de Nominatim."""
    check_rate_limit(f"reclpub:{get_real_ip(request)}", max_requests=20, window_seconds=60)
    return await geocodificar_direccion(q, limit, solo_direcciones=True, id_municipio=current["id_municipio"])


# ─── GET /publico/reclamos/geo/reverse ───────────────────────────────────────

@router.get("/geo/reverse",
            responses={502: {"description": "Nominatim no disponible"}})
async def geo_reverse_vecino(
    request: Request,
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    current: dict = Depends(get_current_ciudadano),
):
    """Geocoding INVERSO (GPS del celular → dirección legible) para autocompletar
    el domicilio de los tickets rápidos de emergencia y del form de reclamos de
    la PWA. Antes la app le pegaba directo a Nominatim desde el cliente; ahora
    pasa por el mismo helper (rate-limit global + User-Agent de ZARIS, §22).
    Scope 'publico'. Bucket propio de rate-limit por IP (§5)."""
    check_rate_limit(f"georevpub:{get_real_ip(request)}", max_requests=20, window_seconds=60)
    return await reverse_geocodificar(lat, lon)


# Estado que ve el vecino (mig 112): la auditoría posterior al cierre es interna.
_ESTADO_VECINO = "CASE WHEN r.estado IN ('En auditoría','Auditado') THEN 'Resuelto' ELSE r.estado END"

# Retrabajo de una auditoría observada (F4, PLAN_AUDITORIA_RECLAMOS.md): el vecino lo
# ve, pero su descripción guarda la observación del auditor (la necesita la cuadrilla)
# y esa observación es interna. El vecino ve la descripción de SU reclamo original.
# Requiere `LEFT JOIN reclamos ro ON ro.id_reclamo = r.id_reclamo_origen_auditoria`.
_DESCRIPCION_VECINO = """CASE WHEN r.id_reclamo_origen_auditoria IS NOT NULL
         THEN COALESCE(NULLIF(TRIM(ro.descripcion), ''),
                       'Reabierto por control de calidad del reclamo ' || COALESCE(ro.nro_reclamo, ''))
         ELSE r.descripcion END"""

# Primera entrada del historial de un retrabajo (la escribe observar_ot en
# ordenes_trabajo.py y el generador demo con este mismo texto): su nota trae la
# observación del auditor, así que se reemplaza por un texto genérico.
_ACCION_ALTA_RETRABAJO = "Reclamo ingresado por auditoría observada"


def _historial_vecino(item: dict, nro_origen: Optional[str]) -> dict:
    if item.get("accion") == _ACCION_ALTA_RETRABAJO:
        item["accion"] = "Reclamo reabierto por control de calidad"
        item["nota"] = (f"Vamos a volver a hacer el trabajo del reclamo {nro_origen}."
                        if nro_origen else "Vamos a volver a hacer el trabajo.")
    return item


# ─── GET /publico/reclamos ───────────────────────────────────────────────────

@router.get("")
async def listar_mis_reclamos(
    estado: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
):
    """Lista SOLO los reclamos del vecino logueado (id_ciudadano del token).

    Auditoría posterior al cierre (mig 112): para el vecino un reclamo 'En auditoría'
    o 'Auditado' sigue 'Resuelto' (la auditoría es interna). Los retrabajos que nacen
    de una auditoría observada SÍ se listan (F4), con la descripción del reclamo
    original y `origen_auditoria_nro` para que la app diga de dónde salen."""
    conds = ["r.activo = TRUE", "r.id_ciudadano = :id_c"]
    params: dict = {"id_c": current["id_ciudadano"], "limit": limit, "offset": offset}
    if estado:
        conds.append(f"{_ESTADO_VECINO} = :estado")
        params["estado"] = estado

    result = await db.execute(text(f"""
        SELECT
            r.id_reclamo, r.nro_reclamo, {_ESTADO_VECINO} AS estado,
            {_DESCRIPCION_VECINO} AS descripcion,
            r.direccion, r.fecha_alta, r.fecha_modificacion, r.fecha_cierre,
            r.latitud, r.longitud,
            r.id_tipo_reclamo, tr.nombre AS tipo_nombre,
            tr.id_subarea, s.nombre AS subarea_nombre,
            r.id_reclamo_origen_auditoria, ro.nro_reclamo AS origen_auditoria_nro
        FROM reclamos r
        LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
        LEFT JOIN subarea s ON s.id_subarea = tr.id_subarea
        LEFT JOIN reclamos ro ON ro.id_reclamo = r.id_reclamo_origen_auditoria
        WHERE {' AND '.join(conds)}
        ORDER BY r.fecha_alta DESC
        LIMIT :limit OFFSET :offset
    """), params)
    return [_to_dict(r) for r in result.fetchall()]


# ─── GET /publico/reclamos/{id} ──────────────────────────────────────────────

@router.get("/{id_reclamo}")
async def obtener_mi_reclamo(
    id_reclamo: int,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
):
    """Detalle de un reclamo PROPIO. Guard duro: 404 si no es del vecino (no se
    filtra info de terceros; mismo cuerpo para 'no existe' y 'no es tuyo').
    Un retrabajo de auditoría (F4) se muestra con la descripción del original y su
    alta en el historial con texto genérico: la observación del auditor es interna."""
    result = await db.execute(text(f"""
        SELECT
            r.id_reclamo, r.nro_reclamo, {_ESTADO_VECINO} AS estado,
            {_DESCRIPCION_VECINO} AS descripcion,
            r.direccion, r.resolucion,
            r.fecha_alta, r.fecha_modificacion, r.fecha_cierre, r.sla_vencimiento,
            r.canal_origen, r.fuente_geolocalizacion,
            r.latitud, r.longitud,
            r.id_localidad, loc.nombre AS localidad_nombre,
            r.id_tipo_reclamo, tr.nombre AS tipo_nombre, tr.sla_dias,
            tr.id_subarea, s.nombre AS subarea_nombre,
            r.id_reclamo_origen_auditoria, ro.nro_reclamo AS origen_auditoria_nro
        FROM reclamos r
        LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
        LEFT JOIN subarea s ON s.id_subarea = tr.id_subarea
        LEFT JOIN localidades loc ON loc.id_localidad = r.id_localidad
        LEFT JOIN reclamos ro ON ro.id_reclamo = r.id_reclamo_origen_auditoria
        WHERE r.id_reclamo = :id AND r.activo = TRUE AND r.id_ciudadano = :id_c
    """), {"id": id_reclamo, "id_c": current["id_ciudadano"]})
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")

    d = _to_dict(row)

    # Historial: solo acciones públicas, sin identidad del agente interno ni rastro
    # de la auditoría posterior (mig 112): se omiten los pasos a 'En auditoría'/
    # 'Auditado' y la cancelación de una auditoría (En auditoría → Resuelto,
    # «Auditoría cancelada»). Lo que fue 'En auditoría' se muestra 'Resuelto': en
    # los datos anteriores a la mig 112 ese paso ES el cierre real.
    # Notas: las del historial son internas (reasignaciones con nombres de agentes,
    # notas de supervisión). El vecino ve SOLO la resolución (mig 117, César
    # 2026-10-21), que es la nota del paso 'Resuelto' igual a reclamos.resolucion.
    hist = await db.execute(text("""
        SELECT h.accion,
               CASE WHEN h.estado_anterior IN ('En auditoría','Auditado') THEN 'Resuelto'
                    ELSE h.estado_anterior END AS estado_anterior,
               h.estado_nuevo,
               CASE WHEN h.estado_nuevo = 'Resuelto' AND r.resolucion IS NOT NULL
                         AND h.nota = r.resolucion THEN h.nota END AS nota,
               h.fecha_alta
        FROM reclamo_historial h
        JOIN reclamos r ON r.id_reclamo = h.id_reclamo
        WHERE h.id_reclamo = :id
          AND (h.estado_nuevo IS NULL OR h.estado_nuevo NOT IN ('En auditoría','Auditado'))
          AND h.accion IS DISTINCT FROM 'Auditoría cancelada'
        ORDER BY h.fecha_alta ASC
    """), {"id": id_reclamo})
    d["historial"] = [_historial_vecino(_to_dict(h), d.get("origen_auditoria_nro"))
                      for h in hist.fetchall()]

    return d


# ─── POST /publico/reclamos ──────────────────────────────────────────────────

@router.post("", status_code=201)
async def crear_mi_reclamo(
    body: dict,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
):
    """El vecino crea un reclamo a su propio nombre. id_ciudadano sale del token.

    Paridad de obligatoriedad con el alta del backoffice + piso elevado para
    autoservicio: el reclamo del vecino DEBE traer tipo y dirección (decisión del
    municipio — sin clasificación ni ubicación una cuadrilla no puede actuar). El
    backoffice los acepta opcionales, pero la autogestión no afloja esos campos."""
    descripcion = (body.get("descripcion") or "").strip()
    if len(descripcion) < 5:
        raise HTTPException(status_code=422, detail="La descripción debe tener al menos 5 caracteres")

    id_ciudadano = current["id_ciudadano"]
    id_tipo = body.get("id_tipo_reclamo")
    direccion = (body.get("direccion") or "").strip()

    if not id_tipo:
        raise HTTPException(status_code=422, detail="Campo requerido: id_tipo_reclamo")
    if not direccion:
        raise HTTPException(status_code=422, detail="Campo requerido: direccion")

    # Validar tipo (debe existir y estar activo) + derivar id_area de subarea.id_area.
    r_tipo = await db.execute(text("""
        SELECT s.id_area
        FROM tipo_reclamo tr
        LEFT JOIN subarea s ON s.id_subarea = tr.id_subarea
        WHERE tr.id_tipo_reclamo = :id_tr AND tr.activo = TRUE AND tr.id_municipio = :mun
    """), {"id_tr": id_tipo, "mun": current["id_municipio"]})
    row_tipo = r_tipo.fetchone()
    if not row_tipo:
        raise HTTPException(status_code=422, detail="Tipo de reclamo inválido")
    id_area = row_tipo.id_area

    data = {
        "id_ciudadano":  id_ciudadano,
        "id_tipo_reclamo": id_tipo,
        "id_area":       id_area,
        "descripcion":   descripcion,
        "direccion":     direccion,
        "latitud":       body.get("latitud"),
        "longitud":      body.get("longitud"),
        "id_localidad":  body.get("id_localidad"),
        "fuente_geolocalizacion": body.get("fuente_geolocalizacion"),
    }

    # Derivación automática de localidad (2026-08-30): la PWA no la manda; si hay
    # coordenadas, matchear contra el catálogo (best-effort, nunca falla).
    if data["id_localidad"] is None and data["latitud"] is not None and data["longitud"] is not None:
        loc = await localidad_desde_coords(db, data["latitud"], data["longitud"])
        if loc:
            data["id_localidad"] = loc["id_localidad"]

    try:
        # Estado inicial 'Sin asignar' (FK + VARCHAR en paralelo, §22).
        r_est = await db.execute(text(
            "SELECT id_estado_reclamo FROM estado_reclamo WHERE nombre = 'Sin asignar' AND activo = TRUE LIMIT 1"
        ))
        est_row = r_est.fetchone()
        data["id_estado_fk"] = est_row.id_estado_reclamo if est_row else None

        result = await db.execute(text("""
            INSERT INTO reclamos
                (id_ciudadano, id_tipo_reclamo, id_area, descripcion, direccion,
                 domicilio_reclamo, prioridad, estado, id_estado_fk,
                 latitud, longitud, id_localidad, canal_origen,
                 fuente_geolocalizacion, activo, fecha_alta, fecha_modificacion,
                 id_usuario_alta, id_usuario_modificacion, id_municipio)
            VALUES
                (:id_ciudadano, :id_tipo_reclamo, :id_area, :descripcion, :direccion,
                 :direccion, 'Media', 'Sin asignar', :id_estado_fk,
                 :latitud, :longitud, :id_localidad, :canal_origen,
                 :fuente_geolocalizacion, TRUE, NOW(), NOW(),
                 NULL, NULL, :id_municipio)
            RETURNING id_reclamo, nro_reclamo
        """), {**data, "canal_origen": CANAL_VECINO, "id_municipio": current["id_municipio"]})
        await db.commit()
        row = result.fetchone()
        id_reclamo = row.id_reclamo
        nro_reclamo = row.nro_reclamo or f"REC-{id_reclamo}"

        # Historial inicial: id_usuario_alta NULL (lo originó el vecino, no un agente).
        await db.execute(text("""
            INSERT INTO reclamo_historial
                (id_reclamo, accion, estado_anterior, estado_nuevo, nota, fecha_alta, id_usuario_alta,
                 id_municipio)
            VALUES (:id_r, 'Reclamo ingresado', NULL, 'Sin asignar',
                    'Reclamo registrado por el vecino desde la app', NOW(), NULL, :mun)
        """), {"id_r": id_reclamo, "mun": current["id_municipio"]})
        await db.commit()

        # Mail de confirmacion al vecino (best-effort, post-commit). No bloquea ni
        # rompe la creacion: si falta email o el branding no se puede leer, se omite.
        email_vecino = (current.get("email") or "").strip()
        if email_vecino:
            try:
                municipio_nombre, municipio_logo_url = await _municipio_branding(db, current["id_municipio"])
                background_tasks.add_task(
                    enviar_mail_confirmacion_reclamo_ciudadano,
                    to=email_vecino,
                    nombre=current.get("nombre") or "",
                    apellido=current.get("apellido") or "",
                    nro_reclamo=nro_reclamo,
                    descripcion=descripcion,
                    direccion=direccion,
                    municipio_nombre=municipio_nombre,
                    frontend_url=settings.APP_VECINOS_FRONTEND_URL,
                    municipio_logo_url=municipio_logo_url,
                    id_municipio=current["id_municipio"],
                )
            except Exception:
                logger.warning("No se pudo encolar el mail de confirmacion del reclamo %s", nro_reclamo)

        # Gestión con asignación automática (mig 114): se asigna sola, después de responder.
        background_tasks.add_task(autoasignar_reclamo, id_reclamo)

        return {"id_reclamo": id_reclamo, "nro_reclamo": nro_reclamo, "estado": "Sin asignar"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Error al crear reclamo público: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
