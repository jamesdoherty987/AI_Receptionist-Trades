import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { readFileSync, writeFileSync } from 'fs'
import { resolve } from 'path'

// Plugin to stamp sw.js with a unique build hash on every build
function swVersionStamp() {
  return {
    name: 'sw-version-stamp',
    writeBundle() {
      const swPath = resolve('dist', 'sw.js');
      try {
        let sw = readFileSync(swPath, 'utf-8');
        const buildId = Date.now().toString(36);
        sw = sw.replace(/bfy-cache-v[\w.]+/g, `bfy-cache-${buildId}`);
        sw = sw.replace(/bfy-runtime-v[\w.]+/g, `bfy-runtime-${buildId}`);
        writeFileSync(swPath, sw);
      } catch {}
    }
  };
}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), swVersionStamp()],
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
    // Build to 'dist' inside frontend folder for Vercel
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks: {
          // Split heavy deps into separate cacheable chunks
          'vendor-charts': ['recharts'],
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
        },
      },
    },
  }
})
