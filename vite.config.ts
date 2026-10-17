import { defineConfig } from 'vite';

export default defineConfig({
  base: './',
  build: { chunkSizeWarningLimit: 650 },
  server: { port: 5173, strictPort: true },
});
