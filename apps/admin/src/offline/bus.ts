/**
 * Minimal pub/sub — `syncEngine.ts` outbox/connectivity o'zgarganda
 * `emit()` qiladi, `useOfflineSync.ts` React hook shu orqali qayta chiziladi.
 * Zustand/Context ishlatilmadi: bu modul React'dan MUSTAQIL (sinov, fon
 * vazifasi mantig'ida ham chaqiriladi).
 */

type Listener = () => void;

const listeners = new Set<Listener>();

export function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function emit(): void {
  for (const listener of listeners) listener();
}
