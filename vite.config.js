import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'path'

export default defineConfig({
  plugins: [
    tailwindcss(),
  ],
  root: resolve('./frontend/assets'),
  base: '/static/dist/',
  build: {
    manifest: true,
    outDir: resolve('./frontend/static/dist'),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: resolve('./frontend/assets/main.js'),
      },
    },
  },
  server: {
    host: 'localhost',
    port: 5173,
    origin: 'http://localhost:5173',
  },
})
