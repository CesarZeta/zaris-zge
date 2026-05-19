"""
Helpers de versionado del catalogo de tramites.

Regla acordada (sesion 2026-05-18):
- Si v1 (o vN actual) NO tiene tramites instanciados -> permitir editar in-place
- Si SI tiene tramites instanciados -> forzar crear v2 (borrador)

Una version en estado 'publicado' con tramites instanciados es inmutable.
Una version en estado 'borrador' siempre es editable.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def version_tiene_tramites(db: AsyncSession, id_version: int) -> int:
    """Cuenta tramites instanciados que apuntan a esta version."""
    row = (await db.execute(
        text("SELECT COUNT(*) AS n FROM tramite WHERE id_tipo_tramite_version = :v"),
        {"v": id_version},
    )).fetchone()
    return int(row.n) if row else 0


async def cargar_version(db: AsyncSession, id_version: int) -> dict:
    """Devuelve la fila de tipo_tramite_version como dict, o 404."""
    row = (await db.execute(
        text("""
            SELECT id_tipo_tramite_version, id_tipo_tramite, version_num,
                   estado, publicada_en, activo, id_municipio
            FROM tipo_tramite_version
            WHERE id_tipo_tramite_version = :v
        """),
        {"v": id_version},
    )).fetchone()
    if not row:
        raise HTTPException(404, "Version de tipo de tramite no encontrada")
    return {
        "id_tipo_tramite_version": row.id_tipo_tramite_version,
        "id_tipo_tramite": row.id_tipo_tramite,
        "version_num": row.version_num,
        "estado": row.estado,
        "publicada_en": row.publicada_en,
        "activo": row.activo,
        "id_municipio": row.id_municipio,
    }


async def asegurar_editable(db: AsyncSession, id_version: int) -> dict:
    """
    Valida que una version se pueda editar in-place.

    Permitido si:
    - estado = 'borrador' (siempre editable)
    - estado = 'publicado' Y la version no tiene tramites instanciados

    Devuelve la fila de la version. Levanta 409 si no es editable.
    """
    ver = await cargar_version(db, id_version)

    if not ver["activo"]:
        raise HTTPException(409, "La version esta inactiva")

    if ver["estado"] == "archivado":
        raise HTTPException(409, "La version esta archivada")

    if ver["estado"] == "borrador":
        return ver

    # estado = 'publicado': editable solo si nadie la usa
    n = await version_tiene_tramites(db, id_version)
    if n > 0:
        raise HTTPException(
            409,
            f"La version v{ver['version_num']} ya tiene {n} tramite(s) instanciado(s). "
            "Crea una nueva version (borrador) para editar el circuito.",
        )

    return ver


async def crear_borrador_desde_publicada(
    db: AsyncSession,
    id_tipo_tramite: int,
    id_municipio: int,
    id_agente: int | None = None,
) -> int:
    """
    Crea una nueva version_num + 1 en estado 'borrador', copiando
    estructura (campos, estados, transiciones, docs requeridos) desde
    la version publicada actual.

    Devuelve id_tipo_tramite_version del nuevo borrador.
    """
    # 1. Verificar que no haya ya un borrador abierto
    existente = (await db.execute(
        text("""
            SELECT id_tipo_tramite_version, version_num
            FROM tipo_tramite_version
            WHERE id_tipo_tramite = :tt AND estado = 'borrador' AND activo = TRUE
            ORDER BY version_num DESC
            LIMIT 1
        """),
        {"tt": id_tipo_tramite},
    )).fetchone()
    if existente:
        raise HTTPException(
            409,
            f"Ya existe un borrador abierto (v{existente.version_num}, id={existente.id_tipo_tramite_version}). "
            "Publicalo o archivalo antes de crear otro.",
        )

    # 2. Obtener proxima version_num
    max_row = (await db.execute(
        text("SELECT COALESCE(MAX(version_num), 0) AS m FROM tipo_tramite_version WHERE id_tipo_tramite = :tt"),
        {"tt": id_tipo_tramite},
    )).fetchone()
    nueva_version = int(max_row.m) + 1

    # 3. Buscar version publicada para copiar
    publicada = (await db.execute(
        text("""
            SELECT ttv.id_tipo_tramite_version
            FROM tipo_tramite tt
            JOIN tipo_tramite_version ttv ON ttv.id_tipo_tramite_version = tt.id_version_publicada
            WHERE tt.id_tipo_tramite = :tt
        """),
        {"tt": id_tipo_tramite},
    )).fetchone()

    # 4. Crear borrador
    new_id = (await db.execute(
        text("""
            INSERT INTO tipo_tramite_version
                (id_tipo_tramite, version_num, estado, activo, id_municipio)
            VALUES (:tt, :vn, 'borrador', TRUE, :mun)
            RETURNING id_tipo_tramite_version
        """),
        {"tt": id_tipo_tramite, "vn": nueva_version, "mun": id_municipio},
    )).scalar_one()

    # 5. Si habia version publicada, copiar estructura
    if publicada:
        await _copiar_estructura(db, publicada.id_tipo_tramite_version, new_id, id_municipio)

    return int(new_id)


async def _copiar_estructura(
    db: AsyncSession,
    id_version_origen: int,
    id_version_destino: int,
    id_municipio: int,
) -> None:
    """Copia campos, estados, transiciones y docs_requeridos de una version a otra."""
    # Campos (sin FKs internas, copia directa)
    await db.execute(
        text("""
            INSERT INTO tipo_tramite_campo
                (id_tipo_tramite_version, nombre_interno, etiqueta, tipo_dato,
                 obligatorio, orden, opciones_jsonb, validacion_jsonb, ayuda,
                 visible_en_listado, activo, id_municipio)
            SELECT :dst, nombre_interno, etiqueta, tipo_dato,
                   obligatorio, orden, opciones_jsonb, validacion_jsonb, ayuda,
                   visible_en_listado, TRUE, :mun
            FROM tipo_tramite_campo
            WHERE id_tipo_tramite_version = :src AND activo = TRUE
        """),
        {"src": id_version_origen, "dst": id_version_destino, "mun": id_municipio},
    )

    # Estados: necesitamos mapeo viejo_id -> nuevo_id para transiciones y docs
    estados_viejos = (await db.execute(
        text("""
            SELECT id_tipo_tramite_estado, codigo, etiqueta, descripcion, color,
                   orden, es_inicial, es_final, permite_adjuntar, permite_comentar,
                   oculto_para_iniciador
            FROM tipo_tramite_estado
            WHERE id_tipo_tramite_version = :src AND activo = TRUE
            ORDER BY orden
        """),
        {"src": id_version_origen},
    )).fetchall()

    mapa_estados: dict[int, int] = {}
    for e in estados_viejos:
        nuevo_id = (await db.execute(
            text("""
                INSERT INTO tipo_tramite_estado
                    (id_tipo_tramite_version, codigo, etiqueta, descripcion, color,
                     orden, es_inicial, es_final, permite_adjuntar, permite_comentar,
                     oculto_para_iniciador, activo, id_municipio)
                VALUES (:v, :cod, :eti, :desc, :col, :ord, :ini, :fin, :adj, :com,
                        :oci, TRUE, :mun)
                RETURNING id_tipo_tramite_estado
            """),
            {
                "v": id_version_destino, "cod": e.codigo, "eti": e.etiqueta,
                "desc": e.descripcion, "col": e.color, "ord": e.orden,
                "ini": e.es_inicial, "fin": e.es_final, "adj": e.permite_adjuntar,
                "com": e.permite_comentar, "oci": e.oculto_para_iniciador,
                "mun": id_municipio,
            },
        )).scalar_one()
        mapa_estados[e.id_tipo_tramite_estado] = int(nuevo_id)

    # Transiciones (re-mapeando estado_origen/destino)
    transiciones = (await db.execute(
        text("""
            SELECT id_estado_origen, id_estado_destino, etiqueta_accion, orden,
                   quien_puede_jsonb, requiere_comentario, requiere_adjunto,
                   destino_automatico_jsonb, notifica_iniciador
            FROM tipo_tramite_transicion
            WHERE id_tipo_tramite_version = :src AND activo = TRUE
        """),
        {"src": id_version_origen},
    )).fetchall()

    import json
    for t in transiciones:
        await db.execute(
            text("""
                INSERT INTO tipo_tramite_transicion
                    (id_tipo_tramite_version, id_estado_origen, id_estado_destino,
                     etiqueta_accion, orden, quien_puede_jsonb,
                     requiere_comentario, requiere_adjunto,
                     destino_automatico_jsonb, notifica_iniciador,
                     activo, id_municipio)
                VALUES (:v, :ori, :dst, :eti, :ord, CAST(:qp AS jsonb),
                        :rc, :ra, CAST(:da AS jsonb), :ni, TRUE, :mun)
            """),
            {
                "v": id_version_destino,
                "ori": mapa_estados[t.id_estado_origen],
                "dst": mapa_estados[t.id_estado_destino],
                "eti": t.etiqueta_accion, "ord": t.orden,
                "qp": json.dumps(t.quien_puede_jsonb) if t.quien_puede_jsonb else "{}",
                "rc": t.requiere_comentario, "ra": t.requiere_adjunto,
                "da": json.dumps(t.destino_automatico_jsonb) if t.destino_automatico_jsonb else None,
                "ni": t.notifica_iniciador, "mun": id_municipio,
            },
        )

    # Documentos requeridos (re-mapeando id_tipo_tramite_estado opcional)
    docs = (await db.execute(
        text("""
            SELECT id_tipo_tramite_estado, nombre, descripcion, obligatorio,
                   formatos_permitidos, tamano_max_mb, requiere_firma,
                   firmantes_jsonb, aporta_quien, orden
            FROM tipo_tramite_documento_requerido
            WHERE id_tipo_tramite_version = :src AND activo = TRUE
        """),
        {"src": id_version_origen},
    )).fetchall()

    for d in docs:
        await db.execute(
            text("""
                INSERT INTO tipo_tramite_documento_requerido
                    (id_tipo_tramite_version, id_tipo_tramite_estado, nombre,
                     descripcion, obligatorio, formatos_permitidos, tamano_max_mb,
                     requiere_firma, firmantes_jsonb, aporta_quien, orden,
                     activo, id_municipio)
                VALUES (:v, :est, :nom, :desc, :obl, :for, :tam, :rf,
                        CAST(:fj AS jsonb), :aq, :ord, TRUE, :mun)
            """),
            {
                "v": id_version_destino,
                "est": mapa_estados.get(d.id_tipo_tramite_estado) if d.id_tipo_tramite_estado else None,
                "nom": d.nombre, "desc": d.descripcion, "obl": d.obligatorio,
                "for": list(d.formatos_permitidos or []),
                "tam": d.tamano_max_mb, "rf": d.requiere_firma,
                "fj": json.dumps(d.firmantes_jsonb) if d.firmantes_jsonb else None,
                "aq": d.aporta_quien, "ord": d.orden, "mun": id_municipio,
            },
        )


async def publicar_version(
    db: AsyncSession,
    id_version: int,
    id_agente: int | None = None,
) -> dict:
    """
    Publica una version en borrador. Valida:
    - Estado actual = 'borrador'
    - Al menos 1 estado inicial y >= 1 estado final
    - Todas las transiciones referencian estados de la misma version

    Marca:
    - version.estado = 'publicado', publicada_en = NOW(), id_agente_publicador
    - tipo_tramite.id_version_publicada = id_version (FK deferida)
    - Si habia una version anterior publicada -> queda 'archivado'
    """
    ver = await cargar_version(db, id_version)

    if ver["estado"] != "borrador":
        raise HTTPException(409, f"Solo se puede publicar una version en estado 'borrador' (actual: {ver['estado']})")

    # Validar consistencia minima
    inicial = (await db.execute(
        text("SELECT COUNT(*) AS n FROM tipo_tramite_estado WHERE id_tipo_tramite_version = :v AND es_inicial = TRUE AND activo = TRUE"),
        {"v": id_version},
    )).scalar_one()
    if int(inicial) != 1:
        raise HTTPException(409, f"La version debe tener exactamente 1 estado inicial (tiene {inicial})")

    final = (await db.execute(
        text("SELECT COUNT(*) AS n FROM tipo_tramite_estado WHERE id_tipo_tramite_version = :v AND es_final = TRUE AND activo = TRUE"),
        {"v": id_version},
    )).scalar_one()
    if int(final) < 1:
        raise HTTPException(409, "La version debe tener al menos 1 estado final")

    # Archivar version publicada anterior (si la hay)
    anterior = (await db.execute(
        text("""
            SELECT tt.id_version_publicada
            FROM tipo_tramite tt
            WHERE tt.id_tipo_tramite = :tt
        """),
        {"tt": ver["id_tipo_tramite"]},
    )).fetchone()

    if anterior and anterior.id_version_publicada and anterior.id_version_publicada != id_version:
        await db.execute(
            text("""
                UPDATE tipo_tramite_version
                   SET estado = 'archivado', fecha_modificacion = NOW()
                 WHERE id_tipo_tramite_version = :v
            """),
            {"v": anterior.id_version_publicada},
        )

    # Marcar nueva como publicada
    now = datetime.now(timezone.utc)
    await db.execute(
        text("""
            UPDATE tipo_tramite_version
               SET estado = 'publicado',
                   publicada_en = :now,
                   id_agente_publicador = :ag,
                   fecha_modificacion = NOW()
             WHERE id_tipo_tramite_version = :v
        """),
        {"now": now, "ag": id_agente, "v": id_version},
    )

    # Update FK del tipo
    await db.execute(
        text("""
            UPDATE tipo_tramite
               SET id_version_publicada = :v,
                   fecha_modificacion = NOW()
             WHERE id_tipo_tramite = :tt
        """),
        {"v": id_version, "tt": ver["id_tipo_tramite"]},
    )

    ver["estado"] = "publicado"
    ver["publicada_en"] = now
    return ver
