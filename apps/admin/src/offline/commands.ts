import {
  addShiftMovement,
  ApiError,
  cancelBooking,
  closeBill,
  confirmBooking,
  createExpense,
  closeShift,
  extendBooking,
  getBill,
  openShift,
  rejectBooking,
} from '@playbron/api-client';

import { api } from '../lib/api';
import type { CommandAction, CommandPayloadMap, CommandResultMap } from './types';

/**
 * Buyruq ro'yxati — `action` (satr, IndexedDB'da saqlanadi) → haqiqiy
 * API chaqiruvi. Sahifa reload'idan keyin ham ishlashi kerak, shuning
 * uchun bog'liqlik faqat SAQLANADIGAN qiymatlardan (`payload`, `idempotencyKey`) —
 * hech qanday yopiq o'zgaruvchi (closure) yo'q.
 */
export const COMMAND_EXECUTORS: {
  [A in CommandAction]: (
    payload: CommandPayloadMap[A],
    idempotencyKey: string,
  ) => Promise<CommandResultMap[A]>;
} = {
  SHIFT_OPEN: (payload, key) => openShift(api, payload.clubId, payload.openingCash, key),
  SHIFT_MOVEMENT: (payload, key) =>
    addShiftMovement(
      api,
      payload.clubId,
      payload.shiftId,
      { kind: payload.kind, amount: payload.amount, reason: payload.reason },
      key,
    ),
  SHIFT_CLOSE: (payload, key) => closeShift(api, payload.clubId, payload.shiftId, payload.countedCash, key),
  EXPENSE_CREATE: (payload, key) => createExpense(api, payload.clubId, payload.body, key),
  BOOKING_CONFIRM: (payload, key) => confirmBooking(api, payload.clubId, payload.bookingId, key),
  BOOKING_REJECT: (payload, key) =>
    rejectBooking(api, payload.clubId, payload.bookingId, payload.reason, key),
  BOOKING_CANCEL: (payload, key) =>
    cancelBooking(api, payload.clubId, payload.bookingId, payload.reason, key),
  BOOKING_EXTEND: (payload, key) =>
    extendBooking(api, payload.clubId, payload.bookingId, payload.extraHours, key, payload.expectedVersion),
  BILL_CLOSE: async (payload, key) => {
    // Navbatga qo'yilgan payt bilan sinxronlash payti orasida hisob
    // summasi o'zgargan bo'lishi mumkin (masalan boshqa xodim bar
    // buyurtma qo'shgan) — bunday holda chegirma/qarz/tip sababi endi
    // noto'g'ri summaga tegishli bo'lib qoladi. `BOOKING_EXTEND`ning
    // `expectedVersion` naqshiga o'xshab, yopishdan OLDIN joriy summani
    // qayta so'raymiz va farq bo'lsa `VERSION_CONFLICT` bilan to'xtatamiz —
    // `syncEngine.ts::classify()` buni allaqachon CONFLICT holatiga
    // o'tkazadi, xodim ekranda qayta ko'rib chiqadi.
    const live = await getBill(api, payload.clubId, payload.bookingId);
    if (live.total !== payload.expectedTotal) {
      throw new ApiError(409, {
        code: 'VERSION_CONFLICT',
        message: 'Hisob summasi navbatga qo‘yilgandan beri o‘zgargan',
      });
    }
    return closeBill(api, payload.clubId, payload.bookingId, payload.body, key);
  },
};

const LABELS: Record<CommandAction, string> = {
  SHIFT_OPEN: 'Smena ochish',
  SHIFT_MOVEMENT: 'Kassa harakati',
  SHIFT_CLOSE: 'Smenani yopish',
  EXPENSE_CREATE: 'Xarajat qo‘shish',
  BOOKING_CONFIRM: 'Bronni tasdiqlash',
  BOOKING_REJECT: 'Bronni rad etish',
  BOOKING_CANCEL: 'Bronni bekor qilish',
  BOOKING_EXTEND: 'Bronni uzaytirish',
  BILL_CLOSE: 'Hisobni yopish',
};

export function labelFor(action: CommandAction): string {
  return LABELS[action];
}
