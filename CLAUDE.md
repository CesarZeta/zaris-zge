# Reglas Mandatorias de Desarrollo — ZARIS

## 1. Autenticación JWT (SSO)

- **Login:** `POST /api/v1/auth/login` — body `{ email, password }` → `{ access_token, token_type, user }`. Vigencia: 24 h.
- **Me:** `GET /api/v1/auth/me` — usuario autenticado actual.
- **Storage:** `localStorage` clave `zaris_session` (objeto `{ access_token, user }`). Todos los módulos leen de ahí.
- **Requests:** header `Authorization: Bearer <token>` en todo endpoint protegido. El helper `src/lib/api.ts` lo hace automáticamente.
- **Guard React:** `AppShell` redirige a `/login` sin sesión. No crear login por módulo.
- **Guard vanilla:** verificar `localStorage.getItem('zaris_session')` al inicio; si no existe, redirigir al login.
- **Hashing:** `bcrypt` 5.x directo — `bcrypt.hashpw(password.encode(), bcrypt.gensalt())`. No usar `passlib` (incompatible con bcrypt 4.x+ en Python 3.14+).
- **Seed local:** `cd backend && $env:ENV_FILE=".env.local"; python seed_auth.py`. Password dev: `[redactado]`.
- **Prohibido:** endpoints de auth por módulo, passwords en texto plano.

## 2. Base Única de Ciudadanos (BUC)

Todo módulo con individuos (pacientes, clientes, solicitantes) **debe** referenciar `ciudadanos` via `id_ciudadano`.

- **Prohibido:** tablas propias para datos maestros de personas (DNI, nombre, teléfonos).
- **Obligatorio:** el individuo existe primero y únicamente en la BUC; datos específicos de negocio se referencian externamente.

## 3. Roles y Permisos

`nivel_acceso` en `usuarios`: 1 = Administrador, 2 = Supervisor, 3 = Operador, 4 = Consultor.

Usar `get_current_user` de `app/core/auth.py` en todo endpoint que requiera identidad o permisos.

## 4. Stack Tecnológico

| Superficie | Stack | Directorio |
|---|---|---|
| Web app (shell React) | React 18 + TS + Vite + React Router v7 + Zustand | `web-app/` |
| Módulos legacy | HTML / JS / CSS | `frontend/` |

- **Tipografía web-app:** Space Grotesk + Fraunces + JetBrains Mono. Fuentes en `web-app/src/assets/fonts/`, tokens en `src/styles/tokens.css`.
- **Tipografía vanilla:** Google Fonts — Inter + JetBrains Mono.
- **Iconos:** Lucide React, `stroke-width="1.5"`, `currentColor`.
- **Backend:** FastAPI (Python 3.10+), SQLAlchemy async + asyncpg, PostgreSQL (Supabase prod / `zaris_dev` local).

## 5. Convenciones de Código

- SQL: snake_case.
- API: prefijo `/api/v1/<nombre_modulo>`.
- Archivos frontend: minúsculas con guiones o guiones_bajos.
- Timestamps: UTC.
- Bajas lógicas: `activo = false`, nunca DELETE físico.
- **CORS:** agregar nueva URL a `allow_origins` en `backend/app/main.py`. No duplicar el parámetro — Python lanza `SyntaxError`.
- **Quirk:** `usuarios` usa `fecha_modif` (no `fecha_modificacion`). No renombrar.

## 6. URLs del Proyecto

Monorepo: `github.com/CesarZeta/zaris-zge`.

| Entorno | Servicio | URL / Comando |
|---|---|---|
| Prod | API | `https://zaris-api-production-bf0b.up.railway.app` |
| Prod | Health | `https://zaris-api-production-bf0b.up.railway.app/api/health` |
| Prod | Swagger | `https://zaris-api-production-bf0b.up.railway.app/docs` |
| Prod | Frontend | `https://cesarzeta.github.io/zaris-zge/frontend/menu.html` |
| Local | API | `http://127.0.0.1:8000` — `$env:ENV_FILE=".env.local"; uvicorn app.main:app --host 127.0.0.1 --port 8000` (desde `backend/`) |
| Local | Web app | `http://localhost:5173` — `cd web-app && pnpm dev` |
| Local | Frontend | `http://localhost:8080` — `python -m http.server 8080` (raíz del repo) |
| Local | DB | `postgresql://postgres:145236@127.0.0.1:5432/zaris_dev` |

## 7. Deploy Railway

- **Proyecto:** `inspiring-empathy` → servicio `zaris-api`, branch `main`, root `/backend`.
- **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- El Custom Start Command tiene prioridad sobre el `Procfile`. Si se mueve `main.py`, actualizar en Railway → Settings → Deploy.

## 8. Campos Estándar por Tabla

Toda tabla nueva debe incluir al final:

| Campo | Tipo | Descripción |
|---|---|---|
| `activo` | `BOOLEAN DEFAULT TRUE` | Baja lógica |
| `id_municipio` | `INTEGER` | FK futura → `municipios` |
| `id_subarea` | `INTEGER` | FK futura → `subareas` |
| `fecha_alta` | `TIMESTAMPTZ DEFAULT NOW()` | Creación |
| `fecha_modificacion` | `TIMESTAMPTZ DEFAULT NOW()` | Última modificación — no llamar `fecha_actual` |
| `id_usuario_alta` | `INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL` | Usuario creador |
| `id_usuario_modificacion` | `INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL` | Usuario modificador |

`id_usuario_alta` e `id_usuario_modificacion` los inyecta el backend desde el JWT — no vienen del frontend.

## 9. Horario en Tablas de Servicio

Tablas con horario de atención (`equipos`, `servicios`, etc.) deben incluir:

| Campo | Tipo | Ejemplo |
|---|---|---|
| `dias_semana` | `TEXT` | `"lunes,martes,miércoles,jueves,viernes"` |
| `hora_inicio` | `TIME` | `09:00` |
| `hora_fin` | `TIME` | `16:00` |

## 10. Agregar Módulo al Shell React

1. Crear `web-app/src/modules/<nombre>/`.
2. Crear `index.ts` exportando un `ModuleManifest` (ver `src/lib/types.ts`).
3. Importar el manifest en `web-app/src/modules/index.ts`.
4. El sidebar y el router lo leen automáticamente — cero cambios al shell.

## 11. Design System Visual — Obligatorio

El estilo oficial de ZARIS vive en `design-system/`. **Nunca** usar `styles.css` ni variables `--z-*` (son legacy, eliminadas).

### CSS a incluir en todo HTML frontend (vanilla)

```html
<link rel="stylesheet" href="../design-system/fonts/fonts.css">
<link rel="stylesheet" href="../design-system/colors_and_type.css">
```

### Tokens CSS — no inventar variables propias

| Uso | Token | Valor |
|---|---|---|
| Fondo de página | `var(--zaris-cream)` | `#f2f1ed` |
| Sidebar / nav | `var(--surface-300)` | `#ebeae5` |
| Cards, modales | `var(--surface-100)` | `#f7f7f4` |
| Superficie sutil | `var(--surface-400)` | `#e6e5e0` |
| Texto primario | `var(--fg-1)` | `#26251e` |
| Texto secundario | `var(--fg-2)` | `rgba(38,37,30,.7)` |
| Texto terciario | `var(--fg-3)` | `rgba(38,37,30,.55)` |
| Borde sutil | `var(--border-primary)` | `rgba(38,37,30,.1)` |
| Borde medio | `var(--border-medium)` | `rgba(38,37,30,.2)` |
| Acento naranja | `var(--zaris-orange)` | `#f54e00` |
| Error / hover | `var(--color-error)` | `#cf2d56` |
| Tipografía display | `var(--font-display)` | Space Grotesk |
| Tipografía mono | `var(--font-mono)` | JetBrains Mono |

### Layout shell (sidebar + topbar)

- **Grid:** `display: grid; grid-template-columns: 232px 1fr; grid-template-rows: 52px 1fr; height: 100vh`
- **Topbar:** `height: 52px`, `background: rgba(242,241,237,.88)`, `backdrop-filter: blur(12px)`
- **Sidebar:** `width: 232px`, `background: var(--surface-300)`, `border-right: 1px solid var(--border-primary)`

### Logo y marca

- Usar `../design-system/assets/zaris-mark-flat.svg` en sidebar/topbar (currentColor, sin fondo).
- Formal (splash, login): `../design-system/assets/zaris-mark.svg`.
- **Prohibido:** emoji en la UI del producto.
