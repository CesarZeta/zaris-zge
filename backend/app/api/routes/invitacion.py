"""
ZARIS API — Invitación a elegir la clave (IT-01 F4+F5, Tarea 11). Público.

POST /api/v1/auth/invitacion/aceptar  {token, password}
    Valida el token (vigente, sin usar; si no, 401 con el texto fijo), guarda la clave, marca la
    invitación como usada y habilita la vinculación del segundo factor (24 h; actor = el super que
    invitó). Responde lo mismo que el login para una cuenta en estado `vincular`: el shell sigue
    directo a vincular la app de códigos. Si la cuenta no requiere segundo factor (local, con
    SEGUNDO_FACTOR_OBLIGATORIO=false), responde {requiere_segundo_factor: false} y la persona ingresa
    con su clave.
"""
from types import SimpleNamespace

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import requiere_segundo_factor
from app.core.database import get_db
from app.middleware.rate_limit import check_rate_limit
from app.services import segundo_factor as sf
from app.services.municipios.invitacion import INVITACION_INVALIDA, tomar_invitacion
from app.utils.request_helpers import get_real_ip

router = APIRouter(prefix="/api/v1/auth/invitacion", tags=["Invitación"])


class AceptarIn(BaseModel):
    token: str = Field(..., min_length=20, max_length=200)
    password: str = Field(..., min_length=8, max_length=100)


@router.post("/aceptar", responses={401: {"description": INVITACION_INVALIDA},
                                    503: {"description": "Falta la configuración del segundo factor"}})
async def aceptar_invitacion(body: AceptarIn, request: Request, db: AsyncSession = Depends(get_db)):
    from app.api.routes.segundo_factor import respuesta_login
    check_rate_limit(f"invitacion:{get_real_ip(request)}", max_requests=10, window_seconds=60)
    try:
        sf.comprobar_configuracion()
    except sf.SegundoFactorNoConfigurado:
        raise HTTPException(503, "El segundo factor no está configurado")
    inv = await tomar_invitacion(db, body.token)
    usuario = (await db.execute(text(
        "SELECT id_usuario, id_municipio, nivel_acceso, activo FROM usuarios WHERE id_usuario = :u"),
        {"u": inv.id_usuario})).first()
    if usuario is None or not usuario.activo:
        raise HTTPException(401, INVITACION_INVALIDA)
    await db.execute(text("""
        UPDATE usuarios SET password_hash = :h, debe_cambiar_password = FALSE, password_actualizada_en = NOW(),
                            fecha_ultimo_email_recovery = NULL
         WHERE id_usuario = :u"""),
        {"h": bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode(), "u": inv.id_usuario})
    await db.execute(text("UPDATE usuario_invitacion SET usada_en = NOW() WHERE id_invitacion = :i"),
                     {"i": inv.id_invitacion})
    if not requiere_segundo_factor(usuario.nivel_acceso):
        await db.commit()
        return {"requiere_segundo_factor": False, "mensaje": "Listo: ya podés ingresar con tu correo y tu clave."}
    await sf.habilitar(db, id_usuario=inv.id_usuario, id_municipio=usuario.id_municipio, id_actor=inv.id_usuario_alta)
    await db.commit()
    return await respuesta_login(db, SimpleNamespace(id_usuario=usuario.id_usuario, id_municipio=usuario.id_municipio))
