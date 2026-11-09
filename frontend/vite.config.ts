import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);

export default defineConfig({
  base: '/portal/',
  publicDir: false,
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': 'http://127.0.0.1:8765',
      '/legacy': 'http://127.0.0.1:8765',
      '/static': 'http://127.0.0.1:8765',
    },
  },
  test: {
    root: fileURLToPath(new URL('../', import.meta.url)),
    include: ['quality/frontend/**/*.test.{ts,tsx}'],
    environment: 'jsdom',
    env: { MAP_PREDICT_TEST_ROOT: fileURLToPath(new URL('../', import.meta.url)) },
    setupFiles: ['quality/frontend/setup.ts'],
    alias: {
      react: fileURLToPath(new URL('./node_modules/react', import.meta.url)),
      'react-dom': fileURLToPath(new URL('./node_modules/react-dom', import.meta.url)),
      'react-router': require.resolve('react-router'),
      '@testing-library/react': require.resolve('@testing-library/react'),
      '@testing-library/user-event': require.resolve('@testing-library/user-event'),
      '@testing-library/dom': require.resolve('@testing-library/dom'),
      'fake-indexeddb': require.resolve('fake-indexeddb'),
    },
    restoreMocks: true,
  },
});
