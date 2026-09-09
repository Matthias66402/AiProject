import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    // Läuft im Docker-Container gegen einen Windows-Bind-Mount (./frontend) - inotify
    // erkennt dort Änderungen vom Host oft nicht zuverlässig, daher Polling statt
    // Dateisystem-Events für den Watcher.
    watch: {
      usePolling: true,
      interval: 300,
    },
  },
})
