"""
ZARIS — Login del usuario interno: lo que comparten el login con clave y el segundo paso
(IT-01 F3b). Una cuenta sin segundo factor termina acá desde `POST /auth/login`; una de nivel 0/1
termina acá desde `/auth/segundo-factor/verificar` o `/vinculacion/confirmar`, recién después
del código.
"""
import logging
from typing import Optional

from fastapi import HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_access_token, crear_token_super_admin, modulos_permitidos
from app.core.config_municipio import leer_config
from app.core.municipio import resolver_municipio_de_origen
from app.services.accesos_super import registrar_acceso_super
from app.utils.request_helpers import get_real_ip

logger = logging.getLogger("zaris.auth")

USUARIO_LOGIN_SELECT = """
    SELECT id_usuario, nombre, email, nivel_acceso, password_hash, activo,
           debe_cambiar_password, foto_url, id_municipio
      FROM usuarios
"""


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


async def cargar_usuario(db: AsyncSession, id_usuario: int):
    """La fila de la cuenta con las columnas del login, o None."""
    return (await db.execute(text(USUARIO_LOGIN_SELECT + " WHERE id_usuario = :id"),
                             {"id": id_usuario})).fetchone()


async def perfil_agente_del_usuario(db: AsyncSession, id_usuario: int) -> dict:
    """Cargo, subárea, secretaría (área de la subárea) y equipos del agente
    vinculado al usuario (regla 1:1 §39). Valores None / [] si el usuario no
    tiene agente (externo) o el agente no los tiene.
    La subárea la usan los módulos React para scopear pickers del supervisor
    (Fase 3 roles); la imposición dura vive en el backend de cada módulo.
    Secretaría y equipos son solo para mostrar en las vistas de perfil
    (topbar, menú del avatar, Mi perfil, app de agentes — pedido 2026-10-20)."""
    result = await db.execute(
        text("""SELECT c.nombre AS cargo_nombre,
                       a.id_subarea, s.nombre AS subarea_nombre,
                       s.id_area, ar.nombre AS area_nombre,
                       ARRAY(SELECT e.nombre
                               FROM equipo_agentes ea
                               JOIN equipos e ON e.id_equipo = ea.id_equipo
                              WHERE ea.id_agente = a.id_agente
                                AND ea.activo = TRUE AND e.activo = TRUE
                              ORDER BY e.nombre) AS equipos
                FROM agentes a
                LEFT JOIN cargos c ON c.id_cargo = a.id_cargo
                LEFT JOIN subarea s ON s.id_subarea = a.id_subarea
                LEFT JOIN area ar ON ar.id_area = s.id_area
                WHERE a.id_usuario = :id AND a.activo = TRUE
                LIMIT 1"""),
        {"id": id_usuario},
    )
    row = result.fetchone()
    if not row:
        return {"cargo_nombre": None, "id_subarea": None, "subarea_nombre": None,
                "id_area": None, "area_nombre": None, "equipos": []}
    return {"cargo_nombre": row.cargo_nombre, "id_subarea": row.id_subarea,
            "subarea_nombre": row.subarea_nombre,
            "id_area": row.id_area, "area_nombre": row.area_nombre,
            "equipos": list(row.equipos or [])}


async def _municipio_de_origen(request: Request, db: AsyncSession) -> Optional[int]:
    try:
        return await resolver_municipio_de_origen(request, db)
    except HTTPException:
        return None


async def completar_login(db: AsyncSession, request: Request, user, *, segundo_factor: bool) -> dict:
    """Auditoría del ingreso, renovación de clave y emisión del token. `user` es una fila con las
    columnas de USUARIO_LOGIN_SELECT. `segundo_factor` = la persona pasó el código (claim `sf`)."""
    ip = get_real_ip(request)
    ua = (request.headers.get("user-agent") or "")[:1000]
    es_super = user.nivel_acceso == 0

    if es_super:
        # El super administrador no tiene municipio: su login va al registro de accesos (global),
        # no a usuario_login_log. Si no se puede registrar, no entra.
        await registrar_acceso_super(
            id_usuario=user.id_usuario, accion="login", id_municipio=None, metodo="POST",
            ruta=request.url.path, detalle=f"desde el municipio {await _municipio_de_origen(request, db)}",
            ip=ip, user_agent=ua)

    # Auditoría de login: actualizar el último login (denormalizado para la UI)
    # e insertar la fila append-only en usuario_login_log. Best-effort: un fallo
    # acá no debe impedir el login.
    try:
        await db.execute(
            text("UPDATE usuarios SET fecha_ultimo_login = NOW() WHERE id_usuario = :id"),
            {"id": user.id_usuario},
        )
        if not es_super:
            await db.execute(
                text("""INSERT INTO usuario_login_log (id_usuario, ip, user_agent, id_municipio)
                        VALUES (:id, :ip, :ua, :mun)"""),
                {"id": user.id_usuario, "ip": ip[:64], "ua": ua, "mun": user.id_municipio},
            )
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        logger.warning("No se pudo registrar auditoría de login id=%s: %s", user.id_usuario, exc)

    # Politica de renovacion de credenciales (mig 96): si la clave supera la
    # vigencia configurada (password_renovacion_dias, 0 = desactivado), se
    # fuerza el cambio reutilizando el gate existente de debe_cambiar_password.
    debe_cambiar = bool(user.debe_cambiar_password)
    if not debe_cambiar:
        try:
            _vig = await leer_config(db, "password_renovacion_dias", user.id_municipio)
            _dias = int(str(_vig).strip()) if _vig is not None else 0
        except (TypeError, ValueError):
            _dias = 0
        if _dias > 0:
            vencida = await db.scalar(text("""
                SELECT 1 FROM usuarios
                WHERE id_usuario = :id
                  AND password_actualizada_en IS NOT NULL
                  AND password_actualizada_en < NOW() - make_interval(days => CAST(:d AS integer))
            """), {"id": user.id_usuario, "d": _dias})
            if vencida:
                await db.execute(text(
                    "UPDATE usuarios SET debe_cambiar_password = TRUE WHERE id_usuario = :id"
                ), {"id": user.id_usuario})
                await db.commit()
                debe_cambiar = True
                logger.info("RENOVACION PASSWORD forzada por vigencia | id=%s | dias=%s",
                            user.id_usuario, _dias)

    token = (crear_token_super_admin(user.id_usuario, segundo_factor=segundo_factor) if es_super
             else create_access_token({"sub": str(user.id_usuario), "mun": user.id_municipio,
                                       "sf": segundo_factor}))
    modulos = await modulos_permitidos(db, user.id_usuario, user.nivel_acceso)
    perfil = await perfil_agente_del_usuario(db, user.id_usuario)
    user_data = {
        "id_usuario": user.id_usuario,
        "nombre": user.nombre,
        "email": user.email,
        "nivel_acceso": user.nivel_acceso,
        "id_municipio": user.id_municipio,
        # Super administrador (IT-01 F3): el shell le muestra el selector de municipio.
        "es_super_admin": es_super,
        "modulos_permitidos": modulos,
        # Cargo del agente vinculado (None si externo/sin cargo) — lo muestra
        # el topbar del shell debajo de "Nombre · Rol".
        "cargo_nombre": perfil["cargo_nombre"],
        # Subárea del agente vinculado — los módulos React la usan para scopear
        # pickers cuando el usuario es supervisor (nivel 2, Fase 3 roles).
        "id_subarea": perfil["id_subarea"],
        "subarea_nombre": perfil["subarea_nombre"],
        # Secretaría y equipos del agente — solo para las vistas de perfil.
        "id_area": perfil["id_area"],
        "area_nombre": perfil["area_nombre"],
        "equipos": perfil["equipos"],
        "foto_url": user.foto_url,
        # Si TRUE, el frontend debe forzar el cambio de contraseña antes de
        # dejar usar el sistema (clave temporal en primer ingreso, o clave
        # vencida por la politica de renovacion mig 96).
        "debe_cambiar_password": debe_cambiar,
    }
    return {"access_token": token, "token_type": "bearer", "user": user_data}
