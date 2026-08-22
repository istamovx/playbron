import { describe, expect, it } from 'vitest';

import { applyOutboxEvent, isRetryable, needsAttention, recoverInterrupted } from './outboxReducer';
import type { OutboxItem } from './types';

function makeItem(overrides: Partial<OutboxItem<'BOOKING_EXTEND'>> = {}): OutboxItem<'BOOKING_EXTEND'> {
  return {
    id: 'item-1',
    clubId: 1,
    userId: 7,
    action: 'BOOKING_EXTEND',
    payload: { clubId: 1, bookingId: 42, extraHours: 1 },
    createdAt: 1000,
    attempts: 0,
    nextRetryAt: 1000,
    status: 'PENDING',
    lastError: null,
    lastErrorCode: null,
    label: 'Bronni uzaytirish',
    ...overrides,
  };
}

describe('applyOutboxEvent', () => {
  it('START_SYNCING moves PENDING → SYNCING without touching attempts', () => {
    const next = applyOutboxEvent(makeItem(), { type: 'START_SYNCING' }, 2000, 1000);
    expect(next.status).toBe('SYNCING');
    expect(next.attempts).toBe(0);
  });

  it('SENT_OK moves to SYNCED and clears any prior error', () => {
    const item = makeItem({ status: 'SYNCING', lastError: 'old', lastErrorCode: 'X' });
    const next = applyOutboxEvent(item, { type: 'SENT_OK' }, 2000, 1000);
    expect(next.status).toBe('SYNCED');
    expect(next.lastError).toBeNull();
    expect(next.lastErrorCode).toBeNull();
  });

  it('NETWORK_ERROR stays PENDING (never terminal), bumps attempts, schedules retry', () => {
    const item = makeItem({ status: 'SYNCING', attempts: 2 });
    const next = applyOutboxEvent(item, { type: 'NETWORK_ERROR', message: 'timeout' }, 5000, 4000);
    expect(next.status).toBe('PENDING');
    expect(next.attempts).toBe(3);
    expect(next.nextRetryAt).toBe(9000);
    expect(next.lastError).toBe('timeout');
    expect(next.lastErrorCode).toBeNull();
  });

  it('BUSINESS_ERROR is terminal (FAILED) — never auto-retried', () => {
    const item = makeItem({ status: 'SYNCING' });
    const next = applyOutboxEvent(
      item,
      { type: 'BUSINESS_ERROR', code: 'EXTEND_RANGE_INVALID', message: '1 dan 3 gacha' },
      5000,
      4000,
    );
    expect(next.status).toBe('FAILED');
    expect(next.lastErrorCode).toBe('EXTEND_RANGE_INVALID');
    expect(isRetryable(next.status)).toBe(false);
  });

  it('VERSION_CONFLICT is terminal (CONFLICT) — never auto-retried', () => {
    const item = makeItem({ status: 'SYNCING' });
    const next = applyOutboxEvent(
      item,
      { type: 'VERSION_CONFLICT', message: 'boshqa xodim o‘zgartirgan' },
      5000,
      4000,
    );
    expect(next.status).toBe('CONFLICT');
    expect(next.lastErrorCode).toBe('VERSION_CONFLICT');
    expect(isRetryable(next.status)).toBe(false);
    expect(needsAttention(next.status)).toBe(true);
  });

  it('recoverInterrupted resets an orphaned SYNCING item back to PENDING', () => {
    // Sahifa "so'rov yuborildi" (SYNCING) holatida yopilgan/qulab tushgan —
    // `isRetryable()` buni QAYTA OLMAYDI, shu sabab `startSyncEngine()`
    // har ishga tushishda avval shuni tiklaydi.
    const item = makeItem({ status: 'SYNCING', attempts: 2 });
    const next = recoverInterrupted(item, 9000);
    expect(next.status).toBe('PENDING');
    expect(next.nextRetryAt).toBe(9000);
    expect(isRetryable(next.status)).toBe(true);
  });

  it('recoverInterrupted leaves non-SYNCING items untouched', () => {
    for (const status of ['PENDING', 'SYNCED', 'FAILED', 'CONFLICT'] as const) {
      const item = makeItem({ status });
      expect(recoverInterrupted(item, 9000)).toBe(item); // ayni o'sha referens
    }
  });

  it('a FAILED item is never picked up again by isRetryable', () => {
    expect(isRetryable('FAILED')).toBe(false);
    expect(isRetryable('CONFLICT')).toBe(false);
    expect(isRetryable('SYNCED')).toBe(false);
    expect(isRetryable('SYNCING')).toBe(false);
    expect(isRetryable('PENDING')).toBe(true);
  });
});
