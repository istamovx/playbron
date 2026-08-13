import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // pnpm monorepo'da bog'langan paket (@playbron/ui) React'ni o'z
  // node_modules'idan oladi — ikki nusxa "Invalid hook call" beradi.
  resolve: { dedupe: ['react', 'react-dom'] },
  server: {
    // Windows'da `localhost` ::1 ga bog'lanib, IPv4 mijozlar ulana olmaydi
    host: '127.0.0.1',
    port: Number(process.env.PORT ?? 5174),
    proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } },
  },
  // sourcemap yoqilsa prod statik saytda to'liq TS manbasi ochilib qoladi
  build: { outDir: 'dist', sourcemap: false },
});
