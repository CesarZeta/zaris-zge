"""
ZARIS API — Autenticación JWT + hashing de contraseñas.

Soporta dos scopes:
- scope='agente' (default): usuarios internos (tabla usuarios). Vigencia 24h.
- scope='publico': ciudadanos de la BUC con credencial (tabla ciudadano_credencial). Vigencia 30d.
Cada guard rechaza tokens del otro scope con 401.

Multi-municipio (IT-01): los dos tokens llevan el claim `mun` (municipio de la cuenta). Un token
sin `mun` (emitido antes del corte) da 401 «Sesión vencida» y la persona vuelve a ingresar. Si la
request trae header Origin, `mun` tiene que coincidir con el municipio de ese origen.

Super administrador (IT-01 F3): nivel 0 sin municipio, token con `sa=True` y sin `mun`. Ante el
resto del código se presenta como administrador (`nivel_acceso` efectivo 1) con la marca
`es_super_admin`; `nivel_real` guarda el 0. Solo lo distinguen a propósito la historia clínica y
lo exclusivo del super administrador. Su municipio sale del header X-Municipio, en
`municipio_actual` (app/core/municipio.py). Plan: PLAN_MULTI_MUNICIPIO_F3.md.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import bcrypt as _bcrypt
from jose import JWTError, jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db

bearer_scheme = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 1440  # 24 h (scope='agente')
# Super administrador: 8 h (decisión de César, 2026-10-26; con F3b quedó definitiva): un token
# robado del rol máximo no debe servir un día entero.
SUPER_ADMIN_TOKEN_MINUTES = 480
SESION_VENCIDA = "Sesión vencida. Volvé a ingresar."

# Segundo factor (IT-01 F3b): niveles que entran con la clave más el código de la app. Ampliarlo
# es cambiar este conjunto y nada más.
NIVELES_CON_SEGUNDO_FACTOR: frozenset[int] = frozenset({0, 1})


def requiere_segundo_factor(nivel_real: int) -> bool:
    return settings.SEGUNDO_FACTOR_OBLIGATORIO and nivel_real in NIVELES_CON_SEGUNDO_FACTOR


def _ahora_epoch() -> int:
    return int(datetime.now(timezone.utc).timestamp())


async def _validar_municipio_token(mun, id_municipio_cuenta: int, request: Request, db: AsyncSession) -> None:
    """El claim `mun` existe, es el de la cuenta y, si hay Origin, el del municipio de ese origen."""
    no_vale = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=SESION_VENCIDA,
                            headers={"WWW-Authenticate": "Bearer"})
    if not isinstance(mun, int) or mun != id_municipio_cuenta:
        raise no_vale
    if request.headers.get("origin"):
        from app.core.municipio import resolver_municipio_de_origen  # import tardío: municipio importa este módulo
        try:
            mun_origen = await resolver_municipio_de_origen(request, db)
        except HTTPException:
            raise no_vale
        if mun_origen != mun:
            raise no_vale


def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Emite JWT para agente (scope='agente' por default). `data` lleva `sub` y `mun` (municipio);
    `sf=True` si la persona pasó el segundo factor. Lleva `iat` para la revocación (F3b)."""
    if not isinstance(data.get("mun"), int):
        raise ValueError("create_access_token: falta el municipio (claim 'mun')")
    to_encode = data.copy()
    # Default scope para todos los tokens emitidos por este helper.
    to_encode.setdefault("scope", "agente")
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=TOKEN_EXPIRE_MINUTES))
    to_encode["exp"] = expire
    to_encode.setdefault("iat", _ahora_epoch())
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def crear_token_super_admin(id_usuario: int, *, segundo_factor: bool) -> str:
    """JWT del super administrador: `sa=True` y sin `mun` (no tiene municipio). Vence a las 8 h
    (SUPER_ADMIN_TOKEN_MINUTES). `sf` = pasó el segundo factor; `iat` para la revocación."""
    return jwt.encode({
        "sub": str(id_usuario),
        "scope": "agente",
        "sa": True,
        "sf": segundo_factor,
        "iat": _ahora_epoch(),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=SUPER_ADMIN_TOKEN_MINUTES),
    }, settings.SECRET_KEY, algorithm=ALGORITHM)


def crear_token_ciudadano(id_ciudadano: int, id_municipio: int, expira_dias: Optional[int] = None) -> str:
    """Emite JWT para ciudadano publico. Vigencia configurable via JWT_PUBLICO_EXPIRA_DIAS (default 30)."""
    dias = expira_dias if expira_dias is not None else settings.JWT_PUBLICO_EXPIRA_DIAS
    to_encode = {
        "sub": str(id_ciudadano),
        "mun": id_municipio,
        "scope": "publico",
        "exp": datetime.now(timezone.utc) + timedelta(days=dias),
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Guard para endpoints de agentes internos. Rechaza tokens scope!='agente' y sin municipio."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autenticado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not credentials:
        raise unauthorized
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        # Default a 'agente' para tokens viejos emitidos antes del scope claim.
        scope = payload.get("scope", "agente")
        if user_id is None:
            raise unauthorized
        if scope != "agente":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Este endpoint requiere autenticacion de agente",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError:
        raise unauthorized

    result = await db.execute(
        text("""SELECT id_usuario, nombre, email, nivel_acceso, activo,
                       debe_cambiar_password, foto_url, id_municipio, sesiones_validas_desde
                FROM usuarios WHERE id_usuario = :id"""),
        {"id": int(user_id)},
    )
    user = result.fetchone()
    if not user or not user.activo:
        raise unauthorized
    vencida = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=SESION_VENCIDA,
                            headers={"WWW-Authenticate": "Bearer"})
    # Segundo factor (F3b): el nivel se lee de la base, así un ascenso o un descenso rige en la
    # request siguiente. Sin `sf`, o con un `iat` anterior a la marca de revocación, la sesión venció.
    if requiere_segundo_factor(user.nivel_acceso):
        if payload.get("sf") is not True:
            raise vencida
        marca = user.sesiones_validas_desde
        iat = payload.get("iat")
        if marca is not None and (not isinstance(iat, int) or iat < int(marca.timestamp())):
            raise vencida
    datos = {k: v for k, v in user._mapping.items() if k != "sesiones_validas_desde"}
    if payload.get("sa") is True:
        # Super administrador: la cuenta tiene que seguir siendo de nivel 0 y sin municipio.
        # No se compara el Origin: entra desde cualquier dirección (spec §3).
        if user.nivel_acceso != 0 or user.id_municipio is not None:
            raise vencida
        return {**datos, "nivel_acceso": 1, "nivel_real": 0, "es_super_admin": True}
    if user.nivel_acceso == 0:
        raise vencida  # una cuenta de nivel 0 solo entra con su token propio
    await _validar_municipio_token(payload.get("mun"), user.id_municipio, request, db)
    return {**datos, "nivel_real": user.nivel_acceso, "es_super_admin": False}


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Guard de nivel Administrador (nivel_acceso == 1). Encadena get_current_user
    (autentica + valida scope agente + usuario activo) y ADEMÁS exige nivel 1.

    Usar en mutaciones sensibles que solo el administrador debe poder ejecutar
    (alta/edición/baja de usuarios, CRUD de maestros, config del sistema). El
    router de BUC/admin_tablas es transversal, así que este guard va POR ENDPOINT
    en las mutaciones, no a nivel router (los GET de búsqueda/catálogo los usan
    todos los niveles). Espeja el require_admin local de admin_permisos.py.
    """
    if current_user.get("nivel_acceso") != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requiere nivel administrador",
        )
    return current_user


async def require_super_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Guard de lo exclusivo del super administrador (IT-01 F3): municipios, parámetros
    globales, catálogo de módulos y Maestros globales."""
    if not current_user.get("es_super_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requiere super administrador")
    return current_user


async def get_current_ciudadano(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Guard para endpoints publicos de ciudadanos. Rechaza tokens scope!='publico'.

    Devuelve dict con campos planos del ciudadano + credencial:
    id_ciudadano, doc_nro (dni), nombre, apellido, email, estado_validacion, activado.
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autenticado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not credentials:
        raise unauthorized
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[ALGORITHM])
        ciudadano_id = payload.get("sub")
        scope = payload.get("scope")
        if ciudadano_id is None:
            raise unauthorized
        if scope != "publico":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Este endpoint requiere autenticacion de ciudadano",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError:
        raise unauthorized

    result = await db.execute(
        text("""
            SELECT c.id_ciudadano, c.doc_nro, c.nombre, c.apellido, c.email,
                   c.estado_validacion, c.ficha_completa, c.activo,
                   cc.activado, cc.activo AS credencial_activa, c.id_municipio
              FROM ciudadanos c
              JOIN ciudadano_credencial cc ON cc.id_ciudadano = c.id_ciudadano
             WHERE c.id_ciudadano = :id
        """),
        {"id": int(ciudadano_id)},
    )
    row = result.fetchone()
    if not row or not row.activo or not row.credencial_activa or not row.activado:
        raise unauthorized
    await _validar_municipio_token(payload.get("mun"), row.id_municipio, request, db)
    return dict(row._mapping)


async def modulos_permitidos(db: AsyncSession, id_usuario: int, nivel: int) -> list[str]:
    """Resuelve la lista de modulo_codigo que un usuario puede ver, aplicando
    el modelo hibrido de CLAUDE.md §30: default por min_nivel_acceso + override
    explicito por usuario_modulos (permitido TRUE otorga, FALSE bloquea).
    """
    defaults = await db.execute(
        text("""
            SELECT modulo_codigo FROM modulos
            WHERE activo = TRUE AND min_nivel_acceso >= :nivel
        """),
        {"nivel": nivel},
    )
    permitidos = {r.modulo_codigo for r in defaults.fetchall()}

    overrides = await db.execute(
        text("""
            SELECT modulo_codigo, permitido FROM usuario_modulos
            WHERE id_usuario = :uid AND activo = TRUE
        """),
        {"uid": id_usuario},
    )
    for r in overrides.fetchall():
        if r.permitido:
            permitidos.add(r.modulo_codigo)
        else:
            permitidos.discard(r.modulo_codigo)
    return sorted(permitidos)


def require_modulo(modulo: str):
    """Dependencia FastAPI que valida que el usuario tenga acceso al modulo
    indicado. Uso: `current = Depends(require_modulo("reclamos"))`. Devuelve
    el `current_user` igual que `get_current_user` para que el endpoint lo use.
    """
    async def _guard(
        current_user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> dict:
        modulos = await modulos_permitidos(
            db, current_user["id_usuario"], current_user["nivel_real"]
        )
        if modulo not in modulos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Sin acceso al modulo '{modulo}'",
            )
        return current_user
    return _guard
