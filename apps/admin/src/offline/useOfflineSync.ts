import { useEffect, useState, useSyncExternalStore } from 'react';

import { subscribe } from './bus';
import { isOnline } from './connectivity';
import { deleteConflict, listConflicts, listOutboxItems } from './db';
import { needsAttention } from './outboxReducer';
import type { ConflictRecord, OutboxItem } from './types';

export interface OfflineSyncState {
  online: boolean;
  pendingCount: number;
  syncingCount: number;
  failed: OutboxItem[];
  conflicts: ConflictRecord[];
}

const EMPTY: OfflineSyncState = {
  online: true,
  pendingCount: 0,
  syncingCount: 0,
  failed: [],
  conflicts: [],
};

/**
 * Konsol banner'i uchun — `bus`ga obuna bo'ladi va har o'zgarishda
 * IndexedDB'dan qayta o'qiydi. Kam-chastotali (mutatsiyalar soniyada bir
 * necha marta emas), shuning uchun har `emit()`da to'liq qayta o'qish
 * qabul qilinadi — qo'shimcha keshlash keraksiz murakkablik qo'shardi.
 */
export function useOfflineSync(): OfflineSyncState {
  const [state, setState] = useState<OfflineSyncState>(EMPTY);

  useEffect(() => {
    let cancelled = false;

    const refresh = (): void => {
      void Promise.all([listOutboxItems(), listConflicts()]).then(([items, conflicts]) => {
        if (cancelled) return;
        setState({
          online: isOnline(),
          pendingCount: items.filter((i) => i.status === 'PENDING' || i.status === 'SYNCING').length,
          syncingCount: items.filter((i) => i.status === 'SYNCING').length,
          failed: items.filter((i) => needsAttention(i.status) && i.status === 'FAILED'),
          conflicts,
        });
      });
    };

    refresh();
    const unsubscribe = subscribe(refresh);
    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, []);

  return state;
}

/** Xodim conflict'ni ko'rib chiqdi — yozuv navbatdan olib tashlanadi.
 * Amalning O'ZI qayta yuborilmaydi: xodim ekranga qaytib, joriy holatni
 * ko'rib, kerak bo'lsa QAYTADAN boshlaydi (audit §16 — hech qachon
 * jimgina qayta qo'llanmaydi). */
export function dismissConflict(id: string): Promise<void> {
  return deleteConflict(id);
}

/** Faqat online holatni kuzatish kerak bo'lgan kichik komponentlar uchun. */
export function useIsOnline(): boolean {
  return useSyncExternalStore(subscribe, isOnline, () => true);
}
