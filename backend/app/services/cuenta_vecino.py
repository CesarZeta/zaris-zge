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

Fichas demo (mig 118): la persona con DNI del rango reservado 99.000.000 + id_agente no
tiene cuenta de App Vecinos por ninguna vía. El vecino entra con su DNI y ese DNI es
ficticio, y el email es el de la cuenta ZARIS (`@municipio.gob.ar`, que no recibe mail).
Al cargar el DNI real en la ficha, el próximo guardado le crea la cuenta como a cualquiera.
"""
import logging
import re

from fastapi import BackgroundTasks
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.config_municipio import leer_configs
from app.services.email import enviar_mail_activacion_ciudadano

logger = logging.getLogger("zaris.cuenta_vecino")

DIAS_ACTIVACION = 7

# Rango reservado de las fichas demo de funcionarios (mig 118): 99.000.000 + id_agente.
_DNI_FICHA_DEMO = re.compile(r"^99\d{6}$")
MSG_FICHA_DEMO = (
    "Esta ficha tiene un DNI de prueba (rango 99.000.000): no se le crea la cuenta de "
    "App Vecinos. Cargá el DNI real de la persona y guardá la ficha."
)


def es_ficha_demo(doc_tipo: str | None, doc_nro: str | None) -> bool:
    """True si la ficha es una de las fichas demo de funcionarios (DNI del rango reservado)."""
    return (doc_tipo or "").upper() == "DNI" and bool(_DNI_FICHA_DEMO.match((doc_nro or "").strip()))


async def _municipio_branding(db: AsyncSession, id_municipio: int) -> tuple[str, str | None]:
    """Devuelve (municipio_nombre, municipio_logo_url) del municipio, desde configuracion_general."""
    cfg = await leer_configs(db, ["municipio_nombre", "municipio_logo_url"], id_municipio)
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
    id_municipio: int,
    id_usuario_alta: int | None,
    background_tasks: BackgroundTasks,
) -> bool:
    """
    Crea (si no existe) la credencial + canal preferido del ciudadano y encola el
    mail de activación. Devuelve True si se encoló un mail (cuenta nueva o token
    regenerado), False si la cuenta ya estaba activada o la ficha es demo (no se hace nada).

    NO commitea — el caller controla la transacción. El mail se encola y corre
    después del commit del caller (BackgroundTasks).
    """
    # Lee el DNI de la DB (no del caller): un PUT que acaba de cargar el DNI real ya
    # hizo flush, así que ese mismo guardado crea la cuenta.
    doc = (await db.execute(
        text("SELECT doc_tipo, doc_nro FROM ciudadanos WHERE id_ciudadano = :id"),
        {"id": id_ciudadano},
    )).fetchone()
    if doc and es_ficha_demo(doc.doc_tipo, doc.doc_nro):
        logger.info("cuenta_vecino: ciudadano %s es ficha demo (DNI de prueba), skip", id_ciudadano)
        return False

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

    municipio_nombre, municipio_logo_url = await _municipio_branding(db, id_municipio)
    background_tasks.add_task(
        enviar_mail_activacion_ciudadano,
        email,
        nombre,
        apellido,
        token,
        municipio_nombre,
        settings.APP_VECINOS_FRONTEND_URL,
        municipio_logo_url,
        id_municipio=id_municipio,
    )
    logger.info("cuenta_vecino: activacion encolada para ciudadano %s (%s)", id_ciudadano, email)
    return True
