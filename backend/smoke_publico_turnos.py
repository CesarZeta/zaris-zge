# -*- coding: utf-8 -*-
"""
Smoke — turnos del vecino logueado (App Vecinos, Etapa C).
Local:  python smoke_publico_turnos.py
Prod:   python smoke_publico_turnos.py https://zaris-api-production-bf0b.up.railway.app

Requiere vecino demo con credencial (local DNI 28547123 / prod 30555444).
Passwords: en local usa la clave dev estandar; contra prod exige ZARIS_QA_PASS
(credenciales en credenciales-testing/, FUERA del repo — §40).

NOTA: por directiva del usuario (2026-06-11) los datos creados NO se limpian —
quedan como seed de demos. El smoke reserva 2 turnos en días distintos: cancela
uno (probar la cancelación es parte del flujo) y deja el otro RESERVADO.
"""
import os
import sys
from collections import OrderedDict

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


def main() -> int:
    c = httpx.Client(timeout=60)

    # 1. Login vecino
    r = c.post(f"{BASE}/api/v1/publico/auth/login", json={"dni": DNI_VECINO, "password": QA_PASS})
    check("1. login vecino", r.status_code == 200, f"({r.status_code})")
    if r.status_code != 200:
        return 1
    H = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # 2. Prestaciones publicables (endpoint anonimo existente, lo reusa la PWA)
    r = c.get(f"{BASE}/api/v1/turnos/publico/prestaciones")
    prestaciones = r.json()
    check("2. prestaciones publicables", r.status_code == 200 and len(prestaciones) > 0,
          f"({len(prestaciones) if isinstance(prestaciones, list) else r.status_code})")
    if not prestaciones:
        return 1

    # 3. Slots de la primera prestacion con slots disponibles
    prest = None
    slots = []
    for p in prestaciones:
        r = c.get(f"{BASE}/api/v1/turnos/publico/slots",
                  params={"id_tipo_prestacion": p["id_tipo_prestacion"], "dias": 14})
        if r.status_code == 200 and r.json():
            prest, slots = p, r.json()
            break
    check("3. slots disponibles", prest is not None and len(slots) > 0,
          f"({prest['nombre'] if prest else '-'}: {len(slots)} slots)")
    if not slots:
        return 1

    # Agrupar slots por fecha (el dup-check es por dia: necesitamos 2 dias distintos)
    por_fecha: "OrderedDict[str, dict]" = OrderedDict()
    for s in slots:
        por_fecha.setdefault(s["fecha"], s)
    fechas = list(por_fecha.keys())

    # 4. Reservar turno A (primer dia con slot libre y sin turno previo del vecino)
    turno_a = None
    slot_a = None
    for f in fechas:
        s = por_fecha[f]
        r = c.post(f"{BASE}/api/v1/publico/turnos/reservar", headers=H, json={
            "id_tipo_prestacion": prest["id_tipo_prestacion"],
            "fecha": s["fecha"], "hora_inicio": s["hora_inicio"],
            "observaciones": "Prueba E2E etapa C (app vecinos)",
        })
        if r.status_code == 201:
            turno_a, slot_a = r.json(), s
            break
        if r.status_code != 409:  # 409 = dup del dia o slot tomado: probar otro dia
            break
    check("4. reservar turno A", turno_a is not None,
          f"({'id ' + str(turno_a['id_turno']) + ' ' + slot_a['fecha'] if turno_a else r.status_code}) {r.text[:100] if turno_a is None else ''}")
    if not turno_a:
        return 1

    # 5. Mismo slot de nuevo -> 409 (solape con la ocupacion espejo)
    r = c.post(f"{BASE}/api/v1/publico/turnos/reservar", headers=H, json={
        "id_tipo_prestacion": prest["id_tipo_prestacion"],
        "fecha": slot_a["fecha"], "hora_inicio": slot_a["hora_inicio"],
    })
    check("5. mismo slot -> 409", r.status_code == 409, f"({r.status_code})")

    # 6. Mis turnos: contiene el turno A reservado
    r = c.get(f"{BASE}/api/v1/publico/turnos", headers=H)
    mios = r.json()
    tiene_a = any(t["id_turno"] == turno_a["id_turno"] and t["estado"] == "reservado" for t in mios)
    check("6. mis turnos contiene A reservado", r.status_code == 200 and tiene_a, f"({len(mios)} turnos)")

    # 7. Sin token -> 401
    r = c.get(f"{BASE}/api/v1/publico/turnos")
    check("7. sin token 401", r.status_code == 401, f"({r.status_code})")

    # 8. Cancelar turno ajeno -> 404 (id que no es del vecino: probamos ids bajos)
    ajeno_404 = None
    ids_mios = {t["id_turno"] for t in mios}
    for cand in range(1, 30):
        if cand in ids_mios:
            continue
        r = c.patch(f"{BASE}/api/v1/publico/turnos/{cand}/cancelar", headers=H)
        ajeno_404 = r.status_code
        break
    check("8. cancelar turno ajeno -> 404", ajeno_404 == 404, f"({ajeno_404})")

    # 9. Reservar turno B en OTRO dia (queda como demo) + cancelar turno A (probar flujo)
    turno_b = None
    for f in fechas:
        if f == slot_a["fecha"]:
            continue
        s = por_fecha[f]
        r = c.post(f"{BASE}/api/v1/publico/turnos/reservar", headers=H, json={
            "id_tipo_prestacion": prest["id_tipo_prestacion"],
            "fecha": s["fecha"], "hora_inicio": s["hora_inicio"],
            "observaciones": "Demo app vecinos (etapa C)",
        })
        if r.status_code == 201:
            turno_b = r.json()
            break
    check("9a. reservar turno B (queda de demo)", turno_b is not None,
          f"({'id ' + str(turno_b['id_turno']) if turno_b else 'sin dia libre'})")

    r = c.patch(f"{BASE}/api/v1/publico/turnos/{turno_a['id_turno']}/cancelar", headers=H)
    check("9b. cancelar turno A", r.status_code == 200 and r.json().get("estado") == "cancelado")

    # 9c. Cancelar de nuevo -> idempotente
    r = c.patch(f"{BASE}/api/v1/publico/turnos/{turno_a['id_turno']}/cancelar", headers=H)
    check("9c. re-cancelar idempotente", r.status_code == 200 and r.json().get("ya_cancelado") is True)

    # 10. El slot del turno A quedo liberado (vuelve a aparecer en /slots)
    r = c.get(f"{BASE}/api/v1/turnos/publico/slots",
              params={"id_tipo_prestacion": prest["id_tipo_prestacion"],
                      "fecha_desde": slot_a["fecha"], "dias": 1})
    libres = r.json() if r.status_code == 200 else []
    liberado = any(s["hora_inicio"] == slot_a["hora_inicio"] for s in libres)
    check("10. slot liberado tras cancelar", liberado, f"({len(libres)} slots ese dia)")

    print(f"\n{'TODOS OK' if fail_count == 0 else 'HAY FALLOS'}: {ok_count} OK / {fail_count} FAIL")
    if turno_b:
        print(f"Queda de demo: turno {turno_b['id_turno']} reservado ({prest['nombre']})")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
