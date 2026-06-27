---
name: Vinculación entre tablas — siempre por ID
description: Toda relación entre dos tablas se modela con FK por id, nunca por matching de strings (email, nombre, legajo). Si la columna no existe, crearla con migración.
type: feedback
---
**Regla:** Cuando dos tablas deben relacionarse (ej: `agentes` y `usuarios`, `ciudadanos` y `usuarios`, `equipos` y `lugares_atencion`), el vínculo se hace con una columna `id_<otra_tabla>` con FK formal — nunca por matching de campos string como email, nombre, legajo o documento.

**Why:** El matching por strings (ej: `agentes.email = usuarios.email`) parece funcionar pero falla en escenarios reales:
- emails que cambian rompen el vínculo silenciosamente,
- duplicados con espacios o mayúsculas distintas no matchean,
- no hay garantía de integridad referencial (la DB no protege).
La regla es explícita: si hace falta vincular, agregar la columna con FK aunque requiera migración.

**How to apply:**
- Antes de proponer una solución que diga "matcheamos por email" o "buscamos por nombre", **frenar** y verificar si existe la FK formal. Si no existe, crear migración primero.
- Endpoints como `/agente/me` deben resolver via `SELECT id_agente FROM agentes WHERE id_usuario = current_user.id_usuario`, no via email.
- Si la tabla destino aún no tiene la columna FK, agregarla con `ALTER TABLE ... ADD COLUMN id_<otra> INTEGER REFERENCES ...(...) ON DELETE SET NULL` y reflejar en el modelo SQLAlchemy.
- Aplicar siempre en local y prod en la misma sesión (CLAUDE.md §24).
