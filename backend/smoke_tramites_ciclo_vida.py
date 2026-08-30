# -*- coding: utf-8 -*-
"""
Smoke — ciclo de vida del trámite hacia el vecino (mig 101):
  - resultado derivado de la transición final (aprobar -> aprobado) + aviso PWA + encuesta,
  - timer de desistimiento (aviso 1 / aviso 2 / aviso final / DESISTIDO automático),
  - desistido manual (POST /resultado),
  - flag `espera_iniciador` editable in-place (PATCH) en una versión publicada con trámites.

SOLO LOCAL: arma fixtures por SQL (tipo_accion de la transición final, plazos de
config, fechas del trámite de prueba para "viajar en el tiempo") y los RESTAURA al
final. Los trámites creados quedan como demo. Requiere uvicorn local en :8000 con
.env.local y el vecino demo DNI 28547123 (id 3).

    python smoke_tramites_ciclo_vida.py
"""
import re
import sys
from collections import deque
from datetime import date

import httpx
import psycopg2

BASE = "http://127.0.0.1:8000"
DB = "postgresql://postgres:145236@127.0.0.1:5432/zaris_dev"
ADMIN = ("ciudadanovl@municipio.gob.ar", "123456")
VECINO = ("28547123", "123456")
ID_CIUDADANO = 3
TIPO_CODIGO = "poda-arbol"
SLA_LEJANO = 36500  # 100 anios: ningun otro tramite cruza umbrales durante el smoke
CFG_KEYS = ("tramite_desistimiento_activo", "tramite_sla_dias_default",
            "tramite_desistimiento_aviso1_dias", "tramite_desistimiento_aviso2_dias",
            "tramite_desistimiento_dias", "tramite_desistimiento_aviso_final_horas")
CFG_SMOKE = {"tramite_desistimiento_activo": "true", "tramite_sla_dias_default": str(SLA_LEJANO),
             "tramite_desistimiento_aviso1_dias": "30", "tramite_desistimiento_aviso2_dias": "60",
             "tramite_desistimiento_dias": "90", "tramite_desistimiento_aviso_final_horas": "72"}

ok_count = fail_count = 0


def check(nombre, cond, extra=""):
    global ok_count, fail_count
    if cond:
        ok_count += 1
        print(f"  OK   {nombre} {extra}")
    else:
        fail_count += 1
        print(f"  FAIL {nombre} {extra}")


def dispatcher_token() -> str:
    for line in open(".env.local", encoding="utf-8"):
        m = re.match(r"\s*DISPATCHER_TOKEN\s*=\s*['\"]?([^'\"\s]+)", line)
        if m:
            return m.group(1)
    sys.exit("No hay DISPATCHER_TOKEN en .env.local")


def valor_campo(c: dict):
    td = c.get("tipo_dato")
    if td == "direccion":
        return "Av. Maipú 1234, Vicente López"
    if td in ("texto", "texto_largo", "textarea"):
        return "Smoke ciclo de vida (mig 101)"
    if td in ("numero", "entero", "decimal"):
        return 1
    if td == "fecha":
        return date.today().isoformat()
    if td == "booleano":
        return True
    if td == "email":
        return "smoke@example.com"
    if td in ("seleccion", "seleccion_multiple"):
        ops = c.get("opciones_jsonb") or []
        if isinstance(ops, dict):
            ops = ops.get("opciones") or []
        first = ops[0] if ops else "a"
        v = first.get("valor") if isinstance(first, dict) else first
        return [v] if td == "seleccion_multiple" else v
    return "smoke"


def main() -> int:
    c = httpx.Client(timeout=90)
    db = psycopg2.connect(DB)
    db.autocommit = True
    cur = db.cursor()
    tok = dispatcher_token()

    # ── 0. Fixtures ────────────────────────────────────────────────────────
    cur.execute("SELECT id_tipo_tramite, id_version_publicada FROM tipo_tramite WHERE codigo=%s", (TIPO_CODIGO,))
    id_tipo, id_ver = cur.fetchone()
    cur.execute("""SELECT id_tipo_tramite_estado FROM tipo_tramite_estado
                   WHERE id_tipo_tramite_version=%s AND es_inicial AND activo""", (id_ver,))
    id_inicial = cur.fetchone()[0]
    cur.execute("""SELECT tr.id_tipo_tramite_transicion, tr.id_estado_origen, tr.id_estado_destino,
                          tr.tipo_accion, tr.requiere_adjunto, ed.es_final, eo.codigo
                     FROM tipo_tramite_transicion tr
                     JOIN tipo_tramite_estado ed ON ed.id_tipo_tramite_estado=tr.id_estado_destino
                     JOIN tipo_tramite_estado eo ON eo.id_tipo_tramite_estado=tr.id_estado_origen
                    WHERE tr.id_tipo_tramite_version=%s AND tr.activo""", (id_ver,))
    trans = cur.fetchall()
    finales = [t for t in trans if t[5] and not t[4]]
    finales.sort(key=lambda t: (t[6] != "aprobada", t[0]))
    tr_final = finales[0]
    id_tr_final, tipo_accion_orig = tr_final[0], tr_final[3]
    cur.execute("UPDATE tipo_tramite_transicion SET tipo_accion='aprobar' WHERE id_tipo_tramite_transicion=%s", (id_tr_final,))

    # BFS inicial -> origen de la transicion final (sin transiciones con adjunto obligatorio)
    grafo = {}
    for t in trans:
        if not t[4]:
            grafo.setdefault(t[1], []).append((t[0], t[2]))
    objetivo = tr_final[1]
    prev = {id_inicial: None}
    q = deque([id_inicial])
    while q:
        n = q.popleft()
        if n == objetivo:
            break
        for id_tr, dest in grafo.get(n, []):
            if dest not in prev:
                prev[dest] = (n, id_tr)
                q.append(dest)
    camino = []
    n = objetivo
    while prev.get(n):
        p, id_tr = prev[n]
        camino.append(id_tr)
        n = p
    camino.reverse()
    camino.append(id_tr_final)

    cur.execute("SELECT clave, valor FROM configuracion_general WHERE clave = ANY(%s)", (list(CFG_KEYS),))
    cfg_orig = dict(cur.fetchall())
    for k, v in CFG_SMOKE.items():
        cur.execute("UPDATE configuracion_general SET valor=%s WHERE clave=%s", (v, k))
    cur.execute("SELECT sla_dias FROM tipo_tramite WHERE id_tipo_tramite=%s", (id_tipo,))
    sla_orig = cur.fetchone()[0]
    cur.execute("UPDATE tipo_tramite SET sla_dias=NULL WHERE id_tipo_tramite=%s", (id_tipo,))
    cur.execute("SELECT email FROM ciudadanos WHERE id_ciudadano=%s", (ID_CIUDADANO,))
    email_vecino = cur.fetchone()[0]
    print(f"fixtures: tipo={id_tipo} ver={id_ver} inicial={id_inicial} tr_final={id_tr_final} "
          f"(era {tipo_accion_orig}) camino={camino} email_vecino={'ok' if email_vecino else 'SIN EMAIL'}")

    try:
        # ── 1. Logins ──────────────────────────────────────────────────────
        r = c.post(f"{BASE}/api/v1/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]})
        check("1a. login admin", r.status_code == 200, f"({r.status_code})")
        HA = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = c.post(f"{BASE}/api/v1/publico/auth/login", json={"dni": VECINO[0], "password": VECINO[1]})
        check("1b. login vecino", r.status_code == 200, f"({r.status_code})")
        HV = {"Authorization": f"Bearer {r.json()['access_token']}"}

        # campos del tipo para el alta
        r = c.get(f"{BASE}/api/v1/tramites/tipos/{id_tipo}", headers=HA)
        campos = r.json().get("campos") or []
        datos = {ca["nombre_interno"]: valor_campo(ca) for ca in campos if ca.get("obligatorio")}

        def crear(asunto: str) -> tuple[int, str]:
            rr = c.post(f"{BASE}/api/v1/tramites", headers=HA, json={
                "id_tipo_tramite": id_tipo, "asunto": asunto,
                "iniciador": {"tipo": "ciudadano", "id_ciudadano": ID_CIUDADANO},
                "datos": datos, "id_municipio": 1,
            })
            if rr.status_code not in (200, 201):
                print("   crear tramite fallo:", rr.status_code, rr.text[:200])
                return 0, ""
            j = rr.json()
            return int(j["id_tramite"]), j.get("numero_expediente", "")

        def avisos_vecino(recurso_id: int) -> list[dict]:
            rr = c.get(f"{BASE}/api/v1/publico/avisos", headers=HV, params={"limit": 100})
            return [a for a in rr.json().get("avisos", []) if a.get("recurso_tipo") == "tramite" and a.get("recurso_id") == recurso_id]

        # ── 2-3. Tramite A + flag espera_iniciador in-place ────────────────
        id_a, num_a = crear("Smoke ciclo de vida A (timer)")
        check("2. crear tramite A (iniciador ciudadano)", id_a > 0, f"({num_a})")
        r = c.patch(f"{BASE}/api/v1/admin/tramites/estados/{id_inicial}/espera-iniciador", headers=HA, json={"espera_iniciador": True})
        check("3. PATCH espera-iniciador=true en version publicada con tramites -> 200",
              r.status_code == 200 and r.json().get("espera_iniciador") is True, f"({r.status_code} {r.text[:80]})")

        # ── 4-5. Timer: viajar en el tiempo y correr el cron ───────────────
        base_pend = len([a for a in avisos_vecino(id_a) if a["tipo"] == "tramite_pendiente"])
        check("4. bandeja sin avisos previos del tramite A", base_pend == 0, f"({base_pend})")
        H_DISP = {"X-Dispatcher-Token": tok}
        for offset, esperado in ((31, 1), (61, 2), (88, 3), (91, "desistido")):
            cur.execute("""UPDATE tramite SET fecha_alta = NOW() - make_interval(days => %s),
                                              fecha_entrada_estado_actual = NOW() - make_interval(days => %s)
                           WHERE id_tramite=%s""", (SLA_LEJANO + offset, SLA_LEJANO + offset, id_a))
            r = c.post(f"{BASE}/api/v1/tramites/mantenimiento/ejecutar", headers=H_DISP)
            des = (r.json() or {}).get("desistimiento", {}) if r.status_code == 200 else {}
            cur.execute("SELECT desist_aviso_nivel, resultado, fecha_archivado, archivado_motivo FROM tramite WHERE id_tramite=%s", (id_a,))
            nivel, res, farch, motivo = cur.fetchone()
            if esperado == "desistido":
                check("5d. cron +91d -> DESISTIDO automatico (resultado + archivado por desistimiento)",
                      r.status_code == 200 and res == "desistido" and farch is not None and motivo == "desistimiento",
                      f"({r.status_code} res={res} motivo={motivo} desistidos={des.get('desistidos')})")
            else:
                check(f"5{'abc'[esperado-1]}. cron +{offset}d -> aviso {esperado} (nivel={esperado}, sigue pendiente)",
                      r.status_code == 200 and nivel == esperado and res == "pendiente",
                      f"({r.status_code} nivel={nivel} avisos_run={des.get('avisos')})")
        av = avisos_vecino(id_a)
        pend = [a for a in av if a["tipo"] == "tramite_pendiente"]
        est = [a for a in av if a["tipo"] == "tramite_estado"]
        check("6. bandeja del vecino: 3 avisos 'tramite_pendiente' + 1 'tramite_estado' (desistido)",
              len(pend) == 3 and len(est) == 1 and "desistido" in (est[0]["titulo"] or "").lower(),
              f"(pend={len(pend)} est={[e['titulo'] for e in est]})")
        check("6b. el ultimo aviso menciona las 72 horas", any("72" in (a["titulo"] or "") for a in pend))
        cur.execute("SELECT tipo, COUNT(*) FROM tramite_movimiento WHERE id_tramite=%s AND tipo IN ('aviso_iniciador','desistido') GROUP BY tipo", (id_a,))
        led = dict(cur.fetchall())
        check("7. ledger: 3 'aviso_iniciador' + 1 'desistido'", led.get("aviso_iniciador") == 3 and led.get("desistido") == 1, f"({led})")
        cur.execute("SELECT COUNT(*) FROM notificacion WHERE recurso_tipo='tramite' AND recurso_id=%s AND tipo='tramite_pendiente_vecino'", (id_a,))
        print(f"  INFO notificaciones internas al colectivo (depende de que la subarea destino tenga usuarios): {cur.fetchone()[0]}")
        cur.execute("SELECT COUNT(*) FROM tramite WHERE id_tramite<>%s AND archivado_motivo='desistimiento' AND fecha_archivado > NOW() - interval '15 minutes'", (id_a,))
        check("8. ningun otro tramite fue desistido por el smoke (SLA lejano)", cur.fetchone()[0] == 0)
        r = c.patch(f"{BASE}/api/v1/admin/tramites/estados/{id_inicial}/espera-iniciador", headers=HA, json={"espera_iniciador": False})
        check("9. PATCH espera-iniciador=false (restaurar)", r.status_code == 200 and r.json().get("espera_iniciador") is False)

        # ── 10-13. Tramite B: transicion final 'aprobar' -> resultado automatico ──
        id_b, num_b = crear("Smoke ciclo de vida B (aprobado)")
        check("10. crear tramite B", id_b > 0, f"({num_b})")
        ultimo = None
        for id_tr in camino:
            ultimo = c.post(f"{BASE}/api/v1/tramites/{id_b}/transicionar", headers=HA,
                            json={"id_tipo_tramite_transicion": id_tr, "comentario": "smoke ciclo de vida"})
            if ultimo.status_code != 200:
                print("   transicion fallo:", id_tr, ultimo.status_code, ultimo.text[:160])
                break
        det = ultimo.json() if ultimo is not None and ultimo.status_code == 200 else {}
        check("11. transicion final 'aprobar' -> resultado='aprobado' automatico",
              det.get("resultado") == "aprobado", f"(resultado={det.get('resultado')})")
        cur.execute("SELECT metadata_jsonb->>'automatico' FROM tramite_movimiento WHERE id_tramite=%s AND tipo='resultado' ORDER BY orden_secuencial DESC LIMIT 1", (id_b,))
        row = cur.fetchone()
        check("11b. ledger 'resultado' con automatico=true", row is not None and row[0] == "true", f"({row})")
        est_b = [a for a in avisos_vecino(id_b) if a["tipo"] == "tramite_estado"]
        check("12. aviso PWA 'termino: APROBADO' en la bandeja del vecino",
              len(est_b) >= 1 and "APROBADO" in (est_b[0]["titulo"] or ""), f"({[e['titulo'] for e in est_b]})")
        cur.execute("SELECT token_unico, estado FROM encuesta_envio WHERE id_tramite=%s AND activo", (id_b,))
        enc = cur.fetchone()
        check("13. encuesta CSAT creada con id_tramite (estado pendiente)", enc is not None and enc[1] == "pendiente",
              f"({enc})" if not email_vecino else "")
        if enc:
            r = c.get(f"{BASE}/api/v1/admin/encuestas/envios", headers=HA, params={"id_tramite": id_b})
            lst = r.json() if r.status_code == 200 else []
            check("13b. admin /envios?id_tramite -> tipo 'tramites' y referencia = numero",
                  r.status_code == 200 and len(lst) == 1 and lst[0].get("tipo") == "tramites" and lst[0].get("referencia") == num_b,
                  f"({r.status_code} {lst[0].get('tipo') if lst else '-'} {lst[0].get('referencia') if lst else '-'})")
            r = c.get(f"{BASE}/api/v1/publico/encuesta/{enc[0]}")
            check("13c. form publico carga la encuesta del tramite (200, menciona el expediente)",
                  r.status_code == 200 and num_b in r.text, f"({r.status_code})")

        # ── 14. Tramite C: desistido MANUAL ────────────────────────────────
        id_c, num_c = crear("Smoke ciclo de vida C (desistido manual)")
        r = c.post(f"{BASE}/api/v1/tramites/{id_c}/resultado", headers=HA, json={"resultado": "desistido", "comentario": "smoke manual"})
        cur.execute("SELECT resultado, archivado_motivo FROM tramite WHERE id_tramite=%s", (id_c,))
        res_c = cur.fetchone()
        est_c = [a for a in avisos_vecino(id_c) if a["tipo"] == "tramite_estado"]
        check("14. POST /resultado desistido -> 200 + archivado por desistimiento + aviso al vecino",
              r.status_code == 200 and res_c == ("desistido", "desistimiento") and len(est_c) == 1,
              f"({r.status_code} {res_c} avisos={len(est_c)})")
        r = c.post(f"{BASE}/api/v1/tramites/{id_c}/resultado", headers=HA, json={"resultado": "cualquiera"})
        check("14b. resultado invalido -> 422", r.status_code == 422, f"({r.status_code})")
    finally:
        # ── Restaurar fixtures ────────────────────────────────────────────
        cur.execute("UPDATE tipo_tramite_transicion SET tipo_accion=%s WHERE id_tipo_tramite_transicion=%s", (tipo_accion_orig, id_tr_final))
        for k, v in cfg_orig.items():
            cur.execute("UPDATE configuracion_general SET valor=%s WHERE clave=%s", (v, k))
        cur.execute("UPDATE tipo_tramite SET sla_dias=%s WHERE id_tipo_tramite=%s", (sla_orig, id_tipo))
        cur.execute("UPDATE tipo_tramite_estado SET espera_iniciador=FALSE WHERE id_tipo_tramite_estado=%s", (id_inicial,))
        print("fixtures restaurados (tipo_accion, config, sla_dias, flag)")

    print(f"\nRESULTADO: {ok_count} OK / {fail_count} FAIL")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
