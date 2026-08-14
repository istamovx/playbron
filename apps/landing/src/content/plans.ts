/**
 * Tarif narxlari — **yagona manba**. Ikkala til shu yerdan o'qiydi.
 *
 * Qiymatlar `docs/03-entitlements.md` dan olingan va u yerda "taxminiy, biznes
 * tomonidan tasdiqlanishi kerak" deb belgilangan. Yakuniy narx kelganda faqat
 * shu fayl o'zgaradi — matn fayllariga tegilmaydi.
 */

export interface PlanPrice {
  code: 'gold' | 'platinium' | 'infinite';
  /** So'm, oyiga. `null` — narx e'lon qilinmagan, o'rniga «Bog'laning». */
  month: number | null;
  /** So'm, yiliga (ikki oy tekin). */
  year: number | null;
  /** Narx ro'yxatida ajratib ko'rsatiladi. */
  featured: boolean;
}

export const PLAN_PRICES: readonly PlanPrice[] = [
  { code: 'gold', month: 490_000, year: 4_900_000, featured: false },
  { code: 'platinium', month: 990_000, year: 9_900_000, featured: true },
  { code: 'infinite', month: 1_890_000, year: 18_900_000, featured: false },
];

/** `490000` → `490 000`. Ajratgich — uzilmas probel, qatorda sinmaydi. */
export function formatSum(value: number): string {
  return String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
}
