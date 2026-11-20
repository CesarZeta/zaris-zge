# -*- coding: utf-8 -*-
"""
Smoke — archivos con carpeta por municipio y crons por municipio (IT-01 F6.4,
PLAN_MULTI_MUNICIPIO_F6_4.md).

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_archivos_municipio.py

SOLO LOCAL. Storage simulado: en local las credenciales de Storage son las de prod, así que el smoke
nunca sube ni borra objetos reales.
"""
import asyncio
import os
import sys

os.environ.setdefault("ENV_FILE", ".env.local")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

OK = FAIL = 0


def check(cond: bool, nombre: str, detalle: str = "") -> None:
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  OK   {nombre}")
    else:
        FAIL += 1
        print(f"  FAIL {nombre} {detalle}")


def lanza(fn, *args) -> bool:
    try:
        fn(*args)
    except ValueError:
        return True
    return False


def parte_rutas() -> None:
    print("— rutas")
    from app.core import storage as st
    check(st.ruta_de_municipio(1, "reclamos/5/a.jpg") == "m1/reclamos/5/a.jpg", "ruta_con_municipio")
    check(st.ruta_de_municipio(None, "usuarios/102/avatar-x.png") == "global/usuarios/102/avatar-x.png",
          "ruta_sin_municipio_va_a_global")
    check(lanza(st.ruta_de_municipio, 1, "../x"), "ruta_invalida_lanza")
    check(lanza(st.ruta_de_municipio, 1, "m2/reclamos/5/a.jpg"), "ruta_ya_prefijada_lanza")
    check(lanza(st.ruta_de_municipio, None, "global/a"), "ruta_ya_global_lanza")
    check(st.municipio_de_ruta("m12/ot/1/a.png") == 12, "municipio_de_ruta")
    check(st.municipio_de_ruta("reclamos/1/a.png") is None, "municipio_de_ruta_formato_viejo")
    check(st.municipio_de_ruta("mx/a") is None, "municipio_de_ruta_prefijo_raro")
    check(st.municipio_de_ruta("global/usuarios/1/a.png") is None, "municipio_de_ruta_global")
    check(st.es_avatar_de("usuarios/6/avatar-ab12.png", 6, 1), "avatar_formato_viejo")
    check(st.es_avatar_de("m1/usuarios/6/avatar-ab12.png", 6, 1), "avatar_formato_nuevo")
    check(not st.es_avatar_de("m2/usuarios/6/avatar-ab12.png", 6, 1), "avatar_otro_municipio")
    check(not st.es_avatar_de("m1/usuarios/7/avatar-ab12.png", 6, 1), "avatar_otro_usuario")
    check(not st.es_avatar_de("m1/usuarios/102/avatar-ab.png", 102, None), "avatar_super_con_municipio")
    check(st.es_avatar_de("global/usuarios/102/avatar-ab.png", 102, None), "avatar_super_global")
    check(st.es_avatar_de("usuarios/102/avatar-ab.png", 102, None), "avatar_super_formato_viejo")
    check(not st.es_avatar_de("global/usuarios/6/avatar-ab.png", 6, 1), "avatar_global_de_cuenta_con_municipio")


class StorageMock:
    """Storage en memoria (patrón de smoke_alta_municipio.py)."""

    def __init__(self):
        self.subidos: list[tuple[str, str]] = []
        self.borrados: list[tuple[str, str]] = []

    def instalar(self):
        from app.core import storage
        from app.core.config import settings as s

        def b(bucket):
            return bucket or s.SUPABASE_ADJUNTOS_BUCKET

        async def firmar_subida(path, bucket=None):
            return {"upload_url": f"https://mock/up/{b(bucket)}/{path}", "token": "t", "path": path, "bucket": b(bucket)}

        async def subir(path, contenido, content_type, bucket=None):
            self.subidos.append((b(bucket), path))

        async def borrar(path, bucket=None):
            self.borrados.append((b(bucket), path))

        async def firmar_bajada(path, ttl_sec=3600, bucket=None):
            return f"https://mock/down/{b(bucket)}/{path}"

        storage.crear_signed_upload_url, storage.subir_objeto = firmar_subida, subir
        storage.borrar_objeto, storage.crear_signed_download_url = borrar, firmar_bajada
        return self


def jpeg_200px() -> bytes:
    """JPEG mínimo que pasa el validador del perfil (lee el SOF): 200x200 y más de 1 KB."""
    app0 = b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    relleno = b"\xff\xfe" + (1202).to_bytes(2, "big") + b"x" * 1200
    sof = b"\xff\xc0\x00\x11\x08\x00\xc8\x00\xc8\x03\x01\x22\x00\x02\x11\x01\x03\x11\x01"
    return b"\xff\xd8" + app0 + relleno + sof + b"\xff\xd9"


async def parte_subidas() -> None:
    print("— subidas")
    import io

    import httpx
    from fastapi import UploadFile
    from sqlalchemy import text

    from app.core import storage as st
    from app.core.config import settings
    from app.core.sistema import SesionSistema
    from app.main import app
    from app.services.tramites import documentos as svc_docs

    if "zaris_dev" not in settings.ASYNC_DATABASE_URI:
        sys.exit("ABORT: este smoke es SOLO LOCAL (la DB configurada no es zaris_dev).")
    mock = StorageMock().instalar()
    pwd = os.environ.get("ZARIS_QA_PASS") or "123456"

    async def q1(sql: str, **p):
        async with SesionSistema() as s:
            r = (await s.execute(text(sql), p)).mappings().first()
            return dict(r) if r else None

    async def ejecutar(sql: str, **p):
        async with SesionSistema() as s:
            await s.execute(text(sql), p)
            await s.commit()

    admin = await q1("SELECT id_usuario, id_municipio, foto_url FROM usuarios WHERE email = 'ciudadanovl@municipio.gob.ar'")
    mun = admin["id_municipio"]
    vecino = await q1("SELECT c.id_ciudadano, c.foto_path FROM ciudadanos c WHERE c.doc_nro = '28547123' AND c.id_municipio = :m", m=mun)
    reclamo = await q1("SELECT id_reclamo FROM reclamos WHERE id_municipio = :m AND activo ORDER BY id_reclamo DESC LIMIT 1", m=mun)
    reclamo_vec = await q1("""SELECT id_reclamo FROM reclamos WHERE id_ciudadano = :c AND activo
                               AND estado NOT IN ('Resuelto','Cancelado','En auditoría','Auditado')
                             ORDER BY id_reclamo DESC LIMIT 1""", c=vecino["id_ciudadano"])
    ot = await q1("SELECT id_ot FROM ordenes_trabajo WHERE id_municipio = :m AND activo ORDER BY id_ot DESC LIMIT 1", m=mun)
    pref = f"m{mun}/"

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://smoke.local", timeout=90) as c:
        r = await c.post("/api/v1/auth/login", json={"identificador": "ciudadanovl@municipio.gob.ar", "password": pwd})
        ha = {"Authorization": f"Bearer {r.json()['access_token']}"}
        archivo = {"nombre_archivo": "smoke.png", "mime_type": "image/png", "tamano_bytes": 100}

        r = await c.post(f"/api/v1/reclamos/{reclamo['id_reclamo']}/adjuntos/upload-url", headers=ha, json=archivo)
        ruta = r.json().get("storage_path", "") if r.status_code == 201 else ""
        check(ruta.startswith(f"{pref}reclamos/{reclamo['id_reclamo']}/"), "subida_adjunto_reclamo", f"{r.status_code} {ruta or r.text[:200]}")
        if r.status_code == 201:
            await ejecutar("DELETE FROM reclamo_adjuntos WHERE id_adjunto = :i", i=r.json()["id_adjunto"])

        r = await c.post(f"/api/v1/ot/{ot['id_ot']}/adjuntos/upload-url", headers=ha, json=archivo)
        ruta = r.json().get("storage_path", "") if r.status_code == 201 else ""
        check(ruta.startswith(f"{pref}ot/{ot['id_ot']}/"), "subida_adjunto_ot", f"{r.status_code} {ruta or r.text[:200]}")
        if r.status_code == 201:
            await ejecutar("DELETE FROM ot_adjuntos WHERE id_adjunto = :i", i=r.json()["id_adjunto"])

        info = await svc_docs.guardar_archivo_mock(
            UploadFile(io.BytesIO(b"%PDF-1.4 smoke"), filename="smoke.pdf"), "EXP-SMOKE-1", 2026, "smoke", mun)
        check(info["storage_path"].startswith(f"{pref}tramites/2026/"), "subida_documento_tramite", info["storage_path"])

        r = await c.post("/api/v1/config/identidad/logo-upload-url", headers=ha, json={"mime_type": "image/png", "tamano_bytes": 100})
        check(r.status_code == 200 and r.json()["path"].startswith(f"{pref}logo-"), "subida_logo", f"{r.status_code} {r.text[:200]}")

        r = await c.post("/api/v1/auth/me/foto-upload-url", headers=ha, json={"mime_type": "image/png", "tamano_bytes": 100})
        nueva = r.json() if r.status_code == 200 else {}
        check(nueva.get("path", "").startswith(f"{pref}usuarios/{admin['id_usuario']}/avatar-"), "subida_foto_usuario", f"{r.status_code} {r.text[:200]}")
        if nueva:
            r = await c.put("/api/v1/auth/me/foto", headers=ha, json={"foto_url": nueva["public_url"]})
            check(r.status_code == 200, "foto_usuario_formato_nuevo_ok", f"{r.status_code} {r.text[:200]}")
        vieja = st.url_publica(f"usuarios/{admin['id_usuario']}/avatar-0a1b2c.png", "config-assets")
        r = await c.put("/api/v1/auth/me/foto", headers=ha, json={"foto_url": vieja})
        check(r.status_code == 200, "foto_usuario_formato_viejo_ok", f"{r.status_code} {r.text[:200]}")
        ajena = st.url_publica(f"m{mun + 1000}/usuarios/{admin['id_usuario']}/avatar-0a1b2c.png", "config-assets")
        r = await c.put("/api/v1/auth/me/foto", headers=ha, json={"foto_url": ajena})
        check(r.status_code == 422, "foto_usuario_prefijo_ajeno_422", f"{r.status_code}")
        await ejecutar("UPDATE usuarios SET foto_url = :u WHERE id_usuario = :i", u=admin["foto_url"], i=admin["id_usuario"])

        r = await c.post("/api/v1/auth/login", json={"identificador": "super.admin@prueba-aislamiento.com.ar", "password": pwd})
        if r.status_code == 200 and "access_token" in r.json():
            hs = {"Authorization": f"Bearer {r.json()['access_token']}"}
            r = await c.post("/api/v1/auth/me/foto-upload-url", headers=hs, json={"mime_type": "image/png", "tamano_bytes": 100})
            check(r.status_code == 200 and r.json()["path"].startswith("global/usuarios/"), "subida_foto_super", f"{r.status_code} {r.text[:200]}")
        else:
            check(False, "subida_foto_super", f"sin el super local (correr smoke_super_admin.py): {r.status_code}")

        r = await c.post("/api/v1/publico/auth/login", json={"dni": "28547123", "password": pwd})
        hv = {"Authorization": f"Bearer {r.json()['access_token']}"} if r.status_code == 200 else {}
        check(bool(hv), "login_vecino", f"{r.status_code} {r.text[:200]}")
        if hv and reclamo_vec:
            r = await c.post(f"/api/v1/publico/reclamos/{reclamo_vec['id_reclamo']}/adjuntos/upload-url", headers=hv,
                             json={"nombre_archivo": "smoke.jpg", "mime_type": "image/jpeg", "tamano_bytes": 100})
            ruta = r.json().get("storage_path", "") if r.status_code == 201 else ""
            check(ruta.startswith(f"{pref}reclamos/{reclamo_vec['id_reclamo']}/"), "subida_adjunto_reclamo_vecino", f"{r.status_code} {ruta or r.text[:200]}")
            if r.status_code == 201:
                await ejecutar("DELETE FROM reclamo_adjuntos WHERE id_adjunto = :i", i=r.json()["id_adjunto"])
        elif hv:
            check(False, "subida_adjunto_reclamo_vecino", "el vecino 28547123 no tiene un reclamo abierto")
        if hv:
            idc = vecino["id_ciudadano"]
            await ejecutar("UPDATE ciudadanos SET foto_path = :p WHERE id_ciudadano = :i", p=f"perfiles/{idc}.jpg", i=idc)
            mock.borrados.clear()
            r = await c.post("/api/v1/publico/perfil/foto", headers=hv,
                             files={"archivo": ("smoke.jpg", jpeg_200px(), "image/jpeg")})
            fila = await q1("SELECT foto_path FROM ciudadanos WHERE id_ciudadano = :i", i=idc)
            check(r.status_code == 200 and fila["foto_path"] == f"{pref}perfiles/{idc}.jpg"
                  and any(p == f"perfiles/{idc}.jpg" for _, p in mock.borrados),
                  "foto_vecino_reemplaza_vieja", f"{r.status_code} {fila} {mock.borrados} {r.text[:200]}")
            await ejecutar("UPDATE ciudadanos SET foto_path = :p WHERE id_ciudadano = :i", p=f"perfiles/{idc}.jpg", i=idc)
            mock.borrados.clear()
            r = await c.delete("/api/v1/publico/perfil/foto", headers=hv)
            check(r.status_code == 200 and [p for _, p in mock.borrados] == [f"perfiles/{idc}.jpg"],
                  "foto_vecino_quitar_usa_ruta_guardada", f"{r.status_code} {mock.borrados}")
            await ejecutar("UPDATE ciudadanos SET foto_path = :p WHERE id_ciudadano = :i", p=vecino["foto_path"], i=idc)


def parte_vaciado() -> None:
    print("— vaciado")
    from app.services.municipios.vaciado import archivo_del_municipio
    check(archivo_del_municipio("m3/reclamos/1/a.jpg", 3), "vaciado_borra_su_carpeta")
    check(archivo_del_municipio("reclamos/1/a.jpg", 3), "vaciado_borra_formato_viejo")
    check(not archivo_del_municipio("m1/reclamos/1/a.jpg", 3), "vaciado_no_borra_prefijo_ajeno")
    check(not archivo_del_municipio("global/usuarios/1/avatar-a.png", 3), "vaciado_no_borra_global")
    check(not archivo_del_municipio("../m3/x", 3), "vaciado_no_borra_ruta_invalida")


async def parte_crons() -> None:
    print("— crons")
    import httpx
    from sqlalchemy import text

    from app.core.config import settings
    from app.core.sistema import SesionSistema
    from app.main import app
    from app.services.tramites import ciclo_vida as svc_ciclo

    settings.RESEND_API_KEY = ""  # MOCK: el dispatcher de encuestas no manda mails reales
    settings.DISPATCHER_TOKEN = settings.DISPATCHER_TOKEN or "smoke-f64"
    h = {"X-Dispatcher-Token": settings.DISPATCHER_TOKEN}
    async with SesionSistema() as s:
        operables = {r.id_municipio: r.nombre for r in (await s.execute(text(
            "SELECT id_municipio, nombre FROM municipios WHERE estado IN ('puesta_en_marcha','produccion','demo')"))).all()}

    def bien(j: dict) -> bool:
        ms = j.get("municipios") or []
        return ({m["id_municipio"]: m["nombre"] for m in ms} == operables and j.get("con_error") == []
                and all(m["estado"] in ("ok", "omitido") for m in ms))

    rutas = [("cron_encuestas", "/api/v1/admin/encuestas/dispatcher/ejecutar", {}),
             ("cron_tramites", "/api/v1/tramites/mantenimiento/ejecutar", {}),
             ("cron_integridad_dry_run", "/api/v1/usuarios/mantenimiento/integridad-cuentas", {"dry_run": "true"})]
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://smoke.local", timeout=300) as c:
        for nombre, ruta, params in rutas:
            r = await c.post(ruta, headers=h, params=params)
            j = r.json() if r.status_code == 200 else {}
            check(r.status_code == 200 and bien(j), nombre, f"{r.status_code} {str(j)[:300] or r.text[:300]}")

        original = svc_ciclo.procesar_desistimientos

        async def falla(*a, **k):
            # Como un error de la base: la primera línea dice qué pasó; las siguientes traen la consulta
            # y sus parámetros (datos de vecinos), que no pueden llegar al log público de Actions.
            raise RuntimeError("falla de prueba F6.4\n[SQL: UPDATE x]\n[parameters: ('vecino.f64@correo.com',)]")

        svc_ciclo.procesar_desistimientos = falla
        try:
            r = await c.post("/api/v1/tramites/mantenimiento/ejecutar", headers=h)
        finally:
            svc_ciclo.procesar_desistimientos = original
        j = r.json() if r.status_code == 200 else {}
        errores = [m for m in j.get("municipios", []) if m["estado"] == "error"]
        check(r.status_code == 200 and errores and all("desistimiento" in (m["error"] or "") for m in errores)
              and any(operables[errores[0]["id_municipio"]] in e for e in j.get("con_error", [])),
              "tramites_desistimiento_falla", f"{r.status_code} {str(j.get('municipios'))[:300]}")
        check(r.status_code == 200 and "vecino.f64@correo.com" not in r.text and "[SQL:" not in r.text
              and "falla de prueba F6.4" in r.text, "error_publico_sin_parametros", r.text[:400])

        from app.core.database import AsyncSessionLocal
        from app.core.municipio import por_cada_municipio

        async def revienta(id_m):
            raise RuntimeError("primera línea\n[parameters: ('vecino.f64@correo.com',)]")

        async with AsyncSessionLocal() as db:
            res = await por_cada_municipio(db, "smoke F6.4", revienta)
        textos = [v.get("error", "") for v in res.values()]
        check(textos and all(t == "RuntimeError: primera línea" for t in textos),
              "por_cada_municipio_error_sin_parametros", str(textos)[:300])


async def main() -> None:
    parte_rutas()
    parte_vaciado()
    await parte_subidas()
    await parte_crons()
    print(f"\n{OK} OK, {FAIL} FAIL")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    asyncio.run(main())
