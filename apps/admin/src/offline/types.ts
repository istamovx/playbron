import type { ExpenseCreateIn, ExpenseDto, ShiftDto } from '@playbron/api-client';

/**
 * Offline Sync Layer — turlar.
 *
 * Manba: `playbron-security-offline-10-10-audit.md` §4 (IndexedDB store'lari)
 * va §5 (mutatsiyalar toifasi). Audit uchta toifa taklif qiladi (xavfsiz /
 * konflikt-sezgir / pulga oid), lekin bu kodda barchasi BITTA mexanizmdan
 * o'tadi — sabab: backend allaqachon ikkita primitivga ega
 * (`Idempotency-Key` — `core/idempotency.py`, `expected_version` —
 * `0041_booking_version_command_id.py`), ular takroriy yuborishni va
 * eskirgan holatni ALLAQACHON xavfsiz qiladi. Uch xil quvur qurish shu
 * ikki primitivni takrorlagan bo'lardi.
 *
 * Qamrov ATAYLAB faqat MUTATSIYA (yozuv) tomoni: o'qish keshi ("entities"
 * do'koni, audit §4dagi jadval) BU YERDA YO'Q — bu alohida, katta UX
 * loyihasi (Live Board/hisobotlarni offline ko'rsatish). Hozirgi maqsad —
 * audit P0'ning o'zagi: "internet uzilganda xodimning amali yo'qolmaydi".
 */

export type CommandAction =
  | 'SHIFT_OPEN'
  | 'SHIFT_MOVEMENT'
  | 'SHIFT_CLOSE'
  | 'EXPENSE_CREATE'
  | 'BOOKING_CONFIRM'
  | 'BOOKING_REJECT'
  | 'BOOKING_EXTEND'
  | 'BOOKING_CANCEL';

export type OutboxStatus = 'PENDING' | 'SYNCING' | 'SYNCED' | 'FAILED' | 'CONFLICT';

/** IndexedDB `outbox` qatori — audit §4 `OutboxItem` naqshi. */
export interface OutboxItem<A extends CommandAction = CommandAction> {
  /** UUID — shu ID bevosita `Idempotency-Key` sifatida ham ishlatiladi. */
  id: string;
  clubId: number;
  userId: number | null;
  action: A;
  payload: CommandPayloadMap[A];
  createdAt: number;
  attempts: number;
  nextRetryAt: number;
  status: OutboxStatus;
  lastError: string | null;
  lastErrorCode: string | null;
  /** UI'da ko'rsatish uchun qisqa tavsif — masalan "Smena ochish". */
  label: string;
}

export interface ConflictRecord {
  /** = konflikt bergan outbox item id. */
  id: string;
  action: CommandAction;
  label: string;
  reason: string;
  createdAt: number;
}

// ── Har bir buyruqning payload (saqlanadigan, JSON-serializable) shakli ────

export interface ShiftOpenPayload {
  clubId: number;
  openingCash: number;
}

export interface ShiftMovementPayload {
  clubId: number;
  shiftId: number;
  kind: 'IN' | 'OUT';
  amount: number;
  reason: string;
}

export interface ShiftClosePayload {
  clubId: number;
  shiftId: number;
  countedCash: number;
}

export interface ExpenseCreatePayload {
  clubId: number;
  body: ExpenseCreateIn;
}

export interface BookingConfirmPayload {
  clubId: number;
  bookingId: number;
}

export interface BookingRejectPayload {
  clubId: number;
  bookingId: number;
  reason?: string;
}

export interface BookingCancelPayload {
  clubId: number;
  bookingId: number;
  reason?: string;
}

export interface BookingExtendPayload {
  clubId: number;
  bookingId: number;
  extraHours: number;
  expectedVersion?: number;
}

export interface CommandPayloadMap {
  SHIFT_OPEN: ShiftOpenPayload;
  SHIFT_MOVEMENT: ShiftMovementPayload;
  SHIFT_CLOSE: ShiftClosePayload;
  EXPENSE_CREATE: ExpenseCreatePayload;
  BOOKING_CONFIRM: BookingConfirmPayload;
  BOOKING_REJECT: BookingRejectPayload;
  BOOKING_CANCEL: BookingCancelPayload;
  BOOKING_EXTEND: BookingExtendPayload;
}

export interface ExtendResult {
  id: number;
  hours: number;
  startsAt: string;
  endsAt: string;
  version: number;
}

export interface CommandResultMap {
  SHIFT_OPEN: ShiftDto;
  SHIFT_MOVEMENT: ShiftDto;
  SHIFT_CLOSE: ShiftDto;
  EXPENSE_CREATE: ExpenseDto;
  BOOKING_CONFIRM: void;
  BOOKING_REJECT: void;
  BOOKING_CANCEL: void;
  BOOKING_EXTEND: ExtendResult;
}
