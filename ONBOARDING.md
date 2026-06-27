# Onboarding — ZARIS ZGE

Guía de arranque local para un desarrollador nuevo. Las reglas de desarrollo
viven en [`CLAUDE.md`](CLAUDE.md); esto es solo cómo dejar el entorno corriendo.

> **Arquitectura en 30 segundos.** Un único **shell vanilla** (`index.html` +
> `frontend/`) es el contenedor del producto. Carga módulos en un `<iframe>`:
> algunos son HTML/JS vanilla (`frontend/*.html`), otros son un build React
> (`web-app/`, publicado en `web-app/dist/`). El backend es FastAPI
> (`backend/`). La **App Vecinos** (PWA del ciudadano) vive en un **repo
> separado**: `CesarZeta/zaris-vecinos`.

---

## 1. Requisitos

- **Python 3.10+** (el backend usa SQLAlchemy async + asyncpg).
- **Node 18+ y pnpm** (para `web-app/`).
- **PostgreSQL 14+** local (base `zaris_dev`).
- **Git Bash** o equivalente (los hooks corren en sh).

## 2. Clonar e instalar

```bash
git clone https://github.com/CesarZeta/zaris-zge.git
cd zaris-zge

# Backend
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows
pip install -r requirements.txt
cp .env.example .env.local        # editar con tus valores locales
cd ..

# Frontend React
cd web-app
pnpm install
cd ..
```

## 3. Variables de entorno

- **Backend:** `backend/.env.local` (a partir de `backend/.env.example`).
  Para local solo necesitás la DB; el resto (Supabase, Resend, VAPID) puede
  quedar vacío — el backend cae a modo MOCK donde corresponde.
- **Web-app:** `web-app/.env.development` ya apunta a `127.0.0.1:8000`. No tocar.
- **Los valores reales de producción viven en Railway**, no en el repo. Nadie
  los comparte por chat. Si necesitás un secreto de prod para una tarea
  puntual, pedilo al admin del proyecto.

## 4. Base de datos local

La forma soportada de arrancar la DB local es **restaurar un dump** que te pasa
el admin del proyecto (por fuera del repo — un `.sql` o `.dump` no se commitea).
Las migraciones de `backend/migrations/` (20→91) son **incrementales**: asumen un
schema base previo, así que **no** sirven para construir la base desde cero por
sí solas. Sirven para entender qué cambió y para replicar en prod, no como
bootstrap.

```bash
# Crear la base (una vez)
psql -U postgres -c "CREATE DATABASE zaris_dev;"

# Restaurar el dump que te pasó el admin:
#   formato .sql (texto):
psql -U postgres -d zaris_dev -f zaris_dev_dump.sql
#   formato .dump (custom, comprimido):
# pg_restore -U postgres -d zaris_dev --no-owner zaris_dev_dump.dump

# Sembrar/asegurar auth (passwords dev = 123456):
cd backend
ENV_FILE=".env.local" python seed_auth.py
# Datos demo opcionales (idempotente):
ENV_FILE=".env.local" python seed_demo.py
```

> **Para el admin — generar el dump que se le pasa al colaborador** (desde la
> raíz, con tu `zaris_dev` poblada). El dump NO va al repo; se comparte por un
> canal privado:
> ```bash
> pg_dump -U postgres -d zaris_dev --no-owner --no-privileges -f zaris_dev_dump.sql
> ```
> Si querés excluir datos sensibles de prueba antes de compartir, hacelo sobre
> una copia. Para la última migración aplicada, ver CLAUDE.md §21 (hoy: **91**).

## 5. Levantar los tres procesos

Cada uno en su terminal (ver URLs completas en CLAUDE.md §6):

```bash
# A) Backend  -> http://127.0.0.1:8000  (Swagger en /docs)
cd backend
ENV_FILE=".env.local" uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# B) Shell del producto + módulos vanilla -> http://localhost:8080
python -m http.server 8080            # desde la raíz del repo

# C) Shell React standalone (solo para iterar módulos React) -> http://localhost:5173
cd web-app && pnpm dev
```

- **Para ver el producto real** (shell vanilla cargando módulos React en iframe):
  usá `http://localhost:8080/index.html`. El `localhost:5173` es solo andamiaje
  de desarrollo (su sidebar/topbar NO son los de producción — CLAUDE.md §4).
- Login dev: `<usuario>@municipio.gob.ar` / `123456`.

## 6. Hook de typecheck (obligatorio)

```bash
bash tools/hooks/install.sh     # idempotente
```

Corre `tsc -b --noEmit` en cada commit que toque `web-app/**`. Si el commit
solo toca `backend/` o `frontend/`, sale en 0 sin penalizar. Para correrlo a
mano: `cd web-app && pnpm typecheck`.

## 7. Build del bundle React (antes de publicar)

El shell React se publica versionado en `web-app/dist/`. **CI lo rebuildea
solo** al pushear cambios en `web-app/**` (workflow `deploy-web-app.yml`). No
hace falta commitear el `dist` a mano salvo casos puntuales — y si lo hacés,
buildeá en modo prod (sin `VITE_API_BASE` apuntando a `127.0.0.1`). Detalles y
quirks de Windows en la skill `win-quirks`.

## 8. App Vecinos (PWA) — repo separado

La PWA del ciudadano NO está acá. Está en `CesarZeta/zaris-vecinos` (deploy en
Vercel, `vecinos.zaris.com.ar`). Tiene su propio README. **Consume este backend**
(`/api/v1/publico/*`), así que para trabajar la PWA contra local hay que tener
el backend de `zaris-zge` corriendo y `APP_VECINOS_FRONTEND_URL` apuntando a la
PWA local (`http://localhost:5174`).

## 9. Antes de pedir review

- [ ] `pnpm typecheck` pasa (si tocaste `web-app/`).
- [ ] Verificaste el cambio **navegando en `localhost:8080`** (no solo leyendo
      el código — CLAUDE.md §41).
- [ ] No agregaste ningún `.env` con secretos al commit (`git status`).
- [ ] Migraciones nuevas en `backend/migrations/`, numeradas **92+** (la 91 es
      la última usada). Aplicar en local **y** prod en la misma sesión (CLAUDE.md §24).
- [ ] Reportes de QA con PoCs **no** se commitean (CLAUDE.md §40).
