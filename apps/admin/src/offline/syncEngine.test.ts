import { ApiError, NetworkError } from '@playbron/api-client';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { _clearAllForTests, _resetForTests, listConflicts, listOutboxItems, putOutboxItem } from './db';

// `connectivity.ts` transitively imports `../lib/api` (real ApiClient,
// `import.meta.env` talab qiladi) — sinovda kerak emas, shuning uchun
// butunlay almashtiriladi.
let online = true;
vi.mock('./connectivity', () => ({
  isOnline: () => online,
}));

const executors = {
  SHIFT_OPEN: vi.fn(),
};
vi.mock('./commands', () => ({
  COMMAND_EXECUTORS: new Proxy(
    {},
    {
      get: (_target, action: string) => executors[action as keyof typeof executors],
    },
  ),
  labelFor: () => 'Smena ochish',
}));

// Mock'lardan KEYIN import qilinadi — vitest hoisting `vi.mock` chaqiruvlarini
// avtomatik yuqoriga ko'chiradi, lekin aniqlik uchun tartib saqlanadi.
const { runCommand, drainQueue } = await import('./syncEngine');
const { useBoard } = await import('../store/board');

const META = { clubId: 1, userId: 7 };

beforeEach(async () => {
  _resetForTests();
  await _clearAllForTests();
  online = true;
  executors.SHIFT_OPEN.mockReset();
  // `drainQueue()` faqat FAOL klub itemlarini yuboradi (club-switch race
  // himoyasi) — sinovda META.clubId bilan mos qilib qo'yiladi.
  useBoard.getState().setActiveClub(META.clubId);
});

describe('runCommand — online, immediate path (no queue noise)', () => {
  it('success: resolves with the result, writes NOTHING to the outbox', async () => {
    executors.SHIFT_OPEN.mockResolvedValue({ id: 99 });

    const outcome = await runCommand('SHIFT_OPEN', { clubId: 1, openingCash: 0 }, META);

    expect(outcome).toEqual({ synced: true, result: { id: 99 } });
    expect(await listOutboxItems()).toHaveLength(0);
  });

  it('business error: throws the ORIGINAL error, writes NOTHING to the outbox', async () => {
    const businessError = new ApiError(400, { code: 'OPENING_CASH_INVALID', message: 'manfiy' });
    executors.SHIFT_OPEN.mockRejectedValue(businessError);

    await expect(runCommand('SHIFT_OPEN', { clubId: 1, openingCash: -1 }, META)).rejects.toBe(
      businessError,
    );
    expect(await listOutboxItems()).toHaveLength(0);
  });

  it('version conflict: throws the ORIGINAL error, writes NOTHING to the outbox', async () => {
    const conflict = new ApiError(409, { code: 'VERSION_CONFLICT', message: 'eskirgan' });
    executors.SHIFT_OPEN.mockRejectedValue(conflict);

    await expect(runCommand('SHIFT_OPEN', { clubId: 1, openingCash: 0 }, META)).rejects.toBe(
      conflict,
    );
    expect(await listOutboxItems()).toHaveLength(0);
  });

  it('network error: does NOT throw, queues a PENDING item for later retry', async () => {
    executors.SHIFT_OPEN.mockRejectedValue(new NetworkError());

    const outcome = await runCommand('SHIFT_OPEN', { clubId: 1, openingCash: 0 }, META);

    expect(outcome).toEqual({ synced: false });
    const items = await listOutboxItems();
    expect(items).toHaveLength(1);
    expect(items[0]?.status).toBe('PENDING');
    expect(items[0]?.action).toBe('SHIFT_OPEN');
  });
});

describe('runCommand — offline (checked before attempting)', () => {
  it('queues immediately without ever calling the executor', async () => {
    online = false;

    const outcome = await runCommand('SHIFT_OPEN', { clubId: 1, openingCash: 0 }, META);

    expect(outcome).toEqual({ synced: false });
    expect(executors.SHIFT_OPEN).not.toHaveBeenCalled();
    const items = await listOutboxItems();
    expect(items).toHaveLength(1);
    expect(items[0]?.status).toBe('PENDING');
  });
});

describe('drainQueue — background retry of already-queued items', () => {
  it('syncs a PENDING item once back online', async () => {
    online = false;
    await runCommand('SHIFT_OPEN', { clubId: 1, openingCash: 0 }, META);
    expect(await listOutboxItems()).toHaveLength(1);

    online = true;
    executors.SHIFT_OPEN.mockResolvedValue({ id: 42 });
    await drainQueue();

    const items = await listOutboxItems();
    expect(items[0]?.status).toBe('SYNCED');
  });

  it('a repeated network error stays PENDING with incremented attempts (never gives up)', async () => {
    online = false;
    await runCommand('SHIFT_OPEN', { clubId: 1, openingCash: 0 }, META);

    online = true;
    executors.SHIFT_OPEN.mockRejectedValue(new NetworkError());
    // nextRetryAt boshida "hozir" — birinchi drain darhol urinadi.
    await drainQueue();

    const items = await listOutboxItems();
    expect(items[0]?.status).toBe('PENDING');
    expect(items[0]?.attempts).toBe(1);
  });

  it('a VERSION_CONFLICT during background retry moves to CONFLICT and records it', async () => {
    online = false;
    await runCommand('SHIFT_OPEN', { clubId: 1, openingCash: 0 }, META);

    online = true;
    executors.SHIFT_OPEN.mockRejectedValue(
      new ApiError(409, { code: 'VERSION_CONFLICT', message: 'boshqa xodim o‘zgartirgan' }),
    );
    await drainQueue();

    const items = await listOutboxItems();
    expect(items[0]?.status).toBe('CONFLICT');
    const conflicts = await listConflicts();
    expect(conflicts).toHaveLength(1);
    expect(conflicts[0]?.reason).toBe('boshqa xodim o‘zgartirgan');
  });

  it('skips (does not attempt) a PENDING item queued for a club that is no longer active', async () => {
    online = false;
    await runCommand('SHIFT_OPEN', { clubId: 1, openingCash: 0 }, META);

    online = true;
    useBoard.getState().setActiveClub(999); // xodim boshqa klubga o'tdi
    executors.SHIFT_OPEN.mockResolvedValue({ id: 1 });
    await drainQueue();

    expect(executors.SHIFT_OPEN).not.toHaveBeenCalled();
    const items = await listOutboxItems();
    expect(items[0]?.status).toBe('PENDING'); // FAILED emas — shunchaki kutmoqda

    // Klub qayta faollashsa — endi yuboriladi.
    useBoard.getState().setActiveClub(1);
    await drainQueue();
    expect(executors.SHIFT_OPEN).toHaveBeenCalledTimes(1);
  });

  it('recovers an item orphaned in SYNCING (simulated crash mid-request) and retries it', async () => {
    online = false;
    await runCommand('SHIFT_OPEN', { clubId: 1, openingCash: 0 }, META);
    online = true;

    // `attemptOne()` odatda avval SYNCING deb yozadi — shu holatni to'g'ridan
    // to'g'ri simulyatsiya qilamiz (masalan sahifa javob kelmasdan yopilgan).
    const [stuck] = await listOutboxItems();
    if (stuck) await putOutboxItem({ ...stuck, status: 'SYNCING' });

    executors.SHIFT_OPEN.mockResolvedValue({ id: 7 });
    await drainQueue();

    const items = await listOutboxItems();
    expect(items[0]?.status).toBe('SYNCED');
  });

  it('treats IDEMPOTENCY_IN_PROGRESS (another tab mid-flight) as retryable, not FAILED', async () => {
    online = false;
    await runCommand('SHIFT_OPEN', { clubId: 1, openingCash: 0 }, META);

    online = true;
    executors.SHIFT_OPEN.mockRejectedValue(
      new ApiError(409, { code: 'IDEMPOTENCY_IN_PROGRESS', message: 'hali bajarilmoqda' }),
    );
    await drainQueue();

    const items = await listOutboxItems();
    expect(items[0]?.status).toBe('PENDING');
    expect(items[0]?.attempts).toBe(1);
  });

  it('a BUSINESS_ERROR during background retry is terminal (FAILED), not retried again', async () => {
    online = false;
    await runCommand('SHIFT_OPEN', { clubId: 1, openingCash: 0 }, META);

    online = true;
    executors.SHIFT_OPEN.mockRejectedValue(
      new ApiError(400, { code: 'OPENING_CASH_INVALID', message: 'manfiy' }),
    );
    await drainQueue();
    const afterFirst = await listOutboxItems();
    expect(afterFirst[0]?.status).toBe('FAILED');

    // Yana bir drain — FAILED item QAYTA urinilmasligi kerak.
    executors.SHIFT_OPEN.mockClear();
    await drainQueue();
    expect(executors.SHIFT_OPEN).not.toHaveBeenCalled();
  });
});
