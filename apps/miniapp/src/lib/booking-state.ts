import { GRACE_MIN } from '@playbron/ui';
import type { MyBookingDto } from '@playbron/api-client';

import type { MsgKey } from '../i18n';

/**
 * Bron holatining VAQT bo'yicha bosqichi.
 *
 * Avval "aktiv seans" `mock/data.ts::SESSION_START/SESSION_END` konstantalari
 * edi — ilova har ochilganda 19:30–21:30 oralig'idagi soxta seansni
 * ko'rsatardi va u hech qachon tugamasdi. Endi manba `GET /me/bookings`:
 * seans oynasi o'tishi bilan bron o'z-o'zidan tarixga tushadi.
 *
 * Taqqoslash LAHZALAR ustida (`startsAt`/`endsAt` — UTC ISO), shuning uchun
 * bu yerda vaqt zonasi kerak emas; zona faqat KO'RSATISHDA ishlatiladi
 * (`lib/slots.ts::formatWindow`).
 */
export type TimePhase = 'before' | 'during' | 'grace' | 'after';

const graceMs = GRACE_MIN * 60_000;

export function timePhase(booking: MyBookingDto, nowMs: number): TimePhase {
  const from = new Date(booking.startsAt).getTime();
  const to = new Date(booking.endsAt).getTime();
  if (nowMs < from) return 'before';
  if (nowMs < to) return 'during';
  if (nowMs < to + graceMs) return 'grace';
  return 'after';
}

/**
 * Tarixga tushdimi.
 *
 * `closed` — server bergan haqiqat manbai (`bookings.closed_at`): hisob
 * seans oynasi tugashini KUTMASDAN yopilishi mumkin. Vaqt arifmetikasi
 * faqat undan keyin ishlatiladi.
 */
export const isHistory = (booking: MyBookingDto, nowMs: number): boolean =>
  booking.closed || booking.status === 'CANCELLED' || timePhase(booking, nowMs) === 'after';

/** Kartadagi holat yozuvining i18n kaliti. */
export function statusKey(booking: MyBookingDto, nowMs: number): MsgKey {
  if (booking.status === 'CANCELLED') return 'statusCancelled';
  // Hisob yopilgan — vaqtga qaramay yakunlangan.
  if (booking.closed) return 'statusDone';
  const phase = timePhase(booking, nowMs);
  const confirmed = booking.status === 'CONFIRMED';
  if (phase === 'after') return confirmed ? 'statusDone' : 'statusExpired';
  if (phase === 'during' || phase === 'grace') return confirmed ? 'statusLive' : 'statusPending';
  return confirmed ? 'statusConfirmed' : 'statusPending';
}

/** Holat rangi — kartaning chap chekkasi va yozuvi. */
export function statusAccent(booking: MyBookingDto, nowMs: number): string {
  switch (statusKey(booking, nowMs)) {
    case 'statusLive':
      return 'var(--primary-100)';
    case 'statusConfirmed':
      return 'var(--secondary-500)';
    case 'statusPending':
      return 'var(--yellow-100)';
    default:
      return 'var(--fg-4)';
  }
}

/**
 * Hozir yurayotgan seans — FAQAT tasdiqlangan bron.
 * Tasdiqlanmagan (`PENDING`) bron oynasi kelib qolsa ham seans emas:
 * xodim uni hali qabul qilmagan.
 */
export function activeSession(bookings: MyBookingDto[], nowMs: number): MyBookingDto | null {
  const live = bookings
    .filter((booking) => booking.status === 'CONFIRMED' && !booking.closed)
    .filter((booking) => {
      const phase = timePhase(booking, nowMs);
      return phase === 'during' || phase === 'grace';
    })
    .sort((a, b) => new Date(a.endsAt).getTime() - new Date(b.endsAt).getTime());
  return live[0] ?? null;
}

/** Eng yaqin kelayotgan bron — bekor qilinmagani. */
export function nextBooking(bookings: MyBookingDto[], nowMs: number): MyBookingDto | null {
  const upcoming = bookings
    .filter((booking) => booking.status !== 'CANCELLED' && timePhase(booking, nowMs) === 'before')
    .sort((a, b) => new Date(a.startsAt).getTime() - new Date(b.startsAt).getTime());
  return upcoming[0] ?? null;
}
