import type { ScreenId } from './mock/data';

/**
 * Ekran ↔ URL. Router kiritilishining sababi vizual emas:
 *   • Click/Payme to'lovdan `return_url` ga qaytadi — ilinadigan manzil kerak;
 *   • brauzerning «orqaga» tugmasi ishlashi kerak;
 *   • bo'limga to'g'ridan-to'g'ri havola yuborish (masalan botdan) kerak;
 *   • route guard shu qatlamda yoziladi.
 */

export const SCREEN_PATH: Record<ScreenId, string> = {
  // Xodim
  live: '/live',
  timeline: '/timeline',
  orders: '/orders',
  pos: '/pos',
  shift: '/shift',
  blacklist: '/blacklist',
  // Klub admini
  dashboard: '/dashboard',
  staff: '/staff',
  club: '/club',
  products: '/products',
  reports: '/reports',
  expenses: '/expenses',
  settings: '/settings',
};

const PATH_SCREEN = new Map<string, ScreenId>(
  Object.entries(SCREEN_PATH).map(([screen, path]) => [path, screen as ScreenId]),
);

export const pathOf = (screen: ScreenId): string => SCREEN_PATH[screen];

/** Noma'lum manzil — `null`, chaqiruvchi rolga mos boshlang'ich ekranga yo'naltiradi. */
export function screenOf(pathname: string): ScreenId | null {
  const clean = pathname.replace(/\/+$/, '') || '/';
  return PATH_SCREEN.get(clean) ?? null;
}
