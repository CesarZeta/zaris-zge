# -*- coding: utf-8 -*-
"""
Restablece y habilita el segundo factor de un super administrador (IT-01 F3b,
PLAN_MULTI_MUNICIPIO_F3B.md, Tarea 5). Para los administradores de un municipio lo hace el super
desde Usuarios; para el nivel 0 no hay botón: se usa este script.

    cd backend
    # local (solo zaris_dev):
    $env:ENV_FILE=".env.local"; python habilitar_segundo_factor.py --email X
    # prod: imprime el SQL para correrlo por execute_sql (no conecta a ninguna base):
    python habilitar_segundo_factor.py --email X --imprimir-sql

Mismo efecto que el botón: borra la app vinculada y los códigos de emergencia, corta las sesiones
abiertas y abre 24 h para vincular la app desde el login. Sale con error si el email no es de una
cuenta de nivel 0. El email no se escribe en ningún archivo del repo.
"""
import argparse
import asyncio
import os
import sys

os.environ.setdefault("ENV_FILE", ".env.local")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _literal(v: str) -> str:
    return "'" + v.replace("'", "''") + "'"


def imprimir_sql(email: str) -> None:
    from app.services.segundo_factor import HABILITACION_HORAS
    cuenta = (f"SELECT id_usuario FROM usuarios WHERE lower(email) = {_literal(email)} "
              f"AND nivel_acceso = 0 AND id_municipio IS NULL")
    print(f"""BEGIN;
INSERT INTO usuario_segundo_factor (id_usuario, id_municipio, habilitado_hasta)
SELECT id_usuario, NULL, NOW() + make_interval(hours => {HABILITACION_HORAS}) FROM ({cuenta}) c
ON CONFLICT (id_usuario) DO UPDATE
   SET secreto_cifrado = NULL, secreto_pendiente_cifrado = NULL, confirmado_en = NULL,
       ultimo_paso = NULL, intentos_fallidos = 0, bloqueado_hasta = NULL,
       habilitado_hasta = EXCLUDED.habilitado_hasta, fecha_modificacion = NOW();
UPDATE usuario_codigo_emergencia SET activo = FALSE WHERE activo AND id_usuario IN ({cuenta});
UPDATE usuarios SET sesiones_validas_desde = date_trunc('second', NOW()) WHERE id_usuario IN ({cuenta});
INSERT INTO usuario_segundo_factor_evento (id_usuario, id_municipio, evento)
SELECT id_usuario, NULL, 'habilitado' FROM ({cuenta}) c;
COMMIT;
SELECT id_usuario, habilitado_hasta, secreto_cifrado IS NULL AS sin_app
  FROM usuario_segundo_factor WHERE id_usuario IN ({cuenta});""")


async def habilitar_local(email: str) -> int:
    from sqlalchemy import text

    from app.core.config import settings
    from app.core.database import AsyncSessionLocal
    from app.services import segundo_factor as sf

    if "zaris_dev" not in settings.ASYNC_DATABASE_URI:
        print("ABORT: sin --imprimir-sql este script solo conecta a zaris_dev.")
        return 2
    async with AsyncSessionLocal() as db:
        if (await db.execute(text("SELECT current_database()"))).scalar() != "zaris_dev":
            print("ABORT: la base conectada no es zaris_dev.")
            return 2
        id_u = (await db.execute(text(
            "SELECT id_usuario FROM usuarios WHERE lower(email) = :e AND nivel_acceso = 0 AND id_municipio IS NULL"),
            {"e": email})).scalar()
        if id_u is None:
            print("404: no hay una cuenta de nivel 0 (super administrador) con ese email.")
            return 3
        await sf.habilitar(db, id_usuario=id_u, id_municipio=None, id_actor=None)
        await db.commit()
    print(f"OK: segundo factor restablecido; la cuenta {id_u} puede vincular la app en las próximas "
          f"{sf.HABILITACION_HORAS} h.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Restablece y habilita el segundo factor de un super administrador.")
    p.add_argument("--email", required=True)
    p.add_argument("--imprimir-sql", action="store_true", help="Imprime el SQL y no conecta.")
    args = p.parse_args()
    email = args.email.strip().lower()
    if "@" not in email:
        print("ABORT: --email no parece un email.")
        return 2
    if args.imprimir_sql:
        imprimir_sql(email)
        return 0
    return asyncio.run(habilitar_local(email))


if __name__ == "__main__":
    sys.exit(main())
