import path from 'node:path';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      include: ['src/features/**', 'src/lib/**'],
      exclude: ['**/*.test.*', '**/index.ts', 'src/api/schema.d.ts'],
      thresholds: { lines: 80 },
      reporter: ['text', 'lcov'],
    },
  },
});
