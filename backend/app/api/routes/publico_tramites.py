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

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi import Path as Path_
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
    DocumentosSubidosOut,
    MiTramiteDetalleOut,
    MiTramiteOut,
    RespuestaPedidoOut,
    TipoOfrecidoDetalleOut,
    TipoOfrecidoOut,
)
from app.services import identidad as svc_identidad
from app.services import notificaciones as svc_notif
from app.services.tramites import alta as svc_alta
from app.services.tramites import creacion as svc_creacion
from app.services.tramites import documentos as svc_docs
from app.services.tramites import movimientos as svc_mov
from app.services.tramites import pedidos as svc_pedidos
from app.utils.request_helpers import get_real_ip

router = APIRouter(prefix="/api/v1/publico/tramites", tags=["publico-tramites"])
logger = logging.getLogger("zaris.publico_tramites")

MAX_ID = 2_147_483_647
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


async def _validar_archivos(archivos: list[UploadFile], docs_ids: list[int], docs: dict[int, dict],
                            ya_subidos: dict[int, int] | None = None) -> dict[int, int]:
    """Valida todos los archivos contra sus documentos requeridos ANTES de subir nada: documento
    conocido, cantidad, formato, tamaño declarado y contenido. `ya_subidos` = cuántos tiene ya cada
    documento (se suman a la cantidad máxima). Devuelve cuántos archivos llegan por documento."""
    por_doc: dict[int, int] = {}
    # Todo chequeo barato (documento, cantidad, tamaño declarado) ANTES de leer ningún archivo.
    for f, id_doc in zip(archivos, docs_ids):
        doc = docs.get(id_doc)
        if not doc:
            raise HTTPException(422, "Un archivo no corresponde a ningún documento de este trámite")
        por_doc[id_doc] = por_doc.get(id_doc, 0) + 1
        if por_doc[id_doc] + (ya_subidos or {}).get(id_doc, 0) > (doc["cantidad_max_archivos"] or 1):
            raise HTTPException(422, f"'{doc['nombre']}' admite hasta {doc['cantidad_max_archivos']} archivo(s)")
        if svc_docs._extension(f.filename or "") not in svc_docs.ALLOWED_MIME_MAP:
            raise HTTPException(422, f"El archivo '{f.filename or ''}' tiene un formato no aceptado")
        max_mb = min(doc.get("tamano_max_mb") or svc_docs.UPLOADS_MAX_SIZE_MB, svc_docs.UPLOADS_MAX_SIZE_MB)
        if f.size is not None and f.size > max_mb * 1024 * 1024:
            raise HTTPException(422, f"El archivo '{f.filename or ''}' supera el tamaño máximo de {max_mb} MB")
    for f, id_doc in zip(archivos, docs_ids):
        try:
            await svc_docs.validar_archivo_mock(f, docs[id_doc])
        except HTTPException as e:
            raise _a_422(e)
    return por_doc


async def _guardar_documentos(db: AsyncSession, request: Request, id_tramite: int, numero: str,
                              id_municipio: int, id_ciudadano: int, archivos: list[UploadFile],
                              docs_ids: list[int | None], docs: dict[int | None, dict], subidos: list[str],
                              id_tramite_pedido: int | None = None) -> None:
    """Sube cada archivo a Storage y crea su `tramite_documento` + movimiento `adjunto`, todo en la
    transacción del llamador (que commitea, o hace rollback y borra `subidos`). Con `id_tramite_pedido`
    los documentos son la respuesta a un pedido: sin documento requerido (`docs_ids` = None)."""
    anio = datetime.now(timezone.utc).year
    for f, id_doc in zip(archivos, docs_ids):
        doc = docs[id_doc]
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
                    id_agente_subio, id_ciudadano_subio, id_municipio, id_tramite_pedido
                ) VALUES (
                    :tramite, :doc_req, :nombre, :nombre_orig,
                    :path, :mime, :tamano, :hash,
                    FALSE, 'no_requiere', :pos,
                    NULL, :cid, :mun, :pedido
                )
                RETURNING id_tramite_documento
            """),
            {
                "tramite": id_tramite, "doc_req": id_doc,
                "nombre": doc["nombre"] or info["nombre_archivo_original"],
                "nombre_orig": info["nombre_archivo_original"],
                "path": info["storage_path"], "mime": info["mime_type"],
                "tamano": info["tamano_bytes"], "hash": info["hash_sha256"],
                "pos": posicion, "cid": id_ciudadano, "mun": id_municipio, "pedido": id_tramite_pedido,
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


# Pseudo-documento de la respuesta a un pedido: no hay documento requerido, así que solo valen los
# topes generales (formato y tamaño de `documentos.py`, cantidad de `MAX_ARCHIVOS_TOTAL`).
_DOC_RESPUESTA = {"nombre": None, "cantidad_max_archivos": MAX_ARCHIVOS_TOTAL, "tamano_max_mb": None,
                  "formatos_permitidos": []}


@router.post("/{id_tramite}/pedidos/{id_pedido}/responder", response_model=RespuestaPedidoOut)
async def responder_pedido(
    request: Request,
    background_tasks: BackgroundTasks,
    id_tramite: int = Path_(..., ge=1, le=MAX_ID),
    id_pedido: int = Path_(..., ge=1, le=MAX_ID),
    texto: str = Form(..., min_length=1, max_length=4000),
    archivos: list[UploadFile] = File(default=[]),
    db: AsyncSession = Depends(get_db),
    ciudadano: dict = Depends(get_current_ciudadano),
    id_municipio: int = Depends(municipio_vecino),
):
    check_rate_limit(f"trampub:ped:{get_real_ip(request)}", max_requests=20, window_seconds=60)
    id_c = ciudadano["id_ciudadano"]
    t = await _mi_tramite(db, id_tramite, id_c, id_municipio)  # 404 idéntico si no es suyo

    if t.get("fecha_archivado") is not None or t.get("es_final"):
        raise HTTPException(409, "El trámite ya terminó: el pedido quedó sin efecto.")
    texto = texto.strip()
    if len(texto) < 5:
        raise HTTPException(422, "La respuesta tiene que tener al menos 5 caracteres")
    if len(archivos) > MAX_ARCHIVOS_TOTAL:
        raise HTTPException(422, f"Se admiten hasta {MAX_ARCHIVOS_TOTAL} archivos por vez")
    # Todo lo que se puede chequear sin tocar el pedido va ANTES de tomarlo (el lock dura poco).
    docs_ids: list[int | None] = [None] * len(archivos)
    await _validar_archivos(archivos, docs_ids, {None: _DOC_RESPUESTA})

    # El pedido se toma con FOR UPDATE y debe estar abierto: la respuesta concurrente espera acá y recibe 409.
    pedido = await svc_pedidos.tomar_abierto_para_responder(db, id_tramite, id_pedido)
    if pedido["pide_archivo"] and not archivos:
        await db.rollback()
        raise HTTPException(422, "Este pedido necesita que adjuntes al menos un archivo.")

    subidos: list[str] = []
    try:
        await _guardar_documentos(db, request, id_tramite, t["numero_expediente"], id_municipio, id_c,
                                  archivos, docs_ids, {None: _DOC_RESPUESTA}, subidos, id_tramite_pedido=id_pedido)
        await db.execute(
            text("""
                UPDATE tramite_pedido_iniciador
                   SET estado = 'respondido', respuesta_texto = :txt, fecha_respuesta = NOW(),
                       fecha_modificacion = NOW()
                 WHERE id_tramite_pedido = :p
            """), {"txt": texto, "p": id_pedido})
        await svc_mov.registrar_movimiento(
            db, id_tramite, "respuesta_iniciador", None, None, id_municipio, request,
            comentario=texto,
            metadata_jsonb={"id_tramite_pedido": id_pedido, "archivos": len(archivos)},
            id_ciudadano_actor=id_c,
        )
        await db.commit()
    except BaseException:
        await db.rollback()
        await svc_docs.borrar_archivos(subidos)
        raise

    await svc_notif.notificar_respuesta_vecino(db, id_tramite, background_tasks)
    return RespuestaPedidoOut(respondido=True)


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
    por_doc = await _validar_archivos(archivos, docs_ids, docs_alta)
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
        await _guardar_documentos(db, request, id_tramite, numero, id_municipio, id_ciudadano,
                                  archivos, docs_ids, docs_alta, subidos)
        await db.commit()
    except BaseException:
        await db.rollback()
        await svc_docs.borrar_archivos(subidos)
        raise

    # Post-commit (fail-safe interno): bandeja de la gestión y mail al vecino con el número.
    await svc_notif.notificar_tramite_a_bandeja(db, id_tramite, "creacion", background_tasks)
    await svc_notif.notificar_inicio_a_iniciador(db, id_tramite, background_tasks)
    return AltaTramiteOut(id_tramite=id_tramite, numero_expediente=numero)


# ── Ver mis trámites (spec §5.4) y aportar los documentos del paso (§5.5) ───
# Las rutas con `{id_tramite}` van DESPUÉS de las fijas (`/tipos`): el greedy atrapa un segmento.
# Un trámite que no es del token es un 404 idéntico al de un id inexistente.

NO_ENCONTRADO = "Trámite no encontrado"

_SQL_MIS = """
    SELECT t.id_tramite, t.numero_expediente, t.datos_jsonb, t.resultado, t.fecha_alta,
           t.fecha_entrada_estado_actual, t.id_tipo_tramite_version, t.id_tipo_tramite_estado_actual,
           t.destinatario_actual_tipo,
           tt.nombre AS tipo_nombre, e.etiqueta AS estado_etiqueta, e.color AS estado_color,
           e.oculto_para_iniciador AS estado_oculto, t.fecha_archivado, COALESCE(e.es_final, FALSE) AS es_final,
           EXISTS (SELECT 1 FROM tramite_pedido_iniciador p
                    WHERE p.id_tramite = t.id_tramite AND p.estado = 'abierto' AND p.activo = TRUE)
               AS tiene_pedido_abierto,
           (SELECT COUNT(*) FROM tipo_tramite_documento_requerido d
             WHERE d.id_tipo_tramite_version = t.id_tipo_tramite_version AND d.activo = TRUE
               AND d.obligatorio = TRUE AND d.aporta_quien = 'iniciador' AND d.requiere_firma = FALSE
               AND d.id_tipo_tramite_estado = t.id_tipo_tramite_estado_actual
               AND NOT EXISTS (
                     SELECT 1 FROM tramite_documento td
                      WHERE td.id_tramite = t.id_tramite AND td.activo = TRUE
                        AND td.id_tipo_tramite_documento_requerido = d.id_tipo_tramite_documento_requerido
                        AND td.id_ciudadano_subio IS NOT NULL
                        AND td.fecha_alta >= t.fecha_entrada_estado_actual)) AS documentos_pendientes
      FROM tramite t
      JOIN tipo_tramite_version v ON v.id_tipo_tramite_version = t.id_tipo_tramite_version
      JOIN tipo_tramite tt ON tt.id_tipo_tramite = v.id_tipo_tramite
      JOIN tipo_tramite_estado e ON e.id_tipo_tramite_estado = t.id_tipo_tramite_estado_actual
     WHERE t.id_ciudadano_iniciador = :c AND t.id_municipio = :mun AND t.activo = TRUE
"""


async def _mostrar_estado_visible(db: AsyncSession, filas: list[dict]) -> list[dict]:
    """`oculto_para_iniciador`: un estado oculto nunca se expone (ni etiqueta ni color). Se muestra el
    último estado VISIBLE por el que pasó el trámite (el ledger hacia atrás) o, si no hay, "En trámite"
    sin color. Lo demás (vigencia, pedidos) sigue usando el estado real."""
    for f in filas:
        if not f.get("estado_oculto"):
            continue
        prev = (await db.execute(
            text("""
                SELECT e.etiqueta, e.color FROM tramite_movimiento m
                  JOIN tipo_tramite_estado e ON e.id_tipo_tramite_estado = m.id_estado_destino
                 WHERE m.id_tramite = :t AND m.activo = TRUE
                   AND m.tipo IN ('creacion', 'transicion', 'cambio_estado')
                   AND e.oculto_para_iniciador = FALSE
                 ORDER BY m.orden_secuencial DESC LIMIT 1
            """), {"t": f["id_tramite"]})).mappings().first()
        f["estado_etiqueta"] = prev["etiqueta"] if prev else "En trámite"
        f["estado_color"] = prev["color"] if prev else None
    return filas


def _resumen_out(r) -> dict:
    return {
        "id_tramite": r["id_tramite"], "numero_expediente": r["numero_expediente"],
        "tipo_nombre": r["tipo_nombre"], "estado_etiqueta": r["estado_etiqueta"],
        "estado_color": r["estado_color"], "resultado": r["resultado"], "fecha_alta": r["fecha_alta"],
        "tiene_pedido_abierto": bool(r["tiene_pedido_abierto"]),
        "documentos_pendientes": int(r["documentos_pendientes"] or 0),
    }


async def _mi_tramite(db: AsyncSession, id_tramite: int, id_ciudadano: int, id_municipio: int) -> dict:
    fila = (await db.execute(
        text(_SQL_MIS + " AND t.id_tramite = :id"),
        {"c": id_ciudadano, "mun": id_municipio, "id": id_tramite},
    )).mappings().first()
    if not fila:
        raise HTTPException(404, NO_ENCONTRADO)
    return (await _mostrar_estado_visible(db, [dict(fila)]))[0]


def _opcion_etiqueta(opciones, valor) -> str:
    """Etiqueta de una opción de selección: acepta `[{valor, etiqueta}]`, `{"opciones": [...]}` o
    strings sueltos; si el valor no está, se muestra tal cual."""
    if isinstance(opciones, dict):
        opciones = opciones.get("opciones")
    for o in opciones or []:
        if isinstance(o, dict) and str(o.get("valor")) == str(valor):
            return str(o.get("etiqueta") or valor)
    return str(valor)


def _valor_legible(campo: dict, valor) -> str:
    tipo = campo["tipo_dato"]
    if valor is None or valor == "":
        return ""
    if tipo == "direccion":
        if isinstance(valor, dict):
            return str(valor.get("texto") or "")
        return str(valor)
    if tipo == "seleccion":
        return _opcion_etiqueta(campo["opciones"], valor)
    if tipo == "seleccion_multiple":
        items = valor if isinstance(valor, list) else [valor]
        return ", ".join(_opcion_etiqueta(campo["opciones"], v) for v in items)
    if tipo == "booleano":
        return "Sí" if valor in (True, "true", "True", 1, "1") else "No"
    return str(valor)


async def _datos_legibles(db: AsyncSession, id_version: int, datos: dict) -> list[dict]:
    campos = (await db.execute(
        text("SELECT nombre_interno, etiqueta, tipo_dato, opciones_jsonb AS opciones FROM tipo_tramite_campo "
             "WHERE id_tipo_tramite_version = :v AND activo = TRUE "
             "AND tipo_dato NOT IN ('agente', 'subarea', 'archivo') ORDER BY orden, id_tipo_tramite_campo"),
        {"v": id_version})).mappings().all()
    salida = []
    for c in campos:
        if c["nombre_interno"] in (datos or {}):
            v = _valor_legible(dict(c), datos[c["nombre_interno"]])
            if v != "":
                salida.append({"etiqueta": c["etiqueta"], "valor": v})
    return salida


# Lista cerrada de lo que el vecino ve del ledger (spec §5.4): nada interno ni de agentes.
_TIPOS_HISTORIAL = ("creacion", "transicion", "cambio_estado", "pedido_iniciador", "respuesta_iniciador",
                    "pedido_cancelado", "resultado", "aviso_iniciador", "desistido",
                    "archivado_inactividad", "adjunto")
_TXT_RESULTADO = {"aprobado": "El trámite fue aprobado.", "rechazado": "El trámite fue rechazado.",
                  "desistido": "El trámite se dio por desistido.", "pendiente": "El resultado del trámite quedó pendiente."}


async def _historial(db: AsyncSession, id_tramite: int, id_ciudadano: int) -> list[dict]:
    movs = (await db.execute(
        text("""
            SELECT m.tipo, m.fecha_alta, m.metadata_jsonb, m.id_ciudadano_actor,
                   ed.etiqueta AS estado_destino, ed.oculto_para_iniciador AS destino_oculto,
                   tr.mensaje_iniciador
              FROM tramite_movimiento m
              LEFT JOIN tipo_tramite_estado ed ON ed.id_tipo_tramite_estado = m.id_estado_destino
              LEFT JOIN tipo_tramite_transicion tr ON tr.id_tipo_tramite_transicion = m.id_tipo_tramite_transicion
             WHERE m.id_tramite = :t AND m.activo = TRUE AND m.tipo = ANY(:tipos)
             ORDER BY m.orden_secuencial
        """),
        {"t": id_tramite, "tipos": list(_TIPOS_HISTORIAL)})).mappings().all()
    pedidos = {p["id_tramite_pedido"]: p["texto"] for p in (await db.execute(
        text("SELECT id_tramite_pedido, texto FROM tramite_pedido_iniciador WHERE id_tramite = :t"),
        {"t": id_tramite})).mappings().all()}
    salida = []
    for m in movs:
        tipo, meta = m["tipo"], (m["metadata_jsonb"] or {})
        if tipo == "creacion":
            texto = "Iniciaste el trámite."
        elif tipo in ("transicion", "cambio_estado"):
            if m["destino_oculto"]:
                continue  # estado oculto al iniciador: ni la fila ni su mensaje
            texto = f"El trámite pasó a «{m['estado_destino']}»." if m["estado_destino"] else "El trámite avanzó."
            if m["mensaje_iniciador"]:
                texto += f" {m['mensaje_iniciador'].strip()}"
        elif tipo == "pedido_iniciador":
            idp = meta.get("id_tramite_pedido")
            texto = f"Te pidieron: {pedidos[idp]}" if idp in pedidos else "Te pidieron información o documentación."
        elif tipo == "respuesta_iniciador":
            texto = "Respondiste el pedido."
        elif tipo == "pedido_cancelado":
            texto = "El pedido que te hicieron se canceló."
        elif tipo == "resultado":
            texto = _TXT_RESULTADO.get(meta.get("resultado_nuevo"), "Se registró el resultado del trámite.")
        elif tipo == "aviso_iniciador":
            texto = "Te avisamos que el trámite sigue esperando tu respuesta."
        elif tipo == "desistido":
            texto = "El trámite se dio por desistido."
        elif tipo == "archivado_inactividad":
            texto = "El trámite se archivó por inactividad."
        elif tipo == "adjunto":
            if m["id_ciudadano_actor"] != id_ciudadano:
                continue  # los adjuntos del personal no se muestran
            texto = f"Subiste el documento «{meta.get('nombre') or 'archivo'}»."
        else:
            continue
        salida.append({"fecha": m["fecha_alta"], "texto": texto})
    return salida


@router.get("", response_model=list[MiTramiteOut])
async def mis_tramites(
    db: AsyncSession = Depends(get_db),
    ciudadano: dict = Depends(get_current_ciudadano),
    id_municipio: int = Depends(municipio_vecino),
):
    filas = (await db.execute(
        text(_SQL_MIS + " ORDER BY t.fecha_alta DESC, t.id_tramite DESC"),
        {"c": ciudadano["id_ciudadano"], "mun": id_municipio})).mappings().all()
    filas = await _mostrar_estado_visible(db, [dict(r) for r in filas])
    return [_resumen_out(r) for r in filas]


@router.get("/{id_tramite}", response_model=MiTramiteDetalleOut)
async def detalle_mi_tramite(
    id_tramite: int = Path_(..., ge=1, le=MAX_ID),
    db: AsyncSession = Depends(get_db),
    ciudadano: dict = Depends(get_current_ciudadano),
    id_municipio: int = Depends(municipio_vecino),
):
    id_c = ciudadano["id_ciudadano"]
    t = await _mi_tramite(db, id_tramite, id_c, id_municipio)
    docs = (await db.execute(
        text("SELECT id_tramite_documento, nombre, fecha_alta, binario_purgado FROM tramite_documento "
             "WHERE id_tramite = :t AND id_ciudadano_subio = :c AND activo = TRUE "
             "ORDER BY posicion_orden, id_tramite_documento"),
        {"t": id_tramite, "c": id_c})).mappings().all()
    del_paso = await svc_alta.documentos_del_paso(
        db, id_tramite, t["id_tipo_tramite_version"], t["id_tipo_tramite_estado_actual"],
        t["fecha_entrada_estado_actual"])
    pedido = (await db.execute(
        text("SELECT id_tramite_pedido, texto, pide_archivo, fecha_pedido FROM tramite_pedido_iniciador "
             "WHERE id_tramite = :t AND estado = 'abierto' AND activo = TRUE "
             "ORDER BY fecha_pedido DESC, id_tramite_pedido DESC LIMIT 1"),
        {"t": id_tramite})).mappings().first()
    return {
        **_resumen_out(t),
        "datos": await _datos_legibles(db, t["id_tipo_tramite_version"], t["datos_jsonb"]),
        "documentos": [dict(d) for d in docs],
        "documentos_del_paso": del_paso,
        "pedido_abierto": dict(pedido) if pedido else None,
        "historial": await _historial(db, id_tramite, id_c),
    }


@router.get("/{id_tramite}/documentos/{id_doc}/contenido")
async def contenido_documento(
    id_tramite: int = Path_(..., ge=1, le=MAX_ID),
    id_doc: int = Path_(..., ge=1, le=MAX_ID),
    db: AsyncSession = Depends(get_db),
    ciudadano: dict = Depends(get_current_ciudadano),
    id_municipio: int = Depends(municipio_vecino),
):
    id_c = ciudadano["id_ciudadano"]
    await _mi_tramite(db, id_tramite, id_c, id_municipio)
    doc = (await db.execute(
        text("SELECT storage_path, mime_type, nombre_archivo_original, binario_purgado FROM tramite_documento "
             "WHERE id_tramite_documento = :d AND id_tramite = :t AND id_ciudadano_subio = :c AND activo = TRUE"),
        {"d": id_doc, "t": id_tramite, "c": id_c})).mappings().first()
    if not doc:
        raise HTTPException(404, "Documento no encontrado")
    if doc["binario_purgado"]:
        raise HTTPException(410, "El archivo fue depurado por la política de retención. "
                                 "El registro del documento se conserva en el expediente.")
    contenido = await svc_docs.descargar_bytes(doc["storage_path"])
    nombre = (doc["nombre_archivo_original"] or "documento").replace('"', "").replace("\r", "").replace("\n", "")
    return Response(
        content=contenido,
        media_type=doc["mime_type"] or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{nombre}"'},
    )


@router.post("/{id_tramite}/documentos", status_code=201, response_model=DocumentosSubidosOut)
async def subir_documentos_del_paso(
    request: Request,
    background_tasks: BackgroundTasks,
    id_tramite: int = Path_(..., ge=1, le=MAX_ID),
    documentos: str = Form("[]"),
    archivos: list[UploadFile] = File(default=[]),
    db: AsyncSession = Depends(get_db),
    ciudadano: dict = Depends(get_current_ciudadano),
    id_municipio: int = Depends(municipio_vecino),
):
    check_rate_limit(f"trampubdoc:{get_real_ip(request)}", max_requests=20, window_seconds=60)
    id_c = ciudadano["id_ciudadano"]
    t = await _mi_tramite(db, id_tramite, id_c, id_municipio)

    if not archivos:
        raise HTTPException(422, "No se envió ningún archivo")
    if len(archivos) > MAX_ARCHIVOS_TOTAL:
        raise HTTPException(422, f"Se admiten hasta {MAX_ARCHIVOS_TOTAL} archivos por vez")
    docs_ids = _json_de_form(documentos, "documentos", list)
    if len(docs_ids) != len(archivos) or not all(isinstance(x, int) and not isinstance(x, bool) for x in docs_ids):
        raise HTTPException(422, "Cada archivo tiene que indicar a qué documento corresponde")

    pedidos = await svc_alta.documentos_del_paso(
        db, id_tramite, t["id_tipo_tramite_version"], t["id_tipo_tramite_estado_actual"],
        t["fecha_entrada_estado_actual"])
    docs_paso = {d["id_documento_requerido"]: d for d in pedidos}
    ya = {d["id_documento_requerido"]: int(d["subidos"]) for d in pedidos}
    await _validar_archivos(archivos, docs_ids, docs_paso, ya)

    numero = t["numero_expediente"]
    subidos: list[str] = []
    try:
        await _guardar_documentos(db, request, id_tramite, numero, id_municipio, id_c,
                                  archivos, docs_ids, docs_paso, subidos)
        await db.commit()
    except BaseException:
        await db.rollback()
        await svc_docs.borrar_archivos(subidos)
        raise

    await svc_notif.notificar_documento_vecino(db, id_tramite, background_tasks)
    return DocumentosSubidosOut(subidos=len(archivos))
