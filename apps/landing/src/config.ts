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
  console: dev ? 'http://localhost:5173' : 'https://app.playbron.uz',
  /**
   * Klub egasining ro'yxatdan o'tishi — o'sha kirish ekrani, `?signup=1`
   * bilan darhol ro'yxatdan o'tish panelida ochiladi.
   *
   * Alohida sahifa ATAYLAB yo'q: ikkinchi kirish nuqtasi «bir martalik
   * parolni almashtirmaguncha boshqa ekran ochilmaydi» darvozasi yonidan
   * aylanib o'tish yo'liga aylanardi (`docs/05-auth-redesign.md` §7.3).
   */
  signup: dev ? 'http://localhost:5173/?signup=1' : 'https://app.playbron.uz/?signup=1',
  /** Mijoz Mini App'i (brauzerda ham ochiladi). */
  miniapp: dev ? 'http://localhost:5174' : 'https://mini.playbron.uz',

  /** Mijoz boti — o'yinchilar shu yerdan bron qiladi. */
  customerBot: 'https://t.me/playbronbot',
  /** Ilova boti — xodim va klub admini ilovani shu botdan ochadi. */
  appBot: 'https://t.me/playbronappbot',

  // TODO: haqiqiy aloqa ma'lumotlari bilan almashtiring
  email: 'info@playbron.uz',
  phone: '+998 90 000 00 00',

  /** `tel:` havolasi uchun — faqat raqam. */
  phoneHref: '+998900000000',
} as const;

/** Loyiha ishga tushgan yil — copyright oralig'ining boshi. */
export const LAUNCH_YEAR = 2026;

/**
 * Yuridik shaxs nomi (MChJ / YaTT). Ro'yxatdan o'tgach shu yerga yoziladi.
 *
 * `null` bo'lsa qator umuman chiqmaydi — mavjud bo'lmagan tashkilot nomini
 * ko'rsatib bo'lmaydi.
 */
export const LEGAL_ENTITY: string | null = null;

/**
 * Hero'dagi ko'rsatkichlar.
 *
 * DIQQAT: bular ommaviy sahifada turadigan DA'VO. `null` bo'lsa o'rniga
 * chiziqcha chiqadi — o'ylab topilgan raqam qo'yilmaydi. Haqiqiy son
 * ma'lum bo'lgach faqat shu yer o'zgaradi.
 */
export const STATS: { customers: string | null; clubs: string | null } = {
  customers: null,
  clubs: null,
};
