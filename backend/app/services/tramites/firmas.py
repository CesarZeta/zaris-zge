"""
Logica de firma electronica auditable para el modulo Tramites.

Sin valor legal (Ley 25.506). Constancia interna.
Preparado para enchufar proveedor externo en Fase 3.
"""
from __future__ import annotations

from fastapi import HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.tramites.auth import es_admin
from app.services.tramites.documentos import calcular_sha256_streaming_mock, ruta_absoluta_mock


async def agente_puede_firmar(
    agente_info: dict,
    firma: dict,
) -> tuple[bool, str | None]:
    """
    Reglas:
    - estado debe ser 'pendiente'
    - Si firma.id_agente_asignado: solo ese agente (o admin)
    - Si firma.id_subarea_asignada: agente de esa subarea (o admin)
    - Si firma.id_equipo_asignado: agente de ese equipo (o admin)
    """
    if firma.get("estado") != "pendiente":
        return False, f"La firma ya esta en estado '{firma['estado']}'"

    if es_admin(agente_info["nivel_acceso"]):
        return True, None

    id_ag_asig = firma.get("id_agente_asignado")
    id_sa_asig = firma.get("id_subarea_asignada")
    id_eq_asig = firma.get("id_equipo_asignado")

    if id_ag_asig is not None:
        if agente_info["id_agente"] != id_ag_asig:
            return False, "Esta firma esta asignada a otro agente"
        return True, None

    if id_sa_asig is not None:
        if agente_info["id_subarea"] != id_sa_asig:
            return False, "Tu subarea no esta asignada para firmar este documento"
        return True, None

    if id_eq_asig is not None:
        if id_eq_asig not in agente_info["ids_equipos"]:
            return False, "Tu equipo no esta asignado para firmar este documento"
        return True, None

    # Sin restriccion especifica: cualquiera puede firmar (no deberia pasar
    # con firmantes_jsonb bien configurado, pero fail-open)
    return True, None


async def marcar_firma(
    id_tramite_firma: int,
    agente_info: dict,
    request: Request,
    hash_documento_actual: str,
    db: AsyncSession,
    id_usuario: int,
) -> dict:
    """
    Setea estado='firmado', captura evidencia y devuelve fila actualizada.
    """
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    result = await db.execute(
        text("""
            UPDATE tramite_firma SET
                estado              = 'firmado',
                id_agente_firmante  = :ag,
                firmado_en          = NOW(),
                ip_firma            = :ip,
                user_agent_firma    = :ua,
                hash_documento_firmado = :hash,
                fecha_modificacion  = NOW(),
                id_usuario_modificacion = :uid
            WHERE id_tramite_firma = :fid
            RETURNING id_tramite_firma, estado, firmado_en, hash_documento_firmado
        """),
        {
            "ag": agente_info["id_agente"],
            "ip": ip,
            "ua": ua,
            "hash": hash_documento_actual,
            "uid": id_usuario,
            "fid": id_tramite_firma,
        },
    )
    row = result.fetchone()
    return {
        "id_tramite_firma": row.id_tramite_firma,
        "estado": row.estado,
        "firmado_en": row.firmado_en,
        "hash_documento_firmado": row.hash_documento_firmado,
    }


async def actualizar_estado_firma_documento(
    id_tramite_documento: int,
    db: AsyncSession,
) -> str:
    """
    Recalcula el estado_firma del documento basandose en sus firmas.
    - Si alguna 'firma' esta 'rechazada' -> 'rechazado'
    - Si todas las 'firma' estan 'firmado' -> 'firmado'
    - Si alguna 'firma' sigue 'pendiente' -> 'pendiente'
    Las de rol 'visado' y 'notificacion' son informativas, no bloquean.
    """
    rows = (await db.execute(
        text("""
            SELECT rol_intervencion, estado
            FROM tramite_firma
            WHERE id_tramite_documento = :did AND activo = TRUE
        """),
        {"did": id_tramite_documento},
    )).fetchall()

    firmas_reales = [r for r in rows if r.rol_intervencion == "firma"]

    if not firmas_reales:
        estado_nuevo = "no_requiere"
    elif any(r.estado == "rechazado" for r in firmas_reales):
        estado_nuevo = "rechazado"
    elif all(r.estado == "firmado" for r in firmas_reales):
        estado_nuevo = "firmado"
    else:
        estado_nuevo = "pendiente"

    await db.execute(
        text("""
            UPDATE tramite_documento
            SET estado_firma = :estado, fecha_modificacion = NOW()
            WHERE id_tramite_documento = :did
        """),
        {"estado": estado_nuevo, "did": id_tramite_documento},
    )

    return estado_nuevo


async def verificar_integridad_documento(
    tramite_documento: dict,
) -> str:
    """
    Recalcula SHA256 del archivo en disco y lo compara con el almacenado.
    Lanza HTTPException 500 si hay corrupcion.
    Devuelve el hash actual (para guardarlo al firmar).
    """
    storage_path = tramite_documento.get("storage_path")
    if not storage_path:
        raise HTTPException(500, "El documento no tiene storage_path registrado")

    ruta = ruta_absoluta_mock(storage_path)
    if not ruta.exists():
        raise HTTPException(500, "Archivo no encontrado en disco — posible corrupcion")

    hash_actual = calcular_sha256_streaming_mock(ruta)
    hash_original = tramite_documento.get("hash_sha256")

    if hash_original and hash_actual != hash_original:
        raise HTTPException(
            500,
            "El documento fue modificado desde su subida — no se puede firmar",
        )

    return hash_actual
