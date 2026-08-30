"""
ZARIS API - PERFIL del vecino logueado (App Vecinos).

Bajo /api/v1/publico/perfil. Guard get_current_ciudadano (JWT scope 'publico').

Pendiente del traspaso 2026-07-16 (zaris-vecinos/ESTADO.md): la PWA solo tenia
los datos que devuelve el login (dni/nombre/apellido/email/estado/ficha) y
mostraba "—" en todo lo demas. Este router expone la ficha completa de la BUC
(telefono, domicilio, fecha_nac, nacionalidad, CUIL...) y permite editar SOLO
los datos de contacto y domicilio.

Reglas:
  - El id_ciudadano SIEMPRE sale del token (nunca de body/param).
  - El CUIL placeholder que genera el alta por agente ('20'+DNI+'9', §38 quirks)
    NO se expone como dato real: va `cuil=null` + `cuil_es_placeholder=true`.
  - Editables por el vecino: telefono, calle, altura, localidad, provincia,
    latitud, longitud. NO editables desde la app: DNI, CUIL, nombre, apellido,
    sexo, fecha_nac, nacionalidad (datos de identidad: se corrigen en mostrador)
    ni email (es la credencial de recovery: cambiarlo exige re-verificacion,
    flujo aparte — decision pendiente de Cesar).
  - `fecha_modificacion` (estandar §10) se actualiza; `id_usuario_modificacion`
    queda NULL porque el vecino no es `usuarios`.
"""
import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_ciudadano
from app.core.database import get_db
from app.middleware.rate_limit import check_rate_limit
from app.utils.request_helpers import get_real_ip

logger = logging.getLogger("zaris.publico_perfil")

router = APIRouter(prefix="/api/v1/publico/perfil", tags=["publico-perfil"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class PerfilOut(BaseModel):
    id_ciudadano: int
    dni: str
    doc_tipo: Optional[str] = None
    # NULL cuando el CUIL guardado es el placeholder del alta por agente.
    cuil: Optional[str] = None
    cuil_es_placeholder: bool = False
    nombre: str
    apellido: str
    sexo: Optional[str] = None
    fecha_nac: Optional[str] = None          # YYYY-MM-DD
    id_nacionalidad: Optional[int] = None
    nacionalidad: Optional[str] = None
    calle: Optional[str] = None
    altura: Optional[str] = None
    localidad: Optional[str] = None
    provincia: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    telefono: Optional[str] = None
    email: str
    email_verificado: bool = False
    estado_validacion: str
    ficha_completa: bool = False
    canal_email: bool = True
    canal_push: bool = True
    fecha_alta: Optional[str] = None         # ISO 8601
    fecha_modificacion: Optional[str] = None


class PerfilUpdateIn(BaseModel):
    """Update PARCIAL: solo se tocan los campos presentes en el body
    (`exclude_unset`). Mandar `null` explicito en latitud/longitud los limpia."""
    telefono: Optional[str] = Field(None, min_length=6, max_length=20)
    calle: Optional[str] = Field(None, min_length=1, max_length=200)
    altura: Optional[str] = Field(None, max_length=20)
    localidad: Optional[str] = Field(None, min_length=1, max_length=100)
    provincia: Optional[str] = Field(None, min_length=1, max_length=100)
    latitud: Optional[float] = Field(None, ge=-90, le=90)
    longitud: Optional[float] = Field(None, ge=-180, le=180)

    @field_validator("telefono")
    @classmethod
    def _val_telefono(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        digitos = "".join(ch for ch in v if ch.isdigit())
        if len(digitos) < 6:
            raise ValueError("El teléfono debe tener al menos 6 dígitos")
        return v

    @field_validator("calle", "altura", "localidad", "provincia")
    @classmethod
    def _strip(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if isinstance(v, str) else v


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _solo_digitos(s: Optional[str]) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())


def _cuil_es_placeholder(cuil: Optional[str], dni: Optional[str]) -> bool:
    """El alta por agente (§38) inventa '20' + DNI.zfill(8) + '9' porque `cuil`
    es UNIQUE NOT NULL. No es un CUIL real: no mostrarlo al vecino."""
    c = _solo_digitos(cuil)
    d = _solo_digitos(dni)
    if not c or not d:
        return False
    return c in {f"20{d.zfill(8)}9", f"20{d}9"}


def _iso(v) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return str(v)


async def _perfil_out(db: AsyncSession, id_ciudadano: int) -> PerfilOut:
    row = (await db.execute(text("""
        SELECT c.id_ciudadano, c.doc_tipo, c.doc_nro, c.cuil, c.nombre, c.apellido,
               c.sexo, c.fecha_nac, c.id_nacionalidad, n.pais AS nacionalidad,
               c.calle, c.altura, c.localidad, c.provincia,
               c.latitud, c.longitud, c.telefono, c.email, c.email_chk,
               c.estado_validacion, c.ficha_completa,
               c.fecha_alta, c.fecha_modificacion,
               cp.canal_email, cp.canal_push
          FROM ciudadanos c
          LEFT JOIN nacionalidades n ON n.id = c.id_nacionalidad
          LEFT JOIN ciudadano_canal_preferido cp ON cp.id_ciudadano = c.id_ciudadano
         WHERE c.id_ciudadano = :id AND c.activo = TRUE
    """), {"id": id_ciudadano})).mappings().first()
    if not row:
        raise HTTPException(404, "Ciudadano no encontrado")

    placeholder = _cuil_es_placeholder(row["cuil"], row["doc_nro"])
    return PerfilOut(
        id_ciudadano=row["id_ciudadano"],
        dni=row["doc_nro"],
        doc_tipo=row["doc_tipo"],
        cuil=None if placeholder else row["cuil"],
        cuil_es_placeholder=placeholder,
        nombre=row["nombre"],
        apellido=row["apellido"],
        sexo=row["sexo"],
        fecha_nac=_iso(row["fecha_nac"]),
        id_nacionalidad=row["id_nacionalidad"],
        nacionalidad=row["nacionalidad"],
        calle=row["calle"],
        altura=row["altura"],
        localidad=row["localidad"],
        provincia=row["provincia"],
        # NUMERIC llega como Decimal → float explicito (memoria numeric_decimal_serializa_string)
        latitud=float(row["latitud"]) if row["latitud"] is not None else None,
        longitud=float(row["longitud"]) if row["longitud"] is not None else None,
        telefono=row["telefono"],
        email=row["email"],
        email_verificado=bool(row["email_chk"]),
        estado_validacion=row["estado_validacion"],
        ficha_completa=bool(row["ficha_completa"]),
        canal_email=True if row["canal_email"] is None else bool(row["canal_email"]),
        canal_push=True if row["canal_push"] is None else bool(row["canal_push"]),
        fecha_alta=_iso(row["fecha_alta"]),
        fecha_modificacion=_iso(row["fecha_modificacion"]),
    )


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("", response_model=PerfilOut)
async def mi_perfil(
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
):
    """Ficha completa del vecino logueado (BUC). Solo lectura de identidad;
    contacto/domicilio editables via PUT."""
    return await _perfil_out(db, current["id_ciudadano"])


# Columnas que el vecino puede tocar. Cualquier otra del body se rechaza en el
# schema (Pydantic ignora extras por default, pero el SET se arma SOLO con esta lista).
_EDITABLES = ("telefono", "calle", "altura", "localidad", "provincia", "latitud", "longitud")


@router.put("", response_model=PerfilOut,
            responses={422: {"description": "Body vacío o campo inválido"}})
async def actualizar_mi_perfil(
    body: PerfilUpdateIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
):
    """Actualiza contacto y domicilio del vecino logueado (update parcial).
    Identidad (DNI/CUIL/nombre/fecha_nac/nacionalidad) y email NO se editan acá."""
    check_rate_limit(f"perfilpub:{get_real_ip(request)}", max_requests=10, window_seconds=60)

    cambios = {k: v for k, v in body.model_dump(exclude_unset=True).items() if k in _EDITABLES}
    if not cambios:
        raise HTTPException(422, "No hay campos para actualizar")

    sets = ", ".join(f"{k} = :{k}" for k in cambios)
    params = dict(cambios)
    params["id"] = current["id_ciudadano"]
    res = await db.execute(text(f"""
        UPDATE ciudadanos
           SET {sets}, fecha_modificacion = NOW()
         WHERE id_ciudadano = :id AND activo = TRUE
    """), params)
    if res.rowcount == 0:
        await db.rollback()
        raise HTTPException(404, "Ciudadano no encontrado")
    await db.commit()
    logger.info("perfil: ciudadano %s actualizó %s", current["id_ciudadano"], sorted(cambios))
    return await _perfil_out(db, current["id_ciudadano"])
