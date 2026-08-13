import { ApiError, errorText, signOut as apiSignOut, toSession } from '@playbron/api-client';
import { create } from 'zustand';

import { api } from '../lib/api';

/**
 * Konsol sessiyasi — **faqat Telegram**. Parol yo'q, login yo'q.
 *
 * Manba — backend: `/auth/telegram/widget` (Login Widget) yoki lokal ishlab
 * chiqishda `/auth/dev/login`. Sessiya `@playbron/api-client` ichida saqlanadi,
 * bu store faqat UI ko'radigan qismini ushlab turadi.
 */

export type Role = 'STAFF' | 'CLUB_ADMIN' | 'SUPER_ADMIN';

export const ROLE_LABEL: Record<Role, string> = {
  STAFF: 'Xodim',
  CLUB_ADMIN: 'Klub admini',
  SUPER_ADMIN: 'Super admin',
};

/** Kirish qaysi bot orqali ishlaydi (`@` siz) — deep-link shu nomga ochiladi. */
export const TELEGRAM_LOGIN_BOT: string =
  (import.meta.env['VITE_TELEGRAM_LOGIN_BOT'] as string | undefined) ?? 'playbronadminbot';

/** Lokal dev kirish uchun telegram_id — `.env` dagi super admin. */
const DEV_TELEGRAM_ID = Number(import.meta.env['VITE_DEV_TELEGRAM_ID'] ?? 611207125);

export interface Session {
  userId: number;
  name: string;
  role: Role;
  /** Sessiya tugash lahzasi — refresh muddati. */
  expiresAt: string;
  clubs: { id: number; name: string; role: string }[];
  isSuperAdmin: boolean;
}

interface ApiMembership {
  club_id: number;
  club_name: string;
  role: string;
}

interface ApiSession {
  access_token: string;
  access_expires_at: string;
  refresh_token: string;
  refresh_expires_at: string;
  user: { id: number; first_name: string; last_name: string | null };
  memberships: ApiMembership[];
  is_super_admin: boolean;
}

interface SessionState {
  session: Session | null;
  loading: boolean;
  error: string | null;

  /** Bot orqali kirishni boshlaydi — deep-link uchun nonce qaytaradi. */
  beginTelegramLogin: () => Promise<string>;
  /** Nonce holatini so'raydi; `ready` kelganda sessiyani o'zi o'rnatadi. */
  pollTelegramLogin: (nonce: string) => Promise<'pending' | 'expired' | 'ready'>;
  signInDev: () => Promise<void>;
  signOut: () => void;
  /** Sahifa yangilanganda saqlangan sessiyadan tiklaydi. */
  restore: () => Promise<void>;
  /** Muddati tugagan sessiyani tozalaydi. */
  prune: () => void;
}

/** Eng yuqori rol — bir necha klubda a'zolik bo'lishi mumkin. */
function topRole(memberships: ApiMembership[], superAdmin: boolean): Role {
  if (superAdmin) return 'SUPER_ADMIN';
  if (memberships.some((m) => m.role === 'OWNER' || m.role === 'ADMIN')) return 'CLUB_ADMIN';
  return 'STAFF';
}

function toStoreSession(body: ApiSession): Session {
  return {
    userId: body.user.id,
    name: [body.user.first_name, body.user.last_name].filter(Boolean).join(' ').trim(),
    role: topRole(body.memberships, body.is_super_admin),
    expiresAt: body.refresh_expires_at,
    clubs: body.memberships.map((m) => ({ id: m.club_id, name: m.club_name, role: m.role })),
    isSuperAdmin: body.is_super_admin,
  };
}

export const useSession = create<SessionState>()((set, get) => ({
  session: null,
  loading: false,
  error: null,

  beginTelegramLogin: async () => {
    try {
      const body = await api.post<{ nonce: string; expires_in: number }>(
        '/auth/telegram/start',
        {},
        { anonymous: true },
      );
      return body.nonce;
    } catch (cause) {
      throw cause instanceof ApiError ? new Error(errorText(cause)) : cause;
    }
  },

  pollTelegramLogin: async (nonce) => {
    const body = await api.post<{
      status: 'pending' | 'expired' | 'ready';
      session: ApiSession | null;
    }>(`/auth/telegram/start/${nonce}`, {}, { anonymous: true });

    if (body.status === 'ready' && body.session) {
      api.setSession(toSession(body.session));
      set({ session: toStoreSession(body.session), loading: false });
    }
    return body.status;
  },

  signInDev: async () => {
    set({ loading: true, error: null });
    try {
      const body = await api.post<ApiSession>(
        '/auth/dev/login',
        { telegram_id: DEV_TELEGRAM_ID, first_name: 'Dev' },
        { anonymous: true },
      );
      api.setSession(toSession(body));
      set({ session: toStoreSession(body), loading: false });
    } catch (cause) {
      set({ loading: false, error: errorText(cause) });
      throw cause instanceof ApiError ? new Error(errorText(cause)) : cause;
    }
  },

  signOut: () => {
    void apiSignOut(api);
    set({ session: null, error: null });
  },

  restore: async () => {
    const stored = api.session;
    if (!stored) return;

    set({ loading: true });
    try {
      // `/me` tokenni ham tekshiradi: eskirgan bo'lsa mijoz o'zi yangilaydi
      const me = await api.get<{
        id: number;
        first_name: string;
        last_name: string | null;
        is_super_admin: boolean;
        clubs: { id: number; name: string; role: string; org_id: number }[];
      }>('/me');

      set({
        loading: false,
        session: {
          userId: me.id,
          name: [me.first_name, me.last_name].filter(Boolean).join(' ').trim(),
          role: topRole(
            me.clubs.map((c) => ({ club_id: c.id, club_name: c.name, role: c.role })),
            me.is_super_admin,
          ),
          expiresAt: stored.refreshExpiresAt,
          clubs: me.clubs.map((c) => ({ id: c.id, name: c.name, role: c.role })),
          isSuperAdmin: me.is_super_admin,
        },
      });
    } catch {
      // Token yaroqsiz — kirish ekraniga qaytamiz
      api.signOut();
      set({ session: null, loading: false });
    }
  },

  prune: () => {
    const session = get().session;
    if (session && new Date(session.expiresAt).getTime() <= Date.now()) {
      api.signOut();
      set({ session: null });
    }
  },
}));

/** Sessiya tugashigacha qolgan vaqt — `2 soat 14 daqiqa`. */
export function remainingText(expiresAt: string): string {
  const left = new Date(expiresAt).getTime() - Date.now();
  if (left <= 0) return 'Muddati tugagan';

  const days = Math.floor(left / 86_400_000);
  if (days >= 1) return `${days} kun`;

  const hours = Math.floor(left / 3_600_000);
  const minutes = Math.floor((left % 3_600_000) / 60_000);
  return hours > 0 ? `${hours} soat ${minutes} daqiqa` : `${minutes} daqiqa`;
}
