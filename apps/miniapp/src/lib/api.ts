import { ApiClient, browserStore } from '@playbron/api-client';

/**
 * Mini App uchun API mijozi.
 *
 * Sessiya `sessionStorage` da: Telegram har ochilishda yangi `initData` beradi,
 * shuning uchun uzoq saqlashning ma'nosi yo'q — ilova qayta ochilganda sessiya
 * jimgina qaytadan olinadi.
 */

const DEFAULT_BASE = 'http://127.0.0.1:8000/api/v1';

const envApiUrl = import.meta.env['VITE_API_URL'] as string | undefined;

// Production buildda `VITE_API_URL` yo'qligi jimgina localhost fallback'ga
// tushishi mumkin emas — foydalanuvchi brauzeri o'z kompyuteridagi
// 127.0.0.1'ga murojaat qilib qoladi. Dev serverda fallback normal holat.
if (import.meta.env.PROD && !envApiUrl) {
  throw new Error(
    'VITE_API_URL sozlanmagan — production build localhost API bilan yig‘ilishi mumkin emas.'
  );
}

export const apiBaseUrl: string = envApiUrl ?? DEFAULT_BASE;

export const api = new ApiClient({
  baseUrl: apiBaseUrl,
  store: browserStore('playbron.session', sessionStorage),
});
