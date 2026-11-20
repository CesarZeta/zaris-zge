# IT-01 F6.4 — Archivos con carpeta por municipio y crons con resultado por municipio: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** que todo archivo nuevo quede en la carpeta `m{id_municipio}/` de su bucket, y que el log de cada cron muestre el resultado de cada municipio y falle con el nombre del que dio error.

**Architecture:** dos funciones en `app/core/storage.py` (armar la ruta con el prefijo y leer el municipio de una ruta) que usan los seis lugares que hoy arman rutas. Las validaciones que comparan rutas aceptan el formato viejo (sin prefijo) y el nuevo, y el vaciado deja de borrar un archivo cuyo prefijo dice otro municipio. Para los crons, una función en `app/core/municipio.py` convierte el resultado de `por_cada_municipio` en una lista con nombre y estado, y un script de CI la imprime y hace fallar el paso.

**Tech Stack:** FastAPI, Supabase Storage (httpx, service_role), GitHub Actions (bash + python3 del runner).

**Spec:** [`PLAN_MULTI_MUNICIPIO_F6_DISENO.md`](PLAN_MULTI_MUNICIPIO_F6_DISENO.md) §4.5 y §4.6.

## Global Constraints

- Formato nuevo: **`m{id_municipio}/` + la ruta de hoy**. Ejemplos: `m1/reclamos/3480/<uuid>.jpg`, `m1/ot/3661/<uuid>.png`, `m1/tramites/2026/<expediente>/<uuid>.pdf`, `m1/usuarios/6/avatar-<uuid>.png`, `m1/perfiles/1613.jpg`, `m1/logo-<uuid>.png`. La exportación ya usa `m{id}/` y no cambia.
- **Los archivos existentes no se mueven** y sus rutas en la base no cambian. Todo lo que lee una ruta guardada la usa tal cual.
- El **super administrador** no tiene municipio (F3) y no se le asigna uno: su foto nueva va en la carpeta **`global/`** (`global/usuarios/{id}/avatar-<uuid>.<ext>`), así todo archivo nuevo tiene carpeta (decisión 2026-11-20: César propuso asignarle San Andrés para que no hubiera «uno con y otro sin»; Claude propuso `global/`, que logra lo mismo sin tocar el modelo de cuentas). El vaciado nunca borra nada de `global/`.
- Validaciones que comparan rutas (foto del usuario en `PUT /auth/me/foto` y en el vaciado) aceptan los dos formatos, y el prefijo, si está, tiene que ser el del municipio de la cuenta.
- Sin cambios en los frontends: todos reciben la ruta del backend (verificado: `web-app`, `zaris-vecinos` y `zaris-agentes` solo la tipan).
- Smokes con Storage simulado (en local las credenciales de Storage son las de prod; memoria `reference_storage_local_apunta_a_prod`): los servicios llaman `storage.<función>` por el módulo.
- Los workflows siguen sin `jq`; el script de CI usa el `python3` del runner.
- Crons alcanzados: encuestas, trámites e integridad de cuentas, los tres que recorren municipios con `por_cada_municipio`. Quedan como están el de datos demo, que escribe en un solo municipio (el `demo`) y ya imprime su resultado, y el de mantenimiento de municipios, que purga exportaciones vencidas de todos a la vez.

## Review Focus

1. **Foto del vecino que ya tenía una en el formato viejo** (`perfiles/{id}.jpg`): al subir otra, la vieja tiene que borrarse (si no queda huérfana para siempre), y al quitarla se borra **la ruta guardada**, no una recalculada. → Task 2, casos `foto_vecino_reemplaza_vieja` y `foto_vecino_quitar_usa_ruta_guardada`.
2. **Una ruta guardada con el prefijo de otro municipio** (copiada por el clonador, o puesta a mano): el vaciado no la borra. → Task 3, caso `vaciado_no_borra_prefijo_ajeno`.
3. **Foto de usuario con el prefijo de otro municipio** en `PUT /auth/me/foto`: 422 como hoy con una ruta ajena. → Task 2, caso `foto_usuario_prefijo_ajeno_422`.
4. **Un municipio cuyo cron devuelve un error interno no fatal** (desistimiento de trámites, que hoy se traga): tiene que aparecer como municipio con error en el log. → Task 4, caso `tramites_desistimiento_falla`.
5. **Respuesta del cron sin `municipios`** (backend viejo durante el deploy): el script imprime el cuerpo y no falla por eso, para no romper el cron mientras Railway publica. → Task 4, caso `respuesta_sin_municipios`.

---

## Resultado (2026-11-20)

- **En prod desde `58a5140`**, con la barrera prendida. Prueba real: un adjunto a REC-SAN-2026-003478 quedó en `m1/reclamos/3480/<uuid>.png`, se descargó idéntico y su baja lo borró de Storage. El cron de encuestas, disparado a mano, imprimió `OK Municipalidad de San Andrés (1)` y quedó en verde.
- **Local:** `smoke_archivos_municipio.py` 41/41 con `DB_BARRERA` en `false` y en `true`; los 21 smokes in-process en verde con la barrera; `tools/ci/test_resumen_cron.py` 4/4.
- **Revisión final** (revisor aparte): sin críticos. Un importante corregido: el texto de un error de la base trae la consulta y sus parámetros, y el log de Actions es público. `error_publico` deja solo el tipo y la primera línea; el detalle sigue en el log del servidor.
- **Menores diferidos:** `resumen_cron.py` decide por `con_error` y no por el estado de cada municipio · la foto vieja del vecino se borra sin comprobar su carpeta (solo la escribe el servidor) · `ruta_valida` no rechaza otros `%`-encodings · la parte «crons» del smoke corre el mantenimiento real sobre los datos locales.
- **Para César:** una purga de trámites con errores o encuestas que no se pudieron mandar siguen mostrando el municipio como OK (son resultados por ítem). Si querés que pongan el cron en rojo, es una condición más en `resumen_municipios`.

### Task 1: Rutas por municipio en `storage`

**Files:**
- Modify: `backend/app/core/storage.py`
- Create: `backend/smoke_archivos_municipio.py` (crece en las Tasks 2 y 3)

**Interfaces:**
- Produces:
  - `ruta_de_municipio(id_municipio: int | None, ruta: str) -> str`: `f"m{id}/{ruta}"`, o `f"global/{ruta}"` si `id_municipio` es `None`. `ValueError` si `ruta` no pasa `ruta_valida` o ya empieza con `m<dígitos>/` o `global/`.
  - `municipio_de_ruta(ruta: str) -> int | None`: el `id` de un prefijo `m(\d{1,9})/`, o `None` si no tiene (también para `global/`).
  - `es_avatar_de(ruta: str, id_usuario: int, id_municipio: int | None) -> bool`: `ruta_valida` y `fullmatch` de `(m{id_municipio}/)?usuarios/{id_usuario}/avatar-[0-9a-f-]+\.(png|jpe?g)`; con `id_municipio=None`, `(global/)?usuarios/…` (la cuenta del super).

- [ ] **Step 1: test** — `smoke_archivos_municipio.py`, parte «rutas» (sin base ni red):
  - `ruta_de_municipio(1, "reclamos/5/a.jpg") == "m1/reclamos/5/a.jpg"`; `ruta_de_municipio(None, "usuarios/102/avatar-x.png") == "global/usuarios/102/avatar-x.png"`; `ValueError` con `"../x"`, con `"m2/reclamos/5/a.jpg"` y con `"global/a"`.
  - `municipio_de_ruta("m12/ot/1/a.png") == 12`; `municipio_de_ruta("reclamos/1/a.png") is None`; `municipio_de_ruta("mx/a") is None`.
  - `es_avatar_de("usuarios/6/avatar-ab12.png", 6, 1)` y `es_avatar_de("m1/usuarios/6/avatar-ab12.png", 6, 1)` son `True`; `es_avatar_de("m2/usuarios/6/avatar-ab12.png", 6, 1)`, `es_avatar_de("m1/usuarios/7/avatar-ab12.png", 6, 1)` y `es_avatar_de("m1/usuarios/102/avatar-ab.png", 102, None)` son `False`; `es_avatar_de("global/usuarios/102/avatar-ab.png", 102, None)` es `True`.
- [ ] **Step 2:** correrlo → falla (las funciones no existen). `cd backend; $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_archivos_municipio.py`
- [ ] **Step 3:** implementar las tres funciones en `storage.py`.
- [ ] **Step 4:** correrlo → la parte «rutas» en verde.
- [ ] **Step 5:** commit `feat(storage): rutas con carpeta por municipio (IT-01 F6.4)`.

### Task 2: Los seis lugares que arman rutas

**Files:**
- Modify: `backend/app/api/routes/reclamo_adjuntos.py:91`, `publico_reclamos_adjuntos.py:109` (municipio: `current["id_municipio"]`), `ot_adjuntos.py:116`, `config_identidad.py:212` (`m{id}/logo-<uuid>.<ext>`), `auth.py:508` y `:531`, `publico_perfil.py:54`, `:317`, `:340`
- Modify: `backend/app/services/tramites/documentos.py` — `guardar_archivo_mock(file, numero_expediente, anio, nombre_logico, id_municipio: int)`; `backend/app/api/routes/tramites.py:2085` le pasa el `id_municipio` del handler
- Test: `backend/smoke_archivos_municipio.py`, parte «subidas» (in-process con `ASGITransport`, Storage simulado: `crear_signed_upload_url`, `subir_objeto`, `borrar_objeto`, `crear_signed_download_url`; patrón `_StorageMock` de `smoke_alta_municipio.py`)

**Interfaces:**
- Consumes: `storage.ruta_de_municipio`, `storage.es_avatar_de` (Task 1).
- `publico_perfil`: `_foto_path(id_municipio: int, id_ciudadano: int) -> str` = `m{mun}/perfiles/{id}.jpg`. Al subir: si la ruta guardada es otra, se borra después del UPDATE (best-effort, como el borrado de hoy). Al quitar: se borra `ciudadanos.foto_path` leído de la base.

- [ ] **Step 1: test** — con un administrador, un vecino y una OT/reclamo/trámite del municipio base de `zaris_dev` (buscarlos por consulta, no ids fijos):
  - `subida_adjunto_reclamo`, `subida_adjunto_reclamo_vecino`, `subida_adjunto_ot`, `subida_documento_tramite`, `subida_logo`, `subida_foto_usuario`: la `path` devuelta (o la guardada) empieza con `m{id}/`.
  - `subida_foto_super`: con el super local (`super.admin@prueba-aislamiento.com.ar`, lo crea `smoke_super_admin.py`) la ruta empieza con `global/usuarios/`.
  - `foto_usuario_formato_viejo_ok`: `PUT /auth/me/foto` con la URL pública de `usuarios/{id}/avatar-<uuid>.png` → 200.
  - `foto_usuario_prefijo_ajeno_422`: con `m{otro}/usuarios/{id}/avatar-<uuid>.png` → 422.
  - `foto_vecino_reemplaza_vieja`: con `foto_path = 'perfiles/{id}.jpg'` puesto por SQL, subir una foto → `foto_path` queda `m{id_mun}/perfiles/{id}.jpg` y el mock registra el borrado de `perfiles/{id}.jpg`.
  - `foto_vecino_quitar_usa_ruta_guardada`: con `foto_path` viejo, `DELETE /publico/perfil/foto` borra exactamente esa ruta.
  - Al final, devolver a cada fila tocada su valor original (foto del usuario, foto del vecino, logo).
- [ ] **Step 2:** correrlo → fallan los casos de rutas nuevas.
- [ ] **Step 3:** cambiar los seis lugares.
- [ ] **Step 4:** correrlo con `DB_BARRERA=false` y con `true` → todo en verde. Correr también `smoke_publico_adjuntos.py` (local), que sube y descarga un adjunto real del vecino, y `smoke_tramites_ciclo_vida.py`.
- [ ] **Step 5:** commit `feat(storage): los archivos nuevos van en la carpeta del municipio (IT-01 F6.4)`.

### Task 3: Vaciado con los dos formatos

**Files:**
- Modify: `backend/app/services/municipios/vaciado.py` (`_archivos`, línea ~240)
- Test: `backend/smoke_archivos_municipio.py`, parte «vaciado»

**Interfaces:**
- Consumes: `storage.es_avatar_de`, `storage.municipio_de_ruta` (Task 1).
- Produces: `archivo_del_municipio(ruta: str, id_municipio: int) -> bool` en `vaciado.py`: `ruta_valida`, no empieza con `global/` y (`municipio_de_ruta(ruta)` es `None` o igual a `id_municipio`). `_archivos` recibe `id_municipio` y filtra con ella; la foto del usuario usa `es_avatar_de(ruta, id_usuario, id_municipio)`.

- [ ] **Step 1: test**: `archivo_del_municipio("m3/reclamos/1/a.jpg", 3)`, `archivo_del_municipio("reclamos/1/a.jpg", 3)` → `True`; `vaciado_no_borra_prefijo_ajeno`: `archivo_del_municipio("m1/reclamos/1/a.jpg", 3)` y `archivo_del_municipio("global/usuarios/1/avatar-a.png", 3)` → `False`.
- [ ] **Step 2:** correrlo → falla.
- [ ] **Step 3:** implementar y pasar `id_municipio` desde `vaciar` a `_archivos`.
- [ ] **Step 4:** correrlo, y `smoke_alta_municipio.py` (cubre el vaciado completo con Storage simulado) con `DB_BARRERA=true` → verde.
- [ ] **Step 5:** commit `feat(vaciado): archivos en los dos formatos y nunca de otro municipio (IT-01 F6.4)`.

### Task 4: Resultado por municipio en los crons

**Files:**
- Modify: `backend/app/core/municipio.py` (nueva función), `backend/app/api/routes/encuestas_admin.py:~893`, `tramites_mantenimiento.py:~94`, `usuarios_mantenimiento.py:~72` y `~87`
- Create: `tools/ci/resumen_cron.py`, `tools/ci/test_resumen_cron.py`
- Modify: `.github/workflows/encuestas-dispatcher.yml`, `tramites-mantenimiento.yml`, `integridad-cuentas.yml` (paso `actions/checkout@v4` con `sparse-checkout: tools/ci` y, después del `cat "$BODY"`, `python3 tools/ci/resumen_cron.py "$BODY"`)
- Test: `backend/smoke_archivos_municipio.py`, parte «crons» (in-process, con `X-Dispatcher-Token`)

**Interfaces:**
- Produces:
  - `async def resumen_municipios(db: AsyncSession, por_municipio: dict[int, Any]) -> dict`: `{"municipios": [{"id_municipio": int, "nombre": str, "estado": "ok" | "omitido" | "error", "error": str | None}], "con_error": ["<nombre> (<id>): <error>"]}`, ordenado por id. `"error"` si el resultado es un dict con clave `error` verdadera; `"omitido"` si trae `omitido`; si no, `"ok"`. El nombre sale de `municipios.nombre`.
  - Las tres respuestas suman `**await resumen_municipios(db, por_municipio)` y conservan todo lo de hoy (incluido `por_municipio`). En integridad, también en el dry-run.
  - Trámites: si el desistimiento falla, el resultado del municipio lleva además `"error": "desistimiento: <tipo>: <mensaje>"` (sigue best-effort: lo demás de ese municipio se conserva).
  - `tools/ci/resumen_cron.py <archivo.json>`: imprime una línea por municipio (`OK      San Andrés (1)`, `OMITIDO …`, `ERROR   … — <error>`), y si `con_error` no está vacío imprime `::error::Municipios con error: <lista>` y sale con 1. Sin `municipios` en el JSON: imprime «la respuesta no trae el detalle por municipio (backend anterior a F6.4)» y sale con 0.

- [ ] **Step 1: test** — `tools/ci/test_resumen_cron.py` (sin dependencias; corre con `python tools/ci/test_resumen_cron.py`): con JSON armados en el test, `todos_ok` → exit 0 y una línea `OK` por municipio; `uno_con_error` → exit 1 y el nombre en la línea `::error::`; `respuesta_sin_municipios` → exit 0. Parte «crons» del smoke: los tres endpoints responden 200 con `municipios` (uno por municipio operable de `zaris_dev`, con nombre) y `con_error == []`; `tramites_desistimiento_falla`: con `procesar_desistimientos` reemplazado por una función que lanza, el municipio queda con `estado == "error"` y su nombre en `con_error`.
- [ ] **Step 2:** correr los dos → fallan.
- [ ] **Step 3:** implementar `resumen_municipios`, sumarla a los tres endpoints, el error del desistimiento, el script y los tres workflows.
- [ ] **Step 4:** correr los dos → verde. `smoke_barrera.py` y `tools/barrido_sistema.py` siguen en verde.
- [ ] **Step 5:** commit `feat(crons): resultado por municipio en el log y falla con el nombre (IT-01 F6.4)`.

### Task 5: Corrida completa, prod y documentación

- [ ] **Step 1:** los 30 smokes en local con `DB_BARRERA=true` (como en F6.2); los que estaban en rojo por datos locales siguen igual (`smoke_publico_turnos.py`, ESTADO).
- [ ] **Step 2:** push a `main`; esperar que `/api/health` muestre el commit nuevo; en `/openapi.json` no hay rutas nuevas, así que el marcador es el `commit`.
- [ ] **Step 3: prod** — subir un adjunto a un reclamo de prueba (REC-SAN-2026-003478) con `operadorcom@` por API y comprobar en `reclamo_adjuntos` que la ruta empieza con `m1/` y que la URL firmada descarga el archivo; después darlo de baja (`DELETE`). Disparar el workflow de encuestas a mano: el log muestra `OK San Andrés (1)` (y los demás municipios operables) y el paso queda en verde.
- [ ] **Step 4:** documentación: CLAUDE.md §10 (regla: «todo archivo nuevo se guarda con `storage.ruta_de_municipio`; una ruta nueva de Storage armada a mano es un error»), skill `modulo-reclamos` (formato de ruta de adjuntos), ESTADO y este plan (resultado). Commit y push.
