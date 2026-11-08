import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    // React에서 /api로 요청하면 개발 서버가 Flask로 전달합니다.
    proxy: {
      '/api': 'http://127.0.0.1:5001',
    },
  },
})
