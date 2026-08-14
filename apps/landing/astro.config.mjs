// @ts-check
import sitemap from '@astrojs/sitemap';
import { defineConfig } from 'astro/config';

/**
 * PlayBron landing — to'liq statik, mijoz tomonida JS yo'q.
 *
 * React qo'shilmagan: DS komponentlari React'da, lekin landing'ga faqat ularning
 * **tokenlari** kerak (`@playbron/ui/styles.css`). Barcha bo'lim oddiy HTML +
 * CSS bilan yig'ilgan — natijada sahifa nol bayt JS bilan yuklanadi, hover va
 * animatsiyalar esa CSS ustida ishlaydi.
 *
 * Tillar: `uz` — sukut (`/`), `ru` — `/ru`. Har biri alohida sahifa fayli;
 * sitemap ikkalasini `hreflang` bilan bog'laydi.
 */
export default defineConfig({
  // Canonical, hreflang va sitemap shu manzildan yasaladi. Domen ulanmaguncha
  // Render `SITE_URL` ni o'z manziliga qo'yadi — aks holda qidiruv tizimiga
  // «asl sahifa playbron.uz da» deb aytamiz, u yer esa hali ochilmaydi.
  site: process.env.SITE_URL || 'https://playbron.uz',
  trailingSlash: 'ignore',
  build: { format: 'directory' },

  i18n: {
    defaultLocale: 'uz',
    locales: ['uz', 'ru'],
    routing: { prefixDefaultLocale: false },
  },

  integrations: [
    sitemap({
      i18n: {
        defaultLocale: 'uz',
        locales: { uz: 'uz-UZ', ru: 'ru-RU' },
      },
    }),
  ],

  vite: {
    // Workspace paketi manba TS holida keladi — Vite uni o'zi transpil qiladi
    ssr: { noExternal: ['@playbron/ui'] },
  },
});
