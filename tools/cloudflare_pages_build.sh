#!/usr/bin/env bash
# Build del shell para Cloudflare Pages (proyecto zaris-zge; configuración en docs/cloudflare_pages.md).
#   Comando de build: bash tools/cloudflare_pages_build.sh   ·   Directorio de salida: _site
# Buildea web-app y arma _site/ con lo que sirve el shell, en las mismas rutas que GitHub Pages:
# index.html, frontend/, design-system/, docs/, landing/ y web-app/dist/. El resto del repo
# (backend, sql, planes, CSV) NO se publica.
set -euo pipefail
cd "$(dirname "$0")/.."

# Versión de la publicación (PLAN_VERSIONADO.md): fecha y hora de Argentina del build, más el
# commit. La lee el shell (frontend/js/version.js) y la compara con /version.json para avisar
# que hay una versión nueva; el bundle React la recibe por VITE_APP_VERSION.
COMMIT="${CF_PAGES_COMMIT_SHA:-$(git rev-parse HEAD 2>/dev/null || echo '')}"
COMMIT="${COMMIT:0:7}"
VERSION="$(TZ=America/Argentina/Buenos_Aires date +%Y.%m.%d.%H%M)"
export VITE_APP_VERSION="$VERSION" VITE_APP_COMMIT="$COMMIT"

(cd web-app && pnpm install --frozen-lockfile && pnpm build)

rm -rf _site
mkdir -p _site/web-app
cp index.html _site/
# Con un 404.html en la raíz, Pages NO trata el sitio como SPA: una ruta inexistente da 404
# en lugar de servir el shell (que dentro del iframe mostraría un shell anidado).
cp 404.html _site/
cp -r frontend design-system docs landing _site/
cp -r web-app/dist _site/web-app/dist

printf "window.ZARIS_VERSION = { version: '%s', commit: '%s' };\n" "$VERSION" "$COMMIT" > _site/frontend/js/version.js
printf '{"version":"%s","commit":"%s"}\n' "$VERSION" "$COMMIT" > _site/version.json
echo "Versión $VERSION ($COMMIT)"

echo "_site listo: $(find _site -type f | wc -l) archivos"
