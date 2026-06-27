# Cómo colaboramos — trabajo por módulos

Convenciones para que dos o más personas trabajen en paralelo sin pisarse.
El arranque del entorno está en [`ONBOARDING.md`](ONBOARDING.md); las reglas de
código en [`CLAUDE.md`](CLAUDE.md).

## Ramas y PRs

- **`main` es la rama de producción.** No se pushea directo: todo entra por
  **Pull Request**.
- Una rama por unidad de trabajo, con prefijo de tipo + módulo:
  ```
  feat/<modulo>-<descripcion-corta>      feat/vecinos-reclamo-fotos
  fix/<modulo>-<descripcion-corta>       fix/tramites-pase-destinatario
  docs/<descripcion>                     docs/onboarding
  ```
- Mantené la rama chica y cerca de `main`: `git fetch && git rebase origin/main`
  seguido, así el PR no acumula conflictos.
- En el PR: descripción de qué cambia, cómo se probó, y si tocó backend cuál
  endpoint/migración. Quien revisa mira que pase typecheck y que no haya `.env`
  ni secretos en el diff.

## Coordinación entre repos

| Repo | Qué vive ahí | Quién |
|---|---|---|
| `zaris-zge` (este) | Backend FastAPI + shell vanilla + módulos React + DS | Backend / backoffice |
| `zaris-vecinos` | PWA del ciudadano (y luego la del funcionario) | App móvil |

La PWA **consume el backend de `zaris-zge`** vía `/api/v1/publico/*`. Si un
cambio en la PWA necesita un endpoint nuevo o un campo nuevo en la respuesta,
ese cambio es **backend, va en `zaris-zge`** y se mergea primero. Coordinar el
contrato (shape del JSON) antes de implementar las dos puntas.

## Evitar choques (lo que más duele con varias personas)

1. **`web-app/dist/` lo rebuildea CI.** No edites el `dist` a mano salvo
   necesidad real. Tras pushear algo que toca `web-app/**`, CI commitea
   `build(web-app): publicar dist [skip ci]` a `main` ~1-2 min después. Antes
   de tu próximo push: `git fetch && git pull --rebase origin main`, o rebota
   por non-fast-forward (CLAUDE.md §32).

2. **Numeración de migraciones.** Cada migración nueva es un archivo en
   `migrations/` con número correlativo. **La última usada es la 91; usá 92+.**
   Si dos ramas crean la 92, una tiene que renumerar al mergear. Avisá en el PR
   qué número tomaste, o reservá el número antes de empezar.

3. **Aplicá migraciones en local Y prod en la misma sesión** (CLAUDE.md §24),
   nunca solo en una — se desincronizan. Backup antes de UPDATE/DELETE masivos
   en prod.

4. **No edites `CLAUDE.md` y código en el mismo commit** si podés evitarlo —
   facilita el review y los rebases.

## Seguridad — innegociable

- **El repo es público** (se sirve bajo `zge.zaris.com.ar`). Todo lo commiteado
  queda publicado. Antes de `git add`: ¿hay algún secreto, `.env`, dump de DB,
  o reporte de QA con un PoC explotable? Si sí, no va (CLAUDE.md §40, §6).
- Secretos solo en Railway/Supabase/Vercel (variables de entorno), nunca en el
  código ni en el `.env.example` (ahí solo placeholders).
- Datos reales de los municipios (DNIs, domicilios, salud) están bajo Ley
  25.326. No los copies a local ni los pegues en chats/issues.

## Antes de abrir el PR

- [ ] `cd web-app && pnpm typecheck` pasa (si tocaste React).
- [ ] Probado navegando, no solo leído.
- [ ] Sin secretos ni `.env` en el diff.
- [ ] Migración (si la hay) numerada 92+ y aplicada en local + prod.
- [ ] Rama rebaseada sobre `origin/main`.
