import { ApiClient, browserStore } from '@playbron/api-client';

/**
 * Mini App uchun API mijozi.
 *
 * Sessiya `sessionStorage` da: Telegram har ochilishda yangi `initData` beradi,
 * shuning uchun uzoq saqlashning ma'nosi yo'q — ilova qayta ochilganda sessiya
 * jimgina qaytadan olinadi.
 */

const DEFAULT_BASE = 'http://127.0.0.1:8000/api/v1';

export const apiBaseUrl: string =
  (import.meta.env['VITE_API_URL'] as string | undefined) ?? DEFAULT_BASE;

export const api = new ApiClient({
  baseUrl: apiBaseUrl,
  store: browserStore('playbron.session', sessionStorage),
});
