"""
Mock storage para documentos de tramites (Fase 2).

Los archivos se guardan en backend/uploads/tramites/{anio}/{numero_expediente}/{slug}.{ext}
SHA256 streaming (chunks 64KB). Interfaz nombrada para refactor a Supabase en Fase 3.
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import re
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

UPLOADS_BASE = Path("backend/uploads")
UPLOADS_MAX_SIZE_MB = 25

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
    Guarda el archivo en disco local.
    Devuelve {storage_path, hash_sha256, tamano_bytes, mime_type, nombre_archivo_original}.
    """
    ext = _extension(file.filename or "bin")
    slug_base = _slug(nombre_logico or Path(file.filename or "archivo").stem)
    if not slug_base:
        slug_base = "archivo"

    directorio = UPLOADS_BASE / "tramites" / str(anio) / _slug(numero_expediente)
    directorio.mkdir(parents=True, exist_ok=True)

    # Resolver colisiones de nombre
    candidato = directorio / f"{slug_base}.{ext}"
    sufijo = 2
    while candidato.exists():
        candidato = directorio / f"{slug_base}_{sufijo}.{ext}"
        sufijo += 1

    contenido = await file.read()
    candidato.write_bytes(contenido)

    sha256 = calcular_sha256_streaming_mock(candidato)
    mime = ALLOWED_MIME_MAP.get(ext) or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"

    storage_path = str(candidato.relative_to(Path("backend")))

    return {
        "storage_path": storage_path,
        "hash_sha256": sha256,
        "tamano_bytes": len(contenido),
        "mime_type": mime,
        "nombre_archivo_original": file.filename or candidato.name,
    }


def calcular_sha256_streaming_mock(file_path: Path, chunk_size: int = 65536) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def ruta_absoluta_mock(storage_path: str) -> Path:
    """Devuelve la ruta absoluta en disco a partir del storage_path relativo."""
    return Path("backend") / storage_path


def existe_archivo_mock(storage_path: str) -> bool:
    return ruta_absoluta_mock(storage_path).exists()


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
