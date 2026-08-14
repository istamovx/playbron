import type { APIRoute } from 'astro';

/**
 * `robots.txt` statik fayl emas, chunki undagi sitemap manzili sayt manzili
 * bilan bir xil bo'lishi shart. `public/` dagi qo'lda yozilgan nusxa domen
 * o'zgarganda eskirib qolardi.
 */
export const GET: APIRoute = ({ site }) => {
  const sitemap = new URL('sitemap-index.xml', site).href;

  return new Response(`User-agent: *\nAllow: /\n\nSitemap: ${sitemap}\n`, {
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  });
};
