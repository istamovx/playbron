/**
 * Sessiya saqlash. Ikki yuza — ikki xil talab:
 *   • Mini App — `sessionStorage`, chunki Telegram har ochilishda yangi `initData`
 *     beradi va sessiyani jimgina qayta olish mumkin.
 *   • Konsol — `localStorage`, chunki brauzer tab'i yopilib qayta ochilishi normal.
 */

export interface Session {
  accessToken: string;
  accessExpiresAt: string;
  refreshToken: string;
  refreshExpiresAt: string;
}

export interface SessionStore {
  read: () => Session | null;
  write: (session: Session | null) => void;
}

/** Access token muddati tugashiga shuncha qolganda oldindan yangilanadi. */
const REFRESH_SKEW_MS = 30_000;

export function isExpiring(session: Session): boolean {
  return new Date(session.accessExpiresAt).getTime() - Date.now() <= REFRESH_SKEW_MS;
}

export function isRefreshDead(session: Session): boolean {
  return new Date(session.refreshExpiresAt).getTime() <= Date.now();
}

export function browserStore(key: string, storage: Storage): SessionStore {
  return {
    read() {
      try {
        const raw = storage.getItem(key);
        if (!raw) return null;
        const parsed = JSON.parse(raw) as Partial<Session>;
        if (!parsed.accessToken || !parsed.refreshToken) return null;
        return parsed as Session;
      } catch {
        // Buzilgan yozuv — tozalab, qaytadan kirishga yo'l ochamiz
        storage.removeItem(key);
        return null;
      }
    },
    write(session) {
      if (session) storage.setItem(key, JSON.stringify(session));
      else storage.removeItem(key);
    },
  };
}

/** Test va SSR uchun — hech qayerga yozmaydi. */
export function memoryStore(): SessionStore {
  let current: Session | null = null;
  return {
    read: () => current,
    write: (session) => {
      current = session;
    },
  };
}
