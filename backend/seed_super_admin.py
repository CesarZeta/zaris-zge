# -*- coding: utf-8 -*-
"""
Alta de un super administrador (IT-01 F3, PLAN_MULTI_MUNICIPIO_F3.md, Tarea 1).

    cd backend
    # local (con clave de desarrollo, solo zaris_dev):
    $env:ENV_FILE=".env.local"; python seed_super_admin.py --email X --nombre "Y" --password-dev 123456
    # prod: imprime el INSERT para correrlo por execute_sql (no conecta a ninguna base):
    python seed_super_admin.py --email X --nombre "Y" --imprimir-sql

Crea una cuenta de nivel 0 sin municipio. Sin --password-dev la clave es el bcrypt de bytes
aleatorios que se descartan: nadie la conoce y se elige con «Olvidé mi contraseña».
Idempotente. Sale con error si el email ya lo usa otra cuenta interna (los identificadores del
nivel 0 quedan reservados, spec §3). Requiere la migración 127.
"""
import argparse
import asyncio
import os
import secrets
import sys

import bcrypt

os.environ.setdefault("ENV_FILE", ".env.local")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Columnas que escribe el alta. Toda columna NOT NULL sin default de `usuarios` tiene que estar acá.
COLUMNAS = ("nombre", "nivel_acceso", "username", "email", "password_hash", "id_municipio",
            "activo", "buc_acceso", "debe_cambiar_password")


def _hash(clave: str | None) -> str:
    plano = clave if clave is not None else secrets.token_hex(32)
    return bcrypt.hashpw(plano.encode(), bcrypt.gensalt()).decode()


def _valores(args) -> dict:
    return {
        "nombre": args.nombre.strip(),
        "nivel_acceso": 0,
        "username": (args.username or args.email).strip().lower(),
        "email": args.email.strip().lower(),
        "password_hash": _hash(args.password_dev),
        "id_municipio": None,
        "activo": True,
        "buc_acceso": False,
        # Con clave de desarrollo se entra directo; sin ella, el reseteo por mail limpia la marca.
        "debe_cambiar_password": args.password_dev is None,
    }


def _literal(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, int):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def imprimir_sql(args) -> None:
    v = _valores(args)
    cols = ", ".join(COLUMNAS)
    vals = ", ".join(_literal(v[c]) for c in COLUMNAS)
    print(f"INSERT INTO usuarios ({cols})\nSELECT {vals}\n WHERE NOT EXISTS "
          f"(SELECT 1 FROM usuarios WHERE lower(email) = {_literal(v['email'])} "
          f"OR lower(username) = {_literal(v['username'])})\nRETURNING id_usuario, email, nivel_acceso, id_municipio;")


async def alta(args) -> int:
    from sqlalchemy import text

    from app.core.config import settings
    from app.core.database import AsyncSessionLocal

    if args.password_dev is not None and "zaris_dev" not in settings.ASYNC_DATABASE_URI:
        print("ABORT: --password-dev solo se acepta contra zaris_dev.")
        return 2
    v = _valores(args)
    async with AsyncSessionLocal() as db:
        faltan = [r[0] for r in (await db.execute(text("""
            SELECT column_name FROM information_schema.columns
             WHERE table_schema = 'public' AND table_name = 'usuarios'
               AND is_nullable = 'NO' AND column_default IS NULL""")))
                  if r[0] not in COLUMNAS]
        if faltan:
            print(f"ABORT: usuarios tiene columnas NOT NULL sin default que el alta no escribe: {faltan}")
            return 2
        existente = (await db.execute(text("""
            SELECT id_usuario, nivel_acceso, id_municipio FROM usuarios
             WHERE lower(email) = :e OR lower(username) = :u"""),
            {"e": v["email"], "u": v["username"]})).fetchall()
        if existente:
            if len(existente) == 1 and existente[0].nivel_acceso == 0 and existente[0].id_municipio is None:
                print(f"Ya existe: super administrador id_usuario={existente[0].id_usuario}. Sin cambios.")
                return 0
            print(f"409: ese email o usuario ya lo usa otra cuenta interna ({[tuple(r) for r in existente]}).")
            return 3
        cols = ", ".join(COLUMNAS)
        marcas = ", ".join(f":{c}" for c in COLUMNAS)
        nuevo = (await db.execute(text(f"INSERT INTO usuarios ({cols}) VALUES ({marcas}) RETURNING id_usuario"),
                                  v)).scalar()
        await db.commit()
    print(f"OK: super administrador creado, id_usuario={nuevo}, email={v['email']}.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Alta de un super administrador (nivel 0, sin municipio).")
    p.add_argument("--email", required=True)
    p.add_argument("--nombre", required=True)
    p.add_argument("--username", help="Por defecto, el email.")
    p.add_argument("--password-dev", help="Clave conocida, solo contra zaris_dev.")
    p.add_argument("--imprimir-sql", action="store_true", help="Imprime el INSERT y no conecta.")
    args = p.parse_args()
    if "@" not in args.email:
        print("ABORT: --email no parece un email.")
        return 2
    if args.imprimir_sql:
        if args.password_dev is not None:
            print("ABORT: --imprimir-sql no admite --password-dev.")
            return 2
        imprimir_sql(args)
        return 0
    return asyncio.run(alta(args))


if __name__ == "__main__":
    sys.exit(main())
