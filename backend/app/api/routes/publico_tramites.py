"""
ZARIS API — Trámites del VECINO logueado (portal, scope publico).
Prefijo: /api/v1/publico/tramites

- GET  /tipos        → tipos que el municipio le ofrece (spec §5.1) y si puede iniciarlos hoy
- GET  /tipos/{id}   → campos y documentos del alta de un tipo ofrecido
- POST ""            → inicia un trámite en UN request multipart, todo o nada (spec §5.3)

Reglas del alta:
- El iniciador sale SIEMPRE del token (`resolver_iniciador` con el id del vecino logueado).
- Todo se valida antes de crear algo: tipo ofrecido, identidad (si el tipo la exige), campos,
  documentos (presencia, formato, tamaño, cantidad). Un error es 422 y no queda nada.
- Los archivos se suben a Storage ya con el trámite creado en la transacción; si algo falla
  después de subir, se hace rollback y se borra lo subido.
- Rate-limit por IP con clave prefijada `trampub:` (el rate_limit clavea por string, §5).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_ciudadano
from app.core.database import get_db
from app.core.municipio import municipio_vecino
from app.middleware.rate_limit import check_rate_limit
from app.schemas.publico_tramites import (
    AltaTramiteOut,
    CampoPublicoOut,
    DocumentoAltaOut,
    TipoOfrecidoDetalleOut,
    TipoOfrecidoOut,
)
from app.services import identidad as svc_identidad
from app.services import notificaciones as svc_notif
from app.services.tramites import alta as svc_alta
from app.services.tramites import creacion as svc_creacion
from app.services.tramites import documentos as svc_docs
from app.services.tramites import movimientos as svc_mov
from app.utils.request_helpers import get_real_ip

router = APIRouter(prefix="/api/v1/publico/tramites", tags=["publico-tramites"])
logger = logging.getLogger("zaris.publico_tramites")

MAX_ARCHIVOS_TOTAL = 20            # partes `archivos` por request
MAX_CUERPO_BYTES = 25 * 1024 * 1024  # tope del body (lo aplica LimiteCuerpoMiddleware, antes de parsear)


def _tipo_out(t: dict, identidad_ok: bool) -> dict:
    bloqueado = bool(t["exige_identidad_validada"]) and not identidad_ok
    return {
        "id_tipo_tramite": t["id_tipo_tramite"],
        "nombre": t["nombre"],
        "descripcion": t.get("descripcion"),
        "exige_identidad_validada": bool(t["exige_identidad_validada"]),
        "puede_iniciar": not bloqueado,
        "motivo_no_puede": svc_identidad.MSG_IDENTIDAD_PORTAL if bloqueado else None,
    }


@router.get("/tipos", response_model=list[TipoOfrecidoOut])
async def listar_tipos(
    db: AsyncSession = Depends(get_db),
    ciudadano: dict = Depends(get_current_ciudadano),
    id_municipio: int = Depends(municipio_vecino),
):
    tipos = await svc_alta.tipos_ofrecidos(db, id_municipio)
    identidad_ok = bool(await svc_identidad.identidad_validada(db, ciudadano["id_ciudadano"]))
    return [_tipo_out(t, identidad_ok) for t in tipos]


@router.get("/tipos/{id_tipo_tramite}", response_model=TipoOfrecidoDetalleOut)
async def detalle_tipo(
    id_tipo_tramite: int,
    db: AsyncSession = Depends(get_db),
    ciudadano: dict = Depends(get_current_ciudadano),
    id_municipio: int = Depends(municipio_vecino),
):
    tipos = await svc_alta.tipos_ofrecidos(db, id_municipio, id_tipo_tramite)
    if not tipos:
        raise HTTPException(404, "Trámite no encontrado")
    t = tipos[0]
    identidad_ok = bool(await svc_identidad.identidad_validada(db, ciudadano["id_ciudadano"]))
    campos = (await db.execute(
        text("""
            SELECT nombre_interno, etiqueta, tipo_dato, obligatorio, opciones_jsonb AS opciones, ayuda, orden
              FROM tipo_tramite_campo
             WHERE id_tipo_tramite_version = :ver AND activo = TRUE
             ORDER BY orden, id_tipo_tramite_campo
        """),
        {"ver": t["id_version_publicada"]},
    )).mappings().all()
    estado_inicial = await svc_alta.estado_inicial_de(db, t["id_version_publicada"])
    docs = await svc_alta.documentos_del_alta(db, t["id_version_publicada"], estado_inicial) if estado_inicial else []
    return {
        **_tipo_out(t, identidad_ok),
        "campos": [CampoPublicoOut(**dict(c)) for c in campos],
        "documentos": [DocumentoAltaOut(**d) for d in docs],
    }


def _json_de_form(valor: str, nombre: str, esperado: type):
    try:
        v = json.loads(valor)
    except (TypeError, ValueError):
        raise HTTPException(422, f"'{nombre}' no es un JSON válido")
    if not isinstance(v, esperado):
        raise HTTPException(422, f"'{nombre}' tiene un formato inválido")
    return v


def _a_422(e: HTTPException) -> HTTPException:
    """Los errores de validación del servicio salen como 400; en el portal son 422 con un texto."""
    detalle = e.detail
    if isinstance(detalle, dict) and "errores_validacion" in detalle:
        detalle = "; ".join(str(x) for x in detalle["errores_validacion"])
    return HTTPException(422, detalle)


@router.post("", status_code=201, response_model=AltaTramiteOut)
async def iniciar_tramite(
    request: Request,
    background_tasks: BackgroundTasks,
    id_tipo_tramite: int = Form(...),
    datos: str = Form("{}"),
    documentos: str = Form("[]"),
    archivos: list[UploadFile] = File(default=[]),
    db: AsyncSession = Depends(get_db),
    ciudadano: dict = Depends(get_current_ciudadano),
    id_municipio: int = Depends(municipio_vecino),
):
    # 20/min por IP: es una escritura con archivos; el cupo cubre reintentos humanos.
    check_rate_limit(f"trampub:{get_real_ip(request)}", max_requests=20, window_seconds=60)
    id_ciudadano = ciudadano["id_ciudadano"]

    datos_d = _json_de_form(datos, "datos", dict)
    if len(archivos) > MAX_ARCHIVOS_TOTAL:
        raise HTTPException(422, f"Se admiten hasta {MAX_ARCHIVOS_TOTAL} archivos por trámite")
    docs_ids = _json_de_form(documentos, "documentos", list)
    if len(docs_ids) != len(archivos) or not all(isinstance(x, int) and not isinstance(x, bool) for x in docs_ids):
        raise HTTPException(422, "Cada archivo tiene que indicar a qué documento corresponde")

    # 1. Tipo ofrecido a este vecino
    ofrecidos = await svc_alta.tipos_ofrecidos(db, id_municipio, id_tipo_tramite)
    if not ofrecidos:
        raise HTTPException(404, "Trámite no encontrado")
    tipo_row = (await db.execute(
        text("""
            SELECT tt.*, m.codigo_corto FROM tipo_tramite tt
            JOIN municipios m ON m.id_municipio = tt.id_municipio
            WHERE tt.id_tipo_tramite = :id AND tt.activo = TRUE AND tt.id_municipio = :mun
        """),
        {"id": id_tipo_tramite, "mun": id_municipio},
    )).fetchone()
    if not tipo_row or not tipo_row.id_version_publicada:
        raise HTTPException(404, "Trámite no encontrado")
    tipo = dict(tipo_row._mapping)

    # 2. Iniciador = el del token (mismas validaciones que el backoffice) e identidad del tipo
    iniciador_fks = await svc_creacion.resolver_iniciador(
        {"tipo": "ciudadano", "id_ciudadano": id_ciudadano}, tipo, id_municipio, db)
    if tipo.get("exige_identidad_validada") and not await svc_identidad.identidad_validada(db, id_ciudadano):
        raise HTTPException(422, svc_identidad.MSG_IDENTIDAD_PORTAL)

    # 3. Campos del formulario: solo se conservan los campos activos del tipo (el ledger es append-only)
    campos_ok = {r[0] for r in (await db.execute(
        text("SELECT nombre_interno FROM tipo_tramite_campo WHERE id_tipo_tramite_version = :v AND activo = TRUE "
             "AND tipo_dato NOT IN ('archivo', 'agente', 'subarea')"),
        {"v": tipo["id_version_publicada"]})).all()}
    datos_d = {k: v for k, v in datos_d.items() if k in campos_ok}
    try:
        await svc_creacion.validar_campos_contra_tipo(datos_d, tipo["id_version_publicada"], id_municipio, db)
    except HTTPException as e:
        raise _a_422(e)

    # 4. Documentos: todos los archivos contra su documento requerido, antes de subir nada
    estado_inicial = await svc_alta.estado_inicial_de(db, tipo["id_version_publicada"])
    if not estado_inicial:
        raise HTTPException(500, "El tipo de tramite no tiene estado inicial configurado")
    docs_alta = {d["id_documento_requerido"]: d for d in
                 await svc_alta.documentos_del_alta(db, tipo["id_version_publicada"], estado_inicial)}
    # Todo chequeo barato (documento, cantidad, tamaño declarado) ANTES de leer ningún archivo.
    por_doc: dict[int, int] = {}
    for f, id_doc in zip(archivos, docs_ids):
        doc = docs_alta.get(id_doc)
        if not doc:
            raise HTTPException(422, "Un archivo no corresponde a ningún documento de este trámite")
        por_doc[id_doc] = por_doc.get(id_doc, 0) + 1
        if por_doc[id_doc] > (doc["cantidad_max_archivos"] or 1):
            raise HTTPException(422, f"'{doc['nombre']}' admite hasta {doc['cantidad_max_archivos']} archivo(s)")
        if svc_docs._extension(f.filename or "") not in svc_docs.ALLOWED_MIME_MAP:
            raise HTTPException(422, f"El archivo '{f.filename or ''}' tiene un formato no aceptado")
        max_mb = min(doc.get("tamano_max_mb") or svc_docs.UPLOADS_MAX_SIZE_MB, svc_docs.UPLOADS_MAX_SIZE_MB)
        if f.size is not None and f.size > max_mb * 1024 * 1024:
            raise HTTPException(422, f"El archivo '{f.filename or ''}' supera el tamaño máximo de {max_mb} MB")
    for f, id_doc in zip(archivos, docs_ids):
        try:
            await svc_docs.validar_archivo_mock(f, docs_alta[id_doc])
        except HTTPException as e:
            raise _a_422(e)
    for id_doc, doc in docs_alta.items():
        n = por_doc.get(id_doc, 0)
        if doc["obligatorio"] and n == 0:
            raise HTTPException(422, f"Falta el documento obligatorio: {doc['nombre']}")

    # 5. Crear todo en una transacción; lo subido se borra si algo falla antes del commit
    subidos: list[str] = []
    try:
        id_tramite = await svc_alta.crear_tramite_en_db(
            db,
            tipo=tipo,
            datos=datos_d,
            asunto=tipo["nombre"],
            iniciador_fks=iniciador_fks,
            iniciador_tipo="ciudadano",
            id_municipio=id_municipio,
            actor_agente=None,
            id_ciudadano_actor=id_ciudadano,
            id_usuario=None,
            destinatario=("subarea", tipo["id_subarea"]),
            request=request,
        )
        numero = (await db.execute(
            text("SELECT numero_expediente FROM tramite WHERE id_tramite = :id"), {"id": id_tramite})).scalar()
        anio = datetime.now(timezone.utc).year
        for f, id_doc in zip(archivos, docs_ids):
            doc = docs_alta[id_doc]
            info = await svc_docs.guardar_archivo_mock(
                f, numero, anio, doc["nombre"] or Path(f.filename or "archivo").stem, id_municipio)
            subidos.append(info["storage_path"])
            posicion = await svc_docs.obtener_proxima_posicion(id_tramite, db)
            doc_row = (await db.execute(
                text("""
                    INSERT INTO tramite_documento (
                        id_tramite, id_tipo_tramite_documento_requerido,
                        nombre, nombre_archivo_original,
                        storage_path, mime_type, tamano_bytes, hash_sha256,
                        requiere_firma, estado_firma, posicion_orden,
                        id_agente_subio, id_ciudadano_subio, id_municipio
                    ) VALUES (
                        :tramite, :doc_req, :nombre, :nombre_orig,
                        :path, :mime, :tamano, :hash,
                        FALSE, 'no_requiere', :pos,
                        NULL, :cid, :mun
                    )
                    RETURNING id_tramite_documento
                """),
                {
                    "tramite": id_tramite, "doc_req": id_doc,
                    "nombre": doc["nombre"] or info["nombre_archivo_original"],
                    "nombre_orig": info["nombre_archivo_original"],
                    "path": info["storage_path"], "mime": info["mime_type"],
                    "tamano": info["tamano_bytes"], "hash": info["hash_sha256"],
                    "pos": posicion, "cid": id_ciudadano, "mun": id_municipio,
                },
            )).fetchone()
            await svc_mov.registrar_movimiento(
                db, id_tramite, "adjunto", None, None, id_municipio, request,
                metadata_jsonb={
                    "id_tramite_documento": doc_row.id_tramite_documento,
                    "nombre": info["nombre_archivo_original"],
                    "hash_sha256": info["hash_sha256"],
                    "tamano_bytes": info["tamano_bytes"],
                    "requiere_firma": False,
                },
                id_ciudadano_actor=id_ciudadano,
            )
        await db.commit()
    except BaseException:
        await db.rollback()
        await svc_docs.borrar_archivos(subidos)
        raise

    # Post-commit (fail-safe interno): bandeja de la gestión y mail al vecino con el número.
    await svc_notif.notificar_tramite_a_bandeja(db, id_tramite, "creacion", background_tasks)
    await svc_notif.notificar_inicio_a_iniciador(db, id_tramite, background_tasks)
    return AltaTramiteOut(id_tramite=id_tramite, numero_expediente=numero)
