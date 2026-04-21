---
name: Reglas de Desarrollo ZARIS
description: Reglas y directrices obligatorias para el desarrollo de módulos en la suite ZARIS Gestión Estatal.
---

# Reglas Mandatorias de Desarrollo para ZARIS

Al desarrollar nuevas características o módulos para la suite ZARIS, usted **DEBE** adherirse
a estas reglas estrictamente.

## 1. Login Único y Centralizado

El sistema entero (BUC, Agenda, Historia Clínica, CRM, etc.) opera bajo la premisa de
**Single Sign-On (Login Único)**.

- **Prohibido:** Crear pantallas de login, modales de autenticación o validaciones de
  contraseñas de manera individual en cada módulo.
- **Obligatorio:** Toda la autenticación ocurre en `home.html` (o el servicio de auth
  principal). Los módulos deben asumir que la autenticación ya sucedió y simplemente
  verificar la existencia de la sesión compartida (ej. chequeando `zaris_session` en
  `localStorage`). Si no hay sesión, el usuario es redirigido a `home.html`.

## 2. Base Única de Ciudadanos (BUC) como Fuente Única de Verdad

Cualquier módulo que requiera registrar interacciones con individuos (pacientes, clientes,
usuarios, solicitantes de turnos) **DEBE** consumir la entidad `Ciudadano` desde la BUC.

- **Prohibido:** Crear tablas o entidades separadas para almacenar datos maestros de
  personas (como DNI, nombre, teléfonos) dentro de un módulo subsidiario.
- **Obligatorio:** Utilizar su llave primaria (ej. `id_ciudadano`) y referenciar siempre a
  la tabla/fuente original `ciudadanos`. Los datos extra específicos de un negocio
  pueden añadirse a la BUC si son relevantes globalmente; de lo contrario se referencian
  externamente, pero el individuo siempre existe primero y únicamente en la BUC.

## 3. Accesos y Roles Modulares (Arquitectura Futura)

Las credenciales son para toda la suite, pero a corto/mediano plazo habrá control de
acceso modular.

- Al generar nuevas arquitecturas de seguridad o diseñar los roles, anticipe que los
  usuarios tendrán un conjunto de permisos que dictarán a qué aplicaciones o módulos
  de la suite pueden acceder.
- Utilice la misma tabla de usuarios y sesiones subyacente, pero añada configuraciones
  de acceso modulares o banderas (flags) cuando sea requerido.

## 4. Stack Tecnológico

- **Frontend:** Vanilla HTML/JS/CSS (sin frameworks)
- **Backend:** FastAPI (Python 3.10+)
- **Base de Datos:** PostgreSQL (Supabase en producción, Postgres 14 local en desarrollo)
- **Deploy:** Railway (API) — el frontend actualmente corre solo en local
- **Tipografía:** Google Fonts — Inter + JetBrains Mono

## 5. Convenciones de Código

- SQL: snake_case para tablas y columnas
- API: prefijo `/api/v1/` + nombre_modulo
- Archivos frontend: minúsculas con guiones o guiones_bajos
- Timestamps: UTC siempre
- Bajas lógicas: campo `activo = false`, nunca DELETE físico

## 6. URLs del Proyecto

### Producción

- **API:** `https://zaris-api-production-bf0b.up.railway.app`
- **Health check:** `https://zaris-api-production-bf0b.up.railway.app/api/health`
- **API docs (Swagger):** `https://zaris-api-production-bf0b.up.railway.app/docs`

### Repositorio

El proyecto ZARIS Gestión Estatal (ZGE) está organizado como **monorepo**. Todo el
código (frontend, backend, SQL, documentación) vive en un único repositorio.

- **Repositorio:** `github.com/CesarZeta/zaris-zge` (privado)
- **Estructura:**
  - `backend/` — FastAPI (deploy automático a Railway desde la rama `main`)
  - `frontend/` — Vanilla HTML/JS/CSS (aún no deployado, corre en local)
  - `sql/` — Scripts de esquema y migraciones
  - `docs/` — Documentación técnica

### Desarrollo Local

- **API:** `http://127.0.0.1:8000`
- **Frontend:** `http://localhost:8080`
- **Base de datos:** `postgresql://postgres@127.0.0.1:5432/zaris_dev`
