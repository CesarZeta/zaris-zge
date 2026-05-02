"""
ZARIS API — Rutas del módulo BUC (Base Única de Ciudadanos).
Endpoints: /api/v1/buc/
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.buc import (
    Usuario, Nacionalidad, TipoRepresentacion, Actividad,
    Ciudadano, Empresa, CiudadanoEmpresa
)
from passlib.context import CryptContext

from app.schemas.buc import (
    UsuarioCreate, UsuarioUpdate, UsuarioOut,
    NacionalidadOut, TipoRepresentacionOut, ActividadOut,
    CiudadanoCreate, CiudadanoUpdate, CiudadanoOut, CiudadanoConNacionalidad,
    EmpresaCreate, EmpresaUpdate, EmpresaOut, EmpresaConActividad,
    CiudadanoEmpresaCreate, CiudadanoEmpresaOut
)

router = APIRouter(prefix="/api/v1/buc", tags=["BUC"])
logger = logging.getLogger("zaris.buc")
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ═══════════════════════════════════════════════════════════════
# USUARIOS
# ═══════════════════════════════════════════════════════════════

@router.get("/usuarios/buscar", response_model=list[UsuarioOut])
async def buscar_usuario(
    q: str = Query(..., min_length=1, description="Nombre, username o CUIL"),
    tipo: str = Query("auto", description="'numero' para CUIL/username, 'texto' para nombre, 'auto' para detectar"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Buscar usuarios por nombre, username o CUIL."""
    es_numerico = tipo == "numero" or (tipo == "auto" and q.replace("-", "").isdigit())
    if es_numerico:
        cond = or_(
            Usuario.cuil.ilike(f"%{q}%"),
            Usuario.username.ilike(f"%{q}%"),
        )
    else:
        cond = or_(
            Usuario.nombre.ilike(f"%{q}%"),
            Usuario.username.ilike(f"%{q}%"),
        )
    stmt = select(Usuario).where(cond).order_by(Usuario.nombre).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/usuarios", response_model=list[UsuarioOut])
async def listar_usuarios(
    solo_activos: bool = Query(True, description="Filtrar solo usuarios activos"),
    db: AsyncSession = Depends(get_db)
):
    """Listar usuarios del sistema (para selector modificado_por)."""
    stmt = select(Usuario).order_by(Usuario.nombre)
    if solo_activos:
        stmt = stmt.where(Usuario.activo == True)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/usuarios/{id}", response_model=UsuarioOut)
async def obtener_usuario(id: int, db: AsyncSession = Depends(get_db)):
    """Obtener usuario por ID."""
    result = await db.execute(select(Usuario).where(Usuario.id_usuario == id))
    u = result.scalars().first()
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return u


@router.post("/usuarios", response_model=UsuarioOut, status_code=201)
async def crear_usuario(data: UsuarioCreate, db: AsyncSession = Depends(get_db)):
    """Alta de usuario con contraseña hasheada (bcrypt)."""
    existing = await db.execute(select(Usuario).where(Usuario.username == data.username))
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail=f"Ya existe un usuario con username '{data.username}'")

    data_dict = data.model_dump()
    data_dict["password_hash"] = _pwd.hash(data_dict.pop("password"))

    usuario = Usuario(**data_dict)
    db.add(usuario)
    await db.commit()
    await db.refresh(usuario)
    logger.info("ALTA usuario | id=%s | username=%s", usuario.id_usuario, usuario.username)
    return usuario


@router.put("/usuarios/{id}", response_model=UsuarioOut)
async def modificar_usuario(id: int, data: UsuarioUpdate, db: AsyncSession = Depends(get_db)):
    """Modificar datos de usuario. Si se envía 'password', se re-hashea."""
    result = await db.execute(select(Usuario).where(Usuario.id_usuario == id))
    usuario = result.scalars().first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    update_data = data.model_dump(exclude_unset=True)
    if "password" in update_data:
        update_data["password_hash"] = _pwd.hash(update_data.pop("password"))

    campos_modificados = list(update_data.keys())
    for field, value in update_data.items():
        setattr(usuario, field, value)

    await db.commit()
    await db.refresh(usuario)
    logger.info("MODIFICACION usuario | id=%s | username=%s | campos=%s",
                usuario.id_usuario, usuario.username, campos_modificados)
    return usuario


@router.put("/usuarios/{id}/estado", response_model=UsuarioOut)
async def cambiar_estado_usuario(
    id: int,
    activo: bool = Query(..., description="true para reactivar, false para dar de baja"),
    db: AsyncSession = Depends(get_db)
):
    """Dar de alta o de baja a un usuario (soft delete)."""
    result = await db.execute(select(Usuario).where(Usuario.id_usuario == id))
    usuario = result.scalars().first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    usuario.activo = activo
    await db.commit()
    await db.refresh(usuario)
    accion = "REACTIVACION" if activo else "BAJA"
    logger.info("%s usuario | id=%s | username=%s", accion, usuario.id_usuario, usuario.username)
    return usuario


# ═══════════════════════════════════════════════════════════════
# CATÁLOGOS
# ═══════════════════════════════════════════════════════════════

@router.get("/nacionalidades", response_model=list[NacionalidadOut])
async def listar_nacionalidades(db: AsyncSession = Depends(get_db)):
    """Listar todas las nacionalidades."""
    result = await db.execute(select(Nacionalidad).order_by(Nacionalidad.pais))
    return result.scalars().all()


@router.get("/actividades", response_model=list[ActividadOut])
async def listar_actividades(db: AsyncSession = Depends(get_db)):
    """Listar todas las actividades CLAE."""
    result = await db.execute(select(Actividad).order_by(Actividad.descripcion))
    return result.scalars().all()


@router.get("/tipo-representacion", response_model=list[TipoRepresentacionOut])
async def listar_tipo_representacion(db: AsyncSession = Depends(get_db)):
    """Listar tipos de representación ciudadano-empresa."""
    result = await db.execute(select(TipoRepresentacion).order_by(TipoRepresentacion.id))
    return result.scalars().all()


# ═══════════════════════════════════════════════════════════════
# CIUDADANOS
# ═══════════════════════════════════════════════════════════════

@router.get("/ciudadanos/buscar", response_model=list[CiudadanoOut])
async def buscar_ciudadano(
    q: str = Query(..., min_length=1, description="DNI, CUIL, Email o Nombre"),
    tipo: str = Query("auto", description="'numero' para DNI/CUIL, 'texto' para nombre/apellido, 'auto' para detectar"),
    limit: int = Query(20, ge=1, le=100, description="Máximo de resultados"),
    offset: int = Query(0, ge=0, description="Desplazamiento para paginación"),
    db: AsyncSession = Depends(get_db)
):
    """Buscar ciudadano por DNI, CUIL, email o nombre (contains)."""
    es_numerico = tipo == "numero" or (tipo == "auto" and q.replace("-", "").isdigit())

    if es_numerico:
        cond = or_(
            Ciudadano.doc_nro.ilike(f"%{q}%"),
            Ciudadano.cuil.ilike(f"%{q}%"),
        )
    else:
        cond = or_(
            Ciudadano.nombre.ilike(f"%{q}%"),
            Ciudadano.apellido.ilike(f"%{q}%"),
            Ciudadano.email.ilike(f"%{q}%"),
        )

    query = (
        select(Ciudadano)
        .where(Ciudadano.activo == True, cond)
        .order_by(Ciudadano.apellido, Ciudadano.nombre)
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/ciudadanos/verificar-duplicado")
async def verificar_duplicado_ciudadano(
    campo: str = Query(..., description="Campo a verificar: email, telefono, cuil, doc_nro"),
    valor: str = Query(..., description="Valor a buscar"),
    excluir_id: Optional[int] = Query(None, description="ID a excluir (para edición)"),
    db: AsyncSession = Depends(get_db)
):
    """Verificar si ya existe un ciudadano con ese valor en el campo dado."""
    campo_map = {
        "email": Ciudadano.email,
        "telefono": Ciudadano.telefono,
        "cuil": Ciudadano.cuil,
        "doc_nro": Ciudadano.doc_nro,
    }
    if campo not in campo_map:
        raise HTTPException(status_code=400, detail=f"Campo '{campo}' no soportado")

    col = campo_map[campo]
    q = select(Ciudadano).where(col == valor, Ciudadano.activo == True)
    if excluir_id:
        q = q.where(Ciudadano.id_ciudadano != excluir_id)
    result = await db.execute(q)
    c = result.scalars().first()
    if c:
        return {"existe": True, "id": c.id_ciudadano, "nombre": f"{c.apellido}, {c.nombre}", "cuil": c.cuil}
    return {"existe": False}


@router.post("/ciudadanos", response_model=CiudadanoOut, status_code=201)
async def crear_ciudadano(
    data: CiudadanoCreate,
    db: AsyncSession = Depends(get_db)
):
    """Alta de ciudadano."""
    existing = await db.execute(
        select(Ciudadano).where(
            Ciudadano.doc_tipo == data.doc_tipo,
            Ciudadano.doc_nro == data.doc_nro
        )
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=409,
            detail=f"Ya existe un ciudadano con {data.doc_tipo} {data.doc_nro}"
        )

    existing_cuil = await db.execute(
        select(Ciudadano).where(Ciudadano.cuil == data.cuil)
    )
    if existing_cuil.scalars().first():
        raise HTTPException(status_code=409, detail=f"Ya existe un ciudadano con CUIL {data.cuil}")

    ciudadano = Ciudadano(**data.model_dump())
    db.add(ciudadano)
    await db.commit()
    await db.refresh(ciudadano)

    logger.info(
        "ALTA ciudadano | id=%s | doc=%s %s | cuil=%s | nombre=%s %s",
        ciudadano.id_ciudadano, ciudadano.doc_tipo, ciudadano.doc_nro,
        ciudadano.cuil, ciudadano.apellido, ciudadano.nombre
    )
    return ciudadano


@router.get("/ciudadanos/{id}", response_model=CiudadanoConNacionalidad)
async def obtener_ciudadano(id: int, db: AsyncSession = Depends(get_db)):
    """Obtener ciudadano por ID con datos de nacionalidad."""
    result = await db.execute(
        select(Ciudadano)
        .options(selectinload(Ciudadano.nacionalidad))
        .where(Ciudadano.id_ciudadano == id, Ciudadano.activo == True)
    )
    ciudadano = result.scalars().first()
    if not ciudadano:
        raise HTTPException(status_code=404, detail="Ciudadano no encontrado")
    return ciudadano


@router.put("/ciudadanos/{id}", response_model=CiudadanoOut)
async def modificar_ciudadano(
    id: int,
    data: CiudadanoUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Modificar ciudadano existente (update parcial)."""
    result = await db.execute(
        select(Ciudadano).where(Ciudadano.id_ciudadano == id, Ciudadano.activo == True)
    )
    ciudadano = result.scalars().first()
    if not ciudadano:
        raise HTTPException(status_code=404, detail="Ciudadano no encontrado")

    update_data = data.model_dump(exclude_unset=True)
    campos_modificados = list(update_data.keys())
    for field, value in update_data.items():
        setattr(ciudadano, field, value)

    await db.commit()
    await db.refresh(ciudadano)

    logger.info(
        "MODIFICACION ciudadano | id=%s | cuil=%s | campos=%s | usuario=%s",
        ciudadano.id_ciudadano, ciudadano.cuil, campos_modificados, ciudadano.modificado_por
    )
    return ciudadano


@router.put("/ciudadanos/{id}/estado", response_model=CiudadanoOut)
async def cambiar_estado_ciudadano(
    id: int,
    activo: bool = Query(..., description="true para reactivar, false para dar de baja"),
    db: AsyncSession = Depends(get_db)
):
    """Dar de baja o reactivar un ciudadano (soft delete)."""
    result = await db.execute(select(Ciudadano).where(Ciudadano.id_ciudadano == id))
    ciudadano = result.scalars().first()
    if not ciudadano:
        raise HTTPException(status_code=404, detail="Ciudadano no encontrado")
    ciudadano.activo = activo
    await db.commit()
    await db.refresh(ciudadano)
    accion = "REACTIVACION" if activo else "BAJA"
    logger.info("%s ciudadano | id=%s | cuil=%s", accion, ciudadano.id_ciudadano, ciudadano.cuil)
    return ciudadano


@router.get("/ciudadanos/{id}/empresas-vinculadas")
async def obtener_empresas_vinculadas(id: int, db: AsyncSession = Depends(get_db)):
    """Obtener las empresas vinculadas a un ciudadano (via tabla ciudadano_empresa)."""
    result = await db.execute(
        select(CiudadanoEmpresa)
        .options(
            selectinload(CiudadanoEmpresa.empresa),
            selectinload(CiudadanoEmpresa.tipo_representacion)
        )
        .where(
            CiudadanoEmpresa.id_ciudadano == id,
            CiudadanoEmpresa.activo == True
        )
    )
    relaciones = result.scalars().all()
    datos = []
    for rel in relaciones:
        emp = rel.empresa
        if emp and emp.activo:
            datos.append({
                "id_relacion":            rel.id,
                "id_empresa":             emp.id_empresa,
                "cuit":                   emp.cuit,
                "nombre":                 emp.nombre,
                "telefono":               emp.telefono,
                "email":                  emp.email,
                "calle":                  emp.calle,
                "localidad":              emp.localidad,
                "provincia":              emp.provincia,
                "id_actividad":           emp.id_actividad,
                "tipo_representacion":    rel.tipo_representacion.tipo if rel.tipo_representacion else None,
                "id_tipo_representacion": rel.id_tipo_representacion,
            })
    return datos


# ═══════════════════════════════════════════════════════════════
# EMPRESAS
# ═══════════════════════════════════════════════════════════════

@router.get("/empresas/buscar", response_model=list[EmpresaOut])
async def buscar_empresa(
    q: str = Query(..., min_length=1, description="CUIT, Email o Nombre"),
    tipo: str = Query("auto", description="'numero' para CUIT, 'texto' para nombre, 'auto' para detectar"),
    limit: int = Query(20, ge=1, le=100, description="Máximo de resultados"),
    offset: int = Query(0, ge=0, description="Desplazamiento para paginación"),
    db: AsyncSession = Depends(get_db)
):
    """Buscar empresa por CUIT, email o nombre (contains)."""
    es_numerico = tipo == "numero" or (tipo == "auto" and q.replace("-", "").isdigit())
    if es_numerico:
        q_normalizado = q.replace("-", "")
        cond = func.replace(Empresa.cuit, "-", "").ilike(f"%{q_normalizado}%")
    else:
        cond = or_(
            Empresa.nombre.ilike(f"%{q}%"),
            Empresa.email.ilike(f"%{q}%"),
        )
    query = (
        select(Empresa)
        .where(Empresa.activo == True, cond)
        .order_by(Empresa.nombre)
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/empresas/verificar-duplicado")
async def verificar_duplicado_empresa(
    campo: str = Query(..., description="Campo a verificar: email, telefono, cuit"),
    valor: str = Query(..., description="Valor a buscar"),
    excluir_id: Optional[int] = Query(None, description="ID a excluir (para edición)"),
    db: AsyncSession = Depends(get_db)
):
    """Verificar si ya existe una empresa con ese valor en el campo dado."""
    campo_map = {
        "email": Empresa.email,
        "telefono": Empresa.telefono,
        "cuit": Empresa.cuit,
    }
    if campo not in campo_map:
        raise HTTPException(status_code=400, detail=f"Campo '{campo}' no soportado")

    col = campo_map[campo]
    q = select(Empresa).where(col == valor, Empresa.activo == True)
    if excluir_id:
        q = q.where(Empresa.id_empresa != excluir_id)
    result = await db.execute(q)
    e = result.scalars().first()
    if e:
        return {"existe": True, "id": e.id_empresa, "nombre": e.nombre, "cuit": e.cuit}
    return {"existe": False}


@router.post("/empresas", response_model=EmpresaOut, status_code=201)
async def crear_empresa(
    data: EmpresaCreate,
    db: AsyncSession = Depends(get_db)
):
    """Alta de empresa."""
    existing = await db.execute(
        select(Empresa).where(Empresa.cuit == data.cuit)
    )
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail=f"Ya existe una empresa con CUIT {data.cuit}")

    empresa = Empresa(**data.model_dump())
    db.add(empresa)
    await db.commit()
    await db.refresh(empresa)

    logger.info(
        "ALTA empresa | id=%s | cuit=%s | nombre=%s",
        empresa.id_empresa, empresa.cuit, empresa.nombre
    )
    return empresa


@router.get("/empresas/{id}", response_model=EmpresaConActividad)
async def obtener_empresa(id: int, db: AsyncSession = Depends(get_db)):
    """Obtener empresa por ID con datos de actividad."""
    result = await db.execute(
        select(Empresa)
        .options(selectinload(Empresa.actividad))
        .where(Empresa.id_empresa == id, Empresa.activo == True)
    )
    empresa = result.scalars().first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    return empresa


@router.put("/empresas/{id}", response_model=EmpresaOut)
async def modificar_empresa(
    id: int,
    data: EmpresaUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Modificar empresa existente."""
    result = await db.execute(
        select(Empresa).where(Empresa.id_empresa == id, Empresa.activo == True)
    )
    empresa = result.scalars().first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    update_data = data.model_dump(exclude_unset=True)
    campos_modificados = list(update_data.keys())
    for field, value in update_data.items():
        setattr(empresa, field, value)

    await db.commit()
    await db.refresh(empresa)

    logger.info(
        "MODIFICACION empresa | id=%s | cuit=%s | campos=%s | usuario=%s",
        empresa.id_empresa, empresa.cuit, campos_modificados, empresa.modificado_por
    )
    return empresa


@router.put("/empresas/{id}/estado", response_model=EmpresaOut)
async def cambiar_estado_empresa(
    id: int,
    activo: bool = Query(..., description="true para reactivar, false para dar de baja"),
    db: AsyncSession = Depends(get_db)
):
    """Dar de baja o reactivar una empresa (soft delete)."""
    result = await db.execute(select(Empresa).where(Empresa.id_empresa == id))
    empresa = result.scalars().first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    empresa.activo = activo
    await db.commit()
    await db.refresh(empresa)
    accion = "REACTIVACION" if activo else "BAJA"
    logger.info("%s empresa | id=%s | cuit=%s", accion, empresa.id_empresa, empresa.cuit)
    return empresa


# ═══════════════════════════════════════════════════════════════
# CIUDADANO-EMPRESA (relación)
# ═══════════════════════════════════════════════════════════════

@router.post("/ciudadano-empresa", response_model=CiudadanoEmpresaOut, status_code=201)
async def crear_relacion_ciudadano_empresa(
    data: CiudadanoEmpresaCreate,
    db: AsyncSession = Depends(get_db)
):
    """Crear relación ciudadano-empresa con tipo de representación."""
    cid = await db.execute(
        select(Ciudadano).where(Ciudadano.id_ciudadano == data.id_ciudadano, Ciudadano.activo == True)
    )
    if not cid.scalars().first():
        raise HTTPException(status_code=404, detail="Ciudadano no encontrado")

    emp = await db.execute(
        select(Empresa).where(Empresa.id_empresa == data.id_empresa, Empresa.activo == True)
    )
    if not emp.scalars().first():
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    existing = await db.execute(
        select(CiudadanoEmpresa).where(
            CiudadanoEmpresa.id_ciudadano == data.id_ciudadano,
            CiudadanoEmpresa.id_empresa == data.id_empresa,
            CiudadanoEmpresa.id_tipo_representacion == data.id_tipo_representacion
        )
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=409,
            detail="Ya existe esta relacion ciudadano-empresa con ese tipo de representacion"
        )

    relacion = CiudadanoEmpresa(**data.model_dump())
    db.add(relacion)
    await db.commit()
    await db.refresh(relacion)

    logger.info(
        "VINCULACION ciudadano-empresa | ciudadano_id=%s | empresa_id=%s | tipo_rep=%s",
        relacion.id_ciudadano, relacion.id_empresa, relacion.id_tipo_representacion
    )
    return relacion
