import { ApiError, errorText, signOut as apiSignOut, toSession } from '@playbron/api-client';
import { create } from 'zustand';

import { api } from '../lib/api';

/**
 * Ilova sessiyasi — **login va parol**.
 *
 * Telegram bu yerda identifikatsiya qilmaydi: u faqat ilovani ochadigan yuza
 * (Mini App) va bildirishnoma kanali. Shuning uchun `initData` bu oqimda
 * umuman ishlatilmaydi — ikkinchi imzo yuzasi paydo bo'lsa, ikki endpoint
 * bir-birining tokenini qabul qilib qo'yish xavfi tug'ilardi
 * (`docs/05-auth-redesign.md` §11.1).
 */

export type Role = 'STAFF' | 'CLUB_ADMIN' | 'SUPER_ADMIN';

export const ROLE_LABEL: Record<Role, string> = {
  STAFF: 'Xodim',
  CLUB_ADMIN: 'Klub admini',
  SUPER_ADMIN: 'Super admin',
};

export interface Session {
  userId: number;
  name: string;
  login: string | null;
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
  user: { id: number; first_name: string; last_name: string | null; login: string | null };
  memberships: ApiMembership[];
  is_super_admin: boolean;
  must_change_password: boolean;
}

interface SessionState {
  session: Session | null;
  loading: boolean;
  error: string | null;
  /** Birov bergan parol bir martalik — almashtirilmaguncha boshqa ekran ochilmaydi. */
  mustChangePassword: boolean;

  signIn: (login: string, password: string) => Promise<void>;
  changePassword: (current: string, next: string) => Promise<void>;
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
    login: body.user.login,
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
  mustChangePassword: false,

  signIn: async (login, password) => {
    set({ loading: true, error: null });
    try {
      const body = await api.post<ApiSession>(
        '/auth/staff/login',
        { login, password },
        { anonymous: true },
      );
      api.setSession(toSession(body));
      set({
        session: toStoreSession(body),
        mustChangePassword: body.must_change_password,
        loading: false,
      });
    } catch (cause) {
      set({ loading: false, error: errorText(cause) });
      throw cause instanceof ApiError ? new Error(errorText(cause)) : cause;
    }
  },

  changePassword: async (current, next) => {
    set({ loading: true, error: null });
    try {
      // Javob — YANGI sessiya: server eski tokenlarni bekor qiladi, shuning
      // uchun ularni almashtirmasak keyingi so'rov 401 bo'lardi
      const body = await api.post<ApiSession>('/auth/staff/password/change', {
        current_password: current,
        new_password: next,
      });
      api.setSession(toSession(body));
      set({
        session: toStoreSession(body),
        mustChangePassword: false,
        loading: false,
      });
    } catch (cause) {
      set({ loading: false, error: errorText(cause) });
      throw cause instanceof ApiError ? new Error(errorText(cause)) : cause;
    }
  },

  signOut: () => {
    void apiSignOut(api);
    set({ session: null, error: null, mustChangePassword: false });
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
        login: string | null;
        is_super_admin: boolean;
        clubs: { id: number; name: string; role: string; org_id: number }[];
      }>('/me');

      set({
        loading: false,
        session: {
          userId: me.id,
          name: [me.first_name, me.last_name].filter(Boolean).join(' ').trim(),
          login: me.login,
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
      set({ session: null, mustChangePassword: false });
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
