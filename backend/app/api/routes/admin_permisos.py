"""
ZARIS API — Endpoints admin para permisos por modulo (CLAUDE.md §30).

GET    /api/v1/admin/permisos/modulos                    → catalogo de modulos
PUT    /api/v1/admin/permisos/modulos/{codigo}           → editar min_nivel_acceso
GET    /api/v1/admin/permisos/usuarios/{id}/modulos      → resolucion + overrides
PUT    /api/v1/admin/permisos/usuarios/{id}/modulos      → set bulk de overrides

Todas estas rutas requieren `nivel_acceso = 1` (administrador). El guard se
aplica via `require_admin` local porque la mig 38 incluye al modulo 'usuarios'
con min_nivel=1, pero la matriz de permisos es transversal — no la atamos a un
modulo concreto del catalogo.

Municipio (IT-01): los permisos por usuario son de los usuarios del municipio del
administrador (municipio_actual); un usuario de otro municipio responde 404, igual que
uno inexistente. El catalogo de modulos es global (habilitacion por municipio en F4).

Super administrador (IT-01 F3): el catálogo es global, así que cambiarlo es solo del super
administrador (afecta a todos los municipios) y queda en su registro de accesos. Los módulos
con min_nivel_acceso = 0 (p. ej. `municipios`) son exclusivos del super administrador: no se
listan a los demás, no se otorgan por permiso individual y su nivel no se edita.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, modulos_permitidos, require_super_admin
from app.core.database import get_db
from app.core.municipio import municipio_actual
from app.services.accesos_super import registrar_acceso_super

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


@router.get("/modulos", response_model=list[ModuloOut])
async def listar_modulos(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    rows = await db.execute(text("""
        SELECT modulo_codigo, nombre, descripcion, min_nivel_acceso, activo
        FROM modulos
        WHERE min_nivel_acceso > 0 OR :es_super
        ORDER BY min_nivel_acceso, modulo_codigo
    """), {"es_super": bool(admin.get("es_super_admin"))})
    return [dict(r._mapping) for r in rows.fetchall()]


class ModuloUpdate(BaseModel):
    min_nivel_acceso: int = Field(ge=1, le=4)


@router.put("/modulos/{codigo}", response_model=ModuloOut)
async def actualizar_modulo(
    codigo: str,
    body: ModuloUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_super_admin),
):
    actual = await db.scalar(text("SELECT min_nivel_acceso FROM modulos WHERE modulo_codigo = :c"),
                             {"c": codigo})
    if actual == 0:
        raise HTTPException(422, MODULO_EXCLUSIVO)
    await registrar_acceso_super(
        id_usuario=admin["id_usuario"], accion="catalogo_global", id_municipio=None,
        metodo=request.method, ruta=request.url.path,
        detalle=f"modulo {codigo}: min_nivel_acceso {actual} → {body.min_nivel_acceso}",
        user_agent=request.headers.get("user-agent"))
    res = await db.execute(text("""
        UPDATE modulos
           SET min_nivel_acceso = :nivel,
               fecha_modificacion = NOW(),
               id_usuario_modificacion = :uid
         WHERE modulo_codigo = :codigo AND activo = TRUE
         RETURNING modulo_codigo, nombre, descripcion, min_nivel_acceso, activo
    """), {"nivel": body.min_nivel_acceso, "uid": admin["id_usuario"], "codigo": codigo})
    row = res.fetchone()
    if not row:
        raise HTTPException(404, f"Modulo '{codigo}' no encontrado o inactivo")
    await db.commit()
    return dict(row._mapping)


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

    permitidos = await modulos_permitidos(db, user.id_usuario, user.nivel_acceso)

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

    permitidos = await modulos_permitidos(db, user.id_usuario, user.nivel_acceso)
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
