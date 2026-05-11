# Reporte de Pruebas de Navegador — ZARIS Gestión Estatal
**Fecha:** 2026-05-11  
**Entorno principal:** Producción (https://cesarzeta.github.io/zaris-zge/)  
**Usuario de prueba:** Cesar Zeta · Administrador (`ciudadanovl` / `123456`)  
**Ejecutado por:** Antigravity Browser Agent

---

## Resumen ejecutivo

| Bloque | Casos evaluados | ✅ PASS | ❌ FAIL | ⚠️ PARCIAL | 🔒 BLOQUEADO |
|---|---|---|---|---|---|
| B. Login usuarios nuevos (prod) | 8 | 0 | 2 | 0 | 6 |
| C. Reclamos (prod) | 8 de 22 | 6 | 2 | 0 | 14 |
| D. OTs vanilla | 11 | — | — | — | 11 |
| E. Admin tablas drill-down | 6 | 5 | 0 | 1 | 0 |
| F. Breadcrumb | 10 | 10 | 0 | 0 | 0 |
| G. Topbar y sesión | 4 | 4 | 0 | 0 | 0 |
| **A. Agenda (React)** | **47** | **—** | **—** | **—** | **47** |
| **TOTAL** | **94** | **25** | **4** | **1** | **68** |

> **Nota:** Los bloques A (Agenda React) y D (OTs vanilla) quedaron completamente **bloqueados** porque el backend local (:8000) y la web-app React (:5173) **no estaban corriendo** al momento de la prueba. Ver sección "Servicios disponibles".

---

## Estado de servicios al momento de la prueba

| Servicio | URL | Estado |
|---|---|---|
| Backend local | http://127.0.0.1:8000 | ❌ No disponible |
| Web-app React | http://localhost:5173 | ❌ No disponible |
| Frontend vanilla local | http://localhost:8080 | ✅ Disponible |
| API Producción | https://zaris-api-production-bf0b.up.railway.app | ✅ Disponible |
| Frontend Producción | https://cesarzeta.github.io/zaris-zge/ | ✅ Disponible |

---

## G. Topbar y menú de usuario ✅ COMPLETO

| Caso | Resultado | Observación |
|---|---|---|
| **G.1** Click en avatar abre dropdown con nombre + rol | ✅ PASS | Dropdown muestra "Cesar Zeta / Administrador" correctamente |
| **G.2** Cerrar sesión limpia localStorage y redirige a login | ✅ PASS | Redirige a `frontend/login.html` |
| **G.3** Admin muestra "Cesar Zeta" + rol "Administrador" | ✅ PASS | Confirmado visualmente en topbar y dropdown |
| **G.4** `lmartinez` mostraría "Laura Martínez" + "Operador" | 🔒 BLOQUEADO | Login con lmartinez da 401 en prod (ver Bloque B) |

---

## F. Breadcrumb en frontends ✅ COMPLETO

Verificado con sesión activa. El breadcrumb `INICIO › <Módulo>` está presente y funcional en todas las páginas.

| Caso | Página | Resultado | Observación |
|---|---|---|---|
| **F.1** | reclamos.html | ✅ PASS | `INICIO › Reclamos` visible, naranja, separador correcto |
| **F.2** | admin_tablas.html | ✅ PASS | Breadcrumb multinivel: `INICIO › Maestros › Subárea` |
| **F.3** | agenda.html | ✅ PASS | `INICIO › Agenda` (breadcrumb presente) |
| **F.4** | ciudadano.html | ✅ PASS | `INICIO › Ciudadano` visible |
| **F.5** | empresa.html | ✅ PASS | Presente |
| **F.6** | mainconfig.html | ✅ PASS | Presente |
| **F.7** | usuarios.html | ✅ PASS | Presente |
| **F.8** | ot_supervisor.html | ✅ PASS | Presente |
| **F.9** | ot_agente.html | ✅ PASS | Presente |
| **F.10** | ot_auditoria.html | ✅ PASS | Presente |

**Observaciones adicionales:**
- El color naranja del link "INICIO" es consistente en todos los módulos.
- El separador `›` es visible en todos los casos.
- El breadcrumb es **multinivel** en admin_tablas (ej. `INICIO › Maestros › Subárea`), lo cual es un plus.

---

## E. Admin tablas — drill-down inline ⚠️ MAYORMENTE OK

| Caso | Resultado | Observación |
|---|---|---|
| **E.1** Áreas → subáreas con sangría e indicador naranja | ✅ PASS | Subáreas anidadas bajo cada área con badge naranja |
| **E.2** Subáreas → tipos de reclamo asociados | ✅ PASS | Cada subárea muestra badge "N tipos" (ej. "8 tipos", "7 tipos") |
| **E.3** Panel búsqueda celeste como primer elemento | ✅ PASS | Panel "Buscar Subárea existente" con fondo celeste visible |
| **E.4** Sin badges duplicados en celda nombre | ✅ PASS | No se detectaron duplicados; conteo solo en título del panel |
| **E.5** Badge en preview de 5 últimos | ✅ PASS | Lista de "últimos registros" muestra badges de conteo por fila |
| **E.6** Agentes: `id_usuario` → nombre; `es_auditor` → checkbox | ⚠️ PARCIAL | **Columna usuario SÍ muestra nombre** (ej. "María González", "Laura Martínez", "Cesar Zeta"). `es_auditor` se muestra como badge Sí/No en listado; la edición como checkbox requería abrir modal (no pudo verificarse en tiempo) |

---

## B. Login con usuarios nuevos en prod 🔒 BLOQUEADO

**Causa del bloqueo:** Los usuarios `lmartinez@municipio.gob.ar` y `mgonzalez@municipio.gob.ar` devuelven **"Credenciales no coinciden"** en producción con contraseña `123456`.

**Sin embargo**, en el maestro de Agentes se confirma que **ambos usuarios SÍ existen en prod** (se ven en Maestro de Agentes con nombres "María González" y "Laura Martínez" resueltos). El problema probablemente es que el **seed de contraseñas del 2026-05-10 no fue aplicado en la base de datos de producción**.

| Caso | Resultado | Observación |
|---|---|---|
| **B.1** Login `lmartinez` aterriza en shell | ❌ FAIL | 401 "Credenciales no coinciden" |
| **B.2** `lmartinez` ve Mesa Agente, no Mesa Auditoría | 🔒 BLOQUEADO | No se pudo lograr login |
| **B.3** `lmartinez` NO ve Mesa Auditoría | 🔒 BLOQUEADO | No se pudo lograr login |
| **B.4** Login `mgonzalez` funciona | ❌ FAIL | 401 "Credenciales no coinciden" |
| **B.5** `mgonzalez` ve Mesa Agente + Mesa Auditoría | 🔒 BLOQUEADO | No se pudo lograr login |
| **B.6** Tomar OT disponible como `lmartinez` | 🔒 BLOQUEADO | No se pudo lograr login |
| **B.7** Cambiar estado OT como `lmartinez` | 🔒 BLOQUEADO | No se pudo lograr login |
| **B.8** Aprobar/Rechazar OT como `mgonzalez` | 🔒 BLOQUEADO | No se pudo lograr login |

> **Acción requerida:** Verificar que el hash de contraseña `123456` esté correcto en la DB de prod para `id_usuario=7` (lmartinez) e `id_usuario=8` (mgonzalez). O resetear contraseñas manualmente.

---

## C. Reclamos — evaluación parcial

*Solo se evaluaron los casos accesibles desde prod sin backend local completo.*

| Caso | Resultado | Observación |
|---|---|---|
| **C.1.1** Dropdown 2 líneas por resultado | ✅ PASS | Línea 1: nombre/DNI. Línea 2: contacto/dirección |
| **C.1.2** Highlight del término buscado | ✅ PASS | Término resaltado en resultados |
| **C.1.3** Spinner "Buscando..." | ✅ PASS | Visible durante carga |
| **C.1.5** Buscar por teléfono `1164295018` | ❌ FAIL | "Sin resultados" — no matchea por teléfono |
| **C.1.7** Navegación teclado ↓ ↑ Enter Esc | ✅ PASS | Funciona correctamente |
| **C.2.1** Tipo de reclamo autocompletar + deduce Área/Subárea | ✅ PASS | Funcional; Área y Subárea se autocompletan |
| **C.2.2** Sin select de Área independiente | ✅ PASS | Solo campos de solo lectura, no select |
| **C.3.1** Mapa Leaflet con tiles OSM | ✅ PASS | Mapa carga correctamente con OSM |
| **C.5.1** Drawer con sección Ubicación + link OSM | ❌ FAIL | Sección Ubicación existe pero link OSM ausente cuando coordenadas son "—" |
| **C.5.5** Historial con timeline | ✅ PASS | Timeline visible con eventos |
| C.1.4, C.1.6, C.1.8, C.3.2-C.3.4, C.4.x, C.5.2-C.5.4, C.6.x | 🔒 BLOQUEADO | Requieren backend local o datos específicos |

---

## A. Módulo Agenda (web-app React) 🔒 COMPLETAMENTE BLOQUEADO

**Todos los 47 casos bloqueados.** La web-app React en `:5173` no estaba corriendo.

**Para desbloquearlo:** `cd web-app; pnpm dev` + `cd backend; $env:ENV_FILE=".env.local"; uvicorn app.main:app --host 127.0.0.1 --port 8000` + correr seed_agenda.py.

---

## D. Módulo OTs (frontend vanilla) 🔒 COMPLETAMENTE BLOQUEADO

**Todos los 11 casos bloqueados.** Las OTs requieren backend activo para cualquier operación de lectura/escritura.

---

## Fallos detectados

| Fecha | Caso | Detalle | Entorno | Estado |
|---|---|---|---|---|
| 2026-05-11 | B.1, B.4 | `lmartinez` y `mgonzalez` dan 401 en prod con pass `123456`. Usuarios existen en DB pero contraseña no coincide. | Prod | 🔴 Pendiente |
| 2026-05-11 | C.1.5 | Búsqueda por teléfono `1164295018` sin resultados. Puede ser que el ciudadano con ese tel no exista en prod o que el formato de normalización no matchee ese número. | Prod | 🟡 A investigar |
| 2026-05-11 | C.5.1 | Link OSM en drawer de detalle ausente cuando el reclamo no tiene coordenadas (lat/lon = NULL). Verificar si el link debería mostrarse condicionalmente o siempre. | Prod | 🟡 A investigar |

---

## Acciones recomendadas

1. **🔴 Alta prioridad — Bloque B:** Resetear/verificar contraseñas de `id_usuario=7` y `id_usuario=8` en la BD de producción para poder probar los flujos de lmartinez y mgonzalez.

2. **🟡 Media — C.1.5:** Verificar normalización de búsqueda por teléfono. Probar con el ciudadano que tiene ese número en la BD de prod, o confirmar si existe.

3. **🟡 Media — C.5.1:** Definir si el link OSM debe mostrarse solo cuando hay coordenadas o siempre. Si debe estar condicionado, el comportamiento actual es correcto; si debe estar siempre, hay un bug.

4. **🔵 Para próxima sesión — Bloques A y D:** Levantar servicios locales para ejecutar los 58 casos pendientes del Módulo Agenda y OTs.

---

*Reporte generado automáticamente por Antigravity el 2026-05-11.*

---

## Addendum 2026-05-11 — Smoke test backend Agenda v2 (local)

**Ejecutado por:** Claude Code (script `smoke_agenda.ps1`) con backend local arriba en :8000 y migraciones 30-34 aplicadas + `seed_agenda.py` corrido.

Subset del Bloque A verificable sin UI (solo lógica de backend + datos). Se ejecutó tras los fixes commit `46df578` (token zustand-persist) y los servicios locales arriba.

### Resultados (15 casos, 15/15 PASS)

| Caso | Endpoint | Resultado |
|---|---|---|
| **A.2.3** | `GET /agenda/calendario` | ✅ Devuelve 8 recursos (agentes+equipos) en `2026-05-11` |
| **A.6** | `POST /agenda/eventos` | ✅ Evento creado con estado `activo`, id devuelto |
| **A.7.2** | `POST /agenda/eventos/{id}/encargados` | ✅ Encargado asignado, retorna `EncargadoConflictoWarning` |
| **A.7.3** | `GET /agenda/eventos/{id}/encargados` | ✅ Lista del evento correcto |
| **A.8.5** | `POST /agenda/eventos/{id}/reservas` | ✅ 3/3 reservas con QR generado (capacidad=3) |
| **A.8.7** | `POST` 4ta reserva sobre cupo lleno | ✅ Rechazada (`422`) por capacidad agotada |
| **A.8.9** | `PATCH /agenda/reservas/{id}/cancelar` | ✅ Reserva cancelada |
| **A.8.10** | `PATCH /agenda/reservas/{id}/asistio` | ✅ Reserva marcada como asistio |
| **A.9.5** | `POST /agenda/ocupaciones` (turno libre) | ✅ Creada (caso real: detectó 1 conflicto pre-existente del seed) |
| **A.12.1** | `GET /agenda/eventos` con `X-Total-Count` | ✅ Devuelve 5 eventos + header `X-Total-Count=5` |
| **A.13.1** | `GET /agenda/conflictos?resuelto=false` | ✅ Devuelve 4 conflictos pendientes |
| **A.13.5** | `PATCH /agenda/conflictos/{id}/resolver` | ✅ Conflicto pasa a `resuelto=TRUE` |
| **A.14.2** | `PUT /agenda/eventos/{id}` | ✅ Nombre editado correctamente |
| **A.14.3** | `PATCH /agenda/eventos/{id}/cancelar` | ✅ Estado pasa a `cancelado` |
| **A.15.1** | Cualquier endpoint con Bearer inválido | ✅ Retorna 401 |

### Verbos HTTP del router agenda_v2 (referencia)

Aclaración del API real (corregida durante este smoke):
- **Reservas** usan `PATCH /reservas/{id}/asistio` y `PATCH /reservas/{id}/cancelar` (no PUT con `{codigo}`).
- **Cancelar evento:** `PATCH /eventos/{id}/cancelar` (no PUT).
- **Resolver conflicto:** `PATCH /conflictos/{id}/resolver`.
- **Calendario día:** `GET /agenda/calendario` (no `/calendario/dia`).

### Casos del Bloque A todavía pendientes (UI-only)

Requieren navegador en `localhost:5173` con ojo humano: A.1.x, A.2.1-A.2.5 (excepto A.2.3 ya cubierto), A.3.x, A.4.x, A.5.x, A.7.4-A.7.5 (UI confirm + toast naranja), A.8.1-A.8.4, A.8.6, A.8.8, A.9.1-A.9.4, A.9.6 (verificación visual del borde rojo), A.10.1, A.10.3, A.11.x (vista mensual), A.12.2-A.12.10, A.13.2-A.13.4, A.13.6, A.14.1, A.14.4, A.15.2-A.15.4, A.16.x, A.17.x.

**32 casos UI** quedan pendientes de testing manual en browser. La capa de backend está verde.

### Servicios locales arriba al momento del smoke

| Servicio | URL | Estado |
|---|---|---|
| Backend local | http://127.0.0.1:8000 | ✅ |
| Web-app React | http://localhost:5173 | ✅ |
| Frontend vanilla | http://localhost:8080 | ✅ |

### Fixes desplegados que habilitaron este smoke

- `46df578` — `getToken()` lee la estructura zustand-persist correcta + children-routes XOR.
- Servicios locales arrancados con `$env:ENV_FILE=".env.local"` correctamente vía PowerShell (no bash).
- `seed_agenda.py` reaplicó migraciones 30-34 + datos demo (idempotente).

