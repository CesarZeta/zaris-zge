# IT-01 F6.5 — Restauración de una exportación: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** que la exportación de un municipio (el zip de F4+F5) se pueda levantar en una base Postgres vacía y el backend funcione contra ella con los datos de ese municipio.

**Architecture:** herramienta fuera de la aplicación, `tools/restaurar_exportacion.py`, con dos comandos. `volcar` toma de la base de ZARIS en uso la estructura (`pg_dump` en dos secciones: antes y después de los datos) y las tablas globales. `restaurar` crea la estructura sin restricciones, carga globales y zip con `json_populate_recordset` y recién después aplica restricciones, índices, triggers y políticas: las FK se validan al crearse y ningún trigger recalcula nada durante la carga. Al final ajusta las secuencias, aplica los permisos de la barrera (migración 138) y compara los conteos con el zip.

**Tech Stack:** Python 3 + asyncpg, `pg_dump`/`psql` 17.

**Spec:** [`PLAN_MULTI_MUNICIPIO_F6_DISENO.md`](PLAN_MULTI_MUNICIPIO_F6_DISENO.md) §4.7 y §5.

## Prueba previa (2026-11-21)

Con el zip de San Andrés de `zaris_dev` (68.081 filas, 84 tablas) en una base nueva:
- Estructura entera antes de los datos: falla `tipo_prestacion` por un CHECK `NOT VALID` (filas viejas que no lo cumplen). `pg_dump` deja esos CHECK en la sección *post-data* → cargar entre las dos secciones lo resuelve.
- `usuarios.password_hash` es NOT NULL y no viaja en el zip. Las suscripciones push, los códigos de emergencia y las invitaciones no se pueden cargar sin su secreto (NOT NULL), y sin él no sirven.
- Las filas creadas por el super administrador apuntan a una cuenta que no viaja (no tiene municipio). En `zaris_dev` además hay 23 cuentas borradas a las que todavía apuntan `usuario_login_log` y `usuario_modulos` (residuo de smokes).
- Con esos tres manejos: carga sin errores y el *post-data* entero aplica (`rc 0`), o sea, todas las FK válidas.
- Prod (relevado por MCP): PostgreSQL 17.6, ninguna función ni default de `public` usa extensiones, las políticas solo nombran a `zaris_app`, 40 tablas `_backup_*`.

## Global Constraints

- **[Claude] Globales desde la base en uso.** El zip trae solo las tablas de municipio; las 19 `global` (la fila de `municipios`, geografía, módulos, estados) y los parámetros globales (`configuracion_general` con municipio NULL) los saca `volcar` de la base de ZARIS en el mismo formato JSON del zip. De `municipios` se restaura solo la fila del municipio del zip.
- **Sin secretos, como la exportación:** cada cuenta interna recibe el mismo hash bcrypt de una clave al azar que se descarta (nadie entra hasta restablecerla, y el login responde 401 normal); las del vecino quedan sin clave (`ciudadano_credencial.password_hash` admite NULL). No se cargan `ciudadano_push_subscription`, `usuario_push_subscription`, `usuario_codigo_emergencia` ni `usuario_invitacion`; el informe dice cuántas filas quedaron afuera. El segundo factor queda sin secreto: los niveles 0/1 vuelven a vincular la app.
- **[Claude] Cuenta referenciada que no vino** (el super, o una borrada): se crea inactiva, nivel 0, sin municipio, sin email, `username` `no-exportada-<id>`, para no perder el registro de quién hizo qué. El informe las cuenta.
- **Base destino vacía**: si `public` tiene alguna tabla, la herramienta no toca nada y termina con error.
- `_backup_*` no se vuelcan.
- La herramienta crea `zaris_app` sin login si el servidor destino no lo tiene (las políticas lo nombran); darle clave es de quien opera ese servidor.
- Los archivos de Storage no están en la exportación: las rutas guardadas quedan, el binario no (fuera de alcance, el diseño no lo pide).
- Ninguna clave en la línea de comandos ni en la salida: las conexiones salen de variables de entorno (`ORIGEN_URL`, `DESTINO_URL`) y se imprimen sin clave.

## Review Focus

1. **Conteos**: cada tabla del zip tiene en la base restaurada las mismas filas que el zip, salvo las cuatro sin secreto (reportadas). → Task 2, `conteos_iguales`.
2. **Integridad**: el *post-data* aplica sin error (todas las FK válidas). → Task 2, `post_data_ok`.
3. **Secuencias**: un INSERT nuevo en `reclamos` no choca con un id restaurado. → Task 2, `secuencias`.
4. **Base no vacía**: `restaurar` sobre una base con tablas termina con error y no la toca. → Task 2, `destino_no_vacio`.
5. **Ninguna clave de cuenta** en la base restaurada coincide con la de origen. → Task 2, `sin_claves`.

---

### Task 1: Herramienta

**Files:**
- Create: `tools/restaurar_exportacion.py`
- Create: `tools/test_restaurar_exportacion.py` (funciones puras, sin base)

**Interfaces:**
- `python tools/restaurar_exportacion.py volcar --salida <dir>` (origen en `ORIGEN_URL`): escribe `pre-data.sql`, `post-data.sql`, `globales.zip`, `manifiesto.json`.
- `python tools/restaurar_exportacion.py restaurar --base <dir> --zip <export.zip>` (destino en `DESTINO_URL`): imprime el informe en JSON y termina con código 1 si algo no cierra.
- Puras: `preparar_filas(tabla, filas, hash_cuentas)`, `referencias_a_usuarios(post_data_sql) -> [(tabla, columna)]`, `municipio_del_zip(contenido) -> int` (error si hay más de uno).

- [ ] **Step 1:** test de las funciones puras → falla.
- [ ] **Step 2:** implementar → verde.
- [ ] **Step 3:** commit `feat(tools): restaurar la exportacion de un municipio en una base vacia (IT-01 F6.5)`.

### Task 2: Prueba en local

**Files:**
- Create: `backend/smoke_restauracion.py`

- [ ] **Step 1:** el smoke arma el zip de San Andrés con `armar_zip` (el código de la exportación), corre `volcar` contra `zaris_dev` y `restaurar` en `zaris_restaurada_smoke` (la crea y la borra), y verifica los cinco puntos del Review Focus.
- [ ] **Step 2:** backend en proceso contra la base restaurada (`POSTGRES_DB=zaris_restaurada_smoke`), con `DB_BARRERA` en `false` y en `true`: una cuenta administradora con clave puesta por el smoke entra, `GET /dashboard/resumen` y `GET /reclamos` traen lo mismo que en `zaris_dev`.
- [ ] **Step 3:** commit `test(restauracion): San Andres restaurado en una base vacia (IT-01 F6.5)`.

### Task 3: Prueba con la exportación de prod

- [ ] **Step 1:** César pide la exportación de San Andrés en Municipios → ficha → Exportación y la descarga (el super, con segundo factor).
- [ ] **Step 2:** `volcar` contra prod (pooler, conexión directa) y `restaurar` en una base local nueva; informe con conteos iguales.
- [ ] **Step 3:** backend local contra esa base, inicio de San Andrés en el navegador.
- [ ] **Step 4:** borrar la base y los archivos (datos reales, no quedan en la máquina más que lo necesario).

---

## Resultado (2026-11-21)

- **Tasks 1 y 2 hechas** (`e0f7562`, `bd88668`): `tools/test_restaurar_exportacion.py` 9/9 y `backend/smoke_restauracion.py` 18/18. San Andrés de `zaris_dev` (68.081 filas, 84 tablas) se restaura en 7 s con los conteos iguales al zip (80 tablas, 66.506 filas, más 1.575 sin secreto que quedan afuera a propósito), el post-data entero (563 FK válidas), 95 secuencias y la barrera. El backend contra la base restaurada da el mismo inicio y el mismo listado de reclamos que `zaris_dev`, con la barrera apagada y prendida.
- **Task 3, parte hecha:** `volcar` contra prod (pooler, solo lectura) y la estructura de prod aplicada a un Postgres 17 vacío: 103 tablas, 104 políticas, 98 triggers y 563 FK, sin errores. Los archivos de prod se borraron de la máquina.
- **Task 3, falta:** la restauración con la exportación real de San Andrés. Armar el zip desde esta máquina contra prod quedó bloqueado por el control de permisos (trae datos de vecinos); va por el camino del producto: el super lo pide y lo descarga desde la ficha del municipio → «Exportaciones» → «Exportar ahora» → «Descargar».
