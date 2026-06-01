# backup-prod

Hace un **backup completo a demanda** de la base de datos de **producción** (Supabase) a un archivo `.sql` fechado en el disco local. Es la red de seguridad de los datos reales — el proyecto está en plan **Free de Supabase, que NO tiene backups automáticos gestionados** (verificado 2026-05-20).

> **Por qué existe:** local (`zaris_dev`) NO es backup de prod — son DBs separadas con datos divergentes (IDs distintos, filas distintas). El código está en GitHub; los datos NO. Este skill es el único respaldo de datos hasta que se suba a Supabase Pro.

## Uso

```
/backup-prod
```

Sin argumentos. Genera `backups/zaris_prod_<YYYY-MM-DD_HHmm>.sql`.

## Qué NO hace

- No sube nada a ningún lado (el dump queda en tu disco).
- No toca prod (solo lectura — `pg_dump`).
- `backups/` está en `.gitignore` — los dumps tienen datos reales del municipio y **nunca** deben ir al repo (es público, §6).

## Pasos

### 1. Conexión de prod

`backend/.env` ya apunta a prod (`POSTGRES_SERVER=db.lshfwsscvfsklrmbvkwl.supabase.co`). Leer de ahí: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_SERVER`, `POSTGRES_PORT`, `POSTGRES_DB`.

> **Verificar que `.env` apunta a prod, no a local.** Si `POSTGRES_SERVER` es `127.0.0.1`, ESE es el `.env.local` de desarrollo — abortar, estarías backupeando tu copia local en vez de prod.

### 2. Carpeta destino

Crear `backups/` en la raíz del repo si no existe (ya gitignored).

### 3. Ejecutar pg_dump (PostgreSQL 17 — matchea prod 17.6)

Desde la tool **PowerShell** (no Bash — el path con espacios y `$env:` son PS):

```powershell
# Leer credenciales de backend/.env (parsear el archivo)
$envFile = "c:\Users\Cesar\Documents\ZARIS\Desarrollo\ZGE\backend\.env"
$cfg = @{}
Get-Content $envFile | ForEach-Object {
  if ($_ -match '^\s*([A-Z_]+)\s*=\s*(.*)$') { $cfg[$matches[1]] = $matches[2].Trim('"').Trim() }
}
if ($cfg.POSTGRES_SERVER -eq '127.0.0.1') { throw "ABORTAR: .env apunta a LOCAL, no prod" }

$ts = Get-Date -Format "yyyy-MM-dd_HHmm"
$out = "c:\Users\Cesar\Documents\ZARIS\Desarrollo\ZGE\backups\zaris_prod_$ts.sql"
$env:PGPASSWORD = $cfg.POSTGRES_PASSWORD

& "C:\Program Files\PostgreSQL\17\bin\pg_dump.exe" `
  --host=$($cfg.POSTGRES_SERVER) --port=$($cfg.POSTGRES_PORT) `
  --username=$($cfg.POSTGRES_USER) --dbname=$($cfg.POSTGRES_DB) `
  --no-owner --no-acl --clean --if-exists `
  --file=$out
$env:PGPASSWORD = $null

if (Test-Path $out) {
  $kb = [math]::Round((Get-Item $out).Length / 1KB, 1)
  "OK -> $out ($kb KB)"
} else { "FALLO: no se genero el archivo" }
```

Flags:
- `--no-owner --no-acl`: portabilidad (el dump se puede restaurar en cualquier DB sin depender de roles de Supabase).
- `--clean --if-exists`: el dump incluye `DROP ... IF EXISTS` antes de cada `CREATE`, así se puede re-aplicar sobre una DB existente sin chocar.
- Esquema **+ datos** (sin `--schema-only` ni `--data-only` = dump completo).

### 4. Quirk de conexión — host directo IPv6

`db.<ref>.supabase.co:5432` resuelve a **IPv6** en muchos casos. Si `pg_dump` falla con `could not translate host name` o `Network is unreachable`:

- **Opción A — pooler IPv4** (más confiable): usar host `aws-0-us-east-1.pooler.supabase.com`, puerto `5432` (session mode), usuario `postgres.lshfwsscvfsklrmbvkwl` (el ref va pegado al user en el pooler). El password es el mismo. La connection string exacta está en **Supabase → Settings → Database → Connection string → modo "Session"** — pedírsela al usuario si el host directo falla.
- **Opción B**: si la red local tiene IPv6, el host directo funciona sin cambios.

Probar primero el host de `.env` (directo). Si falla por DNS/red, caer al pooler.

### 5. Verificar el dump

- `Test-Path` + tamaño > 0 (un dump de ZARIS con datos ronda **varios MB**; si pesa < 50 KB, algo salió mal — probablemente solo trajo el esquema o falló a mitad).
- Opcional: `Select-String -Path $out -Pattern "PostgreSQL database dump" -List` confirma cabecera válida, y `COPY public.ciudadanos` confirma que trajo datos.

### 6. Reportar

Path del archivo, tamaño, y fecha. Recordarle al usuario que el dump vive solo en su disco (conviene copiarlo a otro lado: nube personal, disco externo).

## Restaurar (referencia, NO parte del flujo normal)

Para restaurar este dump en una DB nueva/vacía:

```powershell
$env:PGPASSWORD = "<password>"
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" --host=<host> --port=5432 --username=postgres --dbname=postgres --file="<ruta_al_dump>.sql"
```

⚠️ El dump tiene `--clean --if-exists`: **dropea las tablas antes de recrearlas**. NUNCA restaurar sobre prod sin estar 100% seguro — es destructivo. Para recuperación real de prod, primero clonar a una DB de staging y validar ahí.

## Cadencia sugerida

A demanda antes de cualquier operación riesgosa en prod (migración destructiva, re-seed masivo), y como rutina semanal mientras el proyecto siga en plan Free. Si pasa a Supabase Pro, los backups diarios automáticos cubren el caso y este skill queda como complemento puntual.
