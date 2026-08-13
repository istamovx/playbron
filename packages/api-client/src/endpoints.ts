import type { ApiClient } from './client';
import { toSession } from './client';
import type { AuthSession, Entitlements, Me } from './types';

/**
 * Endpoint funksiyalari. Har biri bitta backend marshrutiga mos keladi —
 * ekranlar URL yozmaydi, shu yerdan chaqiradi.
 */

// ── Auth ──────────────────────────────────────────────────────────────────

/** Mini App: `window.Telegram.WebApp.initData` bilan kirish. */
export async function signInWithInitData(
  api: ApiClient,
  initData: string,
): Promise<AuthSession> {
  const body = await api.post<AuthSession>(
    '/auth/telegram/initdata',
    { init_data: initData },
    { anonymous: true },
  );
  api.setSession(toSession(body));
  return body;
}

/** Landing: Telegram Login Widget javobi bilan kirish. */
export async function signInWithWidget(
  api: ApiClient,
  payload: Record<string, unknown>,
): Promise<AuthSession> {
  const body = await api.post<AuthSession>('/auth/telegram/widget', payload, {
    anonymous: true,
  });
  api.setSession(toSession(body));
  return body;
}

export async function signOut(api: ApiClient): Promise<void> {
  const session = api.session;
  if (session) {
    try {
      await api.post<void>('/auth/logout', { refresh_token: session.refreshToken });
    } catch {
      // Server javob bermasa ham lokal sessiya tozalanadi
    }
  }
  api.signOut();
}

// ── Me ────────────────────────────────────────────────────────────────────

export const getMe = (api: ApiClient): Promise<Me> => api.get<Me>('/me');

export const getEntitlements = (api: ApiClient): Promise<Entitlements> =>
  api.get<Entitlements>('/me/entitlements');

/** So'rov kalitlari — kesh bir joydan boshqariladi. */
export const queryKeys = {
  me: ['me'] as const,
  entitlements: (clubId: number | null) => ['me', 'entitlements', clubId] as const,
};
