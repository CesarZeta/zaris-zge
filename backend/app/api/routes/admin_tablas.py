"""
ZARIS API — Endpoints CRUD genéricos para tablas administrativas.
Prefijo: /api/v1/admin/

Municipio (IT-01): las tablas de catálogo y operativas se listan, leen, crean, editan
y dan de baja dentro del municipio del usuario (municipio_actual). Un id de otro
municipio responde igual que uno inexistente (404) y un id de otro municipio en el
body, 422 «<entidad> inexistente». Las tablas globales no se filtran: las lee
cualquiera (alimentan selects) y las modifica solo el administrador del municipio
base hasta F3; `municipios`, además, solo la lee él.
"""
import logging
from datetime import date, time
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user, require_admin
from app.core.municipio import municipio_actual
from app.services.accesos_super import registrar_acceso_super

router = APIRouter(tags=["Admin Tablas"])
logger = logging.getLogger("zaris.admin_tablas")

# ─── Registro de tablas ────────────────────────────────────────────────────────
# pk: columna de clave primaria
# cols: columnas editables (excluye pk y timestamps estándar)
# fecha_mod: nombre del campo de última modificación (varía por tabla)
# exclude: columnas a ocultar en respuestas (ej: password_hash)

TABLE_CONFIG: dict[str, dict] = {
    "area": {
        "pk": "id_area",
        "cols": ["nombre", "descripcion"],
        "fecha_mod": "fecha_modificacion",
    },
    "subarea": {
        "pk": "id_subarea",
        # asignacion_manual (mig 121): la gestión queda afuera de la asignación automática
        # general (clave reclamos_asignacion_automatica de configuracion_general).
        "cols": ["nombre", "descripcion", "id_area", "asignacion_manual"],
        "fecha_mod": "fecha_modificacion",
    },
    "tipo_usuario": {
        "pk": "id_tipo_usuario",
        "cols": ["nombre", "descripcion"],
        "fecha_mod": "fecha_modificacion",
    },
    "cargos": {
        "pk": "id_cargo",
        "cols": ["nombre", "descripcion"],
        "fecha_mod": "fecha_modificacion",
    },
    "usuarios": {
        # NOTA: id_tipo_usuario NO existe en la tabla usuarios (era drift histórico
        # del TABLE_CONFIG). Las columnas reales de pertenencia son id_subarea + es_externo.
        "pk": "id_usuario",
        "cols": ["nombre", "nivel_acceso", "username", "cuil", "buc_acceso", "id_subarea", "es_externo"],
        "fecha_mod": "fecha_modif",
        # El token de recovery permite resetear la clave de la cuenta: no sale
        # nunca, ni al admin (2026-10-21).
        "exclude": ["password_hash", "token_recovery", "token_recovery_expira",
                    "fecha_ultimo_email_recovery"],
    },
    "agentes": {
        "pk": "id_agente",
        "cols": ["nombre", "apellido", "legajo", "dni", "cuil", "email", "telefono", "id_cargo", "id_subarea", "id_usuario", "es_auditor"],
        "fecha_mod": "fecha_modificacion",
        # Lectura con el vínculo a la ficha de la BUC (vía usuarios.id_ciudadano):
        # si existe, los datos personales se editan en la ficha (2026-10-20).
        "select": ("a.*, u.id_ciudadano AS id_ciudadano_ficha",
                   "agentes a LEFT JOIN usuarios u ON u.id_usuario = a.id_usuario", "a"),
    },
    "equipos": {
        "pk": "id_equipo",
        "cols": ["nombre", "descripcion", "id_subarea", "tipo_grupo", "dias_semana", "hora_inicio", "hora_fin"],
        "fecha_mod": "fecha_modificacion",
        "col_types": {"hora_inicio": "time", "hora_fin": "time"},
    },
    "servicios": {
        "pk": "id",
        "cols": ["nombre", "descripcion", "id_usuario_responsable", "capacidad_agentes",
                 "dias_semana", "hora_inicio", "hora_fin"],
        "fecha_mod": "modificado_en",
        "col_types": {"hora_inicio": "time", "hora_fin": "time"},
    },
    # ── Tablas de Agenda (mig 39 estandariza agenda_clase y agenda_feriado)
    "lugares_atencion": {
        "pk": "id",
        "cols": ["nombre", "direccion", "es_atencion", "capacidad_servicios"],
        "fecha_mod": "modificado_en",
        "has_audit": False,
    },
    "agenda_clase": {
        "pk": "id_agenda_clase",
        "cols": [
            "nombre", "descripcion", "visible_ciudadano", "requiere_rrhh",
            "requiere_servicio", "requiere_lugar", "duracion_slot_minutos",
        ],
        "fecha_mod": "fecha_modificacion",
        "has_audit": True,
    },
    "agenda_feriado": {
        "pk": "id_agenda_feriado",
        "cols": ["fecha", "descripcion", "ambito"],
        "fecha_mod": "fecha_modificacion",
        "has_audit": True,
        "col_types": {"fecha": "date"},
    },
    # ── Reclamos
    "estado_reclamo": {
        "pk": "id_estado_reclamo",
        "cols": ["nombre", "descripcion", "color", "es_final", "orden"],
        "fecha_mod": "fecha_modificacion",
        "has_audit": False,
    },
    "estado_ot": {
        "pk": "id_estado_ot",
        "cols": ["nombre", "descripcion", "color", "es_final", "orden"],
        "fecha_mod": "fecha_modificacion",
        "has_audit": False,
    },
    "equipo_agentes": {
        "pk": "id_equipo_agente",
        "cols": ["id_equipo", "id_agente"],
        "fecha_mod": "fecha_modificacion",
    },
    "tipo_reclamo": {
        "pk": "id_tipo_reclamo",
        # sla_minutos (mig 120) es el SLA; sla_dias lo deriva un trigger y no se edita.
        # asignacion_a (mig 30): a quién se le asigna solo. duracion_estimada_min quedó
        # sin uso cuando los reclamos dejaron de agendarse (2026-10-21).
        "cols": ["nombre", "descripcion", "id_subarea", "sla_minutos", "audit",
                 "asignacion_a"],
        "fecha_mod": "fecha_modificacion",
    },
    "configuracion_general": {
        "pk": "id_config",
        "cols": ["clave", "valor", "tipo", "descripcion"],
        "fecha_mod": "fecha_modificacion",
        "has_audit": False,
    },
    "municipios": {
        "pk": "id_municipio",
        "cols": ["nombre", "provincia", "pais", "codigo_corto"],
        "fecha_mod": "fecha_modificacion",
    },
    # ── Tablas BUC — ahora con auditoría y baja lógica
    "actividades": {
        "pk": "id",
        "cols": ["codigo_clae", "descripcion", "categoria_tasa"],
        "fecha_mod": "fecha_modificacion",
    },
    "tipo_representacion": {
        "pk": "id",
        "cols": ["tipo", "descripcion"],
        "fecha_mod": "fecha_modificacion",
    },
    "nacionalidades": {
        "pk": "id",
        "cols": ["pais", "region"],
        "fecha_mod": "fecha_modificacion",
    },
    # ── Catálogos del módulo Emergencias (mig 82). La taxonomía de incidentes es
    # propia del módulo COM pero se administra desde Maestros (pedido del usuario).
    "emergencia_prioridad": {
        "pk": "id_emergencia_prioridad",
        "cols": ["codigo", "nombre", "descripcion", "sla_minutos_arribo", "color_token", "orden_visual"],
        "fecha_mod": "fecha_modificacion",
    },
    "emergencia_estado": {
        "pk": "id_emergencia_estado",
        "cols": ["codigo", "nombre", "descripcion", "es_inicial", "es_terminal", "es_terminal_positivo", "orden_visual"],
        "fecha_mod": "fecha_modificacion",
    },
    "emergencia_canal_ingreso": {
        "pk": "id_emergencia_canal_ingreso",
        "cols": ["codigo", "nombre", "descripcion", "requiere_operador"],
        "fecha_mod": "fecha_modificacion",
    },
    "emergencia_organismo_derivacion": {
        "pk": "id_emergencia_organismo_derivacion",
        "cols": ["codigo", "nombre", "descripcion", "telefono_contacto", "es_municipal"],
        "fecha_mod": "fecha_modificacion",
    },
    "emergencia_tipo": {
        "pk": "id_emergencia_tipo",
        "cols": ["id_subarea", "codigo_oficial", "codigo", "nombre", "descripcion",
                 "id_prioridad_default", "id_organismo_derivacion_default", "requiere_911", "es_emergencia"],
        "fecha_mod": "fecha_modificacion",
    },
    "emergencia_subtipo": {
        "pk": "id_emergencia_subtipo",
        "cols": ["id_tipo", "codigo", "nombre", "descripcion", "id_prioridad_override"],
        "fecha_mod": "fecha_modificacion",
    },
}

ALLOWED_TABLES = set(TABLE_CONFIG.keys())

# Tablas globales (clase 'global' de municipio_tabla_clase): sin id_municipio.
# configuracion_general es mixta: se ven y se editan solo las filas del municipio
# (las claves globales, como las VAPID, no salen por acá).
_TABLAS_GLOBALES = {"tipo_usuario", "estado_reclamo", "estado_ot", "municipios", "actividades",
                    "tipo_representacion", "nacionalidades", "emergencia_estado"}
_SOLO_SUPER_LECTURA = {"municipios"}

# Columnas del body que apuntan a otra tabla del municipio: (tabla, PK, entidad).
_REFERENCIAS = {
    "id_area": ("area", "id_area", "Área"),
    "id_subarea": ("subarea", "id_subarea", "Subárea"),
    "id_cargo": ("cargos", "id_cargo", "Cargo"),
    "id_usuario": ("usuarios", "id_usuario", "Usuario"),
    "id_usuario_responsable": ("usuarios", "id_usuario", "Usuario"),
    "id_equipo": ("equipos", "id_equipo", "Equipo"),
    "id_agente": ("agentes", "id_agente", "Agente"),
    "id_prioridad_default": ("emergencia_prioridad", "id_emergencia_prioridad", "Prioridad"),
    "id_prioridad_override": ("emergencia_prioridad", "id_emergencia_prioridad", "Prioridad"),
    "id_organismo_derivacion_default": ("emergencia_organismo_derivacion",
                                        "id_emergencia_organismo_derivacion", "Organismo de derivación"),
    "id_tipo": ("emergencia_tipo", "id_emergencia_tipo", "Tipo de emergencia"),
}


def _por_municipio(tabla: str) -> bool:
    return tabla not in _TABLAS_GLOBALES


def _exigir_super_admin(current_user: dict) -> None:
    """Las tablas globales son de todos los municipios: solo las toca el super administrador
    (IT-01 F3; hasta F2 era el administrador del municipio base)."""
    if not current_user.get("es_super_admin"):
        raise HTTPException(status_code=403, detail="Acción exclusiva del super administrador")


async def _autorizar_escritura_global(current_user: dict, tabla: str, accion: str, id: int | None) -> None:
    if tabla in _SOLO_SUPER_LECTURA:
        # Una sola vía de edición: el módulo Municipios (valida subdominio, zona horaria, etc.).
        raise HTTPException(status_code=403, detail="Los municipios se editan desde el módulo Municipios")
    _exigir_super_admin(current_user)
    await registrar_acceso_super(id_usuario=current_user["id_usuario"], accion="catalogo_global",
                                 id_municipio=None,
                                 detalle=f"{accion} {tabla}" + (f" {id}" if id is not None else ""))


async def _validar_referencias(db: AsyncSession, data: dict, id_municipio: int) -> None:
    """422 si un id del body es de otro municipio o no existe (R4)."""
    for col, valor in data.items():
        ref = _REFERENCIAS.get(col)
        if ref is None or valor is None:
            continue
        t, pk, nombre = ref
        try:
            v = int(valor)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail=f"{nombre} inexistente")
        if not await db.scalar(text(f"SELECT 1 FROM {t} WHERE {pk} = :v AND id_municipio = :mun"),
                               {"v": v, "mun": id_municipio}):
            raise HTTPException(status_code=422, detail=f"{nombre} inexistente")

# Tablas que se pueden LEER por el CRUD genérico (para poblar selects FK de otras
# tablas) pero NO mutar desde acá. `usuarios` tiene su propia pantalla
# (módulo React Usuarios, web-app #/usuarios) que hashea password y registra auditoría de login; el
# alta/edición/baja genérico de admin_tablas dejaría usuarios sin login funcional.
READ_ONLY_TABLES = {"usuarios"}


def _bloquear_si_read_only(tabla: str) -> None:
    if tabla in READ_ONLY_TABLES:
        raise HTTPException(
            status_code=403,
            detail=f"La tabla '{tabla}' no se administra desde Maestros. "
                   f"Usá la pantalla dedicada del módulo Usuarios.",
        )


def _get_config(tabla: str) -> dict:
    if tabla not in ALLOWED_TABLES:
        raise HTTPException(status_code=404, detail=f"Tabla '{tabla}' no administrable")
    return TABLE_CONFIG[tabla]


# Parámetros del sistema: solo los lee el administrador (Config → Sistema y
# Maestros; ningún otro módulo los pide por acá). Las claves secretas no salen
# nunca por el CRUD genérico, ni al admin: el backend las lee directo de la DB
# (services/push.py) y ninguna pantalla las muestra. Con la privada VAPID se
# pueden firmar push a todos los dispositivos suscriptos (2026-10-21).
_TABLAS_SOLO_ADMIN_LECTURA = {"configuracion_general"}
_CLAVES_SECRETAS = {"vapid_private_key"}


async def _rechazar_clave_global(db: AsyncSession, tabla: str, data: dict) -> None:
    """Una clave global (id_municipio NULL, como password_renovacion_dias) vale para todos los
    municipios y leer_config prioriza la fila del municipio: crearla o renombrar otra con ese
    nombre la anularía en silencio (I1 de la revisión final de F3). Segunda barrera: trigger
    de la mig 127c."""
    clave = data.get("clave")
    if tabla != "configuracion_general" or not clave:
        return
    if await db.scalar(text("SELECT 1 FROM configuracion_general WHERE clave = :c AND id_municipio IS NULL"),
                       {"c": clave}):
        raise HTTPException(status_code=422, detail=(
            f"«{clave}» es un parámetro global de todos los municipios: lo edita el super administrador "
            f"desde Configuración → Sistema"))


def _bloquear_lectura_si_solo_admin(tabla: str, current_user: dict) -> None:
    if tabla in _TABLAS_SOLO_ADMIN_LECTURA and current_user.get("nivel_acceso") != 1:
        raise HTTPException(status_code=403, detail="Acción exclusiva del administrador")


# Usuarios: fuera del admin, el CRUD genérico solo alimenta selects FK (Maestros
# → agentes.id_usuario, servicios.id_usuario_responsable). Email, CUIL, nivel y
# fechas de login de las cuentas no son de cualquier logueado (2026-10-21).
_COLS_USUARIO_NO_ADMIN = {"id_usuario", "nombre", "id_subarea", "activo"}


def _sanear(tabla: str, d: dict, current_user: dict) -> dict:
    if tabla == "configuracion_general" and d.get("clave") in _CLAVES_SECRETAS:
        d["valor"] = None
        d["valor_oculto"] = True
    if tabla == "usuarios" and current_user.get("nivel_acceso") != 1:
        d = {k: v for k, v in d.items() if k in _COLS_USUARIO_NO_ADMIN}
    return d


# Columnas PII de agentes que solo el Administrador (nivel 1) puede leer por el
# CRUD genérico. El GET de agentes lo usan también el RecursoPicker de OT y otros
# selects (nivel 2/4), que solo necesitan id/nombre/apellido/legajo/subárea — por
# eso NO guardamos el endpoint entero (rompería esos pickers), sino que ocultamos
# el DNI/CUIL/email/teléfono a quien no sea admin. El form de Maestros → Agentes
# corre como admin y sigue viendo todo para prefillar la edición.
_PII_AGENTES = ["dni", "cuil", "email", "telefono"]

# Datos personales del agente: la ficha del ciudadano es la ÚNICA fuente
# (César 2026-10-20). Si el agente está vinculado a una ficha, se actualizan al
# guardarla (services/cuenta_zaris.py) y acá se ignoran.
_COLS_PERSONALES_AGENTE = {"nombre", "apellido", "dni", "cuil", "email", "telefono"}

# Supervisor (nivel 2): completa el perfil laboral de los agentes de SU gestión
# — cargo y legajo; el horario va por los endpoints de Agenda (ya acotados) — y
# su pertenencia a los equipos de su gestión. El resto de Maestros es del admin.
_COLS_AGENTE_SUPERVISOR = {"legajo", "id_cargo"}
_TABLAS_SUPERVISOR = {"agentes", "equipo_agentes"}


def _exclude_efectivo(tabla: str, cfg: dict, current_user: dict,
                      sub_supervisor: int | None = None) -> list[str]:
    """exclude base de la tabla + PII de agentes si el llamador no es admin.
    Un supervisor ve la PII de los agentes de SU gestión (la filtra _row_to_dict
    por fila); el resto de los niveles nunca."""
    exclude = list(cfg.get("exclude", []))
    if tabla == "agentes" and current_user.get("nivel_acceso") != 1 and sub_supervisor is None:
        exclude += _PII_AGENTES
    return exclude


async def _subarea_supervisor(db: AsyncSession, current_user: dict) -> int | None:
    """Subárea del agente vinculado al supervisor (nivel 2, regla 1:1 §39); None
    para otros niveles o si no tiene subárea."""
    if current_user.get("nivel_acceso") != 2:
        return None
    return await db.scalar(text(
        "SELECT id_subarea FROM agentes WHERE id_usuario = :u AND activo = TRUE LIMIT 1"
    ), {"u": current_user["id_usuario"]})


def _filtrar_pii_supervisor(d: dict, sub: int | None) -> dict:
    """Supervisor: PII solo de los agentes de su gestión."""
    if sub is not None and d.get("id_subarea") != sub:
        for col in _PII_AGENTES:
            d.pop(col, None)
    return d


async def _autorizar_escritura(
    db: AsyncSession, tabla: str, accion: str, current_user: dict,
    *, id_municipio: int, id: int | None = None, body: dict | None = None,
) -> dict | None:
    """Admin: todo. Supervisor: solo el perfil laboral de los agentes de su
    gestión (PUT agentes con cargo/legajo) y la pertenencia a equipos de su
    gestión (alta/baja en equipo_agentes). Devuelve el body a aplicar (filtrado
    para el supervisor) o 403/422."""
    nivel = current_user.get("nivel_acceso", 99)
    if nivel == 1:
        if not _por_municipio(tabla):
            await _autorizar_escritura_global(current_user, tabla, accion, id)
        return body
    sub = await _subarea_supervisor(db, current_user)
    if nivel != 2 or tabla not in _TABLAS_SUPERVISOR or sub is None:
        raise HTTPException(status_code=403, detail="Acción exclusiva del administrador")

    if tabla == "agentes":
        if accion != "editar":
            raise HTTPException(status_code=403, detail=(
                "Un supervisor no da de alta ni de baja agentes: completá cargo, "
                "horario y equipos de los agentes de tu gestión."))
        ag = (await db.execute(text(
            "SELECT id_subarea FROM agentes WHERE id_agente = :id AND activo = TRUE AND id_municipio = :mun"),
            {"id": id, "mun": id_municipio})).fetchone()
        if not ag:
            raise HTTPException(status_code=404, detail=f"Registro {id} no encontrado en {tabla}")
        if ag.id_subarea != sub:
            raise HTTPException(status_code=403, detail="El agente pertenece a otra gestión.")
        filtrado = {k: v for k, v in (body or {}).items() if k in _COLS_AGENTE_SUPERVISOR}
        if not filtrado:
            raise HTTPException(status_code=422, detail="Como supervisor solo podés cambiar cargo y legajo.")
        return filtrado

    # equipo_agentes: alta (body con id_equipo/id_agente) o baja (por id).
    if accion == "editar":
        raise HTTPException(status_code=403, detail="Para cambiar un equipo, sacá al agente y sumalo al nuevo.")
    if accion == "crear":
        id_equipo, id_agente = (body or {}).get("id_equipo"), (body or {}).get("id_agente")
    else:
        row = (await db.execute(text(
            "SELECT id_equipo, id_agente FROM equipo_agentes WHERE id_equipo_agente = :id AND id_municipio = :mun"),
            {"id": id, "mun": id_municipio})).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Registro {id} no encontrado en {tabla}")
        id_equipo, id_agente = row.id_equipo, row.id_agente
    eq_sub = await db.scalar(text(
        "SELECT id_subarea FROM equipos WHERE id_equipo = :id AND activo = TRUE AND id_municipio = :mun"),
        {"id": id_equipo, "mun": id_municipio})
    ag_sub = await db.scalar(text(
        "SELECT id_subarea FROM agentes WHERE id_agente = :id AND activo = TRUE AND id_municipio = :mun"),
        {"id": id_agente, "mun": id_municipio})
    if eq_sub != sub or ag_sub != sub:
        raise HTTPException(status_code=403, detail="El equipo y el agente tienen que ser de tu gestión.")
    return body


async def _quitar_personales_si_ficha(db: AsyncSession, tabla: str, id: int, data: dict) -> dict:
    """Agente vinculado a una ficha: sus datos personales no se editan acá."""
    if tabla != "agentes":
        return data
    con_ficha = await db.scalar(text("""
        SELECT u.id_ciudadano FROM agentes a JOIN usuarios u ON u.id_usuario = a.id_usuario
        WHERE a.id_agente = :id
    """), {"id": id})
    if con_ficha is None:
        return data
    return {k: v for k, v in data.items() if k not in _COLS_PERSONALES_AGENTE}


def _row_to_dict(row: Any, exclude: list[str]) -> dict:
    """Convierte un Row de SQLAlchemy a dict, omitiendo columnas sensibles."""
    d = dict(row._mapping)
    for col in exclude:
        d.pop(col, None)
    # Serializar TIME/DATE a string para JSON
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            d[k] = str(v)
    return d


def _coerce_types(data: dict, col_types: dict) -> None:
    """Convierte strings a tipos nativos de Python requeridos por asyncpg."""
    for col, typ in col_types.items():
        if col not in data or data[col] is None:
            continue
        val = data[col]
        if not isinstance(val, str):
            continue
        if typ == "date":
            data[col] = date.fromisoformat(val)
        elif typ == "time":
            h, m = val.split(":")[:2]
            data[col] = time(int(h), int(m))


# ─── GET /{tabla} — listar activos ────────────────────────────────────────────

@router.get("/{tabla}", responses={403: {
    "description": "configuracion_general solo la lee el administrador; las claves secretas vuelven "
                   "con valor null; usuarios: fuera del admin solo id/nombre/subárea/activo"}})
async def listar(
    tabla: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    id_municipio: int = Depends(municipio_actual),
):
    cfg = _get_config(tabla)
    _bloquear_lectura_si_solo_admin(tabla, current_user)
    if tabla in _SOLO_SUPER_LECTURA:
        _exigir_super_admin(current_user)
    pk = cfg["pk"]
    sub = await _subarea_supervisor(db, current_user) if tabla == "agentes" else None
    exclude = _exclude_efectivo(tabla, cfg, current_user, sub)
    sel, frm, al = cfg.get("select", ("*", tabla, None))
    pre = f"{al}." if al else ""
    conds, params = [], {}
    if cfg.get("has_activo", True):
        conds.append(f"{pre}activo = TRUE")
    if _por_municipio(tabla):
        conds.append(f"{pre}id_municipio = :mun")
        params["mun"] = id_municipio
    where = f"WHERE {' AND '.join(conds)}" if conds else ""
    stmt = text(f"SELECT {sel} FROM {frm} {where} ORDER BY {pre}{pk}")
    result = await db.execute(stmt, params)
    rows = result.fetchall()
    return [_sanear(tabla, _filtrar_pii_supervisor(_row_to_dict(r, exclude), sub), current_user) for r in rows]


# ─── GET /{tabla}/{id} — obtener uno ──────────────────────────────────────────

@router.get("/{tabla}/{id}")
async def obtener(
    tabla: str,
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    id_municipio: int = Depends(municipio_actual),
):
    cfg = _get_config(tabla)
    _bloquear_lectura_si_solo_admin(tabla, current_user)
    if tabla in _SOLO_SUPER_LECTURA:
        _exigir_super_admin(current_user)
    pk = cfg["pk"]
    sub = await _subarea_supervisor(db, current_user) if tabla == "agentes" else None
    exclude = _exclude_efectivo(tabla, cfg, current_user, sub)
    sel, frm, al = cfg.get("select", ("*", tabla, None))
    pre = f"{al}." if al else ""
    params: dict = {"id": id}
    del_municipio = ""
    if _por_municipio(tabla):
        del_municipio = f" AND {pre}id_municipio = :mun"
        params["mun"] = id_municipio
    stmt = text(f"SELECT {sel} FROM {frm} WHERE {pre}{pk} = :id{del_municipio}")
    result = await db.execute(stmt, params)
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Registro {id} no encontrado en {tabla}")
    return _sanear(tabla, _filtrar_pii_supervisor(_row_to_dict(row, exclude), sub), current_user)


# ─── POST /{tabla} — crear ────────────────────────────────────────────────────

@router.post("/{tabla}", status_code=201)
async def crear(
    tabla: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    id_municipio: int = Depends(municipio_actual),
):
    cfg = _get_config(tabla)
    _bloquear_si_read_only(tabla)
    body = await _autorizar_escritura(db, tabla, "crear", current_user, id_municipio=id_municipio, body=body)
    allowed = cfg["cols"]
    exclude = cfg.get("exclude", [])

    # Excluir Nones del INSERT para que la DB aplique sus DEFAULT (ej: capacidad_agentes DEFAULT 0)
    data = {k: v for k, v in body.items() if k in allowed and v is not None}
    if not data:
        raise HTTPException(status_code=422, detail="No se recibieron campos válidos")
    await _rechazar_clave_global(db, tabla, data)
    if _por_municipio(tabla):
        await _validar_referencias(db, data, id_municipio)
        data["id_municipio"] = id_municipio

    if cfg.get("has_audit", True):
        data["id_usuario_alta"] = current_user["id_usuario"]

    if cfg.get("has_activo", True) and "activo" not in data:
        data["activo"] = True

    col_types = cfg.get("col_types", {})
    _coerce_types(data, col_types)
    cols = ", ".join(data.keys())
    vals = ", ".join(f":{k}" for k in data.keys())
    stmt = text(f"INSERT INTO {tabla} ({cols}) VALUES ({vals}) RETURNING *")
    try:
        result = await db.execute(stmt, data)
        await db.commit()
        row = result.fetchone()
        return _sanear(tabla, _row_to_dict(row, exclude), current_user)
    except Exception as e:
        await db.rollback()
        logger.error("Error al crear en %s: %s", tabla, e)
        raise HTTPException(status_code=400, detail=str(e))


# ─── PUT /{tabla}/{id} — editar ───────────────────────────────────────────────

AREA_FIJA = "Es un área fija del sistema: se puede renombrar, no dar de baja."


async def _rechazar_baja_area_fija(db: AsyncSession, tabla: str, id: int, id_municipio: int) -> None:
    """IT-01 F4: las áreas fijas (area.es_sistema) se renombran, no se dan de baja. 422 con el texto
    fijo antes de tocar la base (el trigger area_sistema_no_baja es la segunda barrera)."""
    if tabla == "area" and await db.scalar(text(
            "SELECT es_sistema FROM area WHERE id_area = :id AND id_municipio = :mun"),
            {"id": id, "mun": id_municipio}):
        raise HTTPException(status_code=422, detail=AREA_FIJA)


@router.put("/{tabla}/{id}", responses={422: {"description": AREA_FIJA}})
async def editar(
    tabla: str,
    id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    id_municipio: int = Depends(municipio_actual),
):
    cfg = _get_config(tabla)
    _bloquear_si_read_only(tabla)
    body = await _autorizar_escritura(db, tabla, "editar", current_user, id_municipio=id_municipio, id=id, body=body)
    if body.get("activo") is False:
        await _rechazar_baja_area_fija(db, tabla, id, id_municipio)
    pk = cfg["pk"]
    allowed = cfg["cols"]
    fecha_mod = cfg["fecha_mod"]
    exclude = cfg.get("exclude", [])

    data = {k: v for k, v in body.items() if k in allowed}
    data = await _quitar_personales_si_ficha(db, tabla, id, data)
    if tabla == "configuracion_general":
        # La clave secreta llega oculta (valor null) al form: guardarlo no debe
        # borrarla ni renombrarla. Se rota por env var de Railway, no por acá.
        clave_actual = await db.scalar(text(
            "SELECT clave FROM configuracion_general WHERE id_config = :id AND id_municipio = :mun"),
            {"id": id, "mun": id_municipio})
        if clave_actual in _CLAVES_SECRETAS:
            data.pop("valor", None)
            data.pop("clave", None)
    if not data:
        raise HTTPException(status_code=422, detail="No se recibieron campos válidos")
    await _rechazar_clave_global(db, tabla, data)
    del_municipio, extra = "", {}
    if _por_municipio(tabla):
        await _validar_referencias(db, data, id_municipio)
        del_municipio, extra = " AND id_municipio = :__mun", {"__mun": id_municipio}

    if cfg.get("has_audit", True):
        data["id_usuario_modificacion"] = current_user["id_usuario"]
    col_types = cfg.get("col_types", {})
    _coerce_types(data, col_types)
    sets = ", ".join(f"{k} = :{k}" for k in data.keys())
    fecha_extra = f", {fecha_mod} = NOW()" if fecha_mod else ""
    stmt = text(
        f"UPDATE {tabla} SET {sets}{fecha_extra} "
        f"WHERE {pk} = :__id{del_municipio} RETURNING *"
    )
    try:
        result = await db.execute(stmt, {**data, "__id": id, **extra})
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Registro {id} no encontrado en {tabla}")
        if tabla == "agentes" and "id_subarea" in data:
            # Una sola gestión por persona: la del agente (§3). Su usuario 1:1 la
            # acompaña (lo lee el módulo Usuarios y las cuentas viejas). 2026-10-21.
            await db.execute(text("""
                UPDATE usuarios u SET id_subarea = a.id_subarea, fecha_modif = NOW()
                  FROM agentes a
                 WHERE a.id_agente = :id AND u.id_usuario = a.id_usuario
                   AND u.id_subarea IS DISTINCT FROM a.id_subarea
            """), {"id": id})
        await db.commit()
        return _sanear(tabla, _row_to_dict(row, exclude), current_user)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Error al editar en %s id=%s: %s", tabla, id, e)
        raise HTTPException(status_code=400, detail=str(e))


# ─── GET /area/{id}/subareas — drill-down: subáreas de un área ────────────────

@router.get("/area/{id_area}/subareas")
async def subareas_de_area(
    id_area: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    id_municipio: int = Depends(municipio_actual),
):
    """Lista las subáreas activas que pertenecen al área dada,
    con el conteo de tipos de reclamo activos asociados a cada una."""
    if not await db.scalar(text("SELECT 1 FROM area WHERE id_area = :id AND id_municipio = :mun"),
                           {"id": id_area, "mun": id_municipio}):
        raise HTTPException(status_code=404, detail=f"Registro {id_area} no encontrado en area")
    r = await db.execute(text("""
        SELECT s.id_subarea, s.nombre, s.descripcion,
               COUNT(tr.id_tipo_reclamo) FILTER (WHERE tr.activo) AS tipos_activos
        FROM subarea s
        LEFT JOIN tipo_reclamo tr ON tr.id_subarea = s.id_subarea
        WHERE s.id_area = :id_area AND s.activo = TRUE AND s.id_municipio = :mun
        GROUP BY s.id_subarea, s.nombre, s.descripcion
        ORDER BY s.nombre
    """), {"id_area": id_area, "mun": id_municipio})
    return [dict(row._mapping) for row in r.fetchall()]


# ─── GET /subarea/{id}/tipos-reclamo — drill-down: tipos de reclamo de una subárea ──

@router.get("/subarea/{id_subarea}/tipos-reclamo")
async def tipos_de_subarea(
    id_subarea: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    id_municipio: int = Depends(municipio_actual),
):
    """Lista los tipos de reclamo activos que pertenecen a la subárea dada, con su SLA
    en minutos (`sla_minutos`, mig 120; `sla_dias` queda por compatibilidad)."""
    if not await db.scalar(text("SELECT 1 FROM subarea WHERE id_subarea = :id AND id_municipio = :mun"),
                           {"id": id_subarea, "mun": id_municipio}):
        raise HTTPException(status_code=404, detail=f"Registro {id_subarea} no encontrado en subarea")
    r = await db.execute(text("""
        SELECT id_tipo_reclamo, nombre, descripcion, sla_dias, sla_minutos, audit
        FROM tipo_reclamo
        WHERE id_subarea = :id_subarea AND activo = TRUE AND id_municipio = :mun
        ORDER BY nombre
    """), {"id_subarea": id_subarea, "mun": id_municipio})
    return [dict(row._mapping) for row in r.fetchall()]


# ─── DELETE /{tabla}/{id} — baja lógica ───────────────────────────────────────

@router.delete("/{tabla}/{id}", responses={422: {"description": AREA_FIJA}})
async def baja_logica(
    tabla: str,
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    id_municipio: int = Depends(municipio_actual),
):
    cfg = _get_config(tabla)
    _bloquear_si_read_only(tabla)
    await _autorizar_escritura(db, tabla, "baja", current_user, id_municipio=id_municipio, id=id)
    await _rechazar_baja_area_fija(db, tabla, id, id_municipio)
    pk = cfg["pk"]
    fecha_mod = cfg["fecha_mod"]
    if not cfg.get("has_activo", True):
        raise HTTPException(
            status_code=400,
            detail=f"La tabla '{tabla}' no soporta baja lógica (sin campo activo)"
        )
    parts: list[str] = ["activo = FALSE"]
    params: dict = {"id": id}
    if fecha_mod:
        parts.append(f"{fecha_mod} = NOW()")
    if cfg.get("has_audit", True):
        parts.append("id_usuario_modificacion = :uid")
        params["uid"] = current_user["id_usuario"]
    del_municipio = ""
    if _por_municipio(tabla):
        del_municipio = " AND id_municipio = :mun"
        params["mun"] = id_municipio
    stmt = text(f"UPDATE {tabla} SET {', '.join(parts)} WHERE {pk} = :id{del_municipio} RETURNING {pk}")
    try:
        result = await db.execute(stmt, params)
        await db.commit()
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Registro {id} no encontrado en {tabla}")
        return {"ok": True, pk: id}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Error al dar de baja en %s id=%s: %s", tabla, id, e)
        raise HTTPException(status_code=400, detail=str(e))
