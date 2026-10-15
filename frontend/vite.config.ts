import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// GeoSketch frontend build configuration.
// Tailwind v4 is wired through its Vite plugin, so there is no postcss config.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    host: true, // reachable from the phone on the same Wi-Fi while demoing
  },
  preview: {
    port: 5173,
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 900,
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      // Coverage is measured for the logic layer (pure utils, hooks and the API
      // client). Presentational React components are covered by the browser
      // smoke test (scripts/ui-smoke-test.mjs) instead of jsdom assertions.
      include: ['src/utils/**', 'src/hooks/**', 'src/services/**'],
      reporter: ['text', 'lcov'],
      // Floors are set a few points below the measured values so a small,
      // legitimate refactor does not fail the build.
      thresholds: {
        lines: 75,
        functions: 70,
        branches: 70,
        statements: 75,
      },
    },
  },
})
