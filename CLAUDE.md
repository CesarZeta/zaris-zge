---
name: Reglas de Desarrollo ZARIS
description: Reglas y directrices obligatorias para el desarrollo de módulos en la suite ZARIS Gestión Estatal.
---

# Reglas Mandatorias de Desarrollo para ZARIS

Al desarrollar nuevas características o módulos para la suite ZARIS, usted **DEBE** adherirse
a estas reglas estrictamente.

## 1. Login Único y Centralizado (JWT)

El sistema opera bajo **Single Sign-On** basado en JWT.

- **Autenticación:** `POST /api/v1/auth/login` — recibe `{ email, password }`, devuelve
  `{ access_token, user }`. El token tiene vigencia de 24 horas.
- **Token storage:** el token se guarda en `localStorage` bajo la clave `zaris_session`
  (objeto JSON con `access_token` y `user`). Todos los módulos leen de ahí.
- **Requests autenticados:** incluir header `Authorization: Bearer <token>` en toda
  llamada a endpoints protegidos. El helper `src/lib/api.ts` (web-app) lo hace
  automáticamente.
- **Guard en React:** el `AppShell` redirige a `/login` si no hay sesión. No crear
  pantallas de login individuales por módulo.
- **Guard en vanilla HTML:** verificar `localStorage.getItem('zaris_session')` al inicio
  del script; si no existe, redirigir a la pantalla de login.
- **Prohibido:** crear endpoints de auth separados por módulo o guardar passwords en
  texto plano.

## 2. Base Única de Ciudadanos (BUC) como Fuente Única de Verdad

Cualquier módulo que requiera registrar interacciones con individuos (pacientes, clientes,
usuarios, solicitantes de turnos) **DEBE** consumir la entidad `Ciudadano` desde la BUC.

- **Prohibido:** Crear tablas o entidades separadas para almacenar datos maestros de
  personas (como DNI, nombre, teléfonos) dentro de un módulo subsidiario.
- **Obligatorio:** Utilizar su llave primaria (`id_ciudadano`) y referenciar siempre a
  la tabla/fuente original `ciudadanos`. Los datos extra específicos de un negocio
  pueden añadirse a la BUC si son relevantes globalmente; de lo contrario se referencian
  externamente, pero el individuo siempre existe primero y únicamente en la BUC.

## 3. Accesos y Roles Modulares

Las credenciales son para toda la suite. La tabla `usuarios` tiene el campo `nivel_acceso`
(1 = Administrador, 2 = Supervisor, 3 = Operador, 4 = Consultor).

- Usar la dependencia `get_current_user` de `app/core/auth.py` en todo endpoint que
  requiera identificar al usuario o verificar permisos.
- A futuro se añadirán flags de acceso por módulo sobre la misma tabla.

## 4. Stack Tecnológico

### Frontend

| Superficie | Stack | Deploy |
|---|---|---|
| **Web app (shell React)** | React 18 + TypeScript + Vite + React Router v7 + Zustand | `web-app/` — dev local en `localhost:5173` |
| **Módulos legacy (vanilla)** | HTML / JS / CSS sin frameworks | `frontend/` — GitHub Pages |

- **Tipografía (web-app):** Space Grotesk (display/UI) + Fraunces (editorial) + JetBrains Mono
  (código). Fuentes locales en `web-app/src/assets/fonts/`, tokens en `src/styles/tokens.css`.
- **Tipografía (vanilla):** Google Fonts — Inter + JetBrains Mono.
- **Iconos:** Lucide React en la web-app. `stroke-width="1.5"` siempre, `currentColor`.

### Backend

- **FastAPI** (Python 3.10+)
- **Auth:** `python-jose[cryptography]` para JWT + `bcrypt` 5.x directo (no usar `passlib`
  en Python 3.14+, tiene incompatibilidad con `bcrypt` 4.x+).
- **ORM:** SQLAlchemy async + asyncpg.

### Base de Datos

- PostgreSQL (Supabase en producción, Postgres 14 local en `zaris_dev`).

### Deploy

- Railway (API, auto-deploy desde `main`) + GitHub Pages (frontend vanilla).

## 5. Convenciones de Código

- SQL: snake_case para tablas y columnas.
- API: prefijo `/api/v1/` + nombre_modulo.
- Archivos frontend: minúsculas con guiones o guiones_bajos.
- Timestamps: UTC siempre.
- Bajas lógicas: campo `activo = false`, nunca DELETE físico.
- **CORS:** cuando se publique un nuevo frontend en otro dominio o puerto local, agregar
  la URL a la lista `allow_origins` en `backend/app/main.py`. NO duplicar el parámetro
  `allow_origins=`; Python lanza `SyntaxError: keyword argument repeated`.
- **Inconsistencia conocida:** la tabla `usuarios` usa `fecha_modif` (no `fecha_modificacion`)
  por razones históricas. No renombrar — rompería código existente.

## 6. URLs del Proyecto

### Producción

- **API:** `https://zaris-api-production-bf0b.up.railway.app`
- **Health check:** `https://zaris-api-production-bf0b.up.railway.app/api/health`
- **API docs (Swagger):** `https://zaris-api-production-bf0b.up.railway.app/docs`
- **Frontend vanilla:** `https://cesarzeta.github.io/zaris-zge/frontend/menu.html`

### Repositorio

Monorepo en `github.com/CesarZeta/zaris-zge` (público).

```
frontend/    — Vanilla HTML/JS/CSS (GitHub Pages)
backend/     — FastAPI (Railway, auto-deploy desde main)
web-app/     — React/TS shell (dev local, deploy pendiente)
sql/         — Scripts de esquema y migraciones
docs/        — Documentación técnica
design-system/ — Tokens CSS, fuentes, componentes de referencia
```

### Desarrollo Local

| Servicio | URL | Comando |
|---|---|---|
| API | `http://127.0.0.1:8000` | `cd backend && ENV_FILE=.env.local uvicorn app.main:app --host 127.0.0.1 --port 8000` |
| Web app React | `http://localhost:5173` | `cd web-app && pnpm dev` |
| Frontend vanilla | `http://localhost:8080` | `cd frontend && python -m http.server 8080` |
| Base de datos | `postgresql://postgres:145236@127.0.0.1:5432/zaris_dev` | — |

## 7. Configuración de Deploy (Railway)

- **Servicio:** `zaris-api` (proyecto Railway: `inspiring-empathy`)
- **Source Repo:** `CesarZeta/zaris-zge`
- **Branch:** `main` (deploy automático en cada push)
- **Root Directory:** `/backend`
- **Custom Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

> El **Custom Start Command de Railway tiene prioridad sobre el `Procfile`**. Si se mueve
> `main.py` o cambia la estructura, actualizar el comando en Railway → Settings → Deploy,
> no solo el Procfile.

## 8. Campos Estándar Obligatorios por Tabla

Toda tabla nueva en ZARIS debe incluir los siguientes campos al final de la definición:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `activo` | `BOOLEAN DEFAULT TRUE` | Baja lógica — nunca DELETE físico |
| `id_municipio` | `INTEGER` | FK futura a tabla `municipios` |
| `fecha_alta` | `TIMESTAMPTZ DEFAULT NOW()` | Fecha de creación del registro |
| `fecha_modificacion` | `TIMESTAMPTZ DEFAULT NOW()` | Última modificación — nunca llamar `fecha_actual` |
| `id_subarea` | `INTEGER` | FK futura a tabla `subareas` |
| `id_usuario_alta` | `INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL` | Usuario que creó el registro |
| `id_usuario_modificacion` | `INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL` | Usuario de la última modificación |

Los campos `id_usuario_alta` e `id_usuario_modificacion` **no se reciben del frontend** —
los inyecta automáticamente el backend a partir del JWT del request (ver `admin_tablas.py`).

## 9. Estándar de Horario para Tablas con Servicio

Toda tabla que defina horarios de atención o servicio debe incluir:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `dias_semana` | `TEXT` | Días separados por coma: `"lunes,martes,miércoles,jueves,viernes"` |
| `hora_inicio` | `TIME` | Hora de apertura — ej: `09:00` |
| `hora_fin` | `TIME` | Hora de cierre — ej: `16:00` |

Aplica a: `equipos`, `servicios`, y cualquier entidad futura con configuración horaria.

## 10. Sistema de Autenticación — Referencia Técnica

### Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/v1/auth/login` | Login — body: `{ email, password }` → `{ access_token, token_type, user }` |
| `GET` | `/api/v1/auth/me` | Usuario autenticado actual |

### Hashing

- Algoritmo: **bcrypt** via librería `bcrypt` 5.x directamente (no `passlib`).
- En código Python: `bcrypt.hashpw(password.encode(), bcrypt.gensalt())`.
- Password por defecto en desarrollo: `123456`.

### Seed de desarrollo

Para aplicar migraciones de auth y actualizar passwords localmente:

```bash
cd backend
ENV_FILE=.env.local python seed_auth.py
```

### Agregar un módulo nuevo al shell React

1. Crear carpeta `web-app/src/modules/<nombre>/`.
2. Crear `index.ts` exportando un objeto `ModuleManifest` (ver `src/lib/types.ts`).
3. Importar y agregar el manifest en `web-app/src/modules/index.ts`.
4. Cero cambios al shell — el sidebar y el router lo leen automáticamente.
