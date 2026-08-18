import type { ScreenId } from './mock/data';

/**
 * Ekran ↔ URL. Router kiritilishining sababi vizual emas:
 *   • Click/Payme to'lovdan `return_url` ga qaytadi — ilinadigan manzil kerak;
 *   • brauzerning «orqaga» tugmasi ishlashi kerak;
 *   • bo'limga to'g'ridan-to'g'ri havola yuborish (masalan botdan) kerak;
 *   • route guard shu qatlamda yoziladi.
 */

/** `mock/data.ts::ScreenId` ning taxallusi — ekran turlari o'sha yerda. */
export type AppScreenId = ScreenId;

export const SCREEN_PATH: Record<AppScreenId, string> = {
  // Xodim
  live: '/live',
  timeline: '/timeline',
  orders: '/orders',
  bookings: '/bookings',
  pos: '/pos',
  shift: '/shift',
  blacklist: '/blacklist',
  // Klub admini
  dashboard: '/dashboard',
  staff: '/staff',
  products: '/products',
  reports: '/reports',
  expenses: '/expenses',
  pricing: '/pricing',
  settings: '/settings',
  // Super admin
  platform: '/platform',
  'platform-clubs': '/platform/clubs',
  'platform-report': '/platform/report',
  'platform-logs': '/platform/logs',
  'platform-settings': '/platform/settings',
};

const PATH_SCREEN = new Map<string, AppScreenId>(
  Object.entries(SCREEN_PATH).map(([screen, path]) => [path, screen as AppScreenId]),
);

export const pathOf = (screen: AppScreenId): string => SCREEN_PATH[screen];

/** Noma'lum manzil — `null`, chaqiruvchi rolga mos boshlang'ich ekranga yo'naltiradi. */
export function screenOf(pathname: string): AppScreenId | null {
  const clean = pathname.replace(/\/+$/, '') || '/';
  return PATH_SCREEN.get(clean) ?? null;
}
