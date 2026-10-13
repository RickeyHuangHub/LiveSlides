import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Classic, self-contained script: file:// must not require ES modules or fetch.
export default defineConfig({
  plugins: [react()],
  define: { 'process.env.NODE_ENV': JSON.stringify('production') },
  build: {
    outDir: 'offline-dist',
    lib: { entry: 'src/main.jsx', name: 'LiveSlidesOffline', formats: ['iife'], fileName: () => 'player.js', cssFileName: 'player' },
    cssCodeSplit: false,
    sourcemap: false,
  },
});
