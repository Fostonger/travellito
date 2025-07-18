import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    https: false,
    port: 5173,
    allowedHosts: ['biographies-steel-windsor-locate.trycloudflare.com']
  },
}); 