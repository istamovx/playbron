import { ApiClient, browserStore } from '@playbron/api-client';

import { useBoard } from '../store/board';

/**
 * Konsol uchun API mijozi.
 *
 * Sessiya `localStorage` da: brauzer tab'ini yopib qayta ochish normal holat.
 * Faol klub `X-Club-Id` sarlavhasida ketadi — backend RLS kontekstini shundan oladi.
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
  store: browserStore('playbron.session', localStorage),
  clubId: () => useBoard.getState().activeClubId,
  // Refresh tokeni HttpOnly cookie'da (audit §10, `pb_staff_refresh` —
  // `api/src/playbron/modules/auth/router.py`) — `localStorage`da endi
  // faqat access token va muddat belgilari, XSS orqali sessiya butunlay
  // o'g'irlanmaydi (faqat qisqa muddatli access token bilan cheklanadi).
  cookieRefresh: true,
});
