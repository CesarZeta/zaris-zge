# -*- coding: utf-8 -*-
"""
Smoke — perfil + bandeja de avisos + reverse geocoding del vecino logueado
(App Vecinos, pendientes del traspaso 2026-07-16; mig 99).

Local:  python smoke_publico_perfil_avisos.py
Prod:   python smoke_publico_perfil_avisos.py https://zaris-api-production-bf0b.up.railway.app

Requiere vecino demo con credencial (local DNI 28547123 / prod 30555444) y un
usuario interno nivel <= 2 para disparar el cambio de estado que genera el aviso
(local ciudadanovl@ / prod cesar@). Passwords: local usa la clave dev estandar;
contra prod exige ZARIS_QA_PASS (credenciales en credenciales-testing/, FUERA
del repo — §40). Si el login del agente falla (p.ej. clave vencida), los pasos
que dependen de el se marcan SKIP en vez de FAIL.

Los datos creados (1 reclamo del vecino) NO se limpian (directiva 2026-06-11,
quedan como demo). El perfil se restaura a los valores originales al final.
Los pasos de reverse geocoding pegan a Nominatim real (requieren internet).
"""
import os
import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
ES_PROD = "railway" in BASE or "zaris.com.ar" in BASE
DNI_VECINO = sys.argv[2] if len(sys.argv) > 2 else ("30555444" if ES_PROD else "28547123")
EMAIL_AGENTE = os.environ.get("ZARIS_QA_AGENTE") or (
    "cesar@municipio.gob.ar" if ES_PROD else "ciudadanovl@municipio.gob.ar")
QA_PASS = os.environ.get("ZARIS_QA_PASS") or ("123456" if not ES_PROD else None)
if ES_PROD and not QA_PASS:
    sys.exit("Contra prod setea ZARIS_QA_PASS (credenciales en credenciales-testing/, fuera del repo)")

ok_count = 0
fail_count = 0
skip_count = 0


def check(nombre: str, cond: bool, extra: str = "") -> None:
    global ok_count, fail_count
    if cond:
        ok_count += 1
        print(f"  OK   {nombre} {extra}")
    else:
        fail_count += 1
        print(f"  FAIL {nombre} {extra}")


def skip(nombre: str, motivo: str) -> None:
    global skip_count
    skip_count += 1
    print(f"  SKIP {nombre} ({motivo})")


def main() -> int:
    c = httpx.Client(timeout=60)
    P = "/api/v1/publico"

    # ── 1. Login vecino ──────────────────────────────────────────────────────
    r = c.post(f"{BASE}{P}/auth/login", json={"dni": DNI_VECINO, "password": QA_PASS})
    check("1. login vecino", r.status_code == 200, f"({r.status_code})")
    if r.status_code != 200:
        return 1
    H = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # ── 2-5. Perfil ──────────────────────────────────────────────────────────
    r = c.get(f"{BASE}{P}/perfil", headers=H)
    perfil = r.json() if r.status_code == 200 else {}
    check("2. GET /perfil 200 + dni del token", r.status_code == 200 and perfil.get("dni") == DNI_VECINO,
          f"({r.status_code} dni={perfil.get('dni')})")
    campos = ["cuil", "cuil_es_placeholder", "telefono", "calle", "altura", "localidad", "provincia",
              "latitud", "longitud", "fecha_nac", "nacionalidad", "email_verificado", "fecha_alta",
              "canal_push", "ficha_completa"]
    faltan = [k for k in campos if k not in perfil]
    check("3. /perfil trae la ficha extendida", not faltan, f"(faltan={faltan})" if faltan else "")
    check("4. lat/lon son float o null (no string Decimal)",
          all(isinstance(perfil.get(k), (int, float)) or perfil.get(k) is None for k in ("latitud", "longitud")),
          f"({type(perfil.get('latitud')).__name__})")
    check("5. CUIL placeholder no se expone como real",
          not (perfil.get("cuil_es_placeholder") and perfil.get("cuil")),
          f"(placeholder={perfil.get('cuil_es_placeholder')} cuil={perfil.get('cuil')})")

    r = c.get(f"{BASE}{P}/perfil")
    check("6. GET /perfil sin token -> 401", r.status_code == 401, f"({r.status_code})")

    # ── 7-10. PUT perfil (parcial) + restaurar ──────────────────────────────
    r = c.put(f"{BASE}{P}/perfil", headers=H, json={})
    check("7. PUT /perfil body vacio -> 422", r.status_code == 422, f"({r.status_code})")
    r = c.put(f"{BASE}{P}/perfil", headers=H, json={"telefono": "12"})
    check("8. PUT /perfil telefono invalido -> 422", r.status_code == 422, f"({r.status_code})")

    orig = {k: perfil.get(k) for k in ("telefono", "calle", "altura", "localidad", "provincia", "latitud", "longitud")}
    nuevo = {"telefono": "11 5555-0000", "calle": "Av. Maipú", "altura": "1234",
             "localidad": "Vicente López", "provincia": "Buenos Aires",
             "latitud": -34.5265, "longitud": -58.4729}
    r = c.put(f"{BASE}{P}/perfil", headers=H, json=nuevo)
    p2 = r.json() if r.status_code == 200 else {}
    check("9. PUT /perfil contacto+domicilio -> 200 y persiste",
          r.status_code == 200 and p2.get("telefono") == nuevo["telefono"] and p2.get("calle") == nuevo["calle"]
          and abs((p2.get("latitud") or 0) - nuevo["latitud"]) < 1e-6,
          f"({r.status_code})")
    # identidad intacta (el PUT no puede tocarla ni por accidente)
    check("10. PUT no toca identidad (dni/nombre/email)",
          p2.get("dni") == perfil.get("dni") and p2.get("nombre") == perfil.get("nombre")
          and p2.get("email") == perfil.get("email"))
    # campo prohibido en el body: ignorado (Pydantic), la identidad no cambia
    r = c.put(f"{BASE}{P}/perfil", headers=H, json={"telefono": nuevo["telefono"], "nombre": "HACK", "email": "x@x.com"})
    p3 = r.json() if r.status_code == 200 else {}
    check("11. campos no editables en el body se ignoran",
          r.status_code == 200 and p3.get("nombre") == perfil.get("nombre") and p3.get("email") == perfil.get("email"),
          f"({r.status_code})")
    # restaurar (los None se mandan explicitos para limpiar)
    r = c.put(f"{BASE}{P}/perfil", headers=H, json=orig if any(v is not None for v in orig.values())
              else {"telefono": perfil.get("telefono") or "0000000"})
    check("12. perfil restaurado", r.status_code == 200 and r.json().get("telefono") == (orig["telefono"] or r.json().get("telefono")),
          f"({r.status_code})")

    # ── 13. Avisos: baseline ────────────────────────────────────────────────
    r = c.get(f"{BASE}{P}/avisos", headers=H)
    base = r.json() if r.status_code == 200 else {}
    check("13. GET /avisos 200 con contadores", r.status_code == 200 and {"avisos", "no_leidos", "total"} <= set(base),
          f"({r.status_code} total={base.get('total')} no_leidos={base.get('no_leidos')})")
    r = c.get(f"{BASE}{P}/avisos")
    check("14. GET /avisos sin token -> 401", r.status_code == 401, f"({r.status_code})")

    # ── 15-17. Generar un aviso real: reclamo del vecino + cambio de estado por agente
    id_reclamo = None
    r = c.get(f"{BASE}{P}/reclamos/catalogo/tipos", headers=H, params={"limit": 1})
    tipos = r.json() if r.status_code == 200 else []
    if tipos:
        r = c.post(f"{BASE}{P}/reclamos", headers=H, json={
            "id_tipo_reclamo": tipos[0]["id_tipo_reclamo"],
            "direccion": "Av. Maipú 1234, Vicente López",
            "descripcion": "Smoke perfil/avisos — reclamo de prueba para generar un aviso de cambio de estado.",
            "latitud": -34.5265, "longitud": -58.4729,
        })
        id_reclamo = (r.json() or {}).get("id_reclamo") if r.status_code in (200, 201) else None
    check("15. POST /publico/reclamos (vecino)", id_reclamo is not None, f"(id={id_reclamo})")

    ra = c.post(f"{BASE}/api/v1/auth/login", json={"email": EMAIL_AGENTE, "password": QA_PASS})
    HA = {"Authorization": f"Bearer {ra.json()['access_token']}"} if ra.status_code == 200 else None
    id_aviso = None
    if HA and id_reclamo:
        r = c.put(f"{BASE}/api/v1/reclamos/{id_reclamo}/estado", headers=HA, json={"estado": "En gestión"})
        check("16. PUT /reclamos/{id}/estado (agente) -> En gestión", r.status_code == 200, f"({r.status_code} {r.text[:80]})")
        r = c.get(f"{BASE}{P}/avisos", headers=H)
        lst = r.json() if r.status_code == 200 else {}
        primero = (lst.get("avisos") or [{}])[0]
        gen = (primero.get("tipo") == "reclamo_estado" and primero.get("recurso_id") == id_reclamo
               and primero.get("leido") is False and "En gestión" in (primero.get("mensaje") or ""))
        check("17. el cambio de estado generó el aviso (primero de la bandeja, no leído)", gen,
              f"(no_leidos {base.get('no_leidos')}->{lst.get('no_leidos')} url={primero.get('url')})")
        id_aviso = primero.get("id_aviso") if gen else None
        # el aviso NO es visible con token de agente (scope)
        r = c.get(f"{BASE}{P}/avisos", headers=HA)
        check("18. GET /avisos con token de agente -> 401", r.status_code == 401, f"({r.status_code})")
    else:
        skip("16-18. cambio de estado + aviso generado", f"login agente {ra.status_code} / reclamo {id_reclamo}")

    # ── 19-23. Marcar leído / todos / 404 ajeno ─────────────────────────────
    if id_aviso:
        r = c.patch(f"{BASE}{P}/avisos/{id_aviso}/leer", headers=H)
        check("19. PATCH /avisos/{id}/leer -> leido", r.status_code == 200 and r.json().get("leido") is True, f"({r.status_code})")
        r2 = c.patch(f"{BASE}{P}/avisos/{id_aviso}/leer", headers=H)
        check("20. repetir leer es idempotente", r2.status_code == 200 and r2.json().get("leido_en") == r.json().get("leido_en"))
    else:
        skip("19-20. marcar leído", "sin aviso generado")
    r = c.patch(f"{BASE}{P}/avisos/999999999/leer", headers=H)
    check("21. PATCH leer de aviso inexistente/ajeno -> 404", r.status_code == 404, f"({r.status_code})")
    r = c.post(f"{BASE}{P}/avisos/leer-todos", headers=H)
    r2 = c.get(f"{BASE}{P}/avisos", headers=H, params={"solo_no_leidos": "true"})
    check("22. POST /avisos/leer-todos deja 0 no leídos",
          r.status_code == 200 and r2.status_code == 200 and r2.json().get("no_leidos") == 0 and r2.json().get("avisos") == [],
          f"({r.status_code} no_leidos={r2.json().get('no_leidos') if r2.status_code == 200 else '?'})")
    r = c.get(f"{BASE}{P}/portal/mi-resumen", headers=H)
    check("23. /portal/mi-resumen trae avisos.no_leidos",
          r.status_code == 200 and (r.json().get("avisos") or {}).get("no_leidos") == 0, f"({r.status_code})")

    # ── 24-26. Reverse geocoding ────────────────────────────────────────────
    r = c.get(f"{BASE}{P}/reclamos/geo/reverse", params={"lat": -34.5265, "lon": -58.4729})
    check("24. GET /reclamos/geo/reverse sin token -> 401", r.status_code == 401, f"({r.status_code})")
    r = c.get(f"{BASE}{P}/reclamos/geo/reverse", headers=H, params={"lat": -34.5265, "lon": -58.4729})
    rev = r.json() if r.status_code == 200 else {}
    check("25. reverse Vicente López -> encontrado + direccion corta",
          r.status_code == 200 and rev.get("encontrado") is True and bool(rev.get("direccion")) and bool(rev.get("calle")),
          f"({r.status_code} {rev.get('direccion')!r})")
    r = c.get(f"{BASE}{P}/reclamos/geo/reverse", headers=H, params={"lat": 0, "lon": 0})
    rev0 = r.json() if r.status_code == 200 else {}
    check("26. reverse en el océano -> 200 encontrado=false (la PWA cae al GPS crudo)",
          r.status_code == 200 and rev0.get("encontrado") is False and rev0.get("direccion") is None,
          f"({r.status_code} encontrado={rev0.get('encontrado')})")
    r = c.get(f"{BASE}{P}/reclamos/geo/reverse", headers=H, params={"lat": 95, "lon": 0})
    check("27. reverse lat fuera de rango -> 422", r.status_code == 422, f"({r.status_code})")

    print(f"\nRESULTADO: {ok_count} OK / {fail_count} FAIL / {skip_count} SKIP")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
