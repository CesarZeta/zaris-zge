# -*- coding: utf-8 -*-
"""
Smoke — adjuntos públicos de reclamos (App Vecinos, Etapa A).
Corre contra local por default: python smoke_publico_adjuntos.py
Contra prod: python smoke_publico_adjuntos.py https://zaris-api-production-bf0b.up.railway.app

Requiere: vecino demo DNI 28547123 con credencial activada (pass 123456) y,
para el paso 10 (reclamo ajeno), el admin ciudadanovl (local) / cesar (prod).
"""
import base64
import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
ES_PROD = "railway" in BASE or "zaris.com.ar" in BASE
ADMIN_EMAIL = "cesar@municipio.gob.ar" if ES_PROD else "ciudadanovl@municipio.gob.ar"

PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

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


def main() -> int:
    c = httpx.Client(timeout=30)

    # 1. Login vecino
    r = c.post(f"{BASE}/api/v1/publico/auth/login", json={"dni": "28547123", "password": "123456"})
    check("1. login vecino", r.status_code == 200, f"({r.status_code})")
    if r.status_code != 200:
        return 1
    H = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # 2. Catálogo de tipos
    r = c.get(f"{BASE}/api/v1/publico/reclamos/catalogo/tipos", params={"limit": 5}, headers=H)
    check("2. catalogo tipos", r.status_code == 200 and len(r.json()) > 0)
    id_tipo = r.json()[0]["id_tipo_reclamo"]

    # 3. Crear reclamo propio
    r = c.post(f"{BASE}/api/v1/publico/reclamos", headers=H, json={
        "id_tipo_reclamo": id_tipo,
        "descripcion": "Smoke etapa A adjuntos publicos",
        "direccion": "Calle Falsa 123, La Plata",
    })
    check("3. crear reclamo", r.status_code == 201, f"({r.status_code})")
    id_rec = r.json()["id_reclamo"]
    nro = r.json().get("nro_reclamo")
    print(f"       -> {nro} (id {id_rec})")

    # 4. MIME inválido → 422
    r = c.post(f"{BASE}/api/v1/publico/reclamos/{id_rec}/adjuntos/upload-url", headers=H, json={
        "nombre_archivo": "doc.pdf", "mime_type": "application/pdf", "tamano_bytes": 1000,
    })
    check("4. MIME pdf rechazado", r.status_code == 422, f"({r.status_code})")

    # 5. upload-url PNG
    r = c.post(f"{BASE}/api/v1/publico/reclamos/{id_rec}/adjuntos/upload-url", headers=H, json={
        "nombre_archivo": "foto_smoke.png", "mime_type": "image/png", "tamano_bytes": len(PNG_1PX),
    })
    check("5. upload-url", r.status_code == 201, f"({r.status_code}) {r.text[:120] if r.status_code != 201 else ''}")
    if r.status_code != 201:
        return 1
    signed = r.json()
    id_adj = signed["id_adjunto"]

    # 6. PUT binario directo a Supabase Storage
    r = c.put(signed["upload_url"], content=PNG_1PX,
              headers={"Content-Type": "image/png", "x-upsert": "true"})
    check("6. PUT binario a storage", r.status_code in (200, 201), f"({r.status_code})")

    # 7. Confirm
    r = c.post(f"{BASE}/api/v1/publico/reclamos/{id_rec}/adjuntos/{id_adj}/confirm", headers=H, json={})
    check("7. confirm", r.status_code == 200 and r.json().get("ok") is True)

    # 8. Listar + descargar por URL firmada
    r = c.get(f"{BASE}/api/v1/publico/reclamos/{id_rec}/adjuntos", headers=H)
    lista = r.json()
    check("8a. lista 1 adjunto con url", r.status_code == 200 and len(lista) == 1 and lista[0].get("url"))
    r = c.get(lista[0]["url"])
    check("8b. descarga URL firmada", r.status_code == 200 and len(r.content) == len(PNG_1PX),
          f"({r.status_code}, {len(r.content)} bytes)")

    # 9. Sin token → 401
    r = c.get(f"{BASE}/api/v1/publico/reclamos/{id_rec}/adjuntos")
    check("9. sin token 401", r.status_code == 401, f"({r.status_code})")

    # 10. Reclamo ajeno → 404 (mismo cuerpo que inexistente)
    r = c.post(f"{BASE}/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": "123456"})
    if r.status_code == 200:
        HA = {"Authorization": f"Bearer {r.json()['access_token']}"}
        todos = c.get(f"{BASE}/api/v1/reclamos", params={"limit": 50}, headers=HA).json()
        mios = {x["id_reclamo"] for x in c.get(f"{BASE}/api/v1/publico/reclamos", params={"limit": 200}, headers=H).json()}
        ajenos = [t["id_reclamo"] for t in todos if t["id_reclamo"] not in mios]
        if ajenos:
            r = c.get(f"{BASE}/api/v1/publico/reclamos/{ajenos[0]}/adjuntos", headers=H)
            check("10a. GET adjuntos reclamo ajeno 404", r.status_code == 404, f"(id {ajenos[0]}, {r.status_code})")
            r = c.post(f"{BASE}/api/v1/publico/reclamos/{ajenos[0]}/adjuntos/upload-url", headers=H, json={
                "nombre_archivo": "x.png", "mime_type": "image/png", "tamano_bytes": 100,
            })
            check("10b. upload-url reclamo ajeno 404", r.status_code == 404, f"({r.status_code})")
        else:
            print("  SKIP 10. no hay reclamo ajeno")
    else:
        print(f"  SKIP 10. login admin fallo ({r.status_code})")

    # Cleanup en PROD: soft-delete del adjunto (borra binario) — en local se deja como dato de prueba.
    if ES_PROD:
        r = c.delete(f"{BASE}/api/v1/reclamos/{id_rec}/adjuntos/{id_adj}", headers=HA)
        print(f"  cleanup prod: DELETE adjunto -> {r.status_code}")

    print(f"\n{'TODOS OK' if fail_count == 0 else 'HAY FALLOS'}: {ok_count} OK / {fail_count} FAIL")
    print(f"Reclamo de prueba: {nro} (id {id_rec})")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
