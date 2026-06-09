"""
Servicio: crear la cuenta de App Vecinos (credencial + canal + mail de activación)
para un ciudadano YA existente.

Se usa cuando un agente da de alta un ciudadano desde el frontend de Ciudadanos
(BUC): además de la persona en el padrón, se le crea automáticamente la cuenta de
portal y se le manda el mail de activación al email cargado. El vecino abre el mail,
se loguea y elige su propia clave (activación por token, NO clave temporal — §38
Camino B). Es el mismo mecanismo de POST /publico/auth/registrar, pero acá el
ciudadano ya viene con su ficha completa cargada por el agente.

Idempotente: si el ciudadano ya tiene credencial activa, no la duplica
(ciudadano_credencial es 1:1). Si existe sin activar, regenera el token y reenvía.
"""
import logging

from fastapi import BackgroundTasks
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.email import enviar_mail_activacion_ciudadano

logger = logging.getLogger("zaris.cuenta_vecino")

DIAS_ACTIVACION = 7


async def _municipio_branding(db: AsyncSession) -> tuple[str, str | None]:
    """Devuelve (municipio_nombre, municipio_logo_url) leyendo configuracion_general."""
    res = await db.execute(
        text(
            "SELECT clave, valor FROM configuracion_general "
            "WHERE clave IN ('municipio_nombre','municipio_logo_url')"
        )
    )
    cfg = {r.clave: r.valor for r in res.fetchall()}
    return (
        cfg.get("municipio_nombre") or "Tu municipio",
        cfg.get("municipio_logo_url") or None,
    )


async def asegurar_cuenta_vecino(
    db: AsyncSession,
    *,
    id_ciudadano: int,
    nombre: str,
    apellido: str,
    email: str,
    id_municipio: int | None,
    id_usuario_alta: int | None,
    background_tasks: BackgroundTasks,
) -> bool:
    """
    Crea (si no existe) la credencial + canal preferido del ciudadano y encola el
    mail de activación. Devuelve True si se encoló un mail (cuenta nueva o token
    regenerado), False si la cuenta ya estaba activada (no se hace nada).

    NO commitea — el caller controla la transacción. El mail se encola y corre
    después del commit del caller (BackgroundTasks).
    """
    # ¿Ya tiene credencial?
    res = await db.execute(
        text(
            "SELECT id_ciudadano_credencial, activado FROM ciudadano_credencial "
            "WHERE id_ciudadano = :id"
        ),
        {"id": id_ciudadano},
    )
    cred = res.fetchone()

    if cred and cred.activado:
        # Ya tiene cuenta activa: no tocar, no reenviar.
        logger.info("cuenta_vecino: ciudadano %s ya tiene cuenta activada, skip", id_ciudadano)
        return False

    if cred and not cred.activado:
        # Existe sin activar: regenerar token y reenviar.
        res = await db.execute(
            text(f"""
                UPDATE ciudadano_credencial
                   SET token_activacion = gen_random_uuid(),
                       token_activacion_expira = NOW() + INTERVAL '{DIAS_ACTIVACION} days',
                       fecha_ultimo_email_activacion = NOW(),
                       fecha_modificacion = NOW()
                 WHERE id_ciudadano_credencial = :id
                 RETURNING token_activacion
            """),
            {"id": cred.id_ciudadano_credencial},
        )
        token = str(res.fetchone().token_activacion)
    else:
        # No existe: crear credencial + canal preferido.
        res = await db.execute(
            text(f"""
                INSERT INTO ciudadano_credencial
                    (id_ciudadano, password_hash, token_activacion, token_activacion_expira,
                     activado, fecha_ultimo_email_activacion,
                     activo, id_municipio, fecha_alta, fecha_modificacion, id_usuario_alta)
                VALUES
                    (:id, NULL, gen_random_uuid(), NOW() + INTERVAL '{DIAS_ACTIVACION} days',
                     FALSE, NOW(),
                     TRUE, :mun, NOW(), NOW(), :ua)
                RETURNING token_activacion
            """),
            {"id": id_ciudadano, "mun": id_municipio, "ua": id_usuario_alta},
        )
        token = str(res.fetchone().token_activacion)

        # Canal preferido (idempotente por si existiera huérfano)
        await db.execute(
            text("""
                INSERT INTO ciudadano_canal_preferido
                    (id_ciudadano, canal_email, canal_push, canal_whatsapp, canal_sms,
                     activo, id_municipio, fecha_alta, fecha_modificacion, id_usuario_alta)
                SELECT :id, TRUE, TRUE, FALSE, FALSE, TRUE, :mun, NOW(), NOW(), :ua
                 WHERE NOT EXISTS (
                    SELECT 1 FROM ciudadano_canal_preferido WHERE id_ciudadano = :id
                 )
            """),
            {"id": id_ciudadano, "mun": id_municipio, "ua": id_usuario_alta},
        )

        # Lo da de alta un agente → identidad verificada (espeja POST /publico/auth/registrar).
        # `estado_validacion` es columna de DB pero NO está mapeada en el modelo ORM
        # Ciudadano, por eso se setea con UPDATE directo (no por setattr).
        await db.execute(
            text("""
                UPDATE ciudadanos SET estado_validacion = 'verificado', fecha_modificacion = NOW()
                 WHERE id_ciudadano = :id AND estado_validacion <> 'verificado'
            """),
            {"id": id_ciudadano},
        )

    municipio_nombre, municipio_logo_url = await _municipio_branding(db)
    background_tasks.add_task(
        enviar_mail_activacion_ciudadano,
        email,
        nombre,
        apellido,
        token,
        municipio_nombre,
        settings.APP_VECINOS_FRONTEND_URL,
        municipio_logo_url,
    )
    logger.info("cuenta_vecino: activacion encolada para ciudadano %s (%s)", id_ciudadano, email)
    return True
