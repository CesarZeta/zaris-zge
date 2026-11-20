# -*- coding: utf-8 -*-
"""
Smoke — archivos con carpeta por municipio y crons por municipio (IT-01 F6.4,
PLAN_MULTI_MUNICIPIO_F6_4.md).

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_archivos_municipio.py

SOLO LOCAL. Storage simulado: en local las credenciales de Storage son las de prod, así que el smoke
nunca sube ni borra objetos reales.
"""
import asyncio
import os
import sys

os.environ.setdefault("ENV_FILE", ".env.local")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

OK = FAIL = 0


def check(cond: bool, nombre: str, detalle: str = "") -> None:
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  OK   {nombre}")
    else:
        FAIL += 1
        print(f"  FAIL {nombre} {detalle}")


def lanza(fn, *args) -> bool:
    try:
        fn(*args)
    except ValueError:
        return True
    return False


def parte_rutas() -> None:
    print("— rutas")
    from app.core import storage as st
    check(st.ruta_de_municipio(1, "reclamos/5/a.jpg") == "m1/reclamos/5/a.jpg", "ruta_con_municipio")
    check(st.ruta_de_municipio(None, "usuarios/102/avatar-x.png") == "global/usuarios/102/avatar-x.png",
          "ruta_sin_municipio_va_a_global")
    check(lanza(st.ruta_de_municipio, 1, "../x"), "ruta_invalida_lanza")
    check(lanza(st.ruta_de_municipio, 1, "m2/reclamos/5/a.jpg"), "ruta_ya_prefijada_lanza")
    check(lanza(st.ruta_de_municipio, None, "global/a"), "ruta_ya_global_lanza")
    check(st.municipio_de_ruta("m12/ot/1/a.png") == 12, "municipio_de_ruta")
    check(st.municipio_de_ruta("reclamos/1/a.png") is None, "municipio_de_ruta_formato_viejo")
    check(st.municipio_de_ruta("mx/a") is None, "municipio_de_ruta_prefijo_raro")
    check(st.municipio_de_ruta("global/usuarios/1/a.png") is None, "municipio_de_ruta_global")
    check(st.es_avatar_de("usuarios/6/avatar-ab12.png", 6, 1), "avatar_formato_viejo")
    check(st.es_avatar_de("m1/usuarios/6/avatar-ab12.png", 6, 1), "avatar_formato_nuevo")
    check(not st.es_avatar_de("m2/usuarios/6/avatar-ab12.png", 6, 1), "avatar_otro_municipio")
    check(not st.es_avatar_de("m1/usuarios/7/avatar-ab12.png", 6, 1), "avatar_otro_usuario")
    check(not st.es_avatar_de("m1/usuarios/102/avatar-ab.png", 102, None), "avatar_super_con_municipio")
    check(st.es_avatar_de("global/usuarios/102/avatar-ab.png", 102, None), "avatar_super_global")
    check(st.es_avatar_de("usuarios/102/avatar-ab.png", 102, None), "avatar_super_formato_viejo")
    check(not st.es_avatar_de("global/usuarios/6/avatar-ab.png", 6, 1), "avatar_global_de_cuenta_con_municipio")


async def main() -> None:
    parte_rutas()
    print(f"\n{OK} OK, {FAIL} FAIL")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    asyncio.run(main())
