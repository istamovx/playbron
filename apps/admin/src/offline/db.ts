import type { ConflictRecord, OutboxItem } from './types';

/**
 * IndexedDB xom qatlami — audit §4. Faqat CRUD, biznes mantiq YO'Q
 * (`outboxReducer.ts`da). `localStorage` emas — audit §1 shu farqni
 * ataylab ta'kidlaydi: sahifa yopilib qayta ochilsa ham (browser restart
 * while offline — audit §29 test ro'yxati) navbat saqlanib qoladi.
 */

const DB_NAME = 'playbron-offline';
const DB_VERSION = 1;
const OUTBOX_STORE = 'outbox';
const CONFLICTS_STORE = 'conflicts';

let dbPromise: Promise<IDBDatabase> | null = null;

function openDb(): Promise<IDBDatabase> {
  dbPromise ??= new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(OUTBOX_STORE)) {
        const store = db.createObjectStore(OUTBOX_STORE, { keyPath: 'id' });
        store.createIndex('status', 'status');
        store.createIndex('createdAt', 'createdAt');
      }
      if (!db.objectStoreNames.contains(CONFLICTS_STORE)) {
        db.createObjectStore(CONFLICTS_STORE, { keyPath: 'id' });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error as Error);
  });
  return dbPromise;
}

function promisify<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error as Error);
  });
}

/**
 * Bitta so'rovning `onsuccess`i BITTA yozuv izolyatsiya darajasida
 * bajarilganini bildiradi — TRANZAKSIYANING o'zi hali disk'ga
 * yozilmagan (commit) bo'lishi mumkin. `browser restart while offline`
 * kabi haqiqiy uzilishlarga chidamli bo'lish uchun yozuvchi funksiyalar
 * `tx.oncomplete`ni kutadi, faqat so'rov natijasini emas.
 */
function txDone(tx: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error as Error);
    tx.onabort = () => reject(tx.error ?? new Error('IndexedDB tranzaksiyasi bekor qilindi'));
  });
}

export async function putOutboxItem(item: OutboxItem): Promise<void> {
  const db = await openDb();
  const tx = db.transaction(OUTBOX_STORE, 'readwrite');
  tx.objectStore(OUTBOX_STORE).put(item);
  await txDone(tx);
}

export async function listOutboxItems(): Promise<OutboxItem[]> {
  const db = await openDb();
  const tx = db.transaction(OUTBOX_STORE, 'readonly');
  const all = await promisify(tx.objectStore(OUTBOX_STORE).getAll());
  return (all as OutboxItem[]).sort((a, b) => a.createdAt - b.createdAt);
}

/** Eski, sinxronlangan yozuvlarni tozalaydi — navbat cheksiz o'smasin. */
export async function pruneSyncedOlderThan(cutoff: number): Promise<void> {
  const items = await listOutboxItems();
  const stale = items.filter((item) => item.status === 'SYNCED' && item.createdAt < cutoff);
  if (stale.length === 0) return;
  const db = await openDb();
  const tx = db.transaction(OUTBOX_STORE, 'readwrite');
  const store = tx.objectStore(OUTBOX_STORE);
  for (const item of stale) store.delete(item.id);
  await txDone(tx);
}

export async function putConflict(record: ConflictRecord): Promise<void> {
  const db = await openDb();
  const tx = db.transaction(CONFLICTS_STORE, 'readwrite');
  tx.objectStore(CONFLICTS_STORE).put(record);
  await txDone(tx);
}

export async function listConflicts(): Promise<ConflictRecord[]> {
  const db = await openDb();
  const tx = db.transaction(CONFLICTS_STORE, 'readonly');
  const all = await promisify(tx.objectStore(CONFLICTS_STORE).getAll());
  return (all as ConflictRecord[]).sort((a, b) => b.createdAt - a.createdAt);
}

export async function deleteConflict(id: string): Promise<void> {
  const db = await openDb();
  const tx = db.transaction(CONFLICTS_STORE, 'readwrite');
  tx.objectStore(CONFLICTS_STORE).delete(id);
  await txDone(tx);
}

/** Faqat testlar uchun — modul-darajasidagi ulanish keshini tozalaydi. */
export function _resetForTests(): void {
  dbPromise = null;
}

/** Faqat testlar uchun — ikkala do'konni ham butunlay bo'shatadi
 * (`fake-indexeddb` butun vitest jarayoni davomida saqlanib qoladi,
 * haqiqiy brauzer profili kabi — testlar orasida qo'lda tozalash kerak). */
export async function _clearAllForTests(): Promise<void> {
  const db = await openDb();
  const tx = db.transaction([OUTBOX_STORE, CONFLICTS_STORE], 'readwrite');
  tx.objectStore(OUTBOX_STORE).clear();
  tx.objectStore(CONFLICTS_STORE).clear();
  await txDone(tx);
}
