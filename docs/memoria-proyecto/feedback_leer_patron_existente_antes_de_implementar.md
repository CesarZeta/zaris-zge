---
name: feedback_leer_patron_existente_antes_de_implementar
description: "Antes de implementar un manifest/layout/wrapper de módulo React, leer el tipo real y un módulo existente. El contrato de ModuleManifest no siempre coincide con lo que el prompt externo asume."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f84d7548-b002-463d-8332-dbf8d5375172
---

Al crear un módulo React nuevo, leer `src/lib/types.ts` y un módulo existente como referencia ANTES de escribir el `index.tsx`.

**Por qué:** en la sesión 2026-05-16 (módulo Trámites) se cometieron 3 errores seguidos que se hubieran evitado con 2 lecturas previas:

1. `icon: <FileText .../>` (JSX) → correcto: `icon: FileText` (el componente sin instanciar). `ModuleManifest.icon` es `LucideIcon`, no `React.ReactNode`.
2. Campos inexistentes `basePath` y `layout` en el manifest → no existen en la interfaz real.
3. `TramitesLayout` con `<Outlet />` (patrón nested routes) → correcto: `{ children: ReactNode }` con `Wrap(Component)`.

**Cómo aplicar:** antes de escribir `index.tsx` de un módulo nuevo, ejecutar mentalmente este checklist:
- Leer `src/lib/types.ts` → campo `icon`, campos que existen/no existen.
- Abrir `src/modules/reclamos/index.tsx` → copiar el patrón `Wrap(Component)` y la forma del objeto.
- Abrir `src/modules/reclamos/ReclamosLayout.tsx` → confirmar que el layout recibe `{ children: ReactNode }`, no `<Outlet />`.

El patrón correcto resumido:
```tsx
const Wrap = (Component: React.FC) => () => (
  <MiLayout>
    <Component />
  </MiLayout>
)

export const miModule: ModuleManifest = {
  id: 'mi-modulo',
  label: 'mi módulo',
  icon: FileText,          // componente, no JSX
  moduloCodigo: 'mi_modulo',
  routes: [
    { index: true, element: Wrap(Vista) },
    { path: 'nuevo',  element: Wrap(CrearVista) },
    { path: ':param', element: Wrap(DetalleVista) },
  ],
}
```

**Relacionado con:** [[feedback_verificar_forms_navegando_mandatorio]] (verificar en navegador), [[feedback_verificar_pendientes_antes_de_atacar]] (verificar contra el código real antes de asumir).
