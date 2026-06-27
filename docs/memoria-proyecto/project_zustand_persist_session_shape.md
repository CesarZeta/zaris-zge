---
name: Shape de zaris_session en localStorage — web-app vs vanilla difieren
description: localStorage['zaris_session'] en la web-app React usa shape zustand/persist {state:{accessToken,user},version:0}, mientras que frontend vanilla usa {access_token,user} plano. Helpers nuevos deben soportar ambos.
type: project
---
`localStorage['zaris_session']` tiene **dos shapes distintas según la superficie**, y un helper que toque el storage directamente debe manejar ambas o fallar de forma obvia.

**Why:** la web-app React usa `zustand/persist` con `name: 'zaris_session'`, que envuelve el state en `{state:{...},version:0}`. El frontend vanilla escribe `{access_token, user}` plano. Si un helper asume una shape, falla silencioso en la otra (sin token → 401 → redirect a login sin error visible).

**Shapes:**

```jsonc
// web-app/ (zustand-persist)
{
  "state": { "accessToken": "eyJ...", "user": { "id_usuario": 1, "nombre": "...", ... } },
  "version": 0
}

// frontend/ vanilla
{
  "access_token": "eyJ...",
  "user": { "id_usuario": 1, "nombre": "...", ... }
}
```

**How to apply:**
- Helpers que leen `zaris_session` (ej. `getToken()` en `web-app/src/lib/api.ts`) deben probar `parsed?.state?.accessToken ?? parsed?.access_token ?? null` en ese orden.
- Si vas a unificar las dos superficies en el futuro, decidir explícitamente una shape y migrar la otra. Hoy coexisten porque cada una resuelve su storage por su cuenta.
- El nombre de la clave (`'zaris_session'`) está hardcoded en `auth.ts` (web-app) y en cada módulo vanilla. Si se cambia, cambiar en ambos lados.
- El bug histórico: commit `46df578` (2026-05-10) — `getToken()` original solo soportaba la shape vanilla, las requests salían sin token en la web-app.
