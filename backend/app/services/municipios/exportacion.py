"""
Exportación de los datos de un municipio (IT-01 F4+F5, Tarea 16; spec §4.8).

Un zip con un JSON por tabla (las `catalogo` y `operativo` y las filas propias de las `mixta`) en el
bucket privado `exportaciones`, ruta `m{id}/<AAAAMMDD-HHMMSS>.zip`. Vence a los
EXPORTACION_RETENCION_DIAS: la purga diaria borra el objeto. Es el resguardo previo a cada vaciado.
Corre en segundo plano con sesión propia; el estado queda en `municipio_tarea`.
"""
import io
import json
import logging
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.database import AsyncSessionLocal
from app.services.municipios.constantes import EXPORTACION_RETENCION_DIAS

logger = logging.getLogger("zaris.municipios")

BUCKET = "exportaciones"
# Secretos de cuentas que no salen en una exportación (el archivo puede llegar al municipio):
# claves, tokens de un solo uso, secretos del segundo factor y llaves de push.
COLUMNAS_SECRETAS = {"password_hash", "token_recovery", "token_activacion", "token_verificacion", "token_hash",
                     "secreto_cifrado", "secreto_pendiente_cifrado", "codigo_hash", "auth_secret", "p256dh"}


async def crear_tarea(db: AsyncSession, id_municipio: int, tipo: str, id_super: int,
                      detalle: Optional[dict] = None) -> uuid.UUID:
    return await db.scalar(text("""
        INSERT INTO municipio_tarea (id_municipio, tipo, detalle, id_usuario_alta)
        VALUES (:m, :t, CAST(:d AS jsonb), :u) RETURNING id_tarea"""),
        {"m": id_municipio, "t": tipo, "d": json.dumps(detalle or {}), "u": id_super})


async def marcar_tarea(id_tarea: uuid.UUID, estado: str, **campos) -> None:
    """Estado de la tarea en una sesión aparte: queda aunque la transacción del trabajo se revierta."""
    sets = ", ".join(f"{k} = :{k}" for k in campos)
    params = {"t": id_tarea, "e": estado, **campos}
    if "detalle" in campos:
        params["detalle"] = json.dumps(campos["detalle"])
        sets = sets.replace("detalle = :detalle", "detalle = CAST(:detalle AS jsonb)")
    async with AsyncSessionLocal() as db:
        await db.execute(text(f"UPDATE municipio_tarea SET estado = :e, fecha_modificacion = NOW()"
                              f"{', ' + sets if sets else ''} WHERE id_tarea = :t"), params)
        await db.commit()


async def _tablas_exportables(db: AsyncSession) -> list[str]:
    return [r[0] for r in (await db.execute(text("""
        SELECT t.tabla FROM municipio_tabla_clase t
         WHERE t.clase IN ('catalogo', 'operativo', 'mixta')
           AND EXISTS (SELECT 1 FROM information_schema.columns c
                        WHERE c.table_schema = 'public' AND c.table_name = t.tabla AND c.column_name = 'id_municipio')
         ORDER BY t.tabla"""))).all()]


async def armar_zip(db: AsyncSession, id_municipio: int) -> tuple[bytes, dict[str, int]]:
    buf = io.BytesIO()
    cantidades: dict[str, int] = {}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for tabla in await _tablas_exportables(db):
            filas = [{k: v for k, v in r._mapping.items() if k not in COLUMNAS_SECRETAS} for r in (await db.execute(
                text(f'SELECT * FROM "{tabla}" WHERE id_municipio = :m'), {"m": id_municipio})).all()]
            cantidades[tabla] = len(filas)
            z.writestr(f"{tabla}.json", json.dumps(filas, default=str, ensure_ascii=False))
    return buf.getvalue(), cantidades


async def ejecutar_exportacion(id_tarea: uuid.UUID, id_municipio: int) -> bool:
    """Arma el zip y lo sube. True si terminó ok. Nunca levanta: el error queda en la tarea."""
    await marcar_tarea(id_tarea, "corriendo")
    try:
        async with AsyncSessionLocal() as db:
            contenido, cantidades = await armar_zip(db, id_municipio)
        ruta = f"m{id_municipio}/{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{str(id_tarea)[:8]}.zip"
        await storage.subir_objeto(ruta, contenido, "application/zip", bucket=BUCKET)
        async with AsyncSessionLocal() as db:
            await db.execute(text("""
                UPDATE municipio_tarea SET estado = 'ok', archivo = :a, fecha_modificacion = NOW(),
                       vence_en = NOW() + make_interval(days => :d), detalle = CAST(:det AS jsonb)
                 WHERE id_tarea = :t"""),
                {"a": ruta, "d": EXPORTACION_RETENCION_DIAS, "t": id_tarea,
                 "det": json.dumps({"filas": sum(cantidades.values()), "tablas": len(cantidades)})})
            await db.commit()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.exception("exportación del municipio %s", id_municipio)
        await marcar_tarea(id_tarea, "error", detalle={"error": str(exc)[:500]})
        return False


async def purgar_vencidas() -> int:
    """Borra el objeto de las exportaciones vencidas y las marca (archivo NULL). Devuelve cuántas."""
    async with AsyncSessionLocal() as db:
        vencidas = (await db.execute(text("""
            SELECT id_tarea, archivo FROM municipio_tarea
             WHERE tipo = 'exportacion' AND archivo IS NOT NULL AND vence_en < NOW()"""))).all()
    purgadas = 0
    for v in vencidas:
        try:
            await storage.borrar_objeto(v.archivo, bucket=BUCKET)
        except Exception:  # noqa: BLE001
            logger.exception("purga de la exportación %s", v.id_tarea)
            continue
        async with AsyncSessionLocal() as db:
            await db.execute(text("""
                UPDATE municipio_tarea SET archivo = NULL, fecha_modificacion = NOW(),
                       detalle = COALESCE(detalle, '{}'::jsonb) || jsonb_build_object('purgada', NOW())
                 WHERE id_tarea = :t"""), {"t": v.id_tarea})
            await db.commit()
        purgadas += 1
    return purgadas
