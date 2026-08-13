/**
 * Formatlash yordamchilari — ilgari `@playbron/types` da edi, endi UI kutubxonasi
 * mustaqil bo'lishi uchun shu yerda. Pul so'mda, butun son (`bigint`), float yo'q.
 */

export type Sum = bigint;

export const CLUB_TIMEZONE = 'Asia/Tashkent';

/** 3 xonali guruh, ajratgich — bo'sh joy (`182 000`). */
export function formatSum(value: Sum): string {
  const negative = value < 0n;
  const digits = (negative ? -value : value).toString();
  let out = '';
  for (let index = 0; index < digits.length; index += 1) {
    if (index > 0 && (digits.length - index) % 3 === 0) out += ' ';
    out += digits[index];
  }
  return negative ? `-${out}` : out;
}

/** Davomiylik `1:45:20`; manfiy vaqt overtime sifatida `+` bilan chiqadi. */
export function formatDuration(totalSeconds: number): string {
  const sign = totalSeconds < 0 ? '+' : '';
  const abs = Math.abs(Math.trunc(totalSeconds));
  const hours = Math.floor(abs / 3600);
  const minutes = Math.floor((abs % 3600) / 60);
  const seconds = abs % 60;
  return `${sign}${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

// ─────────────────────────── bron qoidalari ───────────────────────────

/**
 * Bron uchun oldindan to'lov — depozit emas, **1 soatlik summa**.
 * Mijoz kelsa umumiy hisobdan ayiriladi, kelmasa klubda qoladi (jarima).
 * Foiz ham, minimal chegara ham yo'q: hamma uchun bir xil va adolatli.
 */
export const PREPAY_HOURS = 1;

export const prepayAmount = (ratePerHour: number): number => ratePerHour * PREPAY_HOURS;

/** Bron boshlangandan keyin mijoz kutiladigan vaqt (daqiqa). Keyin — no-show. */
export const NO_SHOW_MIN = 10;

/** Seans tugagach xona bo'shatilmasdan kutiladigan vaqt (daqiqa). */
export const GRACE_MIN = 10;

/** Seans tugashidan oldin bildirishnoma yuboriladigan lahzalar (daqiqa). */
export const NOTIFY_BEFORE_MIN = [30, 15];

/** `"19:30"` → 1170 daqiqa. */
export function hhmmToMinutes(value: string): number {
  const match = /^(\d{2}):(\d{2})$/.exec(value);
  if (!match) throw new TypeError(`HH:MM kutildi: ${value}`);
  return Number(match[1]) * 60 + Number(match[2]);
}

/** 1170 → `"19:30"`. */
export function minutesToHhmm(value: number): string {
  const normalized = ((value % 1440) + 1440) % 1440;
  return `${String(Math.floor(normalized / 60)).padStart(2, '0')}:${String(normalized % 60).padStart(2, '0')}`;
}
