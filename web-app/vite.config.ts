import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// base: el shell React se publica en GitHub Pages bajo
// https://cesarzeta.github.io/zaris-zge/web-app/
// Vite necesita el base path para resolver assets (CSS, JS, fonts).
// En dev (`pnpm dev`), base sigue siendo '/' para que localhost:5173 funcione.
export default defineConfig(({ command }) => ({
  plugins: [react()],
  base: command === 'build' ? '/zaris-zge/web-app/dist/' : '/',
}))
