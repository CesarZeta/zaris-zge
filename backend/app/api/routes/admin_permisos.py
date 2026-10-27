"""
ZARIS API — Endpoints admin para permisos por modulo (CLAUDE.md §30).

GET    /api/v1/admin/permisos/modulos                    → modulos del municipio (habilitado + nivel)
PUT    /api/v1/admin/permisos/modulos/{codigo}           → nivel minimo (admin) / habilitar (super)
GET    /api/v1/admin/permisos/usuarios/{id}/modulos      → resolucion + overrides
PUT    /api/v1/admin/permisos/usuarios/{id}/modulos      → set bulk de overrides

Todas estas rutas requieren `nivel_acceso = 1` (administrador). El guard se
aplica via `require_admin` local porque la mig 38 incluye al modulo 'usuarios'
con min_nivel=1, pero la matriz de permisos es transversal — no la atamos a un
modulo concreto del catalogo.

Municipio (IT-01): los permisos por usuario son de los usuarios del municipio del
administrador (municipio_actual); un usuario de otro municipio responde 404, igual que
uno inexistente. El catalogo de modulos es global (habilitacion por municipio en F4).

Módulos por municipio (IT-01 F4): el catálogo `modulos` es global y su nivel es el valor por
defecto del alta; lo que se edita acá es `municipio_modulo` del municipio de la request. El
administrador cambia el nivel mínimo (1-5); habilitar o quitar un módulo es solo del super
administrador, con las dependencias y los módulos fijos validados, y queda en su registro
(`municipio_modulos`). Los módulos con min_nivel_acceso = 0 en el catálogo (p. ej. `municipios`)
son exclusivos del super administrador: no existen para los demás (404), no se otorgan por
permiso individual y su nivel no se edita.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, modulos_permitidos
from app.core.database import get_db
from app.core.municipio import municipio_actual
from app.services.accesos_super import registrar_acceso_super_en
from app.services.municipios.constantes import DEPENDENCIAS_MODULOS, MODULOS_FIJOS
from app.services.municipios.modulos import invalidar_modulos, validar_dependencias

router = APIRouter(prefix="/api/v1/admin/permisos", tags=["Admin - Permisos"])

MODULO_EXCLUSIVO = "Ese módulo es exclusivo del super administrador"


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user["nivel_acceso"] != 1:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Requiere nivel administrador")
    return current_user


# ---------------------------------------------------------------------------
# Catalogo de modulos
# ---------------------------------------------------------------------------

class ModuloOut(BaseModel):
    modulo_codigo: str
    nombre: str
    descripcion: Optional[str] = None
    min_nivel_acceso: int
    activo: bool
    habilitado: bool
    fijo: bool
    dependencias: list[str]


_SELECT_MODULOS = """
    SELECT m.modulo_codigo, m.nombre, m.descripcion, m.activo,
           COALESCE(mm.min_nivel_acceso, m.min_nivel_acceso) AS min_nivel_acceso,
           COALESCE(mm.habilitado, FALSE) AS habilitado, m.min_nivel_acceso AS nivel_catalogo
      FROM modulos m
      LEFT JOIN municipio_modulo mm ON mm.modulo_codigo = m.modulo_codigo AND mm.id_municipio = :mun"""


def _modulo_out(r) -> dict:
    return {"modulo_codigo": r.modulo_codigo, "nombre": r.nombre, "descripcion": r.descripcion,
            "min_nivel_acceso": r.min_nivel_acceso, "activo": r.activo, "habilitado": r.habilitado,
            "fijo": r.modulo_codigo in MODULOS_FIJOS,
            "dependencias": sorted(DEPENDENCIAS_MODULOS.get(r.modulo_codigo, ()))}


@router.get("/modulos", response_model=list[ModuloOut])
async def listar_modulos(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
    id_municipio: int = Depends(municipio_actual),
):
    rows = await db.execute(text(
        _SELECT_MODULOS + " WHERE m.activo AND (m.min_nivel_acceso > 0 OR :es_super)"
                          " ORDER BY m.min_nivel_acceso, m.modulo_codigo"),
        {"mun": id_municipio, "es_super": bool(admin.get("es_super_admin"))})
    return [_modulo_out(r) for r in rows.fetchall()]


class ModuloUpdate(BaseModel):
    min_nivel_acceso: Optional[int] = Field(None, ge=1, le=5)
    habilitado: Optional[bool] = None


@router.put("/modulos/{codigo}", response_model=ModuloOut,
            responses={403: {"description": "Habilitar o quitar un módulo es del super administrador"},
                       422: {"description": "Dependencia entre módulos o módulo fijo"}})
async def actualizar_modulo(
    codigo: str,
    body: ModuloUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
    id_municipio: int = Depends(municipio_actual),
):
    es_super = bool(admin.get("es_super_admin"))
    actual = (await db.execute(text(_SELECT_MODULOS + " WHERE m.modulo_codigo = :c AND m.activo"),
                               {"mun": id_municipio, "c": codigo})).fetchone()
    if actual is None or (actual.nivel_catalogo == 0 and not es_super):
        raise HTTPException(404, "Módulo no encontrado")
    if body.min_nivel_acceso is None and body.habilitado is None:
        raise HTTPException(422, "Indicá el nivel mínimo o si el módulo está habilitado")
    if body.habilitado is not None and not es_super:
        raise HTTPException(403, "Habilitar o quitar un módulo es del super administrador")
    if body.min_nivel_acceso is not None and actual.nivel_catalogo == 0:
        raise HTTPException(422, MODULO_EXCLUSIVO)
    if body.habilitado is False and codigo in MODULOS_FIJOS:
        raise HTTPException(422, "Ese módulo no se puede deshabilitar: el municipio no funciona sin él.")
    habilitado = actual.habilitado if body.habilitado is None else body.habilitado
    nivel = actual.min_nivel_acceso if body.min_nivel_acceso is None else body.min_nivel_acceso
    if habilitado != actual.habilitado:
        otros = {r[0] for r in (await db.execute(text(
            "SELECT modulo_codigo FROM municipio_modulo WHERE id_municipio = :mun AND habilitado "
            "AND modulo_codigo <> :c"), {"mun": id_municipio, "c": codigo})).fetchall()}
        await validar_dependencias(otros | {codigo} if habilitado else otros)
    await db.execute(text("""
        INSERT INTO municipio_modulo (id_municipio, modulo_codigo, habilitado, min_nivel_acceso,
                                      id_usuario_alta, id_usuario_modificacion)
        VALUES (:mun, :c, :h, :n, :u, :u)
        ON CONFLICT (id_municipio, modulo_codigo) DO UPDATE
           SET habilitado = EXCLUDED.habilitado, min_nivel_acceso = EXCLUDED.min_nivel_acceso,
               fecha_modificacion = NOW(), id_usuario_modificacion = EXCLUDED.id_usuario_modificacion"""),
        {"mun": id_municipio, "c": codigo, "h": habilitado, "n": nivel, "u": admin["id_usuario"]})
    if es_super:
        # En la misma transacción: si no se puede registrar, el cambio no queda.
        await registrar_acceso_super_en(
            db, id_usuario=admin["id_usuario"], accion="municipio_modulos", id_municipio=id_municipio,
            metodo=request.method, ruta=request.url.path,
            detalle=f"modulo {codigo}: habilitado {actual.habilitado} → {habilitado}; "
                    f"min_nivel_acceso {actual.min_nivel_acceso} → {nivel}",
            user_agent=request.headers.get("user-agent"))
    await db.commit()
    invalidar_modulos(id_municipio)
    nuevo = (await db.execute(text(_SELECT_MODULOS + " WHERE m.modulo_codigo = :c"),
                              {"mun": id_municipio, "c": codigo})).fetchone()
    return _modulo_out(nuevo)


# ---------------------------------------------------------------------------
# Permisos por usuario
# ---------------------------------------------------------------------------

class UsuarioModulosOut(BaseModel):
    id_usuario: int
    nivel_acceso: int
    modulos_permitidos: list[str]       # resolucion final (defaults + overrides)
    overrides: list[dict]               # filas activas de usuario_modulos


@router.get("/usuarios/{id_usuario}/modulos", response_model=UsuarioModulosOut)
async def ver_permisos_usuario(
    id_usuario: int,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
    id_municipio: int = Depends(municipio_actual),
):
    user = (await db.execute(
        text("SELECT id_usuario, nivel_acceso FROM usuarios "
             "WHERE id_usuario = :id AND activo = TRUE AND id_municipio = :mun"),
        {"id": id_usuario, "mun": id_municipio},
    )).fetchone()
    if not user:
        raise HTTPException(404, "Usuario no encontrado")

    permitidos = await modulos_permitidos(db, user.id_usuario, user.nivel_acceso, id_municipio)

    overrides_rows = await db.execute(text("""
        SELECT modulo_codigo, permitido, motivo, fecha_modificacion
        FROM usuario_modulos
        WHERE id_usuario = :uid AND activo = TRUE
        ORDER BY modulo_codigo
    """), {"uid": id_usuario})

    return UsuarioModulosOut(
        id_usuario=user.id_usuario,
        nivel_acceso=user.nivel_acceso,
        modulos_permitidos=permitidos,
        overrides=[dict(r._mapping) for r in overrides_rows.fetchall()],
    )


class OverrideIn(BaseModel):
    modulo_codigo: str
    permitido: bool
    motivo: Optional[str] = None


class UsuarioModulosUpdate(BaseModel):
    overrides: list[OverrideIn]   # set completo: reemplaza los overrides previos


@router.put("/usuarios/{id_usuario}/modulos", response_model=UsuarioModulosOut)
async def set_permisos_usuario(
    id_usuario: int,
    body: UsuarioModulosUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
    id_municipio: int = Depends(municipio_actual),
):
    user = (await db.execute(
        text("SELECT id_usuario, nivel_acceso FROM usuarios "
             "WHERE id_usuario = :id AND activo = TRUE AND id_municipio = :mun"),
        {"id": id_usuario, "mun": id_municipio},
    )).fetchone()
    if not user:
        raise HTTPException(404, "Usuario no encontrado")

    # Validar codigos contra el catalogo (rechaza tipos invalidos antes de tocar la DB)
    codigos = [o.modulo_codigo for o in body.overrides]
    if codigos:
        existentes = await db.execute(text("""
            SELECT modulo_codigo, min_nivel_acceso FROM modulos
             WHERE activo = TRUE AND modulo_codigo = ANY(:codigos)
        """), {"codigos": codigos})
        catalogo = {r.modulo_codigo: r.min_nivel_acceso for r in existentes.fetchall()}
        invalidos = [c for c in codigos if c not in catalogo]
        if invalidos:
            raise HTTPException(422, f"modulo_codigo invalidos: {invalidos}")
        # Un módulo exclusivo del super administrador no se otorga por permiso individual.
        if any(o.permitido and catalogo[o.modulo_codigo] == 0 for o in body.overrides):
            raise HTTPException(422, MODULO_EXCLUSIVO)

    # Reemplazo total: soft-delete los previos, upsert los nuevos.
    await db.execute(text("""
        UPDATE usuario_modulos
           SET activo = FALSE,
               fecha_modificacion = NOW(),
               id_usuario_modificacion = :admin
         WHERE id_usuario = :uid AND activo = TRUE
    """), {"admin": admin["id_usuario"], "uid": id_usuario})

    for ov in body.overrides:
        # UPSERT: si quedo una fila soft-deleted por (uid, codigo), la reactivamos.
        # El constraint UNIQUE (id_usuario, modulo_codigo) cubre ambos casos.
        await db.execute(text("""
            INSERT INTO usuario_modulos
                   (id_usuario, modulo_codigo, permitido, motivo, activo,
                    id_usuario_alta, id_usuario_modificacion, id_municipio)
            VALUES (:uid, :codigo, :perm, :motivo, TRUE, :admin, :admin, :mun)
            ON CONFLICT (id_usuario, modulo_codigo) DO UPDATE
               SET permitido = EXCLUDED.permitido,
                   motivo = EXCLUDED.motivo,
                   activo = TRUE,
                   fecha_modificacion = NOW(),
                   id_usuario_modificacion = :admin
        """), {"uid": id_usuario, "codigo": ov.modulo_codigo,
               "perm": ov.permitido, "motivo": ov.motivo, "admin": admin["id_usuario"],
               "mun": id_municipio})

    await db.commit()

    permitidos = await modulos_permitidos(db, user.id_usuario, user.nivel_acceso, id_municipio)
    overrides_rows = await db.execute(text("""
        SELECT modulo_codigo, permitido, motivo, fecha_modificacion
        FROM usuario_modulos
        WHERE id_usuario = :uid AND activo = TRUE
        ORDER BY modulo_codigo
    """), {"uid": id_usuario})

    return UsuarioModulosOut(
        id_usuario=user.id_usuario,
        nivel_acceso=user.nivel_acceso,
        modulos_permitidos=permitidos,
        overrides=[dict(r._mapping) for r in overrides_rows.fetchall()],
    )
