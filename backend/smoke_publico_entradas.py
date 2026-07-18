# -*- coding: utf-8 -*-
"""
Smoke — entradas del vecino logueado (App Vecinos, Etapa D).
Local:  python smoke_publico_entradas.py
Prod:   python smoke_publico_entradas.py https://zaris-api-production-bf0b.up.railway.app

Requiere vecino demo con credencial (local DNI 28547123 / prod 30555444) y un
admin para sembrar un evento si la cartelera esta vacia. Passwords: en local usa
la clave dev estandar; contra prod exige la env var ZARIS_QA_PASS (las
credenciales de prod viven en credenciales-testing/, FUERA del repo — §40).

NOTA: por directiva del usuario (2026-06-11) los datos creados NO se limpian —
quedan como seed de demos. El smoke deja una entrada RESERVADA del vecino demo.
"""
import os
import sys
from datetime import date, timedelta

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
ES_PROD = "railway" in BASE or "zaris.com.ar" in BASE
DNI_VECINO = sys.argv[2] if len(sys.argv) > 2 else ("30555444" if ES_PROD else "28547123")
QA_PASS = os.environ.get("ZARIS_QA_PASS") or ("123456" if not ES_PROD else None)
if ES_PROD and not QA_PASS:
    sys.exit("Contra prod setea ZARIS_QA_PASS (credenciales en credenciales-testing/, fuera del repo)")

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


ADMINS = ["cesar@municipio.gob.ar", "ciudadanovl@municipio.gob.ar", "roymanos@municipio.gob.ar"]


def sembrar_evento_demo(c: httpx.Client) -> bool:
    """Si la cartelera esta vacia, crea un evento demo con autoservicio via API
    admin (respeta reglas de negocio — no SQL crudo)."""
    h = None
    for email in ADMINS:
        r = c.post(f"{BASE}/api/v1/auth/login", json={"email": email, "password": QA_PASS})
        if r.status_code == 200:
            h = {"Authorization": f"Bearer {r.json()['access_token']}"}
            break
    if h is None:
        print("  (seed) ningun login admin funciono")
        return False
    f = (date.today() + timedelta(days=10)).isoformat()
    r = c.post(f"{BASE}/api/v1/agenda/eventos", headers=h, json={
        "nombre": "Charla demo App Vecinos (etapa D)",
        "descripcion": "Evento demo para la cartelera de la app del vecino.",
        "fecha": f, "hora_inicio": "18:00", "hora_fin": "20:00",
        "capacidad_ciudadanos": 30, "tipo_qr": "nominal",
        "admite_autoservicio": True, "id_municipio": 1,
    })
    print(f"  (seed) evento demo: {r.status_code}")
    return r.status_code in (200, 201)


def main() -> int:
    c = httpx.Client(timeout=60)

    # 1. Login vecino
    r = c.post(f"{BASE}/api/v1/publico/auth/login", json={"dni": DNI_VECINO, "password": QA_PASS})
    check("1. login vecino", r.status_code == 200, f"({r.status_code})")
    if r.status_code != 200:
        return 1
    H = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # 2. Sin token -> 401 (cartelera y mis entradas)
    check("2a. cartelera sin token 401", c.get(f"{BASE}/api/v1/publico/entradas/eventos").status_code == 401)
    check("2b. mis entradas sin token 401", c.get(f"{BASE}/api/v1/publico/entradas").status_code == 401)

    # 3. Cartelera (sembrar evento demo si esta vacia)
    r = c.get(f"{BASE}/api/v1/publico/entradas/eventos", headers=H)
    eventos = r.json() if r.status_code == 200 else []
    if r.status_code == 200 and not eventos:
        if sembrar_evento_demo(c):
            r = c.get(f"{BASE}/api/v1/publico/entradas/eventos", headers=H)
            eventos = r.json() if r.status_code == 200 else []
    check("3. cartelera con eventos", r.status_code == 200 and len(eventos) > 0,
          f"({len(eventos) if isinstance(eventos, list) else r.status_code} eventos)")
    if not eventos:
        return 1

    # Elegir un evento con cupo y sin reserva previa del vecino
    ev = next((e for e in eventos if e["cupo_disponible"] > 0 and not e["ya_reservado"]), None)
    if ev is None:
        # todos reservados: usar el primero ya reservado para los chequeos de dup
        ev = next((e for e in eventos if e["ya_reservado"]), eventos[0])
        ya_tenia = True
    else:
        ya_tenia = False

    # 4. Reservar
    if not ya_tenia:
        r = c.post(f"{BASE}/api/v1/publico/entradas/eventos/{ev['id_evento']}/reservar", headers=H)
        reserva = r.json() if r.status_code == 201 else None
        check("4. reservar entrada", r.status_code == 201 and reserva,
              f"({r.status_code}) {r.text[:120] if r.status_code != 201 else 'id ' + str(reserva['id_evento_reserva'])}")
        if not reserva:
            return 1
        if ev["tipo_qr"] != "ninguno":
            check("4b. reserva trae qr_codigo", bool(reserva.get("qr_codigo")),
                  f"({reserva.get('qr_codigo')})")
    else:
        print("  (4. el vecino ya tenia reserva en todos los eventos — sigo con dup)")

    # 5. Reservar de nuevo el mismo evento -> 409
    r = c.post(f"{BASE}/api/v1/publico/entradas/eventos/{ev['id_evento']}/reservar", headers=H)
    check("5. duplicada -> 409", r.status_code == 409, f"({r.status_code})")

    # 6. Mis entradas: contiene la reserva con datos del evento
    r = c.get(f"{BASE}/api/v1/publico/entradas", headers=H)
    mias = r.json() if r.status_code == 200 else []
    mia = next((m for m in mias if m["id_evento"] == ev["id_evento"]
                and m["estado_codigo"] == "reservada"), None)
    check("6. mis entradas contiene la reserva", mia is not None,
          f"({len(mias)} entradas)")
    if mia and ev["tipo_qr"] != "ninguno":
        check("6b. mi entrada trae qr_codigo", bool(mia.get("qr_codigo")))

    # 7. Cartelera marca ya_reservado
    r = c.get(f"{BASE}/api/v1/publico/entradas/eventos", headers=H)
    ev2 = next((e for e in r.json() if e["id_evento"] == ev["id_evento"]), None)
    check("7. cartelera marca ya_reservado", ev2 is not None and ev2["ya_reservado"] is True)

    # 8. Evento inexistente -> 404
    r = c.post(f"{BASE}/api/v1/publico/entradas/eventos/999999/reservar", headers=H)
    check("8. evento inexistente -> 404", r.status_code == 404, f"({r.status_code})")

    # 9. Cancelar reserva ajena -> 404 (ids bajos que no son mios)
    ids_mias = {m["id_evento_reserva"] for m in mias}
    ajeno_status = None
    for cand in range(1, 50):
        if cand in ids_mias:
            continue
        ajeno_status = c.patch(f"{BASE}/api/v1/publico/entradas/{cand}/cancelar", headers=H).status_code
        break
    check("9. cancelar ajena -> 404", ajeno_status == 404, f"({ajeno_status})")

    # 10. Cancelar la propia + idempotencia + cupo liberado + re-reservar (demo)
    if mia:
        r = c.patch(f"{BASE}/api/v1/publico/entradas/{mia['id_evento_reserva']}/cancelar", headers=H)
        check("10a. cancelar propia", r.status_code == 200 and r.json().get("estado_codigo") == "cancelada")
        r = c.patch(f"{BASE}/api/v1/publico/entradas/{mia['id_evento_reserva']}/cancelar", headers=H)
        check("10b. re-cancelar idempotente", r.status_code == 200 and r.json().get("ya_cancelada") is True)
        r = c.get(f"{BASE}/api/v1/publico/entradas/eventos", headers=H)
        ev3 = next((e for e in r.json() if e["id_evento"] == ev["id_evento"]), None)
        check("10c. cartelera liberada tras cancelar",
              ev3 is not None and ev3["ya_reservado"] is False
              and ev3["cupo_disponible"] >= ev["cupo_disponible"])
        # Re-reservar: queda como demo (directiva: no limpiar)
        r = c.post(f"{BASE}/api/v1/publico/entradas/eventos/{ev['id_evento']}/reservar", headers=H)
        check("10d. re-reservar (queda de demo)", r.status_code == 201,
              f"(id {r.json().get('id_evento_reserva') if r.status_code == 201 else r.status_code})")

    print(f"\n{'TODOS OK' if fail_count == 0 else 'HAY FALLOS'}: {ok_count} OK / {fail_count} FAIL")
    print(f"Queda de demo: entrada reservada del vecino {DNI_VECINO} en '{ev['nombre']}'")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
