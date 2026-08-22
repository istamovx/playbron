import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ command, mode }) => {
  // `lib/api.ts` bu tekshiruvni RUNTIME'da (brauzerda) ham qiladi, lekin
  // shu yerdagi qadam BUILD'ning o'zini to'xtatadi — audit talabi ("missing
  // VITE_API_URL → build FAIL") aynan shu, faqat brauzerda keyinroq
  // yiqilishi emas. Dev serverda (`vite`) tekshirilmaydi — lokal `.env`
  // shart emas, `DEFAULT_BASE` fallback ishlayveradi.
  if (command === 'build' && !loadEnv(mode, process.cwd(), 'VITE_').VITE_API_URL) {
    throw new Error(
      'VITE_API_URL sozlanmagan — production build localhost API bilan yig‘ilishi mumkin emas.',
    );
  }

  return {
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
  };
});
