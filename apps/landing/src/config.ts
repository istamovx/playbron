/**
 * Tashqi manzillar — yagona joy.
 *
 * DIQQAT: `phone` va `email` hozircha o'rinbosar qiymat. Haqiqiysi kelganda
 * faqat shu fayl o'zgaradi.
 */
/**
 * Lokalda ilova va Mini App dev serverlariga yo'naltiriladi — aks holda
 * landing'dagi tugmalar ishlab chiqish paytida prod manzillariga olib ketadi
 * va aylanma yo'l (landing → ilova → landing) sinadi.
 */
const dev = import.meta.env.DEV;

export const SITE = {
  url: 'https://playbron.uz',

  /** Xodim va klub admini ilovasi. */
  console: dev ? 'http://localhost:5173' : 'https://playbron-admin.onrender.com',
  /** Mijoz Mini App'i (brauzerda ham ochiladi). */
  miniapp: dev ? 'http://localhost:5174' : 'https://playbron-miniapp.onrender.com',

  /** Mijoz boti — o'yinchilar shu yerdan bron qiladi. */
  customerBot: 'https://t.me/playbronbot',
  /** Konsol boti — klub egasi va xodim shu orqali kiradi va yozadi. */
  adminBot: 'https://t.me/playbronadminbot',

  // TODO: haqiqiy aloqa ma'lumotlari bilan almashtiring
  email: 'info@playbron.uz',
  phone: '+998 90 000 00 00',

  /** `tel:` havolasi uchun — faqat raqam. */
  phoneHref: '+998900000000',
} as const;

export const LAUNCH_YEAR = 2026;
