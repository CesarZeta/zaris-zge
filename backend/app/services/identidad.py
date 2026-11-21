"""
Identidad validada en el municipio (trámites del vecino, spec §5.10).

Un agente que vio el documento del vecino en persona deja constancia en la ficha
(`ciudadano_identidad_validacion`). Hay a lo sumo una validación ACTIVA por ciudadano
(único parcial `uq_ciudadano_identidad_activa`); revocarla la da de baja (`activo = false`)
conservando quién, cuándo y por qué, y se puede volver a validar.

Los tipos de trámite con `exige_identidad_validada` no se inician sin ella.
NO commitea: el llamador commitea.
"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

# Lo usa el portal del vecino (Task 4) cuando el tipo exige identidad y el vecino no la tiene.
MSG_IDENTIDAD_PORTAL = (
    "Para iniciar este trámite tenés que validar tu identidad en el municipio. "
    "Acercate con tu documento."
)
MSG_IDENTIDAD_BACKOFFICE = "Validá la identidad del vecino en su ficha antes de iniciar este trámite"
MSG_YA_VALIDADA = "La identidad de este vecino ya está validada"
MSG_SIN_VALIDACION = "El vecino no tiene una validación de identidad activa"


async def identidad_validada(db: AsyncSession, id_ciudadano: int) -> Optional[dict]:
    """`{fecha, agente_nombre}` de la validación activa, o None."""
    fila = (await db.execute(
        text("""SELECT v.fecha, TRIM(COALESCE(a.apellido, '') || ', ' || COALESCE(a.nombre, ''), ', ') AS agente_nombre
                  FROM ciudadano_identidad_validacion v
                  LEFT JOIN agentes a ON a.id_agente = v.id_agente
                 WHERE v.id_ciudadano = :c AND v.activo = TRUE
                 LIMIT 1"""),
        {"c": id_ciudadano},
    )).mappings().first()
    return dict(fila) if fila else None


async def validar_identidad(
    db: AsyncSession, *, id_ciudadano: int, id_municipio: int, id_agente: int,
    id_usuario: Optional[int], documento_presentado: str, observacion: Optional[str],
) -> None:
    if await identidad_validada(db, id_ciudadano):
        raise HTTPException(409, MSG_YA_VALIDADA)
    try:
        # SAVEPOINT: si pierde la carrera contra otra validación, la sesión sigue usable.
        async with db.begin_nested():
            await db.execute(
                text("""INSERT INTO ciudadano_identidad_validacion
                          (id_ciudadano, id_agente, documento_presentado, observacion,
                           id_municipio, id_usuario_alta, id_usuario_modificacion)
                        VALUES (:c, :ag, :doc, :obs, :mun, :u, :u)"""),
                {"c": id_ciudadano, "ag": id_agente, "doc": documento_presentado,
                 "obs": observacion, "mun": id_municipio, "u": id_usuario},
            )
    except IntegrityError:
        raise HTTPException(409, MSG_YA_VALIDADA)


async def revocar_identidad(
    db: AsyncSession, *, id_ciudadano: int, id_agente: Optional[int],
    id_usuario: Optional[int], motivo: str,
) -> None:
    res = await db.execute(
        text("""UPDATE ciudadano_identidad_validacion
                   SET activo = FALSE, motivo_revocacion = :m, id_agente_revoca = :ag,
                       fecha_revocacion = NOW(), fecha_modificacion = NOW(),
                       id_usuario_modificacion = :u
                 WHERE id_ciudadano = :c AND activo = TRUE"""),
        {"m": motivo, "ag": id_agente, "u": id_usuario, "c": id_ciudadano},
    )
    if res.rowcount == 0:
        raise HTTPException(404, MSG_SIN_VALIDACION)


async def exigir_identidad_para_tipo(db: AsyncSession, *, tipo: dict, id_ciudadano: Optional[int]) -> None:
    """422 si el tipo exige identidad validada y el ciudadano no la tiene (alta de backoffice)."""
    if tipo.get("exige_identidad_validada") and (
        not id_ciudadano or not await identidad_validada(db, id_ciudadano)
    ):
        raise HTTPException(422, MSG_IDENTIDAD_BACKOFFICE)
