import { formatSum, minutesToHhmm } from '@playbron/ui';

/**
 * Formatlash — dizayn tizimidagi umumiy funksiyalar ustidagi yupqa qatlam.
 *
 * Avval `mock/data.ts` da o'z nusxasi bor edi (`S`, `HM`, `CLK`, `DUR`) va
 * konsoldagi formatdan mustaqil ravishda o'zgarardi. Endi manba bitta —
 * `@playbron/ui/format.ts`.
 */

/**
 * So'm — 3 xonali guruh (`182 000`). Pul butun son, kasr yo'q.
 *
 * `BigInt()` yaroqsiz songa `RangeError` OTADI (`NaN` qaytarmaydi), ya'ni
 * eski API nusxasidan `play_amount`siz javob kelsa xato render paytida
 * chiqib butun ekranni oqartirardi. Bunday holda chiziqcha ko'rsatiladi.
 */
export const money = (value: number): string =>
  Number.isFinite(value) ? formatSum(BigInt(Math.round(value))) : '—';

/** Kun ichidagi daqiqa → `HH:MM`. */
export const hhmm = (minutes: number): string => minutesToHhmm(minutes);

/** Sekundni `HH:MM` ga keltiradi (yuqori paneldagi soat). */
export const clock = (seconds: number): string => minutesToHhmm(Math.floor(seconds / 60));
