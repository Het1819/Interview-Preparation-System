import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// `base` defaults to '/' for root-domain deploys.
// When the deployment path is decided, set VITE_BASE_URL in your CI/CD
// environment (e.g. '/app/' for https://example.com/app/).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const base = env.VITE_BASE_URL || '/';
  const apiTarget = env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

  return {
    base,
    plugins: [react()],
    server: {
      port: 5173,
      host: '0.0.0.0',
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
    build: {
      target: 'es2020',
      sourcemap: false,            // flip to true for staging builds
      chunkSizeWarningLimit: 500,
      rollupOptions: {
        output: {
          manualChunks: {
            'react-vendor': ['react', 'react-dom'],
            'icons': ['lucide-react'],
          },
        },
      },
    },
    preview: {
      port: 4173,
      host: '0.0.0.0',
    },
  };
});
