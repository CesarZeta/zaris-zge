#!/usr/bin/env bash
# Build del shell para Cloudflare Pages (proyecto zaris-zge; configuración en docs/cloudflare_pages.md).
#   Comando de build: bash tools/cloudflare_pages_build.sh   ·   Directorio de salida: _site
# Buildea web-app y arma _site/ con lo que sirve el shell, en las mismas rutas que GitHub Pages:
# index.html, frontend/, design-system/, docs/, landing/ y web-app/dist/. El resto del repo
# (backend, sql, planes, CSV) NO se publica.
set -euo pipefail
cd "$(dirname "$0")/.."

(cd web-app && pnpm install --frozen-lockfile && pnpm build)

rm -rf _site
mkdir -p _site/web-app
cp index.html _site/
cp -r frontend design-system docs landing _site/
cp -r web-app/dist _site/web-app/dist

# Con un 404.html en la raíz, Pages NO trata el sitio como SPA: una ruta inexistente da 404
# en lugar de servir el shell (que dentro del iframe mostraría un shell anidado).
cat > _site/404.html <<'HTML'
<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ZARIS · Página no encontrada</title>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#f2f1ed;color:#26251e;
font-family:system-ui,sans-serif}main{text-align:center;padding:16px}a{color:#f54e00}</style></head>
<body><main><h1>Página no encontrada</h1><p><a href="/index.html">Ir al inicio de ZARIS</a></p></main></body></html>
HTML

echo "_site listo: $(find _site -type f | wc -l) archivos"
