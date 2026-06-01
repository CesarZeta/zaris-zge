"""
Storage de documentos de tramites — Supabase Storage (bucket privado).

Migrado del mock local (backend/uploads/, efimero en Railway) a Supabase el
2026-05-27. El backend calcula el SHA256 sobre los bytes (clave para firmas) y
sube el binario al bucket con service_role. La descarga vuelve a streamear desde
el bucket. Bucket: 'tramites-documentos' (privado).
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage

TRAMITES_BUCKET = "tramites-documentos"
# Tope por defecto para adjuntar (sin documento requerido). Un documento
# requerido puede definir su propio tamano_max_mb (tiene prioridad). 10 MB es
# suficiente para documentacion administrativa; evita binarios pesados en el
# bucket. La UI espeja este valor (FileUploader) — si lo cambias, actualizar
# tambien el hint del front y docs/manual_tramites.html S10.
UPLOADS_MAX_SIZE_MB = 10

ALLOWED_MIME_MAP: dict[str, str] = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _slug(texto: str) -> str:
    """Convierte texto a slug ASCII seguro."""
    texto = texto.lower().strip()
    reemplazos = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n", "ü": "u"}
    for src, dst in reemplazos.items():
        texto = texto.replace(src, dst)
    texto = re.sub(r"[^a-z0-9._-]", "-", texto)
    texto = re.sub(r"-+", "-", texto)
    return texto.strip("-")


def _extension(filename: str) -> str:
    return Path(filename).suffix.lstrip(".").lower()


async def validar_archivo_mock(
    file: UploadFile,
    doc_requerido: dict | None,
) -> None:
    """
    Valida extension y tamaño.
    Si doc_requerido esta dado, aplica sus restricciones.
    Si no, acepta ALLOWED_MIME_MAP con max UPLOADS_MAX_SIZE_MB.
    Lanza HTTPException 400 si falla.
    """
    ext = _extension(file.filename or "")

    if doc_requerido:
        formatos = [f.lower() for f in (doc_requerido.get("formatos_permitidos") or [])]
        if formatos and ext not in formatos:
            raise HTTPException(
                400,
                f"Formato '{ext}' no permitido para este documento. "
                f"Permitidos: {formatos}",
            )
        max_mb = doc_requerido.get("tamano_max_mb") or UPLOADS_MAX_SIZE_MB
    else:
        if ext not in ALLOWED_MIME_MAP:
            raise HTTPException(
                400,
                f"Formato '{ext}' no aceptado. "
                f"Permitidos: {sorted(ALLOWED_MIME_MAP.keys())}",
            )
        max_mb = UPLOADS_MAX_SIZE_MB

    # Verificar tamaño leyendo el archivo (file.size puede no estar disponible)
    contenido = await file.read()
    tamano_mb = len(contenido) / (1024 * 1024)
    if tamano_mb > max_mb:
        raise HTTPException(
            400,
            f"El archivo supera el tamaño maximo de {max_mb} MB "
            f"({tamano_mb:.1f} MB recibido)",
        )
    # Rebobinar para que guardar_archivo_mock pueda leer
    await file.seek(0)


async def guardar_archivo_mock(
    file: UploadFile,
    numero_expediente: str,
    anio: int,
    nombre_logico: str,
) -> dict:
    """
    Sube el archivo a Supabase Storage (bucket privado TRAMITES_BUCKET).

    El backend calcula el SHA256 sobre los bytes (necesario para la verificación
    de integridad en firmas) y luego hace PUT del binario al bucket. El nombre
    conserva el patrón mock por compat, pero ya NO escribe a disco local.

    Devuelve {storage_path, hash_sha256, tamano_bytes, mime_type, nombre_archivo_original}.
    """
    ext = _extension(file.filename or "bin")
    slug_base = _slug(nombre_logico or Path(file.filename or "archivo").stem) or "archivo"

    contenido = await file.read()
    sha256 = hashlib.sha256(contenido).hexdigest()
    mime = ALLOWED_MIME_MAP.get(ext) or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"

    # Path en el bucket: tramites/{anio}/{expediente}/{uuid}.{ext}. El uuid evita
    # colisiones sin necesidad de listar el bucket (el slug va en el nombre lógico DB).
    storage_path = f"tramites/{anio}/{_slug(numero_expediente)}/{uuid.uuid4()}.{ext}"

    await storage.subir_objeto(storage_path, contenido, mime, bucket=TRAMITES_BUCKET)

    return {
        "storage_path": storage_path,
        "hash_sha256": sha256,
        "tamano_bytes": len(contenido),
        "mime_type": mime,
        "nombre_archivo_original": file.filename or f"{slug_base}.{ext}",
    }


async def descargar_bytes(storage_path: str) -> bytes:
    """Descarga el binario del bucket de trámites."""
    return await storage.descargar_objeto(storage_path, bucket=TRAMITES_BUCKET)


async def borrar_archivo(storage_path: str) -> None:
    """Borra el objeto del bucket (best-effort)."""
    await storage.borrar_objeto(storage_path, bucket=TRAMITES_BUCKET)


async def obtener_proxima_posicion(id_tramite: int, db: AsyncSession) -> int:
    row = (await db.execute(
        text("""
            SELECT COALESCE(MAX(posicion_orden), 0) + 1
            FROM tramite_documento
            WHERE id_tramite = :id AND activo = TRUE
        """),
        {"id": id_tramite},
    )).fetchone()
    return row[0]


async def crear_firmas_pendientes(
    id_tramite_documento: int,
    doc_requerido: dict,
    db: AsyncSession,
    id_usuario: int,
    id_municipio: int,
) -> list[int]:
    """
    Si doc_requerido.requiere_firma y tiene firmantes_jsonb,
    crea registros en tramite_firma con estado='pendiente'.
    Devuelve lista de id_tramite_firma creados.
    """
    firmantes = doc_requerido.get("firmantes_jsonb") or []
    if not firmantes or not doc_requerido.get("requiere_firma"):
        return []

    ids_creados: list[int] = []
    for f in firmantes:
        tipo = f.get("tipo")
        fk_id = f.get("id")

        id_agente_asignado = fk_id if tipo == "agente" else None
        id_subarea_asignada = fk_id if tipo == "subarea" else None
        id_equipo_asignado = fk_id if tipo == "equipo" else None

        row = (await db.execute(
            text("""
                INSERT INTO tramite_firma (
                    id_tramite_documento, rol_intervencion, orden,
                    id_agente_asignado, id_subarea_asignada, id_equipo_asignado,
                    estado, id_municipio,
                    id_usuario_alta, id_usuario_modificacion
                ) VALUES (
                    :doc, :rol, :orden,
                    :ag, :sa, :eq,
                    'pendiente', :mun,
                    :uid, :uid
                )
                RETURNING id_tramite_firma
            """),
            {
                "doc": id_tramite_documento,
                "rol": f.get("rol_intervencion", "firma"),
                "orden": f.get("orden", 0),
                "ag": id_agente_asignado,
                "sa": id_subarea_asignada,
                "eq": id_equipo_asignado,
                "mun": id_municipio,
                "uid": id_usuario,
            },
        )).fetchone()
        ids_creados.append(row.id_tramite_firma)

    return ids_creados
