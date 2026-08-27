import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Mode styling murni (frontend saja, tanpa backend) berjalan apa adanya —
// client.js jatuh ke mock lokal di /mock/*.json. Mode integrasi: isi
// VITE_API_BASE di .env.local, mis. VITE_API_BASE=http://127.0.0.1:8000
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
  },
})
