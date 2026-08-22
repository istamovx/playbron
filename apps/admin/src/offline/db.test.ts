import { beforeEach, describe, expect, it } from 'vitest';

import {
  _clearAllForTests,
  _resetForTests,
  deleteConflict,
  listConflicts,
  listOutboxItems,
  pruneSyncedOlderThan,
  putConflict,
  putOutboxItem,
} from './db';
import type { ConflictRecord, OutboxItem } from './types';

function makeItem(overrides: Partial<OutboxItem<'SHIFT_OPEN'>> = {}): OutboxItem<'SHIFT_OPEN'> {
  return {
    id: crypto.randomUUID(),
    clubId: 1,
    userId: 7,
    action: 'SHIFT_OPEN',
    payload: { clubId: 1, openingCash: 50_000 },
    createdAt: Date.now(),
    attempts: 0,
    nextRetryAt: Date.now(),
    status: 'PENDING',
    lastError: null,
    lastErrorCode: null,
    label: 'Smena ochish',
    ...overrides,
  };
}

// `fake-indexeddb`ning global holati testlar orasida saqlanib qoladi —
// har test o'zining unikal ID'lari bilan ishlaydi, tozalash shart emas
// (haqiqiy IndexedDB ham xuddi shunday ishlaydi: sahifa reload'i ma'lumotni
// O'CHIRMAYDI, faqat modul-darajasidagi ulanish keshini tiklash kerak).
beforeEach(async () => {
  _resetForTests();
  await _clearAllForTests();
});

describe('outbox durability', () => {
  it('round-trips an item through put → list', async () => {
    const item = makeItem();
    await putOutboxItem(item);
    const all = await listOutboxItems();
    expect(all.find((i) => i.id === item.id)).toEqual(item);
  });

  it('survives a simulated reload (connection cache reset, data persists)', async () => {
    const item = makeItem();
    await putOutboxItem(item);

    // Sahifa reload'ini taqlid qilish: faqat modul-darajasidagi ulanish
    // promise'i tozalanadi — `indexedDB` global'ining o'zi (fake yoki
    // haqiqiy) YO'Q QILINMAYDI.
    _resetForTests();

    const all = await listOutboxItems();
    expect(all.some((i) => i.id === item.id)).toBe(true);
  });

  it('lists items oldest-first by createdAt', async () => {
    const older = makeItem({ id: 'a', createdAt: 1000 });
    const newer = makeItem({ id: 'b', createdAt: 2000 });
    await putOutboxItem(newer);
    await putOutboxItem(older);

    const all = await listOutboxItems();
    const ids = all.map((i) => i.id);
    expect(ids.indexOf('a')).toBeLessThan(ids.indexOf('b'));
  });

  it('pruneSyncedOlderThan removes only stale SYNCED items', async () => {
    const staleSynced = makeItem({ id: 'stale-synced', status: 'SYNCED', createdAt: 1000 });
    const freshSynced = makeItem({ id: 'fresh-synced', status: 'SYNCED', createdAt: 9_000_000 });
    const stalePending = makeItem({ id: 'stale-pending', status: 'PENDING', createdAt: 1000 });
    await putOutboxItem(staleSynced);
    await putOutboxItem(freshSynced);
    await putOutboxItem(stalePending);

    await pruneSyncedOlderThan(5000);

    const ids = (await listOutboxItems()).map((i) => i.id);
    expect(ids).not.toContain('stale-synced');
    expect(ids).toContain('fresh-synced');
    // PENDING hech qachon jimgina o'chirilmaydi — faqat SYNCED tozalanadi,
    // aks holda hali yuborilmagan amal yo'qolib ketardi (audit §1'ning
    // aynan oldini olishi kerak bo'lgan holat).
    expect(ids).toContain('stale-pending');
  });
});

describe('conflicts store', () => {
  it('round-trips a conflict record and can delete it (dismiss)', async () => {
    const record: ConflictRecord = {
      id: crypto.randomUUID(),
      action: 'BOOKING_EXTEND',
      label: 'Bronni uzaytirish',
      reason: 'Boshqa xodim allaqachon o‘zgartirgan',
      createdAt: Date.now(),
    };
    await putConflict(record);
    expect((await listConflicts()).find((c) => c.id === record.id)).toEqual(record);

    await deleteConflict(record.id);
    expect((await listConflicts()).some((c) => c.id === record.id)).toBe(false);
  });
});
