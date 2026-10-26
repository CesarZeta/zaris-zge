# -*- coding: utf-8 -*-
"""
Login de usuario interno para los scripts que corren contra PROD (IT-01 F3b).

Desde F3b, una cuenta de nivel 0 o 1 no recibe el token con la clave: el login devuelve un
desafío y hace falta el código de la app de autenticación. Este helper lo pide por consola.
En local (segundo factor apagado en .env.local) el login devuelve el token directo y no pregunta.
"""
import sys
from typing import Optional

import httpx


def intentar_login_interno(base: str, email: str, password: str) -> Optional[str]:
    """Token de la cuenta, o None si no se pudo (clave mal, cuenta sin app vinculada, código mal).
    Si la cuenta tiene segundo factor, pide el código por consola."""
    with httpx.Client(timeout=30) as c:
        r = c.post(f"{base}/api/v1/auth/login", json={"identificador": email, "password": password})
        if r.status_code != 200:
            print(f"  login de {email}: {r.status_code} {r.text[:200]}")
            return None
        j = r.json()
        if "access_token" in j:
            return j["access_token"]
        if j.get("estado") != "codigo":
            print(f"  {email}: " + (j.get("mensaje") or "la cuenta no tiene la app de códigos vinculada; "
                                    "vinculala primero desde el login del shell."))
            return None
        codigo = input(f"Código de la app de autenticación para {email}: ").strip()
        r = c.post(f"{base}/api/v1/auth/segundo-factor/verificar",
                   json={"desafio": j["desafio"], "codigo": codigo})
        if r.status_code != 200:
            print(f"  código de {email}: {r.status_code} {r.text[:200]}")
            return None
        return r.json()["access_token"]


def login_interno(base: str, email: str, password: str) -> str:
    """Token de la cuenta; corta el script si no se pudo entrar."""
    token = intentar_login_interno(base, email, password)
    if token is None:
        sys.exit(f"No se pudo entrar con {email}.")
    return token
