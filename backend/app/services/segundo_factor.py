"""
ZARIS — Segundo factor de las cuentas de nivel 0 y 1 (IT-01 F3b).

Código de 6 dígitos de una app de autenticación (TOTP, RFC 6238), con:
- el secreto cifrado (Fernet, `SEGUNDO_FACTOR_CLAVE`) en `usuario_segundo_factor`, fuera de `usuarios`;
- vinculación solo dentro de las 24 h siguientes a que el super la habilite;
- anti-repetición por paso de 30 s, atómico (`UPDATE … WHERE ultimo_paso < :paso`);
- 10 códigos de emergencia de un solo uso (bcrypt);
- bloqueo persistente de 15 min tras 5 fallos consecutivos;
- eventos append-only en `usuario_segundo_factor_evento`.

Ninguna función commitea: commitea el caller. Spec: PLAN_MULTI_MUNICIPIO_F3B_DISENO.md.
"""
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import bcrypt
import pyotp
import segno
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

PASO_SEGUNDOS = 30
DIGITOS = 6
VENTANA = 1  # pasos de tolerancia a cada lado (relojes corridos)
DESAFIO_MINUTOS = 5
INTENTOS_MAX = 5
BLOQUEO_MINUTOS = 15
HABILITACION_HORAS = 24
CANTIDAD_CODIGOS = 10
EMISOR = "ZARIS"
_ALFABETO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # sin 0/O, 1/I/L: se dictan y se copian a mano


class SegundoFactorNoConfigurado(Exception):
    """Falta `SEGUNDO_FACTOR_CLAVE`, no es una clave Fernet o no descifra lo guardado."""


@dataclass
class EstadoCuenta:
    vinculada: bool
    confirmado_en: Optional[datetime]
    habilitado_hasta: Optional[datetime]
    bloqueado_hasta: Optional[datetime]  # solo si el bloqueo sigue vigente
    habilitada: bool  # habilitado_hasta > ahora


# ── Cifrado ─────────────────────────────────────────────────────────────────

def _fernet() -> Fernet:
    clave = settings.SEGUNDO_FACTOR_CLAVE
    if not clave:
        raise SegundoFactorNoConfigurado("SEGUNDO_FACTOR_CLAVE vacía")
    try:
        return Fernet(clave.encode())
    except (ValueError, TypeError) as e:
        raise SegundoFactorNoConfigurado("SEGUNDO_FACTOR_CLAVE no es una clave Fernet") from e


def comprobar_configuracion() -> None:
    """Lanza SegundoFactorNoConfigurado si la clave falta o no es una clave Fernet."""
    _fernet()


def cifrar(secreto: str) -> str:
    return _fernet().encrypt(secreto.encode()).decode()


def descifrar(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as e:
        raise SegundoFactorNoConfigurado("el secreto no descifra con SEGUNDO_FACTOR_CLAVE") from e


# ── Códigos ─────────────────────────────────────────────────────────────────

def normalizar_codigo(texto: str) -> str:
    return "".join(ch for ch in (texto or "") if ch.isdigit())


def normalizar_codigo_emergencia(texto: str) -> str:
    return "".join(ch for ch in (texto or "").upper() if ch.isalnum())


def generar_codigos_emergencia() -> list[str]:
    codigos = []
    for _ in range(CANTIDAD_CODIGOS):
        c = "".join(secrets.choice(_ALFABETO) for _ in range(10))
        codigos.append(f"{c[:5]}-{c[5:]}")
    return codigos


def _paso_valido(secreto: str, codigo: str) -> Optional[int]:
    """Paso de 30 s (actual ±VENTANA) en el que `codigo` es el TOTP de `secreto`, o None."""
    codigo = normalizar_codigo(codigo)
    if len(codigo) != DIGITOS:
        return None
    totp = pyotp.TOTP(secreto, digits=DIGITOS, interval=PASO_SEGUNDOS)
    actual = totp.timecode(datetime.now(timezone.utc))
    for paso in range(actual - VENTANA, actual + VENTANA + 1):
        if hmac.compare_digest(totp.generate_otp(paso), codigo):
            return paso
    return None


# ── Estado y eventos ────────────────────────────────────────────────────────

async def registrar_evento(db: AsyncSession, *, id_usuario: int, id_municipio: Optional[int], evento: str,
                           id_actor: Optional[int] = None, ip: Optional[str] = None,
                           user_agent: Optional[str] = None) -> None:
    await db.execute(text("""
        INSERT INTO usuario_segundo_factor_evento
            (id_usuario, id_municipio, evento, id_usuario_actor, ip, user_agent)
        VALUES (:u, :m, :e, :a, :ip, :ua)"""),
        {"u": id_usuario, "m": id_municipio, "e": evento, "a": id_actor,
         "ip": (ip or None) and ip[:64], "ua": (user_agent or None) and user_agent[:1000]})


async def estado_cuenta(db: AsyncSession, id_usuario: int) -> EstadoCuenta:
    fila = (await db.execute(text("""
        SELECT secreto_cifrado IS NOT NULL AS vinculada, confirmado_en, habilitado_hasta,
               CASE WHEN bloqueado_hasta > NOW() THEN bloqueado_hasta END AS bloqueado_hasta,
               COALESCE(habilitado_hasta > NOW(), FALSE) AS habilitada
          FROM usuario_segundo_factor WHERE id_usuario = :u"""), {"u": id_usuario})).fetchone()
    if fila is None:
        return EstadoCuenta(vinculada=False, confirmado_en=None, habilitado_hasta=None,
                            bloqueado_hasta=None, habilitada=False)
    return EstadoCuenta(vinculada=fila.vinculada, confirmado_en=fila.confirmado_en,
                        habilitado_hasta=fila.habilitado_hasta, bloqueado_hasta=fila.bloqueado_hasta,
                        habilitada=fila.habilitada)


async def bloqueada(db: AsyncSession, id_usuario: int) -> bool:
    return bool((await db.execute(text(
        "SELECT bloqueado_hasta > NOW() FROM usuario_segundo_factor WHERE id_usuario = :u"),
        {"u": id_usuario})).scalar())


async def registrar_fallo(db: AsyncSession, *, id_usuario: int) -> bool:
    """Suma un fallo. Al quinto bloquea 15 min (y vuelve el contador a 0). True si bloqueó."""
    fila = (await db.execute(text("""
        UPDATE usuario_segundo_factor
           SET intentos_fallidos = intentos_fallidos + 1, fecha_modificacion = NOW()
         WHERE id_usuario = :u
     RETURNING intentos_fallidos, id_municipio"""), {"u": id_usuario})).fetchone()
    if fila is None or fila.intentos_fallidos < INTENTOS_MAX:
        return False
    await db.execute(text("""
        UPDATE usuario_segundo_factor
           SET bloqueado_hasta = NOW() + make_interval(mins => :min), intentos_fallidos = 0,
               fecha_modificacion = NOW()
         WHERE id_usuario = :u"""), {"u": id_usuario, "min": BLOQUEO_MINUTOS})
    await registrar_evento(db, id_usuario=id_usuario, id_municipio=fila.id_municipio, evento="bloqueo")
    return True


async def _marcar_sesiones(db: AsyncSession, id_usuario: int) -> None:
    """Revoca los tokens emitidos antes de este segundo (get_current_user compara su iat)."""
    await db.execute(text(
        "UPDATE usuarios SET sesiones_validas_desde = date_trunc('second', NOW()) WHERE id_usuario = :u"),
        {"u": id_usuario})


# ── Habilitación y vinculación ──────────────────────────────────────────────

async def habilitar(db: AsyncSession, *, id_usuario: int, id_municipio: Optional[int],
                    id_actor: Optional[int]) -> None:
    """Restablece y habilita: borra secretos y códigos, corta las sesiones y abre 24 h para vincular."""
    await db.execute(text("""
        INSERT INTO usuario_segundo_factor
            (id_usuario, id_municipio, habilitado_hasta, id_usuario_alta, id_usuario_modificacion)
        VALUES (:u, :m, NOW() + make_interval(hours => :h), :a, :a)
        ON CONFLICT (id_usuario) DO UPDATE
           SET secreto_cifrado = NULL, secreto_pendiente_cifrado = NULL, confirmado_en = NULL,
               ultimo_paso = NULL, intentos_fallidos = 0, bloqueado_hasta = NULL,
               habilitado_hasta = EXCLUDED.habilitado_hasta, id_municipio = EXCLUDED.id_municipio,
               id_usuario_modificacion = EXCLUDED.id_usuario_modificacion, fecha_modificacion = NOW()"""),
        {"u": id_usuario, "m": id_municipio, "h": HABILITACION_HORAS, "a": id_actor})
    await db.execute(text(
        "UPDATE usuario_codigo_emergencia SET activo = FALSE WHERE id_usuario = :u AND activo"),
        {"u": id_usuario})
    await _marcar_sesiones(db, id_usuario)
    await registrar_evento(db, id_usuario=id_usuario, id_municipio=id_municipio, evento="habilitado",
                           id_actor=id_actor)


async def iniciar_vinculacion(db: AsyncSession, *, id_usuario: int, id_municipio: Optional[int],
                              etiqueta: str) -> dict:
    """Secreto nuevo, guardado como PENDIENTE (reemplaza a otro pendiente). El confirmado, si lo
    hay, sigue valiendo hasta que se confirme este."""
    secreto = pyotp.random_base32()
    await db.execute(text("""
        INSERT INTO usuario_segundo_factor (id_usuario, id_municipio, secreto_pendiente_cifrado)
        VALUES (:u, :m, :p)
        ON CONFLICT (id_usuario) DO UPDATE
           SET secreto_pendiente_cifrado = EXCLUDED.secreto_pendiente_cifrado, fecha_modificacion = NOW()"""),
        {"u": id_usuario, "m": id_municipio, "p": cifrar(secreto)})
    uri = pyotp.TOTP(secreto, digits=DIGITOS, interval=PASO_SEGUNDOS).provisioning_uri(
        name=etiqueta, issuer_name=EMISOR)
    return {"qr": segno.make(uri, error="m").svg_data_uri(scale=6), "secreto": secreto,
            "emisor": EMISOR, "cuenta": etiqueta}


async def confirmar_vinculacion(db: AsyncSession, *, id_usuario: int, codigo: str) -> Optional[list[str]]:
    """Si `codigo` vale contra el secreto PENDIENTE: lo confirma, cambia los códigos de emergencia,
    corta las sesiones anteriores y devuelve los 10 códigos nuevos en claro. Si no, None."""
    fila = (await db.execute(text("""
        SELECT secreto_pendiente_cifrado, id_municipio FROM usuario_segundo_factor
         WHERE id_usuario = :u AND secreto_pendiente_cifrado IS NOT NULL"""), {"u": id_usuario})).fetchone()
    if fila is None:
        return None
    paso = _paso_valido(descifrar(fila.secreto_pendiente_cifrado), codigo)
    if paso is None:
        return None
    confirmada = (await db.execute(text("""
        UPDATE usuario_segundo_factor
           SET secreto_cifrado = secreto_pendiente_cifrado, secreto_pendiente_cifrado = NULL,
               confirmado_en = NOW(), ultimo_paso = :p, habilitado_hasta = NULL,
               intentos_fallidos = 0, bloqueado_hasta = NULL, fecha_modificacion = NOW()
         WHERE id_usuario = :u AND secreto_pendiente_cifrado = :pend
     RETURNING 1"""), {"u": id_usuario, "p": paso, "pend": fila.secreto_pendiente_cifrado})).scalar()
    if not confirmada:
        return None  # otra vinculación reemplazó el pendiente entre la lectura y la escritura
    await db.execute(text(
        "UPDATE usuario_codigo_emergencia SET activo = FALSE WHERE id_usuario = :u AND activo"),
        {"u": id_usuario})
    codigos = generar_codigos_emergencia()
    for c in codigos:
        await db.execute(text("""
            INSERT INTO usuario_codigo_emergencia (id_usuario, id_municipio, codigo_hash)
            VALUES (:u, :m, :h)"""),
            {"u": id_usuario, "m": fila.id_municipio,
             "h": bcrypt.hashpw(normalizar_codigo_emergencia(c).encode(), bcrypt.gensalt(rounds=10)).decode()})
    await _marcar_sesiones(db, id_usuario)
    return codigos


# ── Verificación ────────────────────────────────────────────────────────────

async def verificar_codigo(db: AsyncSession, *, id_usuario: int, codigo: str) -> bool:
    """True si `codigo` vale contra el secreto CONFIRMADO y su paso no se usó todavía. El paso
    queda tomado en el mismo UPDATE (dos envíos simultáneos del mismo código: uno solo gana)."""
    cifrado = (await db.execute(text("""
        SELECT secreto_cifrado FROM usuario_segundo_factor
         WHERE id_usuario = :u AND secreto_cifrado IS NOT NULL"""), {"u": id_usuario})).scalar()
    if cifrado is None:
        return False
    paso = _paso_valido(descifrar(cifrado), codigo)
    if paso is None:
        return False
    return bool((await db.execute(text("""
        UPDATE usuario_segundo_factor
           SET ultimo_paso = :p, intentos_fallidos = 0, fecha_modificacion = NOW()
         WHERE id_usuario = :u AND (ultimo_paso IS NULL OR ultimo_paso < :p)
     RETURNING 1"""), {"u": id_usuario, "p": paso})).scalar())


async def usar_codigo_emergencia(db: AsyncSession, *, id_usuario: int, codigo: str) -> bool:
    """True si `codigo` es uno de los códigos de emergencia vigentes; queda usado."""
    norm = normalizar_codigo_emergencia(codigo)
    if len(norm) != 10:
        return False
    filas = (await db.execute(text("""
        SELECT id_codigo_emergencia, codigo_hash FROM usuario_codigo_emergencia
         WHERE id_usuario = :u AND activo AND usado_en IS NULL"""), {"u": id_usuario})).fetchall()
    for f in filas:
        if bcrypt.checkpw(norm.encode(), f.codigo_hash.encode()):
            return bool((await db.execute(text("""
                UPDATE usuario_codigo_emergencia SET usado_en = NOW()
                 WHERE id_codigo_emergencia = :id AND usado_en IS NULL
             RETURNING 1"""), {"id": f.id_codigo_emergencia})).scalar())
    return False
