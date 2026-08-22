import { apiBaseUrl } from '../lib/api';
import { emit } from './bus';

/**
 * Connectivity Manager — audit §6: faqat `navigator.onLine`ga ishonilmaydi
 * (ko'p brauzerda faqat tarmoq adapteri holatini bildiradi, DNS/VPN/proksi
 * muammosini ko'rmaydi). Haqiqiy holat davriy `GET /healthz` bilan
 * tasdiqlanadi.
 */

const HEALTHZ_URL = apiBaseUrl.replace(/\/api\/v1\/?$/, '') + '/healthz';
const PROBE_INTERVAL_MS = 20_000;
const PROBE_TIMEOUT_MS = 5000;

let online = typeof navigator === 'undefined' ? true : navigator.onLine;
let intervalId: ReturnType<typeof setInterval> | null = null;

function setOnline(next: boolean): void {
  if (next === online) return;
  online = next;
  emit();
}

async function probe(): Promise<void> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS);
  try {
    const res = await fetch(HEALTHZ_URL, { signal: controller.signal, cache: 'no-store' });
    setOnline(res.ok);
  } catch {
    setOnline(false);
  } finally {
    clearTimeout(timeout);
  }
}

export function isOnline(): boolean {
  return online;
}

/** Ilova ishga tushishida BIR MARTA chaqiriladi (`main.tsx` yoki `app.tsx`). */
export function startConnectivityWatch(): () => void {
  if (typeof window === 'undefined') return () => {};

  const handleOnline = (): void => {
    // Brauzer "online" desa ham darhol ISHONILMAYDI — healthz tasdiqlaydi
    // (masalan Wi-Fi ulandi, lekin captive portal hali ochilmagan).
    void probe();
  };
  const handleOffline = (): void => setOnline(false);

  window.addEventListener('online', handleOnline);
  window.addEventListener('offline', handleOffline);
  void probe();
  intervalId = setInterval(() => void probe(), PROBE_INTERVAL_MS);

  return () => {
    window.removeEventListener('online', handleOnline);
    window.removeEventListener('offline', handleOffline);
    if (intervalId !== null) clearInterval(intervalId);
    intervalId = null;
  };
}

/** Faqat testlar uchun. */
export function _setOnlineForTests(value: boolean): void {
  setOnline(value);
}
