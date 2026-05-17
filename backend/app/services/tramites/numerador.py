"""
Servicio de numeracion atomica para tramites.

Formato configurable por tipo:
  {prefijo}{sep}{codigo_municipio}{sep}{anio}{sep}{correlativo_padded}
  Ej: POD-LPL-2026-0001

La obtencion del proximo numero usa INSERT ON CONFLICT DO UPDATE para evitar
race conditions sin necesitar bloqueos de tabla.
"""
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def proximo_numero(
    db: AsyncSession,
    id_tipo_tramite: int,
    id_municipio: int,
    anio: int | None = None,
) -> int:
    """Obtiene y reserva el proximo correlativo para (tipo, anio, municipio).

    Atomico via INSERT ... ON CONFLICT DO UPDATE RETURNING.
    """
    if anio is None:
        anio = datetime.utcnow().year

    result = await db.execute(
        text("""
            INSERT INTO tipo_tramite_numerador (id_tipo_tramite, anio, id_municipio, ultimo_numero)
            VALUES (:tipo, :anio, :mun, 1)
            ON CONFLICT (id_tipo_tramite, anio, id_municipio)
            DO UPDATE SET
                ultimo_numero    = tipo_tramite_numerador.ultimo_numero + 1,
                fecha_modificacion = NOW()
            RETURNING ultimo_numero
        """),
        {"tipo": id_tipo_tramite, "anio": anio, "mun": id_municipio},
    )
    row = result.fetchone()
    return row[0]


def formatear_numero(
    prefijo: str,
    separador: str,
    incluye_municipio: bool,
    incluye_anio: bool,
    codigo_municipio: str,
    anio: int,
    correlativo: int,
    largo_correlativo: int,
) -> str:
    """Construye el string del numero de expediente segun config del tipo."""
    partes = [prefijo]
    if incluye_municipio and codigo_municipio:
        partes.append(codigo_municipio)
    if incluye_anio:
        partes.append(str(anio))
    partes.append(str(correlativo).zfill(largo_correlativo))
    return separador.join(partes)
