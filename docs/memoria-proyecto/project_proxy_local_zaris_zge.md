---
name: proxy-local-zaris-zge
description: "Receta para probar el shell vanilla + bundle React embebido en iframe en local, sin GH Pages. El bundle dist tiene base /zaris-zge/ que rompe en localhost normal."
metadata: 
  node_type: memory
  type: project
  originSessionId: a511bbae-7e29-4cf5-a153-a13a6c1bd56c
---

`web-app/vite.config.ts` setea `base: '/zaris-zge/web-app/dist/'` para que GH Pages sirva los assets desde la ruta correcta. En GH Pages funciona porque el repo se sirve bajo `/zaris-zge/`. **En local, `python -m http.server 8080` sirve desde la raiz del repo SIN prefijo**, asi que `http://localhost:8080/web-app/dist/index.html` carga el HTML pero los assets dan 404.

## Receta de proxy local

Script `_serve_local_pages.py` (no commiteado, lo creas y borras por sesion):

```python
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))  # raiz del repo
PREFIX = "/zaris-zge/"
PORT = 8090


class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        path = path.split("?", 1)[0].split("#", 1)[0]
        if path.startswith(PREFIX):
            path = "/" + path[len(PREFIX):]
        elif path == "/zaris-zge":
            path = "/"
        return os.path.join(ROOT, path.lstrip("/").replace("/", os.sep))


def main():
    os.chdir(ROOT)
    with ThreadingHTTPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"serving {ROOT} at http://localhost:{PORT}{PREFIX}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
```

Levantarlo: `python _serve_local_pages.py` desde la raiz del repo. Abrir `http://localhost:8090/zaris-zge/index.html`.

> **El proxy NO manda headers no-cache.** `SimpleHTTPRequestHandler` sirve con cache HTTP estandar, asi que el browser (incluido el browser-MCP) reusa bundles JS/CSS viejos de forma agresiva. Tras un rebuild del `dist/`, el browser puede seguir ejecutando el bundle anterior. **Siempre cache-bustear la URL al navegar despues de un rebuild** (`?_t=<timestamp>`) y `localStorage.clear()` antes de reloguear. Sintoma clasico: rebuildeas el dist contra local pero el iframe sigue pegando a prod -> login rebota. Ver [[feedback_browser_mcp_iframe_cache]] seccion "el bundle cacheado apunta a OTRO entorno". Si te molesta, podes agregar `self.send_header("Cache-Control", "no-store")` en `end_headers()` del Handler.

## Setup adicional

1. **CORS:** agregar `http://localhost:8090` a `allow_origins` en `backend/app/main.py` y reiniciar uvicorn.
2. **Bundle dist:** en local apuntara al `VITE_API_BASE` que tenga compilado. Si lo necesitas contra backend local, rebuildear con `pnpm build --mode development` (toma `.env.development` que apunta a `127.0.0.1:8000`). **No commitear ese dist** — antes del commit, rebuildear sin `--mode` para que tome `.env.production` (Railway).
3. **Login:** el shell vanilla redirige a `frontend/login.html` si no hay sesion. Mismo origen 8090, pero la sesion no se comparte con 8080. Loguearse de nuevo.

## Cleanup post-sesion

- Borrar `_serve_local_pages.py`.
- Bajar el server background.
- Rebuildear `web-app/dist/` en modo prod si lo tocaste.
- Revertir o dejar `localhost:8090` en CORS (es inocuo, no afecta prod).

## Cuando usar esta receta

- Validar que el shell vanilla embebe correctamente un modulo React (incluyendo guards, redirects, comunicacion `window.parent.shellNavigate`).
- Probar el bundle compilado tal cual se va a servir en prod, antes de hacer push.
- Reproducir bugs especificos de GH Pages que no aparecen en `pnpm dev` (cache, base path, hash routing).

Para iteracion rapida normal: usar `localhost:5173` (vite dev) standalone, no esto.
