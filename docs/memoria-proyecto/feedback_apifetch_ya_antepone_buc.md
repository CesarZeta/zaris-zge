---
name: feedback_apifetch_ya_antepone_buc
description: ZUtils.apiFetch (frontend vanilla) ya antepone API_BUC que termina en /buc; no pasar /buc en el endpoint
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a44a6e1e-1317-4ec7-9553-e4b9b5a3579f
---

En los módulos vanilla, `ZUtils.apiFetch(endpoint)` (en `frontend/js/config.js`) construye la URL como `API_BUC + endpoint`, y `API_BUC` **ya termina en `/api/v1/buc`**. Entonces el `endpoint` debe ser **relativo a `/buc`**, sin repetirlo.

- Correcto: `apiFetch('/usuarios/5')` → `.../api/v1/buc/usuarios/5`
- Correcto: `apiFetch('/subareas/buscar?q=x')` → `.../api/v1/buc/subareas/buscar?q=x`
- MAL: `apiFetch('/buc/subareas/buscar')` → `.../api/v1/buc/buc/subareas/buscar` → **404 silencioso**

**Why:** un endpoint backend que vive en `/api/v1/buc/<x>` se llama desde el front vanilla como `apiFetch('/<x>')`, NO `apiFetch('/buc/<x>')`. El doble `/buc` da 404 que el usuario solo ve como "Sin resultados"/"Error: Not Found" en el dropdown — no rompe ruidosamente.

**How to apply:** al agregar un endpoint nuevo bajo el router BUC y consumirlo desde un módulo vanilla, omitir el segmento `/buc` en la llamada. Cazado 2026-05-22 en el buscador predictivo de subáreas de Usuarios; solo se detectó al verificar en navegador (refuerza [[feedback_verificar_forms_navegando_mandatorio]] y [[feedback_verificar_forms_navegando_mandatorio]]). Si el módulo es React, no aplica: ahí se usa `web-app/src/lib/api.ts` con paths absolutos `/api/v1/...` (ver [[feedback_entityselect_path_no_url]] para el quirk inverso de ese helper).
