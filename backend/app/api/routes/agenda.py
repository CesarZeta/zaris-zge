"""
ZARIS API — Rutas del módulo Agenda.
Endpoints: /api/v1/agenda/
"""
import calendar
import logging
from datetime import date, datetime, time, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.agenda import (
    AgendaAgente, AgendaAlerta, AgendaAusencia, AgendaClase,
    AgendaFeriado, AgendaLugar, AgendaLugarServicio, AgendaServicio,
    AgendaServicioAgente, Area, LugarAtencion, Servicio, Turno,
)
from app.schemas.agenda import (
    AgendaAgenteCreate, AgendaAgenteOut, AgendaAgenteUpdate,
    AgendaAlertaOut,
    AgendaAusenciaCreate, AgendaAusenciaOut,
    AgendaClaseCreate, AgendaClaseOut, AgendaClaseUpdate,
    AgendaFeriadoCreate, AgendaFeriadoOut, AgendaFeriadoUpdate,
    AgendaLugarCreate, AgendaLugarOut, AgendaLugarUpdate,
    AgendaServicioCreate, AgendaServicioOut, AgendaServicioUpdate,
    AreaCreate, AreaOut, AreaUpdate,
    CalendarioDiaOut, CalendarioMesOut, DiaCalendario, SlotCalendario,
    LugarAtencionCreate, LugarAtencionOut, LugarAtencionUpdate,
    ServicioCreate, ServicioOut, ServicioUpdate,
    TurnoCreate, TurnoEstadoUpdate, TurnoOut,
)

router = APIRouter(prefix="/api/v1/agenda", tags=["agenda"])
logger = logging.getLogger("zaris.agenda")
_security = HTTPBearer(auto_error=False)


# ── Auth ──────────────────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> dict:
    if not credentials:
        raise HTTPException(status_code=401, detail="Token requerido")
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")


def require_nivel(minimo: int):
    async def dep(user: dict = Depends(get_current_user)) -> dict:
        if user.get("nivel_acceso", 0) < minimo:
            raise HTTPException(
                status_code=403,
                detail=f"Acceso denegado. Se requiere nivel {minimo} o superior",
            )
        return user
    return dep


# ── Helpers de fecha/horario ──────────────────────────────────

def _fechas_solapan(d1: date, h1: Optional[date], d2: date, h2: Optional[date]) -> bool:
    f1 = h1 or date(9999, 12, 31)
    f2 = h2 or date(9999, 12, 31)
    return d1 <= f2 and d2 <= f1


def _horas_solapan(i1: time, f1: time, i2: time, f2: time) -> bool:
    return i1 < f2 and i2 < f1


def _generar_slots(hora_inicio: time, hora_fin: time, duracion_min: int) -> List[tuple]:
    slots = []
    base = datetime(2000, 1, 1)
    actual = datetime.combine(base.date(), hora_inicio)
    fin = datetime.combine(base.date(), hora_fin)
    delta = timedelta(minutes=duracion_min)
    while actual + delta <= fin:
        slots.append((actual.time(), (actual + delta).time()))
        actual += delta
    return slots


# ── Núcleo de calendario por día (reutilizable) ───────────────

async def _datos_dia(
    fecha: date, capa: str, id_area: Optional[int], db: AsyncSession
) -> CalendarioDiaOut:
    r_f = await db.execute(
        select(AgendaFeriado).where(
            AgendaFeriado.fecha == fecha, AgendaFeriado.activo == True
        )
    )
    feriado = r_f.scalars().first()

    bit = 1 << fecha.weekday()
    tipo_map = {"AGENTES": AgendaAgente, "SERVICIOS": AgendaServicio, "LUGARES": AgendaLugar}
    Modelo = tipo_map[capa]

    stmt = select(Modelo).where(
        Modelo.activo == True,
        Modelo.fecha_desde <= fecha,
        or_(Modelo.fecha_hasta.is_(None), Modelo.fecha_hasta >= fecha),
        (Modelo.dias_semana.op("&")(bit)) > 0,
    )
    if id_area:
        stmt = stmt.where(Modelo.id_area == id_area)
    r = await db.execute(stmt)
    agendas = r.scalars().all()

    tipo_t = {"AGENTES": "AGENTE", "SERVICIOS": "SERVICIO", "LUGARES": "LUGAR"}[capa]
    r_t = await db.execute(
        select(Turno).where(
            Turno.fecha == fecha,
            Turno.tipo_agenda == tipo_t,
            Turno.activo == True,
            Turno.estado.notin_(["CANCELADO"]),
        )
    )
    turnos = r_t.scalars().all()
    turnos_by_slot: dict = {}
    for t in turnos:
        key = (t.hora_inicio, t.hora_fin)
        turnos_by_slot[key] = turnos_by_slot.get(key, 0) + 1

    seen: set = set()
    slots: List[SlotCalendario] = []
    for agenda in agendas:
        duracion = getattr(agenda, "duracion_slot_minutos", None) or 30
        for hi, hf in _generar_slots(agenda.hora_inicio, agenda.hora_fin, duracion):
            key = (hi, hf)
            if key in seen:
                continue
            seen.add(key)
            count = turnos_by_slot.get(key, 0)
            slots.append(
                SlotCalendario(
                    hora_inicio=hi,
                    hora_fin=hf,
                    disponible=feriado is None and count == 0,
                    turnos_count=count,
                    es_feriado=feriado is not None,
                )
            )

    slots.sort(key=lambda s: s.hora_inicio)
    return CalendarioDiaOut(
        fecha=fecha,
        es_feriado=feriado is not None,
        feriado_descripcion=feriado.descripcion if feriado else None,
        slots=slots,
    )


# ═══════════════════════════════════════════════════════════════
# ÁREAS
# ═══════════════════════════════════════════════════════════════

@router.get("/areas", response_model=List[AreaOut])
async def listar_areas(
    solo_activos: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(1)),
):
    stmt = select(Area).order_by(Area.nombre)
    if solo_activos:
        stmt = stmt.where(Area.activo == True)
    r = await db.execute(stmt)
    return r.scalars().all()


@router.post("/areas", response_model=AreaOut, status_code=201)
async def crear_area(
    data: AreaCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(4)),
):
    area = Area(**data.model_dump())
    db.add(area)
    await db.commit()
    await db.refresh(area)
    logger.info("ALTA area | id=%s | nombre=%s", area.id, area.nombre)
    return area


@router.patch("/areas/{id}", response_model=AreaOut)
async def editar_area(
    id: int,
    data: AreaUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(4)),
):
    r = await db.execute(select(Area).where(Area.id == id))
    area = r.scalars().first()
    if not area:
        raise HTTPException(404, "Área no encontrada")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(area, k, v)
    area.modificado_en = datetime.utcnow()
    await db.commit()
    await db.refresh(area)
    return area


# ═══════════════════════════════════════════════════════════════
# CLASES DE AGENDA
# ═══════════════════════════════════════════════════════════════

@router.get("/clases", response_model=List[AgendaClaseOut])
async def listar_clases(
    solo_activos: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(1)),
):
    stmt = select(AgendaClase).order_by(AgendaClase.nombre)
    if solo_activos:
        stmt = stmt.where(AgendaClase.activo == True)
    r = await db.execute(stmt)
    return r.scalars().all()


@router.post("/clases", response_model=AgendaClaseOut, status_code=201)
async def crear_clase(
    data: AgendaClaseCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(4)),
):
    d = data.model_dump()
    d.setdefault("creado_por", user.get("id"))
    clase = AgendaClase(**d)
    db.add(clase)
    await db.commit()
    await db.refresh(clase)
    logger.info("ALTA clase | id=%s | nombre=%s", clase.id, clase.nombre)
    return clase


@router.patch("/clases/{id}", response_model=AgendaClaseOut)
async def editar_clase(
    id: int,
    data: AgendaClaseUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(4)),
):
    r = await db.execute(select(AgendaClase).where(AgendaClase.id == id))
    clase = r.scalars().first()
    if not clase:
        raise HTTPException(404, "Clase no encontrada")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(clase, k, v)
    clase.modificado_en = datetime.utcnow()
    await db.commit()
    await db.refresh(clase)
    return clase


# ═══════════════════════════════════════════════════════════════
# FERIADOS
# ═══════════════════════════════════════════════════════════════

@router.get("/feriados", response_model=List[AgendaFeriadoOut])
async def listar_feriados(
    anio: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(1)),
):
    stmt = select(AgendaFeriado).where(AgendaFeriado.activo == True).order_by(AgendaFeriado.fecha)
    if anio:
        stmt = stmt.where(
            AgendaFeriado.fecha.between(date(anio, 1, 1), date(anio, 12, 31))
        )
    r = await db.execute(stmt)
    return r.scalars().all()


@router.post("/feriados", response_model=AgendaFeriadoOut, status_code=201)
async def crear_feriado(
    data: AgendaFeriadoCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(4)),
):
    existing = await db.execute(
        select(AgendaFeriado).where(AgendaFeriado.fecha == data.fecha)
    )
    if existing.scalars().first():
        raise HTTPException(409, f"Ya existe un feriado para {data.fecha}")
    d = data.model_dump()
    d.setdefault("creado_por", user.get("id"))
    feriado = AgendaFeriado(**d)
    db.add(feriado)
    await db.commit()
    await db.refresh(feriado)
    logger.info("ALTA feriado | id=%s | fecha=%s", feriado.id, feriado.fecha)
    return feriado


@router.patch("/feriados/{id}", response_model=AgendaFeriadoOut)
async def editar_feriado(
    id: int,
    data: AgendaFeriadoUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(4)),
):
    r = await db.execute(select(AgendaFeriado).where(AgendaFeriado.id == id))
    feriado = r.scalars().first()
    if not feriado:
        raise HTTPException(404, "Feriado no encontrado")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(feriado, k, v)
    await db.commit()
    await db.refresh(feriado)
    return feriado


# ═══════════════════════════════════════════════════════════════
# SERVICIOS
# ═══════════════════════════════════════════════════════════════

@router.get("/servicios", response_model=List[ServicioOut])
async def listar_servicios(
    id_area: Optional[int] = Query(None),
    solo_activos: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(1)),
):
    stmt = select(Servicio).order_by(Servicio.nombre)
    if solo_activos:
        stmt = stmt.where(Servicio.activo == True)
    if id_area:
        stmt = stmt.where(Servicio.id_area == id_area)
    r = await db.execute(stmt)
    return r.scalars().all()


@router.post("/servicios", response_model=ServicioOut, status_code=201)
async def crear_servicio(
    data: ServicioCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(4)),
):
    d = data.model_dump()
    d.setdefault("creado_por", user.get("id"))
    servicio = Servicio(**d)
    db.add(servicio)
    await db.commit()
    await db.refresh(servicio)
    logger.info("ALTA servicio | id=%s | nombre=%s", servicio.id, servicio.nombre)
    return servicio


@router.patch("/servicios/{id}", response_model=ServicioOut)
async def editar_servicio(
    id: int,
    data: ServicioUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(4)),
):
    r = await db.execute(select(Servicio).where(Servicio.id == id))
    s = r.scalars().first()
    if not s:
        raise HTTPException(404, "Servicio no encontrado")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    s.modificado_en = datetime.utcnow()
    await db.commit()
    await db.refresh(s)
    return s


# ═══════════════════════════════════════════════════════════════
# LUGARES DE ATENCIÓN
# ═══════════════════════════════════════════════════════════════

@router.get("/lugares", response_model=List[LugarAtencionOut])
async def listar_lugares(
    id_area: Optional[int] = Query(None),
    solo_activos: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(1)),
):
    stmt = select(LugarAtencion).order_by(LugarAtencion.nombre)
    if solo_activos:
        stmt = stmt.where(LugarAtencion.activo == True)
    if id_area:
        stmt = stmt.where(LugarAtencion.id_area == id_area)
    r = await db.execute(stmt)
    return r.scalars().all()


@router.post("/lugares", response_model=LugarAtencionOut, status_code=201)
async def crear_lugar(
    data: LugarAtencionCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(4)),
):
    d = data.model_dump()
    d.setdefault("creado_por", user.get("id"))
    lugar = LugarAtencion(**d)
    db.add(lugar)
    await db.commit()
    await db.refresh(lugar)
    logger.info("ALTA lugar | id=%s | nombre=%s", lugar.id, lugar.nombre)
    return lugar


@router.patch("/lugares/{id}", response_model=LugarAtencionOut)
async def editar_lugar(
    id: int,
    data: LugarAtencionUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(4)),
):
    r = await db.execute(select(LugarAtencion).where(LugarAtencion.id == id))
    lugar = r.scalars().first()
    if not lugar:
        raise HTTPException(404, "Lugar no encontrado")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(lugar, k, v)
    lugar.modificado_en = datetime.utcnow()
    await db.commit()
    await db.refresh(lugar)
    return lugar


# ═══════════════════════════════════════════════════════════════
# AGENDAS — AGENTES
# ═══════════════════════════════════════════════════════════════

@router.get("/agendas/agentes", response_model=List[AgendaAgenteOut])
async def listar_agendas_agentes(
    id_usuario: Optional[int] = Query(None),
    id_area: Optional[int] = Query(None),
    activo: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(1)),
):
    stmt = select(AgendaAgente).order_by(AgendaAgente.fecha_desde.desc())
    if id_usuario is not None:
        stmt = stmt.where(AgendaAgente.id_usuario == id_usuario)
    if id_area is not None:
        stmt = stmt.where(AgendaAgente.id_area == id_area)
    if activo is not None:
        stmt = stmt.where(AgendaAgente.activo == activo)
    r = await db.execute(stmt)
    return r.scalars().all()


@router.post("/agendas/agentes", response_model=AgendaAgenteOut, status_code=201)
async def crear_agenda_agente(
    data: AgendaAgenteCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(4)),
):
    r = await db.execute(
        select(AgendaAgente).where(
            AgendaAgente.id_usuario == data.id_usuario,
            AgendaAgente.activo == True,
        )
    )
    for ag in r.scalars().all():
        if (
            _fechas_solapan(data.fecha_desde, data.fecha_hasta, ag.fecha_desde, ag.fecha_hasta)
            and _horas_solapan(data.hora_inicio, data.hora_fin, ag.hora_inicio, ag.hora_fin)
            and bool(data.dias_semana & ag.dias_semana)
        ):
            raise HTTPException(
                422,
                f"Conflicto de disponibilidad con agenda agente id={ag.id}",
            )

    d = data.model_dump()
    d.setdefault("creado_por", user.get("id"))
    agenda = AgendaAgente(**d)
    db.add(agenda)
    await db.commit()
    await db.refresh(agenda)
    logger.info("ALTA agenda_agente | id=%s | usuario=%s", agenda.id, agenda.id_usuario)
    return agenda


@router.patch("/agendas/agentes/{id}", response_model=AgendaAgenteOut)
async def editar_agenda_agente(
    id: int,
    data: AgendaAgenteUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(4)),
):
    r = await db.execute(select(AgendaAgente).where(AgendaAgente.id == id))
    ag = r.scalars().first()
    if not ag:
        raise HTTPException(404, "Agenda agente no encontrada")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(ag, k, v)
    ag.modificado_en = datetime.utcnow()
    await db.commit()
    await db.refresh(ag)
    return ag


@router.patch("/agendas/agentes/{id}/baja", response_model=AgendaAgenteOut)
async def baja_agenda_agente(
    id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(4)),
):
    r = await db.execute(select(AgendaAgente).where(AgendaAgente.id == id))
    ag = r.scalars().first()
    if not ag:
        raise HTTPException(404, "Agenda agente no encontrada")
    ag.activo = False
    ag.fecha_baja = date.today()
    ag.modificado_en = datetime.utcnow()
    await db.commit()
    await db.refresh(ag)
    return ag


# ═══════════════════════════════════════════════════════════════
# AGENDAS — SERVICIOS
# ═══════════════════════════════════════════════════════════════

@router.get("/agendas/servicios", response_model=List[AgendaServicioOut])
async def listar_agendas_servicios(
    id_servicio: Optional[int] = Query(None),
    id_area: Optional[int] = Query(None),
    activo: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(1)),
):
    stmt = select(AgendaServicio).order_by(AgendaServicio.fecha_desde.desc())
    if id_servicio is not None:
        stmt = stmt.where(AgendaServicio.id_servicio == id_servicio)
    if id_area is not None:
        stmt = stmt.where(AgendaServicio.id_area == id_area)
    if activo is not None:
        stmt = stmt.where(AgendaServicio.activo == activo)
    r = await db.execute(stmt)
    return r.scalars().all()


@router.post("/agendas/servicios", response_model=AgendaServicioOut, status_code=201)
async def crear_agenda_servicio(
    data: AgendaServicioCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(4)),
):
    r = await db.execute(
        select(AgendaAgente).where(
            AgendaAgente.id_area == data.id_area,
            AgendaAgente.activo == True,
        )
    )
    agentes = r.scalars().all()
    rrhh_ok = any(
        _fechas_solapan(data.fecha_desde, data.fecha_hasta, ag.fecha_desde, ag.fecha_hasta)
        and _horas_solapan(data.hora_inicio, data.hora_fin, ag.hora_inicio, ag.hora_fin)
        and bool(data.dias_semana & ag.dias_semana)
        for ag in agentes
    )
    if not rrhh_ok:
        raise HTTPException(422, "No hay disponibilidad de RRHH para el período solicitado.")

    d = data.model_dump()
    ids_agente = d.pop("ids_agenda_agente", None) or []
    d.setdefault("creado_por", user.get("id"))
    agenda_srv = AgendaServicio(**d)
    db.add(agenda_srv)
    await db.flush()

    for id_ag in ids_agente:
        db.add(AgendaServicioAgente(id_agenda_servicio=agenda_srv.id, id_agenda_agente=id_ag))

    await db.commit()
    await db.refresh(agenda_srv)
    logger.info("ALTA agenda_servicio | id=%s | servicio=%s", agenda_srv.id, agenda_srv.id_servicio)
    return agenda_srv


@router.patch("/agendas/servicios/{id}", response_model=AgendaServicioOut)
async def editar_agenda_servicio(
    id: int,
    data: AgendaServicioUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(4)),
):
    r = await db.execute(select(AgendaServicio).where(AgendaServicio.id == id))
    srv = r.scalars().first()
    if not srv:
        raise HTTPException(404, "Agenda servicio no encontrada")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(srv, k, v)
    srv.modificado_en = datetime.utcnow()
    await db.commit()
    await db.refresh(srv)
    return srv


# ═══════════════════════════════════════════════════════════════
# AGENDAS — LUGARES
# ═══════════════════════════════════════════════════════════════

@router.get("/agendas/lugares", response_model=List[AgendaLugarOut])
async def listar_agendas_lugares(
    id_lugar: Optional[int] = Query(None),
    id_area: Optional[int] = Query(None),
    activo: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(1)),
):
    stmt = select(AgendaLugar).order_by(AgendaLugar.fecha_desde.desc())
    if id_lugar is not None:
        stmt = stmt.where(AgendaLugar.id_lugar == id_lugar)
    if id_area is not None:
        stmt = stmt.where(AgendaLugar.id_area == id_area)
    if activo is not None:
        stmt = stmt.where(AgendaLugar.activo == activo)
    r = await db.execute(stmt)
    return r.scalars().all()


@router.post("/agendas/lugares", response_model=AgendaLugarOut, status_code=201)
async def crear_agenda_lugar(
    data: AgendaLugarCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(4)),
):
    if not data.independiente_de_servicio:
        r = await db.execute(
            select(AgendaServicio).where(
                AgendaServicio.id_area == data.id_area,
                AgendaServicio.activo == True,
            )
        )
        servicios = r.scalars().all()
        srv_ok = any(
            _fechas_solapan(data.fecha_desde, data.fecha_hasta, s.fecha_desde, s.fecha_hasta)
            and _horas_solapan(data.hora_inicio, data.hora_fin, s.hora_inicio, s.hora_fin)
            and bool(data.dias_semana & s.dias_semana)
            for s in servicios
        )
        if not srv_ok:
            raise HTTPException(422, "No hay servicio disponible para el período solicitado.")

    d = data.model_dump()
    ids_servicio = d.pop("ids_agenda_servicio", None) or []
    d.setdefault("creado_por", user.get("id"))
    agenda_lugar = AgendaLugar(**d)
    db.add(agenda_lugar)
    await db.flush()

    for id_srv in ids_servicio:
        db.add(AgendaLugarServicio(id_agenda_lugar=agenda_lugar.id, id_agenda_servicio=id_srv))

    await db.commit()
    await db.refresh(agenda_lugar)
    logger.info("ALTA agenda_lugar | id=%s | lugar=%s", agenda_lugar.id, agenda_lugar.id_lugar)
    return agenda_lugar


@router.patch("/agendas/lugares/{id}", response_model=AgendaLugarOut)
async def editar_agenda_lugar(
    id: int,
    data: AgendaLugarUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(4)),
):
    r = await db.execute(select(AgendaLugar).where(AgendaLugar.id == id))
    lugar = r.scalars().first()
    if not lugar:
        raise HTTPException(404, "Agenda lugar no encontrada")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(lugar, k, v)
    lugar.modificado_en = datetime.utcnow()
    await db.commit()
    await db.refresh(lugar)
    return lugar


# ═══════════════════════════════════════════════════════════════
# TURNOS
# ═══════════════════════════════════════════════════════════════

@router.get("/turnos", response_model=List[TurnoOut])
async def listar_turnos(
    fecha: Optional[date] = Query(None),
    tipo_agenda: Optional[str] = Query(None),
    id_ciudadano: Optional[int] = Query(None),
    estado: Optional[str] = Query(None),
    reservado_por: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(1)),
):
    stmt = (
        select(Turno)
        .where(Turno.activo == True)
        .order_by(Turno.fecha, Turno.hora_inicio)
    )
    if fecha:
        stmt = stmt.where(Turno.fecha == fecha)
    if tipo_agenda:
        stmt = stmt.where(Turno.tipo_agenda == tipo_agenda)
    if id_ciudadano:
        stmt = stmt.where(Turno.id_ciudadano == id_ciudadano)
    if estado:
        stmt = stmt.where(Turno.estado == estado)
    if reservado_por:
        stmt = stmt.where(Turno.reservado_por == reservado_por)
    stmt = stmt.offset(offset).limit(limit)
    r = await db.execute(stmt)
    return r.scalars().all()


@router.post("/turnos", response_model=TurnoOut, status_code=201)
async def crear_turno(
    data: TurnoCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(2)),
):
    d = data.model_dump()
    d.setdefault("reservado_por", user.get("id"))
    turno = Turno(**d)
    db.add(turno)
    await db.commit()
    await db.refresh(turno)
    logger.info("ALTA turno | id=%s | fecha=%s | tipo=%s", turno.id, turno.fecha, turno.tipo_agenda)
    return turno


@router.patch("/turnos/{id}/estado", response_model=TurnoOut)
async def cambiar_estado_turno(
    id: int,
    data: TurnoEstadoUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(2)),
):
    r = await db.execute(select(Turno).where(Turno.id == id, Turno.activo == True))
    turno = r.scalars().first()
    if not turno:
        raise HTTPException(404, "Turno no encontrado")
    turno.estado = data.estado
    turno.modificado_en = datetime.utcnow()
    await db.commit()
    await db.refresh(turno)
    return turno


@router.patch("/turnos/{id}/cancelar", response_model=TurnoOut)
async def cancelar_turno(
    id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(2)),
):
    r = await db.execute(select(Turno).where(Turno.id == id, Turno.activo == True))
    turno = r.scalars().first()
    if not turno:
        raise HTTPException(404, "Turno no encontrado")
    turno.estado = "CANCELADO"
    turno.activo = False
    turno.fecha_baja = date.today()
    turno.modificado_en = datetime.utcnow()
    await db.commit()
    await db.refresh(turno)
    logger.info("CANCELACION turno | id=%s", turno.id)
    return turno


# ═══════════════════════════════════════════════════════════════
# AUSENCIAS
# ═══════════════════════════════════════════════════════════════

async def _generar_alertas(ausencia: AgendaAusencia, db: AsyncSession) -> None:
    r = await db.execute(
        select(AgendaAgente).where(
            AgendaAgente.id_usuario == ausencia.id_usuario,
            AgendaAgente.activo == True,
        )
    )
    for ag in r.scalars().all():
        if not _fechas_solapan(
            ausencia.fecha_desde, ausencia.fecha_hasta, ag.fecha_desde, ag.fecha_hasta
        ):
            continue
        db.add(AgendaAlerta(
            tipo_alerta="RRHH_AUSENTE",
            id_agenda_agente=ag.id,
            id_ausencia=ausencia.id,
            fecha_desde=ausencia.fecha_desde,
            fecha_hasta=ausencia.fecha_hasta,
            descripcion=(
                f"Agente id={ausencia.id_usuario} ausente "
                f"del {ausencia.fecha_desde} al {ausencia.fecha_hasta}"
            ),
        ))
        r2 = await db.execute(
            select(AgendaServicioAgente).where(
                AgendaServicioAgente.id_agenda_agente == ag.id,
                AgendaServicioAgente.activo == True,
            )
        )
        for link in r2.scalars().all():
            db.add(AgendaAlerta(
                tipo_alerta="SERVICIO_SIN_RRHH",
                id_agenda_servicio=link.id_agenda_servicio,
                id_agenda_agente=ag.id,
                id_ausencia=ausencia.id,
                fecha_desde=ausencia.fecha_desde,
                fecha_hasta=ausencia.fecha_hasta,
                descripcion=(
                    f"Servicio agenda_id={link.id_agenda_servicio} sin RRHH "
                    f"por ausencia agente id={ausencia.id_usuario}"
                ),
            ))
            r3 = await db.execute(
                select(AgendaLugarServicio).where(
                    AgendaLugarServicio.id_agenda_servicio == link.id_agenda_servicio,
                    AgendaLugarServicio.activo == True,
                )
            )
            for ll in r3.scalars().all():
                db.add(AgendaAlerta(
                    tipo_alerta="LUGAR_SIN_SERVICIO",
                    id_agenda_lugar=ll.id_agenda_lugar,
                    id_agenda_servicio=link.id_agenda_servicio,
                    id_ausencia=ausencia.id,
                    fecha_desde=ausencia.fecha_desde,
                    fecha_hasta=ausencia.fecha_hasta,
                    descripcion=(
                        f"Lugar agenda_id={ll.id_agenda_lugar} sin servicio "
                        f"por ausencia agente id={ausencia.id_usuario}"
                    ),
                ))


@router.get("/ausencias", response_model=List[AgendaAusenciaOut])
async def listar_ausencias(
    id_usuario: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(3)),
):
    stmt = (
        select(AgendaAusencia)
        .where(AgendaAusencia.activo == True)
        .order_by(AgendaAusencia.fecha_desde.desc())
    )
    if id_usuario:
        stmt = stmt.where(AgendaAusencia.id_usuario == id_usuario)
    r = await db.execute(stmt)
    return r.scalars().all()


@router.post("/ausencias", response_model=AgendaAusenciaOut, status_code=201)
async def crear_ausencia(
    data: AgendaAusenciaCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(3)),
):
    d = data.model_dump()
    d.setdefault("cargado_por", user.get("id"))
    ausencia = AgendaAusencia(**d)
    db.add(ausencia)
    await db.flush()
    if ausencia.genera_alerta:
        await _generar_alertas(ausencia, db)
    await db.commit()
    await db.refresh(ausencia)
    logger.info(
        "ALTA ausencia | id=%s | usuario=%s | %s → %s",
        ausencia.id, ausencia.id_usuario, ausencia.fecha_desde, ausencia.fecha_hasta,
    )
    return ausencia


# ═══════════════════════════════════════════════════════════════
# ALERTAS
# ═══════════════════════════════════════════════════════════════

@router.get("/alertas", response_model=List[AgendaAlertaOut])
async def listar_alertas(
    tipo_alerta: Optional[str] = Query(None),
    resuelta: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(1)),
):
    stmt = select(AgendaAlerta).order_by(AgendaAlerta.creado_en.desc())
    if tipo_alerta:
        stmt = stmt.where(AgendaAlerta.tipo_alerta == tipo_alerta)
    if resuelta is not None:
        stmt = stmt.where(AgendaAlerta.resuelta == resuelta)
    stmt = stmt.limit(limit)
    r = await db.execute(stmt)
    return r.scalars().all()


@router.patch("/alertas/{id}/resolver", response_model=AgendaAlertaOut)
async def resolver_alerta(
    id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(4)),
):
    r = await db.execute(select(AgendaAlerta).where(AgendaAlerta.id == id))
    alerta = r.scalars().first()
    if not alerta:
        raise HTTPException(404, "Alerta no encontrada")
    alerta.resuelta = True
    alerta.resuelta_por = user.get("id")
    alerta.resuelta_en = datetime.utcnow()
    await db.commit()
    await db.refresh(alerta)
    return alerta


# ═══════════════════════════════════════════════════════════════
# CALENDARIO
# ═══════════════════════════════════════════════════════════════

@router.get("/calendario/dia", response_model=CalendarioDiaOut)
async def calendario_dia(
    fecha: date = Query(...),
    capa: str = Query("AGENTES", pattern="^(AGENTES|SERVICIOS|LUGARES)$"),
    id_area: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(1)),
):
    return await _datos_dia(fecha, capa, id_area, db)


@router.get("/calendario/semana")
async def calendario_semana(
    fecha_inicio: date = Query(...),
    capa: str = Query("AGENTES", pattern="^(AGENTES|SERVICIOS|LUGARES)$"),
    id_area: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(1)),
):
    dias = []
    for i in range(7):
        dia = await _datos_dia(fecha_inicio + timedelta(days=i), capa, id_area, db)
        dias.append(dia)
    return {"fecha_inicio": fecha_inicio, "capa": capa, "dias": dias}


@router.get("/calendario/mes", response_model=CalendarioMesOut)
async def calendario_mes(
    anio: int = Query(..., ge=2020, le=2100),
    mes: int = Query(..., ge=1, le=12),
    capa: str = Query("AGENTES", pattern="^(AGENTES|SERVICIOS|LUGARES)$"),
    id_area: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_nivel(1)),
):
    primer_dia = date(anio, mes, 1)
    ultimo_dia = date(anio, mes, calendar.monthrange(anio, mes)[1])

    r_f = await db.execute(
        select(AgendaFeriado).where(
            AgendaFeriado.activo == True,
            AgendaFeriado.fecha.between(primer_dia, ultimo_dia),
        )
    )
    feriados = {f.fecha: f.descripcion for f in r_f.scalars().all()}

    tipo_map = {"AGENTES": AgendaAgente, "SERVICIOS": AgendaServicio, "LUGARES": AgendaLugar}
    Modelo = tipo_map[capa]
    stmt = select(Modelo).where(
        Modelo.activo == True,
        Modelo.fecha_desde <= ultimo_dia,
        or_(Modelo.fecha_hasta.is_(None), Modelo.fecha_hasta >= primer_dia),
    )
    if id_area:
        stmt = stmt.where(Modelo.id_area == id_area)
    r = await db.execute(stmt)
    agendas = r.scalars().all()

    tipo_t = {"AGENTES": "AGENTE", "SERVICIOS": "SERVICIO", "LUGARES": "LUGAR"}[capa]
    r_t = await db.execute(
        select(Turno).where(
            Turno.fecha.between(primer_dia, ultimo_dia),
            Turno.tipo_agenda == tipo_t,
            Turno.activo == True,
            Turno.estado.notin_(["CANCELADO"]),
        )
    )
    ocupados_por_dia: dict = {}
    for t in r_t.scalars().all():
        ocupados_por_dia[t.fecha] = ocupados_por_dia.get(t.fecha, 0) + 1

    dias: List[DiaCalendario] = []
    current = primer_dia
    while current <= ultimo_dia:
        is_feriado = current in feriados
        bit = 1 << current.weekday()
        slots_totales = 0
        for ag in agendas:
            if not (ag.fecha_desde <= current and (ag.fecha_hasta is None or ag.fecha_hasta >= current)):
                continue
            if not (ag.dias_semana & bit):
                continue
            duracion = getattr(ag, "duracion_slot_minutos", None) or 30
            slots_totales += len(_generar_slots(ag.hora_inicio, ag.hora_fin, duracion))

        ocupados = ocupados_por_dia.get(current, 0)

        if is_feriado:
            estado = "feriado"
        elif slots_totales == 0:
            estado = "fuera"
        elif ocupados >= slots_totales:
            estado = "ocupado"
        elif ocupados > 0:
            estado = "parcial"
        else:
            estado = "disponible"

        dias.append(DiaCalendario(
            fecha=current,
            es_feriado=is_feriado,
            feriado_descripcion=feriados.get(current),
            slots_totales=slots_totales,
            slots_ocupados=ocupados,
            estado=estado,
        ))
        current += timedelta(days=1)

    return CalendarioMesOut(anio=anio, mes=mes, dias=dias)
