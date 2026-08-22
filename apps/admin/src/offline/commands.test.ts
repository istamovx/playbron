import type * as ApiClientModule from '@playbron/api-client';
import { describe, expect, it, vi } from 'vitest';

// `../lib/api` real `ApiClient`ni ishga tushiradi (`import.meta.env` talab
// qiladi) — bu yerda kerak emas, `api-client` funksiyalari to'liq mock.
vi.mock('../lib/api', () => ({ api: {} }));

const getBill = vi.fn();
const closeBill = vi.fn();
vi.mock('@playbron/api-client', async (importOriginal) => {
  const actual = await importOriginal<typeof ApiClientModule>();
  return {
    ...actual,
    addShiftMovement: vi.fn(),
    cancelBooking: vi.fn(),
    confirmBooking: vi.fn(),
    createExpense: vi.fn(),
    closeShift: vi.fn(),
    extendBooking: vi.fn(),
    openShift: vi.fn(),
    rejectBooking: vi.fn(),
    getBill,
    closeBill,
  };
});

const { COMMAND_EXECUTORS } = await import('./commands');
const { ApiError } = await import('@playbron/api-client');

const PAYLOAD = {
  clubId: 1,
  bookingId: 9,
  body: { paymentMethod: 'CASH' as const, paidAmount: 100000 },
  expectedTotal: 100000,
};

describe('COMMAND_EXECUTORS.BILL_CLOSE', () => {
  it('summa mos kelsa — closeBill chaqiriladi', async () => {
    getBill.mockResolvedValue({ bookingId: 9, total: 100000 });
    closeBill.mockResolvedValue({ bookingId: 9, total: 100000 });

    const result = await COMMAND_EXECUTORS.BILL_CLOSE(PAYLOAD, 'idem-key-1');

    expect(closeBill).toHaveBeenCalledWith({}, 1, 9, PAYLOAD.body, 'idem-key-1');
    expect(result).toEqual({ bookingId: 9, total: 100000 });
  });

  it('navbatda kutgan payt summa o‘zgargan bo‘lsa — VERSION_CONFLICT tashlaydi, closeBill CHAQIRILMAYDI', async () => {
    getBill.mockResolvedValue({ bookingId: 9, total: 130000 }); // boshqa xodim bar buyurtma qo'shgan
    closeBill.mockClear();

    await expect(COMMAND_EXECUTORS.BILL_CLOSE(PAYLOAD, 'idem-key-2')).rejects.toMatchObject({
      code: 'VERSION_CONFLICT',
    });
    expect(closeBill).not.toHaveBeenCalled();
  });

  it('VERSION_CONFLICT xatosi ApiError instansiyasi — syncEngine::classify() aynan shu yo‘lni ushlaydi', async () => {
    getBill.mockResolvedValue({ bookingId: 9, total: 999 });

    await expect(COMMAND_EXECUTORS.BILL_CLOSE(PAYLOAD, 'idem-key-3')).rejects.toBeInstanceOf(
      ApiError,
    );
  });
});
