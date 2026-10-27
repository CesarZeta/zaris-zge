// Prueba de raizDelSitio (web-app/src/lib/shellNav.ts): la raiz del shell sale de la ruta, sin suponer
// que el sitio vive bajo un primer segmento (/zaris-zge/ en GitHub Pages) ni en la raiz del dominio
// (Cloudflare Pages, subdominios de municipio).
//   node tools/test_shell_nav.mjs        (Node >= 23: importa el .ts quitando los tipos)
import assert from 'node:assert/strict'
import { raizDelSitio } from '../web-app/src/lib/shellNav.ts'

const casos = [
  // shell padre
  ['/index.html', '/'],
  ['/', '/'],
  ['/zaris-zge/index.html', '/zaris-zge/'],
  ['/zaris-zge/', '/zaris-zge/'],
  // bundle React (fallback standalone)
  ['/web-app/dist/index.html', '/'],
  ['/zaris-zge/web-app/dist/index.html', '/zaris-zge/'],
  // modulo vanilla
  ['/frontend/admin_tablas.html', '/'],
  ['/zaris-zge/frontend/login.html', '/zaris-zge/'],
]
for (const [ruta, esperado] of casos) {
  assert.equal(raizDelSitio(ruta), esperado, ruta)
}
console.log(`OK ${casos.length}/${casos.length}`)
