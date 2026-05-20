"""
Smoke test del backend publico (App Vecinos - Etapa 0).
Ejecuta 15 pasos end-to-end contra http://127.0.0.1:8000 + DB local zaris_dev.

Uso (desde backend/):
    $env:PYTHONIOENCODING="utf-8"; python smoke_publico_auth.py

Sale con exit code 0 si todo pasa, 1 si algun paso falla.
"""
import asyncio
import os
import sys
import json
import re

import httpx
import asyncpg


API_BASE = os.getenv("SMOKE_API", "http://127.0.0.1:8000")
DB_DSN = os.getenv(
    "SMOKE_DB_DSN",
    "postgresql://postgres:145236@127.0.0.1:5432/zaris_dev",
)
ADMIN_EMAIL = "ciudadanovl@municipio.gob.ar"
ADMIN_PASS = "123456"
DNI_TEST = "99999999"
EMAIL_TEST = "test+99999999@zaris.com.ar"
PASS_TEST = "TestPass123"
PASS_NUEVA = "NuevaPass456"


def ok(msg: str):
    print(f"  [OK] {msg}")


def fail(paso: int, detalle: str):
    print(f"\n[FAIL] PASO {paso}: {detalle}")
    sys.exit(1)


async def main():
    print(f"== Smoke publico_auth contra {API_BASE} ==\n")
    conn = await asyncpg.connect(DB_DSN)
    client = httpx.AsyncClient(base_url=API_BASE, timeout=10.0)

    try:
        # ─── PASO 1: cleanup previo ───────────────────────────────────────
        print("PASO 1: cleanup previo")
        await conn.execute(
            "DELETE FROM ciudadanos WHERE doc_nro = $1", DNI_TEST,
        )
        ok(f"cleanup de DNI={DNI_TEST} OK (cascade limpia credencial/canal/push)")

        # ─── PASO 2: login agente ─────────────────────────────────────────
        print("\nPASO 2: login agente admin")
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
        )
        if r.status_code != 200:
            fail(2, f"login admin -> {r.status_code} {r.text}")
        admin_token = r.json()["access_token"]
        ok(f"login admin OK, token scope='agente' (len={len(admin_token)})")

        # ─── PASO 3: POST /registrar ──────────────────────────────────────
        print("\nPASO 3: POST /publico/auth/registrar")
        r = await client.post(
            "/api/v1/publico/auth/registrar",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "dni": DNI_TEST,
                "apellido": "Vecinosmoke",
                "nombre": "Test",
                "email": EMAIL_TEST,
                "telefono": "1140000000",
            },
        )
        if r.status_code != 201:
            fail(3, f"/registrar -> {r.status_code} {r.text}")
        body = r.json()
        if not body.get("activacion_enviada"):
            fail(3, f"activacion_enviada=False en response: {body}")
        id_ciudadano = body["id_ciudadano"]
        ok(f"ciudadano creado id={id_ciudadano}, activacion_enviada=True")

        # ─── PASO 4: verificar DB ─────────────────────────────────────────
        print("\nPASO 4: verificar DB post-registro")
        row = await conn.fetchrow(
            "SELECT estado_validacion, activo FROM ciudadanos WHERE id_ciudadano=$1",
            id_ciudadano,
        )
        if not row or row["estado_validacion"] != "verificado" or not row["activo"]:
            fail(4, f"ciudadano DB row invalida: {row}")
        ok(f"ciudadanos: estado_validacion=verificado activo=true")

        row = await conn.fetchrow(
            "SELECT token_activacion, activado, password_hash FROM ciudadano_credencial WHERE id_ciudadano=$1",
            id_ciudadano,
        )
        if not row or row["token_activacion"] is None or row["activado"] or row["password_hash"] is not None:
            fail(4, f"ciudadano_credencial DB row invalida: {row}")
        ok(f"credencial: token_activacion presente, activado=false, password_hash=NULL")

        row = await conn.fetchrow(
            "SELECT canal_email FROM ciudadano_canal_preferido WHERE id_ciudadano=$1",
            id_ciudadano,
        )
        if not row or not row["canal_email"]:
            fail(4, f"canal_preferido DB row invalida: {row}")
        ok(f"canal_preferido: canal_email=true")

        # ─── PASO 5: leer token_activacion ────────────────────────────────
        print("\nPASO 5: leer token_activacion de la DB")
        row = await conn.fetchrow(
            "SELECT token_activacion FROM ciudadano_credencial WHERE id_ciudadano=$1",
            id_ciudadano,
        )
        token_activacion = str(row["token_activacion"])
        ok(f"token_activacion = {token_activacion}")

        # ─── PASO 6: POST /activar ────────────────────────────────────────
        print("\nPASO 6: POST /publico/auth/activar")
        r = await client.post(
            "/api/v1/publico/auth/activar",
            json={"token": token_activacion, "password": PASS_TEST},
        )
        if r.status_code != 200:
            fail(6, f"/activar -> {r.status_code} {r.text}")
        body = r.json()
        publico_token = body["access_token"]
        if body["ciudadano"]["dni"] != DNI_TEST:
            fail(6, f"ciudadano.dni inesperado: {body}")
        ok(f"activacion OK, JWT scope='publico' devuelto (len={len(publico_token)})")

        # ─── PASO 7: GET /me con scope publico ────────────────────────────
        print("\nPASO 7: GET /publico/auth/me con scope publico")
        r = await client.get(
            "/api/v1/publico/auth/me",
            headers={"Authorization": f"Bearer {publico_token}"},
        )
        if r.status_code != 200:
            fail(7, f"/me -> {r.status_code} {r.text}")
        body = r.json()
        if body["dni"] != DNI_TEST or body["email"] != EMAIL_TEST:
            fail(7, f"datos /me incorrectos: {body}")
        ok(f"/me devuelve datos del ciudadano correctamente")

        # ─── PASO 8: /me con token agente debe dar 401 ───────────────────
        print("\nPASO 8: GET /publico/auth/me con token scope agente -> 401")
        r = await client.get(
            "/api/v1/publico/auth/me",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        if r.status_code != 401:
            fail(8, f"esperaba 401 pero llego {r.status_code}: {r.text}")
        ok(f"guard de scope funciona: token agente rechazado en endpoint publico")

        # ─── PASO 9: POST /login con DNI + PASS_TEST ──────────────────────
        print("\nPASO 9: POST /publico/auth/login")
        r = await client.post(
            "/api/v1/publico/auth/login",
            json={"dni": DNI_TEST, "password": PASS_TEST},
        )
        if r.status_code != 200:
            fail(9, f"/login -> {r.status_code} {r.text}")
        ok(f"login OK con password correcto")

        # ─── PASO 10: 5 logins fallidos -> lockout ───────────────────────
        print("\nPASO 10: 5 logins con password incorrecto -> lockout")
        # reset intentos_fallidos a 0 por las dudas (paso 9 ya lo hizo)
        for i in range(5):
            r = await client.post(
                "/api/v1/publico/auth/login",
                json={"dni": DNI_TEST, "password": "PASSWORD_INCORRECTO_XYZ"},
            )
            if r.status_code != 401:
                fail(10, f"intento {i+1}: esperaba 401, llego {r.status_code}: {r.text}")
        # Verificar lockout en DB
        row = await conn.fetchrow(
            "SELECT bloqueada_hasta FROM ciudadano_credencial WHERE id_ciudadano=$1",
            id_ciudadano,
        )
        if not row["bloqueada_hasta"]:
            fail(10, f"bloqueada_hasta es NULL pero esperaba timestamp futuro")
        ok(f"lockout activado: bloqueada_hasta={row['bloqueada_hasta']}")

        # Liberar lockout manualmente para seguir con el smoke
        await conn.execute(
            "UPDATE ciudadano_credencial SET bloqueada_hasta=NULL, intentos_fallidos=0 WHERE id_ciudadano=$1",
            id_ciudadano,
        )
        ok(f"lockout liberado manualmente para continuar smoke")

        # ─── PASO 11: POST /recuperar-password ───────────────────────────
        print("\nPASO 11: POST /publico/auth/recuperar-password")
        r = await client.post(
            "/api/v1/publico/auth/recuperar-password",
            json={"dni": DNI_TEST},
        )
        if r.status_code != 200:
            fail(11, f"/recuperar-password -> {r.status_code} {r.text}")
        if not r.json().get("enviado"):
            fail(11, f"enviado=False: {r.json()}")
        ok(f"recovery OK (modo MOCK / mail real segun SMTP)")

        # ─── PASO 12: leer token_recovery + /resetear-password ────────────
        print("\nPASO 12: leer token_recovery + POST /publico/auth/resetear-password")
        row = await conn.fetchrow(
            "SELECT token_recovery FROM ciudadano_credencial WHERE id_ciudadano=$1",
            id_ciudadano,
        )
        if not row["token_recovery"]:
            fail(12, "token_recovery NULL despues de /recuperar-password")
        token_recovery = str(row["token_recovery"])
        ok(f"token_recovery = {token_recovery}")

        r = await client.post(
            "/api/v1/publico/auth/resetear-password",
            json={"token": token_recovery, "password": PASS_NUEVA},
        )
        if r.status_code != 200:
            fail(12, f"/resetear-password -> {r.status_code} {r.text}")
        if "access_token" not in r.json():
            fail(12, f"sin access_token en response: {r.json()}")
        ok(f"reset OK, JWT scope publico devuelto")

        # ─── PASO 13: login con nuevo password ───────────────────────────
        print("\nPASO 13: POST /publico/auth/login con nuevo password")
        r = await client.post(
            "/api/v1/publico/auth/login",
            json={"dni": DNI_TEST, "password": PASS_NUEVA},
        )
        if r.status_code != 200:
            fail(13, f"login con nueva pass -> {r.status_code} {r.text}")
        # Login con vieja debe fallar
        r = await client.post(
            "/api/v1/publico/auth/login",
            json={"dni": DNI_TEST, "password": PASS_TEST},
        )
        if r.status_code != 401:
            fail(13, f"login con vieja pass deberia fallar, llego {r.status_code}: {r.text}")
        ok(f"login con nueva pass OK, vieja invalidada")

        # ─── PASO 14: GET /identidad-municipio sin auth ──────────────────
        print("\nPASO 14: GET /publico/identidad-municipio sin auth")
        r = await client.get("/api/v1/publico/identidad-municipio")
        if r.status_code != 200:
            fail(14, f"/identidad-municipio -> {r.status_code} {r.text}")
        body = r.json()
        expected_keys = {
            "municipio_nombre", "municipio_logo_url", "municipio_descripcion",
            "municipio_color_primary", "municipio_color_accent",
        }
        if set(body.keys()) != expected_keys:
            fail(14, f"keys inesperadas: {sorted(body.keys())}")
        ok(f"identidad-municipio OK con las 5 claves: {body}")

        # ─── PASO 15: cleanup final ──────────────────────────────────────
        print("\nPASO 15: cleanup final")
        # Limpiar lockout antes para que no haya residuo
        await conn.execute(
            "DELETE FROM ciudadanos WHERE doc_nro = $1", DNI_TEST,
        )
        # Verificar cascade
        sobrevivientes = await conn.fetchval(
            "SELECT COUNT(*) FROM ciudadano_credencial WHERE id_ciudadano = $1",
            id_ciudadano,
        )
        if sobrevivientes != 0:
            fail(15, f"cascade fallo: {sobrevivientes} filas en credencial")
        ok(f"cleanup OK, sin filas residuales")

        print("\n[OK] TODOS LOS PASOS OK (15/15)")
        return 0

    finally:
        await client.aclose()
        await conn.close()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
