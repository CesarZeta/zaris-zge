# -*- coding: utf-8 -*-
"""
Dominios de un municipio en Cloudflare (IT-01 F4+F5): <sub>.zge|vecinos|agentes.zaris.com.ar.

    python tools/dominios_municipio.py <subdominio>                  # crea lo que falte
    python tools/dominios_municipio.py <subdominio> --solo-verificar # no escribe nada
    python tools/dominios_municipio.py <subdominio> --quitar         # borra dominios y CNAME

Por cada app asocia el dominio al proyecto de Cloudflare Pages y después crea el CNAME
<sub>.<app> -> <proyecto>.pages.dev en la zona zaris.com.ar (en ese orden: un CNAME sin el
dominio asociado en Pages da 522). Idempotente. Un CNAME que ya existe y apunta a otro lado
no se toca: el script aborta.

El token de la API (permisos Zone/DNS/Edit sobre zaris.com.ar y Account/Cloudflare Pages/Edit)
vive en credenciales-testing/cloudflare_api_token.txt, NUNCA en el repo. Se puede indicar otro
archivo con --token-file. Solo biblioteca estándar. Configuración: docs/cloudflare_pages.md.
"""
import argparse
import json
import re
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path

ZONA = "zaris.com.ar"
PROYECTOS = {"zge": "zaris-zge", "vecinos": "zaris-vecinos", "agentes": "zaris-agentes"}
API = "https://api.cloudflare.com/client/v4"
TOKEN_POR_DEFECTO = Path.home() / "Documents" / "ZARIS" / "credenciales-testing" / "cloudflare_api_token.txt"

# Mismo patrón y reservados que el alta de municipios (app/services/municipios/constantes.py).
PATRON_SUBDOMINIO = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
SUBDOMINIOS_RESERVADOS = {"www", "api", "zge", "vecinos", "agentes", "admin", "app", "mail",
                          "soporte", "status", "demo", "modelo"}


def validar_subdominio(sub: str) -> None:
    if not PATRON_SUBDOMINIO.fullmatch(sub or ""):
        raise ValueError(f"subdominio inválido: {sub!r} (minúsculas, números y guiones, sin tildes)")
    if sub in SUBDOMINIOS_RESERVADOS:
        raise ValueError(f"subdominio reservado: {sub!r}")


def _dominios(sub: str):
    for app, proyecto in PROYECTOS.items():
        yield f"{sub}.{app}.{ZONA}", proyecto


def agregar(cf, sub: str) -> None:
    validar_subdominio(sub)
    # Primero se revisan todos los CNAME: si alguno es ajeno, no se escribe nada.
    for dominio, proyecto in _dominios(sub):
        actual = cf.cname(dominio)
        if actual not in (None, f"{proyecto}.pages.dev"):
            raise RuntimeError(f"{dominio} ya tiene un CNAME a {actual}: no se pisa")
    for dominio, proyecto in _dominios(sub):
        if dominio not in cf.dominios_pages(proyecto):
            cf.agregar_dominio_pages(proyecto, dominio)
            print(f"  + {dominio} asociado a {proyecto}")
        if cf.cname(dominio) is None:
            cf.crear_cname(dominio, f"{proyecto}.pages.dev")
            print(f"  + CNAME {dominio} -> {proyecto}.pages.dev")


def quitar(cf, sub: str) -> None:
    validar_subdominio(sub)
    for dominio, proyecto in _dominios(sub):
        if cf.cname(dominio) == f"{proyecto}.pages.dev":
            cf.borrar_cname(dominio)
            print(f"  - CNAME {dominio}")
        if dominio in cf.dominios_pages(proyecto):
            cf.quitar_dominio_pages(proyecto, dominio)
            print(f"  - {dominio} de {proyecto}")


class Cloudflare:
    def __init__(self, token: str):
        self._token = token
        zona = self._pedir("GET", f"/zones?name={ZONA}")
        if not zona:
            raise RuntimeError(f"el token no ve la zona {ZONA}")
        self._zona = zona[0]["id"]
        self._cuenta = zona[0]["account"]["id"]

    def _pedir(self, metodo, ruta, cuerpo=None):
        req = urllib.request.Request(
            API + ruta, method=metodo,
            data=json.dumps(cuerpo).encode() if cuerpo is not None else None,
            headers={"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                datos = json.load(r)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{metodo} {ruta}: HTTP {e.code} {e.read()[:300]!r}") from None
        if not datos.get("success"):
            raise RuntimeError(f"{metodo} {ruta}: {datos.get('errors')}")
        return datos.get("result")

    def _pages(self, proyecto):
        return f"/accounts/{self._cuenta}/pages/projects/{proyecto}/domains"

    def dominios_pages(self, proyecto):
        return {d["name"] for d in self._pedir("GET", self._pages(proyecto)) or []}

    def estado_dominio_pages(self, proyecto, dominio):
        for d in self._pedir("GET", self._pages(proyecto)) or []:
            if d["name"] == dominio:
                return d.get("status")
        return None

    def agregar_dominio_pages(self, proyecto, dominio):
        self._pedir("POST", self._pages(proyecto), {"name": dominio})

    def quitar_dominio_pages(self, proyecto, dominio):
        self._pedir("DELETE", f"{self._pages(proyecto)}/{dominio}")

    def _registro(self, nombre):
        res = self._pedir("GET", f"/zones/{self._zona}/dns_records?type=CNAME&name={nombre}")
        return res[0] if res else None

    def cname(self, nombre):
        r = self._registro(nombre)
        return r["content"] if r else None

    def crear_cname(self, nombre, destino):
        # Proxied; se confirma contra el registro que crea el panel en el corte A
        # (docs/cloudflare_pages.md).
        self._pedir("POST", f"/zones/{self._zona}/dns_records",
                    {"type": "CNAME", "name": nombre, "content": destino, "proxied": True, "ttl": 1})

    def borrar_cname(self, nombre):
        r = self._registro(nombre)
        if r:
            self._pedir("DELETE", f"/zones/{self._zona}/dns_records/{r['id']}")


def verificar(cf, sub: str) -> None:
    validar_subdominio(sub)
    for dominio, proyecto in _dominios(sub):
        try:
            dns = sorted({a[4][0] for a in socket.getaddrinfo(dominio, 443)})[:2]
        except socket.gaierror:
            dns = "no existe"
        pages = cf.estado_dominio_pages(proyecto, dominio) or "no existe"
        try:
            with urllib.request.urlopen(f"https://{dominio}/", timeout=15) as r:
                http = r.status
        except urllib.error.HTTPError as e:
            http = e.code
        except Exception as e:  # DNS, certificado, timeout
            http = f"sin respuesta ({type(e).__name__})"
        print(f"  {dominio}: DNS {dns} · Pages {pages} · GET {http}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("subdominio")
    grupo = ap.add_mutually_exclusive_group()
    grupo.add_argument("--quitar", action="store_true")
    grupo.add_argument("--solo-verificar", action="store_true")
    ap.add_argument("--token-file", type=Path, default=TOKEN_POR_DEFECTO)
    args = ap.parse_args()
    try:
        validar_subdominio(args.subdominio)
    except ValueError as e:
        sys.exit(str(e))
    if not args.token_file.is_file():
        sys.exit(f"Falta el token de Cloudflare en {args.token_file}")
    cf = Cloudflare(args.token_file.read_text(encoding="utf-8").strip())
    if args.solo_verificar:
        verificar(cf, args.subdominio)
    elif args.quitar:
        quitar(cf, args.subdominio)
    else:
        agregar(cf, args.subdominio)
        verificar(cf, args.subdominio)
    return 0


if __name__ == "__main__":
    sys.exit(main())
