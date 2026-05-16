import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// base: el shell React se publica bajo /web-app/dist/ (dominio propio zge.zaris.com.ar)
// En dev (`pnpm dev`), base sigue siendo '/' para que localhost:5173 funcione.
export default defineConfig(({ command }) => ({
  plugins: [react()],
  base: command === 'build' ? '/web-app/dist/' : '/',
}))
