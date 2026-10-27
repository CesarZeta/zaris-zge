# -*- coding: utf-8 -*-
"""
Prueba de tools/dominios_municipio.py con una API de Cloudflare falsa (no toca la red).

    python tools/test_dominios_municipio.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dominios_municipio as dm  # noqa: E402


class CloudflareFalso:
    """Guarda dominios de Pages y registros DNS en memoria y anota cada llamada que escribe."""

    def __init__(self):
        self.dominios: dict[str, set[str]] = {p: set() for p in dm.PROYECTOS.values()}
        self.cnames: dict[str, str] = {}
        self.escrituras: list[tuple] = []

    def dominios_pages(self, proyecto):
        return set(self.dominios[proyecto])

    def agregar_dominio_pages(self, proyecto, dominio):
        self.escrituras.append(("pages+", proyecto, dominio))
        self.dominios[proyecto].add(dominio)

    def quitar_dominio_pages(self, proyecto, dominio):
        self.escrituras.append(("pages-", proyecto, dominio))
        self.dominios[proyecto].discard(dominio)

    def cname(self, nombre):
        return self.cnames.get(nombre)

    def crear_cname(self, nombre, destino):
        self.escrituras.append(("dns+", nombre, destino))
        self.cnames[nombre] = destino

    def borrar_cname(self, nombre):
        self.escrituras.append(("dns-", nombre))
        self.cnames.pop(nombre, None)


FALLAS = []


def check(nombre, ok, detalle=""):
    print(f"  {'OK  ' if ok else 'FAIL'} {nombre}{(' — ' + str(detalle)) if not ok else ''}")
    if not ok:
        FALLAS.append(nombre)


# Validación del subdominio (mismo patrón y reservados que el alta, Tarea 11)
for sub in ("Vicente-Lopez", "córdoba", "api", "zge", "-x", "x-", ""):
    try:
        dm.validar_subdominio(sub)
        check(f"subdominio {sub!r} rechazado", False, "no tiró")
    except ValueError:
        check(f"subdominio {sub!r} rechazado", True)
for sub in ("prueba", "vicente-lopez", "b2"):
    try:
        dm.validar_subdominio(sub)
        check(f"subdominio {sub!r} aceptado", True)
    except ValueError as e:
        check(f"subdominio {sub!r} aceptado", False, e)

# Alta: 3 dominios en Pages y 3 CNAME; cada dominio se asocia ANTES de su CNAME (si no, 522)
cf = CloudflareFalso()
dm.agregar(cf, "prueba")
esperados = {f"prueba.{app}.zaris.com.ar": f"{proy}.pages.dev" for app, proy in dm.PROYECTOS.items()}
check("crea los 3 CNAME al proyecto correcto", cf.cnames == esperados, cf.cnames)
check("asocia los 3 dominios a su proyecto",
      all(f"prueba.{app}.zaris.com.ar" in cf.dominios[proy] for app, proy in dm.PROYECTOS.items()), cf.dominios)
orden_ok = all(
    cf.escrituras.index(("pages+", proy, f"prueba.{app}.zaris.com.ar"))
    < cf.escrituras.index(("dns+", f"prueba.{app}.zaris.com.ar", f"{proy}.pages.dev"))
    for app, proy in dm.PROYECTOS.items())
check("el dominio se asocia en Pages antes de crear el CNAME", orden_ok, cf.escrituras)

# Idempotente: correrlo de nuevo no escribe nada
n = len(cf.escrituras)
dm.agregar(cf, "prueba")
check("segunda corrida no escribe", len(cf.escrituras) == n, cf.escrituras[n:])

# Un CNAME existente que apunta a otro lado: no se pisa, se aborta
cf2 = CloudflareFalso()
cf2.cnames["prueba.zge.zaris.com.ar"] = "otra-cosa.example.com"
try:
    dm.agregar(cf2, "prueba")
    check("CNAME ajeno aborta", False, "no tiró")
except RuntimeError:
    check("CNAME ajeno aborta", True)
check("CNAME ajeno no se pisa", cf2.cnames["prueba.zge.zaris.com.ar"] == "otra-cosa.example.com")

# Quitar: borra lo creado y vuelve a ser idempotente
dm.quitar(cf, "prueba")
check("quitar deja sin CNAME ni dominios", not cf.cnames and not any(cf.dominios.values()), (cf.cnames, cf.dominios))
n = len(cf.escrituras)
dm.quitar(cf, "prueba")
check("quitar dos veces no escribe", len(cf.escrituras) == n)

print(f"\nRESULTADO: {'OK' if not FALLAS else f'{len(FALLAS)} FAIL'}")
sys.exit(1 if FALLAS else 0)
