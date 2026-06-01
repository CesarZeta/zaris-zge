# seed-table

Inserta datos demo en tablas vacías usando `backend/seed_demo.py`. El script es idempotente — saltea tablas que ya tienen datos.

## Uso

```
/seed-table [nombre_tabla | all]
```

Ejemplos:
- `/seed-table` — corre el seed completo contra el entorno local
- `/seed-table estado_reclamo` — inserta solo los datos de esa tabla
- `/seed-table all` — equivalente a correr `seed_demo.py` completo

## Tablas disponibles en seed_demo.py

`estado_reclamo`, `areas`, `lugares_atencion`, `agenda_clase`, `agenda_feriado`, `servicios`, `actividades`, `tipo_representacion`, `nacionalidades`

> Nota: `reclamos_area` y `reclamos_subarea` fueron eliminadas en migración 20 (CLAUDE.md §15). Reclamos usa las tablas generales `area` / `subarea`.

## Pasos

1. Verificar que el backend local está corriendo en `http://127.0.0.1:8000`:
   ```
   GET http://127.0.0.1:8000/api/health
   ```
   Si no responde, iniciar con:
   ```powershell
   cd backend
   $env:ENV_FILE=".env.local"; uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

2. Si el argumento es una tabla específica, extraer solo ese bloque del `SEED_DATA` en `seed_demo.py` y ejecutarlo.

3. Si es `all` o sin argumento:
   ```powershell
   cd backend
   python seed_demo.py
   ```

4. Reportar cuántos registros se insertaron por tabla y cuáles se saltearon (ya tenían datos).

## Notas

- El script hace login automáticamente. En local el admin nivel 1 es `ciudadanovl@municipio.gob.ar` / `123456` (CLAUDE.md §32 quirk 10). Si el seed_demo.py todavía hardcodea `administrativo@…` y falla 401, actualizar el script con el username real consultando `SELECT email FROM usuarios WHERE nivel_acceso=1 AND activo` en `zaris_dev`.
- Si el login falla, verificar que `seed_auth.py` fue ejecutado primero.
- Para correr seed en PROD, cambiar `BASE` y `LOGIN_URL` en `seed_demo.py` a la URL de Railway — confirmar con el usuario antes de hacerlo.
- Nunca correr seed en prod sin confirmación explícita.
