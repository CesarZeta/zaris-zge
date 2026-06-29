---
name: modulo-guias
description: "Usar al trabajar en el módulo Guías (catálogo de manuales) o en los manuales operativos HTML de ZARIS (archivos: web-app/src/modules/guias/ — GuiasIndex.tsx, GuiasLayout.tsx; docs/manual_*.html; sidebar item 'guías'). Cubre el inventario de manuales actuales, las reglas de criterio (sin fechas/nombres, manual como entregable cuando cambia la UI, una sola fuente HTML), cómo registrar una guía nueva en el array GUIAS y el helper urlDocs de resolución de URL en iframe. La RECETA mecánica de generación (Playwright, capturas) vive en la skill `generar-manual`, no acá. Invocar ANTES de crear/registrar una guía nueva o tocar el catálogo del módulo Guías."
---

# Generación de manuales operativos (§36) + Módulo Guías (§37)

> **Receta completa de generación en la skill `generar-manual`** (`.claude/skills/generar-manual/`): setup Playwright, patrón de captura, convenciones del HTML, regenerar capturas tras cambio de UI, cleanup. Invocarla al crear/regenerar un `docs/manual_<modulo>.html`. Esta skill cubre el **inventario**, las **reglas de criterio** y el **módulo Guías** (catálogo).

## §36. Generación de manuales operativos (HTML autocontenidos)

### Manuales actuales (al 2026-06-12)
**Todos viven en `docs/` (carpeta única, pedido del usuario).** `manual_reclamos.html` (Operador+, 10 caps) · `manual_ot.html` (Sup/Agente/Auditor, 9) · `manual_tramites.html` (Operador+, 8) · `manual_admin_tramites.html` (Admin/Sup, 12) · `manual_encuestas.html` (Sup/Admin, texto sin caps) · `manual_turnos.html` (Operador+, 9 caps, 13 secc. — incluye historia de atención, detalle de turno y consultas por ciudadano, 2026-06-11) · `manual_entradas.html` (Operador+, 4 caps, 10 secc.) · **`manual_alta_ciudadanos.html`** (Operador+, 3 caps, 7 secc. — alta por agente + autogestión + URL pública/Config; actualizado 2026-06-12 al alta en un paso §38) · **`manual_emergencias.html`** (Operador+, 10 caps, 10 secc. — COM: recepción, triage, FSM, derivación, App Vecinos, 2026-06-10) · **`manual_alta_vecino.html`** (público, para el vecino, sin caps, 6 secc. — un paso + vía "ya registrado", 2026-06-12) · **`manual_ciudadano.html`** (público, para el vecino, sin caps, 10 secc. — TODAS las interacciones del ciudadano: cuenta/portal, reclamos, emergencias, turnos con y sin cuenta, entradas+QR, trámites presenciales, notificaciones push, encuesta CSAT, troubleshooting; cross-linkeado desde `manual_alta_vecino.html` §5, 2026-06-12) · **`manual_agenda.html`** (Sup+ config / Operador+ consulta, 12 caps, 13 secc. — calendario único: 4 vistas de recurso, Día/Semana/Mes, disponibilidad efectiva, eventos+reservas+QR, feriados/novedades, conflictos, espacios, circuitos OT/Turnos/Entradas; 2026-06-12). **10 registrados en el módulo Guías (§37); `manual_alta_vecino.html` y `manual_ciudadano.html` NO van en Guías** — son guías públicas del vecino (no material de backoffice); el primero se abre desde "¿Cómo me doy de alta?" en `frontend/alta-vecino.html`, el segundo es para compartir en web/redes del municipio. Próximos sugeridos (no obligatorios): Padrones.

### Reglas de criterio (no las olvides)
- **Sin fechas ni nombres personales (mandatorio, 2026-06-11).** Los manuales NO llevan fecha (ni encabezado, ni pie, ni "generado el…") ni el nombre del usuario — solo aplicación, módulo y audiencia. Ver memoria [[feedback_manuales_sin_fechas_ni_nombres]].
- **El manual es parte del entregable cuando cambia la UI que documenta.** Antes de cerrar un cambio de UI/flujo, chequear si ese módulo tiene `docs/manual_<modulo>.html`. Si lo tiene, actualizar texto + capturas afectadas es parte del mismo entregable — un manual que describe la UI vieja miente al usuario. (Cómo detectar el desfasaje y regenerar solo lo afectado: en la skill `generar-manual`.)
- **Una sola fuente por manual.** El HTML es el canónico (es lo que se publica en `docs/` y abre el módulo Guías §37). NO mantener un `.md` paralelo — se desincroniza en silencio (`manual_admin_tramites.md` quedó 5 días atrás, eliminado 2026-05-27).

## §37. Módulo Guías (catálogo de manuales)

Módulo React `/guias` registrado en sidebar después de Configuración. Es el front-end de los manuales generados según §36. **Sin `moduloCodigo` → visible para todos los usuarios autenticados** (es material informativo, no datos protegidos).

**Archivos (`web-app/src/modules/guias/`):**
- `index.tsx` — ModuleManifest (icon: BookOpen).
- `GuiasLayout.tsx` — Layout con breadcrumb INICIO › Guías.
- `pages/GuiasIndex.tsx` — Grid de cards (auto-fill minmax 320px). Cada card abre el HTML correspondiente en pestaña nueva vía `target="_blank"` + `rel="noopener noreferrer"`.

**Sidebar vanilla (`index.html`):** item "guías" sin `data-modulo` para que sea visible para todos. Ícono SVG inline (libro abierto, `stroke-width="1.5"`).

### Cómo agregar una guía nueva

1. Generar `docs/manual_X.html` siguiendo la receta de §36 (skill `generar-manual`).
2. Agregar una entrada al array `GUIAS` en `GuiasIndex.tsx`:
   ```ts
   {
     titulo: 'NOMBRE EN UPPERCASE',
     descripcion: 'Una frase larga (~150 chars) explicando qué cubre el manual.',
     icon: SomeLucideIcon,
     htmlName: 'manual_X.html',
     audiencia: 'Operador o superior',
     tags: ['Operativo', 'N capturas', 'N secciones'],
   }
   ```
3. **No requiere tocar:** module manifest, sidebar vanilla, typecheck, ni rebuild manual del shell.

### Helper `urlDocs(htmlName)` — quirk de resolución de URL

El componente vive en el bundle React (`/web-app/dist/index.html#/guias`) pero los HTMLs están 2 niveles arriba en `/docs/`. El helper detecta entorno:

```ts
function urlDocs(htmlName: string): string {
  // 1. Iframe del shell vanilla (prod o local 8080): usa parent location
  if (window.self !== window.top) {
    try {
      const parentLoc = window.parent.location
      const base = parentLoc.pathname.replace(/[^/]*$/, '')
      return `${parentLoc.origin}${base}docs/${htmlName}`
    } catch { /* cross-origin fallback */ }
  }
  // 2. Standalone localhost:5173 (dev React aislado): apunta al shell vanilla local
  if (window.location.hostname === 'localhost' && window.location.port === '5173') {
    return `http://localhost:8080/docs/${htmlName}`
  }
  // 3. Standalone otros (degenerado)
  return `${window.location.origin}/docs/${htmlName}`
}
```

**Verificado en navegador** (sesión 2026-05-18) que los 3 casos resuelven correcto y los HTMLs cargan en pestaña nueva sin errores.
