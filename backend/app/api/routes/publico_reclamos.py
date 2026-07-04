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
from app.api.routes.geo import geocodificar_direccion
from app.services.email import enviar_mail_confirmacion_reclamo_ciudadano
from app.services.cuenta_vecino import _municipio_branding

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
    cond = ["tr.activo = TRUE"]
    params: dict = {"lim": limit}
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
    return await geocodificar_direccion(q, limit, solo_direcciones=True)


# ─── GET /publico/reclamos ───────────────────────────────────────────────────

@router.get("")
async def listar_mis_reclamos(
    estado: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
):
    """Lista SOLO los reclamos del vecino logueado (id_ciudadano del token)."""
    conds = ["r.activo = TRUE", "r.id_ciudadano = :id_c"]
    params: dict = {"id_c": current["id_ciudadano"], "limit": limit, "offset": offset}
    if estado:
        conds.append("r.estado = :estado")
        params["estado"] = estado

    result = await db.execute(text(f"""
        SELECT
            r.id_reclamo, r.nro_reclamo, r.estado, r.descripcion,
            r.direccion, r.fecha_alta, r.fecha_modificacion, r.fecha_cierre,
            r.latitud, r.longitud,
            r.id_tipo_reclamo, tr.nombre AS tipo_nombre,
            tr.id_subarea, s.nombre AS subarea_nombre
        FROM reclamos r
        LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
        LEFT JOIN subarea s ON s.id_subarea = tr.id_subarea
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
    filtra info de terceros; mismo cuerpo para 'no existe' y 'no es tuyo')."""
    result = await db.execute(text("""
        SELECT
            r.id_reclamo, r.nro_reclamo, r.estado, r.descripcion,
            r.direccion, r.observaciones,
            r.fecha_alta, r.fecha_modificacion, r.fecha_cierre, r.sla_vencimiento,
            r.canal_origen, r.fuente_geolocalizacion,
            r.latitud, r.longitud,
            r.id_localidad, loc.nombre AS localidad_nombre,
            r.id_tipo_reclamo, tr.nombre AS tipo_nombre, tr.sla_dias,
            tr.id_subarea, s.nombre AS subarea_nombre
        FROM reclamos r
        LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
        LEFT JOIN subarea s ON s.id_subarea = tr.id_subarea
        LEFT JOIN localidades loc ON loc.id_localidad = r.id_localidad
        WHERE r.id_reclamo = :id AND r.activo = TRUE AND r.id_ciudadano = :id_c
    """), {"id": id_reclamo, "id_c": current["id_ciudadano"]})
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")

    d = _to_dict(row)

    # Historial: solo acciones públicas (estado + nota), sin identidad del agente interno.
    hist = await db.execute(text("""
        SELECT h.accion, h.estado_anterior, h.estado_nuevo, h.nota, h.fecha_alta
        FROM reclamo_historial h
        WHERE h.id_reclamo = :id
        ORDER BY h.fecha_alta ASC
    """), {"id": id_reclamo})
    d["historial"] = [_to_dict(h) for h in hist.fetchall()]

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
        WHERE tr.id_tipo_reclamo = :id_tr AND tr.activo = TRUE
    """), {"id_tr": id_tipo})
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
                 id_usuario_alta, id_usuario_modificacion)
            VALUES
                (:id_ciudadano, :id_tipo_reclamo, :id_area, :descripcion, :direccion,
                 :direccion, 'Media', 'Sin asignar', :id_estado_fk,
                 :latitud, :longitud, :id_localidad, :canal_origen,
                 :fuente_geolocalizacion, TRUE, NOW(), NOW(),
                 NULL, NULL)
            RETURNING id_reclamo, nro_reclamo
        """), {**data, "canal_origen": CANAL_VECINO})
        await db.commit()
        row = result.fetchone()
        id_reclamo = row.id_reclamo
        nro_reclamo = row.nro_reclamo or f"REC-{id_reclamo}"

        # Historial inicial: id_usuario_alta NULL (lo originó el vecino, no un agente).
        await db.execute(text("""
            INSERT INTO reclamo_historial
                (id_reclamo, accion, estado_anterior, estado_nuevo, nota, fecha_alta, id_usuario_alta)
            VALUES (:id_r, 'Reclamo ingresado', NULL, 'Sin asignar',
                    'Reclamo registrado por el vecino desde la app', NOW(), NULL)
        """), {"id_r": id_reclamo})
        await db.commit()

        # Mail de confirmacion al vecino (best-effort, post-commit). No bloquea ni
        # rompe la creacion: si falta email o el branding no se puede leer, se omite.
        email_vecino = (current.get("email") or "").strip()
        if email_vecino:
            try:
                municipio_nombre, municipio_logo_url = await _municipio_branding(db)
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
                )
            except Exception:
                logger.warning("No se pudo encolar el mail de confirmacion del reclamo %s", nro_reclamo)

        return {"id_reclamo": id_reclamo, "nro_reclamo": nro_reclamo, "estado": "Sin asignar"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Error al crear reclamo público: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
