import { ApiClient, browserStore } from '@playbron/api-client';

import { useBoard } from '../store/board';

/**
 * Konsol uchun API mijozi.
 *
 * Sessiya `localStorage` da: brauzer tab'ini yopib qayta ochish normal holat.
 * Faol klub `X-Club-Id` sarlavhasida ketadi — backend RLS kontekstini shundan oladi.
 */

const DEFAULT_BASE = 'http://127.0.0.1:8000/api/v1';

export const apiBaseUrl: string =
  (import.meta.env['VITE_API_URL'] as string | undefined) ?? DEFAULT_BASE;

export const api = new ApiClient({
  baseUrl: apiBaseUrl,
  store: browserStore('playbron.session', localStorage),
  clubId: () => useBoard.getState().activeClubId,
});
