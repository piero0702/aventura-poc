import { loadEnv } from 'vite';
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const entorno = loadEnv(mode, process.cwd(), 'VITE_');
  return {
    plugins: [react()],
    server: {
      port: 5173,
      strictPort: true,
      watch: { usePolling: true, interval: 200 },
      fs: { strict: true, allow: [process.cwd()] },
      proxy: {
        '/api': {
          target: entorno.VITE_MOTOR_URL || 'http://127.0.0.1:8000',
          changeOrigin: true,
          rewrite: (ruta) => ruta.replace(/^\/api/, ''),
        },
      },
    },
    test: { environment: 'jsdom', globals: true, setupFiles: ['./src/pruebas.configuracion.ts'] },
  };
});
