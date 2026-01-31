import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: true, // Allow access from any host (needed for ngrok)
    allowedHosts: [
      '116f96a9e102.ngrok-free.app', // Your current ngrok URL
      '.ngrok-free.app', // All ngrok-free.app subdomains
      '.ngrok.io', // All ngrok.io subdomains
      'localhost'
    ],
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/twilio': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      }
    }
  },
  build: {
    outDir: '../src/static/dist',
    emptyOutDir: true,
  }
})
