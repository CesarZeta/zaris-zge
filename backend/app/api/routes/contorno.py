"""
Contorno del municipio desde Configuración (administrador del municipio, nivel 1; el super
administrador pasa como nivel 1 eligiendo el municipio en «Operando en»).

PLAN_CONTORNO_MUNICIPIO_DISENO.md §4.5. La depuración vive en services/contorno.py: acá solo se
resuelve el municipio, se aplica el guard y se traducen los errores. Los del alta y la ficha están en
super_admin.py.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.geo import invalidar_bbox
from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.municipio import municipio_actual
from app.services import contorno as ct
from app.services.contorno import OrigenIn, origen_limpio, validar_origen
from app.services.accesos_super import registrar_acceso_super_en

router = APIRouter(prefix="/api/v1/contorno", tags=["Contorno del municipio"])

SIN_PARTIDO = "Este municipio no tiene partido con código oficial: subí un archivo (mirá «¿Cómo armo el archivo?»)."
MAX_GEOJSON = ct.MAX_ENTRADA + 1_000


class PrevisualizarIn(BaseModel):
    geojson: str = Field(..., max_length=MAX_GEOJSON)
    archivo: Optional[str] = Field(None, max_length=200)


class GuardarIn(BaseModel):
    geojson: str = Field(..., max_length=MAX_GEOJSON)
    origen: OrigenIn


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user["nivel_acceso"] != 1:
        raise HTTPException(403, "Requiere nivel administrador")
    return current_user


async def oficial(db: AsyncSession, codigo: Optional[str], codigo_pais: str) -> dict:
    """El contorno oficial del IGN como lo ven las pantallas; traduce los errores del IGN."""
    if not codigo:
        raise HTTPException(409, SIN_PARTIDO)
    try:
        c, origen = await ct.contorno_oficial_ign(codigo, codigo_pais=codigo_pais)
    except ct.IgnSinContorno as e:
        raise HTTPException(404, str(e))
    except ct.IgnNoResponde:
        raise HTTPException(502, "El IGN no respondió o devolvió algo que no se pudo usar. Probá de nuevo en un rato, "
                                 "o subí un archivo.")
    return ct.vista(c, origen)


async def registrar_si_super(db: AsyncSession, usuario: dict, request: Request, id_municipio: int, detalle: str) -> None:
    """Un cambio del super administrador se registra en la misma transacción (CLAUDE.md §1)."""
    if usuario.get("es_super_admin"):
        await registrar_acceso_super_en(db, id_usuario=usuario["id_usuario"], accion="municipio_editar",
                                        id_municipio=id_municipio, metodo=request.method, ruta=request.url.path,
                                        detalle=detalle, user_agent=request.headers.get("user-agent"))


@router.get("")
async def ver_contorno(
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
    id_municipio: int = Depends(municipio_actual),
):
    return {"contorno": await ct.leer_contorno(db, id_municipio),
            "codigo_oficial": await ct.codigo_del_municipio(db, id_municipio)}


@router.post("/previsualizar", responses={422: {"description": "El archivo no sirve: detail + paso del instructivo"}})
async def previsualizar(
    body: PrevisualizarIn,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
    id_municipio: int = Depends(municipio_actual),
):
    """Depura el archivo y lo devuelve para verlo en el mapa. No guarda nada."""
    c = ct.normalizar_contorno(body.geojson, codigo_pais=await ct.pais_del_municipio(db, id_municipio))
    origen = {"via": "archivo", "archivo": body.archivo} if body.archivo else {"via": "archivo"}
    return {**ct.vista(c, origen), "aviso_zona": await ct.aviso_zona(db, id_municipio, c)}


@router.get("/oficial", responses={404: {"description": "El IGN no tiene el contorno"},
                                   409: {"description": "El municipio no tiene partido con código oficial"},
                                   502: {"description": "El IGN no respondió"}})
async def contorno_oficial(
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
    id_municipio: int = Depends(municipio_actual),
):
    """El contorno oficial del IGN para el partido del municipio, para verlo antes de guardarlo."""
    v = await oficial(db, await ct.codigo_del_municipio(db, id_municipio), await ct.pais_del_municipio(db, id_municipio))
    c_aviso = ct.ContornoNormalizado(v["geometria"], v["partes"], v["vertices_antes"], v["vertices_despues"],
                                     v["superficie_km2"], v["recuadro"], v["avisos"])
    return {**v, "aviso_zona": await ct.aviso_zona(db, id_municipio, c_aviso)}


@router.put("", responses={422: {"description": "El archivo no sirve, o el origen IGN no es el del partido"}})
async def guardar(
    body: GuardarIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
    id_municipio: int = Depends(municipio_actual),
):
    """Vuelve a depurar en el servidor (nunca guarda lo del cliente tal cual), guarda el contorno, su
    origen y la zona de búsqueda derivada."""
    await validar_origen(db, body.origen, await ct.codigo_del_municipio(db, id_municipio))
    c = ct.normalizar_contorno(body.geojson, codigo_pais=await ct.pais_del_municipio(db, id_municipio))
    origen = origen_limpio(body.origen)
    zona = await ct.guardar_contorno(db, id_municipio, c, origen)
    await registrar_si_super(db, admin, request, id_municipio, f"contorno guardado ({origen['via']})")
    await db.commit()
    invalidar_bbox(id_municipio)
    return {"contorno": await ct.leer_contorno(db, id_municipio), "zona": zona}


@router.delete("", status_code=204)
async def quitar(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
    id_municipio: int = Depends(municipio_actual),
):
    """Quita el contorno; la zona de búsqueda queda."""
    await ct.quitar_contorno(db, id_municipio)
    await registrar_si_super(db, admin, request, id_municipio, "contorno quitado")
    await db.commit()
    invalidar_bbox(id_municipio)
    return Response(status_code=204)
