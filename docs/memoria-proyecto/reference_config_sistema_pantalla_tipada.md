---
name: reference_config_sistema_pantalla_tipada
description: "Config del sistema (configuracion_general) se edita desde Config React tab Sistema con UI agrupada+tipada, no solo admin_tablas crudo."
metadata: 
  node_type: memory
  type: reference
  originSessionId: 36788751-bb5e-4f15-9590-bd49e399b804
---

Desde 2026-05-25, el tab **Sistema** del módulo Config React (`web-app/src/modules/config/views/ParametrosSistemaView.tsx`, montado dentro de `SistemaView.tsx`) es una pantalla de ajustes real: lee `GET /api/v1/admin/configuracion_general`, agrupa las claves crudas en secciones legibles (Encuestas / Reclamos y OT / App Vecinos / Otros) con etiqueta humana + ayuda + control por tipo (toggle boolean, number con sufijo, text, color hex). Guarda por campo con `PUT /api/v1/admin/configuracion_general/{id_config}` body `{valor}` (handler genérico de admin_tablas). Hooks `useConfigGeneral`/`useActualizarConfigParam`.

- **Catálogo de presentación** vive en `SECCIONES` dentro del .tsx. Una clave nueva en `configuracion_general` aparece automáticamente en "Otros parámetros" (no rompe); para que salga linda, agregarla a `SECCIONES`.
- `municipio_nombre`/`municipio_logo_url` están OCULTAS acá (`CLAVES_OCULTAS`) porque se editan en la pestaña Identidad — no duplicar edición.
- El atajo viejo "Parámetros generales → admin_tablas?tabla=configuracion_general" se quitó; los atajos a Municipios/Maestros quedan como sección secundaria.
- "usuarios" se quitó del sidebar del shell (`index.html`) — la gestión de usuarios es parte de Config → Sistema → "Usuarios del sistema". `frontend/usuarios.html` sigue existiendo.

**Cuándo importa:** si piden agregar un toggle/parámetro de sistema, el patrón completo es: (1) seed la clave en `configuracion_general` (mig), (2) leerla en el backend donde corresponda, (3) sumarla a `SECCIONES` de ParametrosSistemaView. NO mandar al usuario a admin_tablas crudo. Quirk de verificación: el toggle (real `.click()` en button[role=switch]) sí persiste y se ve en DB; los `blur`/input sintéticos NO disparan el onBlur de React (verificar el efecto en DB, no en aria-checked tras refetch).
