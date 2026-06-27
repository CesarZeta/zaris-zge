# Cómo colaboramos — trabajo por módulos

Convenciones para que dos o más personas trabajen en paralelo sin pisarse.
El arranque del entorno está en [`ONBOARDING.md`](ONBOARDING.md); las reglas de
código en [`CLAUDE.md`](CLAUDE.md).

## Ramas y push

- **`main` es la rama de producción.** Push directo a `main` está permitido
  **con todo en verde**: typecheck pasa, probado navegando, sin secretos en el
  diff. Si hay un error, un test rojo o algo que requiera criterio de otro,
  **PARÁ** y abrí un PR o avisá por el canal del equipo (memoria
  `feedback_push_directo_a_main`).
- Para trabajo grande, riesgoso, o que querés que otro mire antes de mergear,
  usá una **rama + PR**. No es obligatorio para cambios chicos y verificados,
  pero siempre es una opción válida.
- Si usás rama, una por unidad de trabajo con prefijo de tipo + módulo:
  ```
  feat/<modulo>-<descripcion-corta>      feat/vecinos-reclamo-fotos
  fix/<modulo>-<descripcion-corta>       fix/tramites-pase-destinatario
  docs/<descripcion>                     docs/onboarding
  ```
  Mantenela chica y cerca de `main`: `git fetch && git rebase origin/main`.
- **Antes de cada push a `main`:** `git fetch && git pull --rebase origin main`
  — el otro (o el bot de CI que rebuildea `dist`) pudo haber pusheado. Sin esto
  rebota por non-fast-forward.

## Coordinación entre repos

| Repo | Qué vive ahí | Quién |
|---|---|---|
| `zaris-zge` (este) | Backend FastAPI + shell vanilla + módulos React + DS | Backend / backoffice |
| `zaris-vecinos` | PWA del ciudadano (y luego la del funcionario) | App móvil |

La PWA **consume el backend de `zaris-zge`** vía `/api/v1/publico/*`. Si un
cambio en la PWA necesita un endpoint nuevo o un campo nuevo en la respuesta,
ese cambio es **backend, va en `zaris-zge`** y se mergea primero. Coordinar el
contrato (shape del JSON) antes de implementar las dos puntas.

### Deploy: no hace falta tocar Vercel

La PWA (`zaris-vecinos`) deploya en **Vercel automáticamente** al pushear a `main`
del repo. **No necesitás ser miembro de Vercel para desarrollar** — tu acceso
`write` al repo de GitHub alcanza: codeás en local, pusheás, y Vercel deploya solo.
Sumar miembros a Vercel tiene costo (plan pago) y no aporta al desarrollo, así que
**no se hace por defecto**. Las tareas que sí requieren Vercel (ver logs de runtime,
cambiar env vars como `VITE_API_URL`, tocar dominio/config del proyecto) las hace el
dueño del proyecto Vercel; si necesitás un log de prod o un cambio de env var,
pedíselo. Mismo modelo para el backend (`zaris-zge` deploya en Railway al pushear) y
para cualquier app nueva a futuro: repo → deploy automático, sin sumar a todos a la
plataforma de hosting.

## Evitar choques (lo que más duele con varias personas)

1. **`web-app/dist/` lo rebuildea CI.** No edites el `dist` a mano salvo
   necesidad real. Tras pushear algo que toca `web-app/**`, CI commitea
   `build(web-app): publicar dist [skip ci]` a `main` ~1-2 min después. Antes
   de tu próximo push: `git fetch && git pull --rebase origin main`, o rebota
   por non-fast-forward (CLAUDE.md §32).

2. **Numeración de migraciones.** Cada migración nueva es un archivo en
   `backend/migrations/` con número correlativo. **La última usada es la 91;
   usá 92+.** Si dos personas crean la 92 en paralelo, una tiene que renumerar.
   Avisá qué número tomaste, o reservalo antes de empezar.

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

## Antes de pushear a `main` (o abrir el PR)

- [ ] `cd web-app && pnpm typecheck` pasa (si tocaste React).
- [ ] Probado navegando, no solo leído.
- [ ] Sin secretos ni `.env` en el diff.
- [ ] Migración (si la hay) numerada 92+ y aplicada en local + prod.
- [ ] `git pull --rebase origin main` hecho (estás al día con el otro y con CI).
- [ ] Si algo está rojo o requiere criterio ajeno: PARÁ, no pushees a `main`.
