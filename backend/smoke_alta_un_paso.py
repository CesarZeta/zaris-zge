# -*- coding: utf-8 -*-
"""
Smoke — alta pública de UN PASO con ficha completa + activar-existente + cuenta-vecino
backoffice (decisión 2026-06-12: sin placeholders falsos en la BUC).

Local:  python smoke_alta_un_paso.py
Prod:   python smoke_alta_un_paso.py https://zaris-api-production-bf0b.up.railway.app

Los datos creados QUEDAN como demo (directiva 2026-06-11, no se limpian).
"""
import random
import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
ES_PROD = "railway" in BASE or "zaris.com.ar" in BASE
ADMIN_EMAIL = "cesar@municipio.gob.ar" if ES_PROD else "ciudadanovl@municipio.gob.ar"

ok_count = 0
fail_count = 0


def check(nombre: str, cond: bool, extra: str = "") -> None:
    global ok_count, fail_count
    if cond:
        ok_count += 1
        print(f"  OK   {nombre} {extra}")
    else:
        fail_count += 1
        print(f"  FAIL {nombre} {extra}")


def cuil_valido(dni: str) -> str:
    """Arma un CUIL 20-DNI-? con dígito verificador módulo 11 real."""
    base = "20" + dni.zfill(8)
    pesos = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    s = sum(int(d) * p for d, p in zip(base, pesos))
    resto = 11 - (s % 11)
    if resto == 11:
        dv = 0
    elif resto == 10:
        # con prefijo 20 no hay dv=10 válido; probamos prefijo 23
        base = "23" + dni.zfill(8)
        s = sum(int(d) * p for d, p in zip(base, pesos))
        resto = 11 - (s % 11)
        dv = 0 if resto == 11 else resto
    else:
        dv = resto
    return base + str(dv)


def main() -> int:
    c = httpx.Client(timeout=60)

    # Slug del municipio (mono-tenant)
    r = c.get(f"{BASE}/api/v1/config/identidad")
    slug = r.json().get("municipio_slug")
    check("0. slug del municipio", r.status_code == 200 and bool(slug), f"({slug})")

    dni = str(random.randint(40_000_000, 44_999_999))
    cuil = cuil_valido(dni)
    email = f"vecino.demo.{dni}@example.com"

    ficha = {
        "municipio_slug": slug,
        "doc_nro": dni,
        "cuil": cuil,
        "nombre": "Vecina",
        "apellido": f"DemoAlta{dni[-4:]}",
        "sexo": "MUJER",
        "fecha_nac": "1988-03-15",
        "id_nacionalidad": 1,
        "calle": "Av. Maipú 950",
        "localidad": "Vicente López",
        "provincia": "Buenos Aires",
        "latitud": -34.5263,
        "longitud": -58.4727,
        "telefono": "11 4444 5566",
        "email": email,
        "password": "demoalta123",
    }

    # 1. Alta completa en un paso
    r = c.post(f"{BASE}/api/v1/publico/alta/cuenta", json=ficha)
    check("1. alta un paso 201", r.status_code == 201, f"({r.status_code}) {r.text[:120] if r.status_code != 201 else ''}")
    if r.status_code != 201:
        return 1
    id_nuevo = r.json()["id_ciudadano"]
    print(f"       -> id_ciudadano {id_nuevo} (DNI {dni})")

    # 2. La ficha quedó completa y SIN placeholders (login admin + GET ciudadano)
    r = c.post(f"{BASE}/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": "123456"})
    check("2a. login admin", r.status_code == 200)
    HA = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = c.get(f"{BASE}/api/v1/buc/ciudadanos/{id_nuevo}", headers=HA)
    ciu = r.json()
    sin_placeholders = (
        ciu.get("cuil") == cuil
        and ciu.get("fecha_nac") == "1988-03-15"
        and ciu.get("sexo") == "MUJER"
        and (ciu.get("telefono") or "").startswith("11")
    )
    check("2b. ficha real sin placeholders", r.status_code == 200 and sin_placeholders,
          f"(cuil={ciu.get('cuil')}, nac={ciu.get('fecha_nac')})")

    # 3. Validaciones canónicas
    r = c.post(f"{BASE}/api/v1/publico/alta/cuenta", json={**ficha, "doc_nro": str(random.randint(45_000_000, 45_999_999)), "cuil": "20123456789"})
    check("3a. CUIL modulo-11 invalido rechazado", r.status_code in (400, 422), f"({r.status_code})")
    r = c.post(f"{BASE}/api/v1/publico/alta/cuenta", json={**ficha, "fecha_nac": "2150-01-01"})
    check("3b. fecha futura rechazada", r.status_code == 400, f"({r.status_code})")
    r = c.post(f"{BASE}/api/v1/publico/alta/cuenta", json=ficha)
    check("3c. DNI duplicado 409 con mensaje de activar-existente",
          r.status_code == 409 and "registrado" in r.text, f"({r.status_code})")

    # 4. activar-existente: DNI recién creado (credencial existe sin activar) -> 200 generico
    r = c.post(f"{BASE}/api/v1/publico/alta/activar-existente", json={"municipio_slug": slug, "doc_nro": dni})
    check("4a. activar-existente DNI existente 200", r.status_code == 200 and r.json().get("enviado") is True)
    r = c.post(f"{BASE}/api/v1/publico/alta/activar-existente", json={"municipio_slug": slug, "doc_nro": "9999111"})
    check("4b. activar-existente DNI inexistente 200 (anti-enum)", r.status_code == 200 and r.json().get("enviado") is True)

    # 5. Backoffice: cuenta-vecino para ciudadano existente (el recien creado: sin activar -> reenvia)
    r = c.post(f"{BASE}/api/v1/buc/ciudadanos/{id_nuevo}/cuenta-vecino", headers=HA)
    check("5a. backoffice cuenta-vecino reenvia", r.status_code == 200 and r.json().get("enviado") is True,
          f"({r.status_code})")
    r = c.post(f"{BASE}/api/v1/buc/ciudadanos/999999/cuenta-vecino", headers=HA)
    check("5b. backoffice ciudadano inexistente 404", r.status_code == 404, f"({r.status_code})")
    r = c.post(f"{BASE}/api/v1/buc/ciudadanos/{id_nuevo}/cuenta-vecino")
    check("5c. backoffice sin JWT 401", r.status_code == 401, f"({r.status_code})")

    print(f"\n{'TODOS OK' if fail_count == 0 else 'HAY FALLOS'}: {ok_count} OK / {fail_count} FAIL")
    print(f"Queda de demo: ciudadano {id_nuevo} (DNI {dni}, ficha completa, credencial sin activar)")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
