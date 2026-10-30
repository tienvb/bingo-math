/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const target = process.env.VITE_PROXY_TARGET || 'http://localhost:8000'
// Bật polling khi source được mount vào container (inotify không qua được bind mount trên macOS/Windows)
const isTrue = (v?: string) => v === 'true' || v === '1'
const usePolling = isTrue(process.env.VITE_USE_POLLING) || isTrue(process.env.CHOKIDAR_USEPOLLING)

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    watch: usePolling ? { usePolling: true, interval: 300 } : undefined,
    proxy: {
      '/api': { target, changeOrigin: true },
      '/ws': { target, ws: true, changeOrigin: true },
      '/avatars': { target, changeOrigin: true },
    },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
})
