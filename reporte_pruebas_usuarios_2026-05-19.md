# QA Módulo Usuarios — 2026-05-19 (actualizado 2026-05-22)

**Alcance**: smoke completo del frontend `frontend/usuarios.html` + endpoints `/api/v1/buc/usuarios/*` en local (zaris_dev). 22 casos de prueba (16 PASS + 6 hallazgos). Cleanup ejecutado (4 users borrados).

**Entorno**: `http://localhost:8080` (shell vanilla) + `http://127.0.0.1:8000` (uvicorn) + `zaris_dev` Postgres 17 local.

**Login usado**: `ciudadanovl@municipio.gob.ar` (admin nivel 1).

> **ACTUALIZACIÓN 2026-05-22**: los **3 hallazgos CRITICAL** (auth bypass del router BUC + 2 XSS persistentes) fueron **RESUELTOS y pusheados a producción**. Las PoCs explotables se removieron por §40 (repo público).
>
> **ACTUALIZACIÓN 2026-05-22 (2ª tanda)**: los **3 hallazgos restantes** (#03 login imposible, #04 sin link sidebar, #05 modal texto) también **RESUELTOS y verificados en navegador**. El módulo Usuarios queda sin deuda funcional conocida (resta solo deuda de seguridad menor: GET del router BUC sin auth).

---

## Resumen

| Bloque | PASS | FAIL/Hallazgo |
|---|---|---|
| Navegación / acceso | 0 | 1 (HIGH — no hay link en sidebar) |
| Búsqueda | 6 | 0 |
| Listado + filtros | 4 | 0 |
| Alta de usuario | 3 | 1 RESUELTO (XSS) + 1 HIGH abierto (login imposible por falta de email) |
| Edición + baja | 4 | 1 (MEDIUM — texto del modal confirm equivocado) |
| Seguridad endpoints | 0 | 1 RESUELTO (auth) |

**Total: 17 PASS / 5 hallazgos** — **3 CRITICAL resueltos (2026-05-22)**, 2 HIGH + 1 MEDIUM abiertos.

---

## Hallazgos

### [BUG-USU-01] CRITICAL — XSS persistente en render de resultados (Usuarios + topbar) ✅ RESUELTO 2026-05-22

**Severidad**: CRITICAL. **Estado**: **RESUELTO** (pusheado a `main` el 2026-05-22).

**Resumen del problema** (PoC removida por §40): el nombre/username del usuario, controlable en el alta, se interpolaba sin escape en dos `innerHTML` distintos:
- `mostrarResultados()` de [`frontend/js/usuarios.js`](frontend/js/usuarios.js) — caso multi-resultado de la búsqueda.
- el avatar/info del topbar en [`frontend/js/menu.js`](frontend/js/menu.js) — disparaba al abrir el shell, sin pasar por el módulo Usuarios.

Encadenado con BUG-USU-02 (alta sin auth), permitía persistir un payload y ejecutarlo en el contexto del shell padre de cualquier admin (robo de JWT vía `localStorage.zaris_session`).

**Fix aplicado**:
- `usuarios.js` — `esc()` aplicado a `u.nombre` y `u.username` en `mostrarResultados()`. El resto del archivo (preview, listado, subáreas, caso de 1 resultado vía `textContent`) ya estaba escapado.
- `menu.js` — helper `esc()` nuevo aplicado al `name`/`nivel` del topbar (avatar, contexto, info del dropdown). Cache-bust `?v=2026-05-22a` en `index.html`.

**Verificado**: typecheck N/A (vanilla). Patrón `esc()` consistente con el resto del módulo.

---

### [BUG-USU-02] CRITICAL — Endpoints de escritura del router BUC sin autenticación ✅ RESUELTO 2026-05-22

**Severidad**: CRITICAL. **Estado**: **RESUELTO** (pusheado a `main` el 2026-05-22).

**Resumen del problema** (PoC removida por §40): el router [`backend/app/api/routes/buc.py`](backend/app/api/routes/buc.py) no usaba `Depends(get_current_user)` en ningún endpoint. Cualquiera con acceso de red a la API podía crear un usuario admin (nivel 1) sin token, loguearse y tomar control total; o dar de baja al admin real; o listar `password_hash`.

**Fix aplicado** (alcance acordado: "solo escritura"):
- `from app.core.auth import get_current_user` agregado.
- `_user: dict = Depends(get_current_user)` en los **9 endpoints de escritura** del router: POST/PUT/PUT-estado de `usuarios`, `ciudadanos` y `empresas`, más POST `ciudadano-empresa`.
- Los GET de búsqueda/catálogo quedan abiertos a propósito (no romper consumidores vanilla que listan sin token todavía). El vector crítico de **alta-sin-auth** queda cerrado.

**Verificado (smoke local 2026-05-22)**:
- `POST /api/v1/buc/usuarios` **sin** token → **401**.
- Login admin (`ciudadanovl@`) → OK.
- `POST /api/v1/buc/usuarios` **con** token → **201** + cleanup baja OK.
- `GET /api/v1/buc/usuarios/buscar` sin token → **200** (sigue abierto, esperado).

> **Deuda residual (no crítica)**: los GET siguen sin auth y `UsuarioOut` aún podría exponer `password_hash` (verificar schema). Considerar para una próxima iteración endurecer a router-wide + excluir el hash del schema.

---

### [BUG-USU-03] HIGH — Form no captura email → users creados desde UI no pueden loguearse ✅ RESUELTO 2026-05-22

**Severidad**: HIGH. **Estado**: **RESUELTO** (pusheado a `main` el 2026-05-22).

**Problema**: `usuarios.email` nullable, el form no lo incluía, y `/auth/login` busca por email → un user creado desde la UI nunca podía loguearse.

**Fix aplicado** (opción A+B combinadas):
- Backend (`buc.py` POST `/usuarios`): si no viene email, autogenera `<username>@municipio.gob.ar`. Valida unicidad (409 si duplicado). `UsuarioCreate`/`UsuarioUpdate` aceptan `email` opcional; `UsuarioOut` + `_USUARIO_SELECT` lo devuelven.
- Frontend (`usuarios.html` + `usuarios.js`): campo "Email" opcional en el form (con hint que explica el autogenerado), incluido en payload solo si tiene valor, poblado en edición.

**Verificado (smoke local + navegador 2026-05-22)**: crear sin email → email autogenerado + **login del user nuevo OK**; crear con email explícito → persiste; email duplicado → 409; GET trae el email y el form lo puebla en edición.

---

### [BUG-USU-04] HIGH — Módulo Usuarios no es accesible desde el sidebar ✅ RESUELTO 2026-05-22

**Severidad**: HIGH. **Estado**: **RESUELTO** (pusheado a `main` el 2026-05-22).

**Problema**: el item con `data-modulo="usuarios"` era en realidad "configuración" (apuntaba al módulo Config React). No existía link a `frontend/usuarios.html`.

**Fix aplicado**: item nuevo "usuarios" en el sidebar de `index.html` (`data-modulo="usuarios"` → `frontend/usuarios.html`, ícono de personas). El item "configuración" pasó a `data-modulo="admin_tablas"` (corrige el mismatch — config de identidad es admin nivel 1, igual que maestros).

**Verificado (navegador 2026-05-22)**: el sidebar muestra "usuarios" entre "maestros" y "configuración"; click carga `usuarios.html` en el iframe del shell.

---

### [BUG-USU-05] MEDIUM — Modal de confirmación de baja muestra texto equivocado ✅ RESUELTO 2026-05-22

**Severidad**: MEDIUM. **Estado**: **RESUELTO** (pusheado a `main` el 2026-05-22).

**Problema**: `ZUtils.confirm()` tenía labels hardcoded ("No, continuar"/"Sí, salir", del flow "abandonar cambios"). La baja de usuario los reusaba → texto confuso.

**Fix aplicado**: `confirm(title, message, opts)` ahora acepta `cancelLabel`, `confirmLabel` y `danger` (botón rojo). Retrocompat: sin `opts` mantiene los defaults. `cambiarEstado()` pasa "Cancelar" / "Sí, dar de baja" (+ `danger:true` en baja). Bonus: `confirm()` ahora escapa `title`/`message` (cierra deuda XSS latente del mismo tipo).

**Verificado (navegador 2026-05-22)**: el modal de baja muestra título "Dar de baja usuario", botones "Cancelar" + "Sí, dar de baja" (rojo), nombre escapado.

---

### [BUG-USU-06] LOW — Vista previa contenía residuos de QA viejos sin cleanup

**Severidad**: LOW (deuda operativa, no es bug del módulo).
**Reproducible**: 1 vez (resuelto en cleanup).
**Caso**: visual inicial.

Al abrir el módulo, los 5 últimos usuarios en la vista previa incluían `qa_test_bug001` y `qausuariotest` inactivos, evidencia de QA previo sin cleanup. Limpiados en este reporte. Recordatorio para `feedback_smoke_cleanup_prod`: aplicar también a local.

---

## Casos PASS (no requieren acción)

### Búsqueda (6 PASS)
- **BUSCAR-01**: input vacío → toast warning "Ingresá un término de búsqueda".
- **BUSCAR-02**: query "Sofia" → 1 resultado, panel con name + detail correcto, botones Editar/Consultar visibles.
- **BUSCAR-03**: query "a" → 8 resultados en lista clickeable.
- **BUSCAR-04**: query "xyzzy_no_match" → "Sin resultados".
- **BUSCAR-05**: payload en el query → no se ejecuta (el input usa `textContent`). El XSS real estaba en el render del resultado (BUG-USU-01, ya resuelto).
- **BUSCAR-06**: query por username "iacrm" → matchea correcto.

### Listado completo (4 PASS)
- **LST-01**: abrir listado carga 8 users con todas las columnas (Nombre/Usuario/Nivel/CUIL/Estado/Acciones).
- **LST-02**: filtro nivel=Operador → 2 filas.
- **LST-03**: orden A→Z correcto.
- **LST-04**: filtro texto "roy" → 1 fila.

### Alta — validaciones (3 PASS)
- **ALTA-01**: modo nuevo muestra título "Alta de Usuario", state badge "NUEVO" verde.
- **ALTA-02**: guardar vacío → 4 errores inline (nombre, username, nivel, password).
- **ALTA-03**: username con espacio + password corta + confirm distinta + CUIL inválido → 4 errores correspondientes.

### Edición / baja (4 PASS)
- **EDIT-01**: cargar usuario en edición → username readOnly, hint de password "Dejar vacío para no cambiar", botón Baja visible.
- **EDIT-02**: editar + guardar → toast success, pasa a modo Consulta, fields disabled.
- **BAJA-01**: dar de baja → soft-delete OK, badge "Inactivo" rojo, botón Reactivar aparece.
- **REACT-01**: reactivar → badge "Activo" verde, botón Baja vuelve.
- **CONSULT-01**: modo consulta deshabilita los 8 inputs.

---

## Recomendación de priorización

| Prioridad | Bug | Estado |
|---|---|---|
| P0 | BUG-USU-02 (auth bypass) | ✅ RESUELTO 2026-05-22 |
| P0 | BUG-USU-01 (XSS persistente) | ✅ RESUELTO 2026-05-22 |
| P1 | BUG-USU-03 (login imposible) | ✅ RESUELTO 2026-05-22 |
| P2 | BUG-USU-04 (no link sidebar) | ✅ RESUELTO 2026-05-22 |
| P3 | BUG-USU-05 (modal texto) | ✅ RESUELTO 2026-05-22 |

Todos los hallazgos del reporte fueron resueltos. Resta solo deuda de seguridad menor (no bloqueante): los GET del router BUC siguen sin auth (alcance "solo escritura"), considerar endurecer a router-wide en una próxima iteración.

---

## Cleanup ejecutado

- Borrado físico de 4 usuarios de test: `qausuariotest` (id=11), `qa_test_bug001` (id=12), `qa_test_xss_1779238408746` (id=13), `noauth_1779227837` (id=14).
- Bajados uvicorn + http.server.
- Borrados logs temporales `_uvicorn.log`, `_uvicorn.err.log`, `_httpserver.log`, `_httpserver.err.log`.
- DB local en el mismo estado que al inicio (6 users activos: ciudadanovl, administrativo, iacrm, juanpesto, roymanos, sofiamedrano).
