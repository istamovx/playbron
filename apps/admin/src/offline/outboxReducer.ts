import type { CommandAction, OutboxItem } from './types';

/**
 * Outbox holat mashinasi — audit §24 ("Offline state machine"):
 *
 *   LOCAL_ONLY → PENDING → SYNCING → SUCCESS → SYNCED
 *                                  → RETRY   → PENDING
 *                                  → 409     → CONFLICT
 *                                  → 4xx     → FAILED
 *
 * Sof funksiya — hech qanday IndexedDB/tarmoq chaqiruvi yo'q, shu sabab
 * DB'siz test bilan to'liq qoplanadi (`sof-funksiya-testi` naqshi, garchi
 * bu pul hisobi emas — biznes-kritik navbat holati bo'lsa ham bir xil
 * qat'iylik bilan).
 */

export type OutboxEvent =
  | { type: 'START_SYNCING' }
  | { type: 'SENT_OK' }
  | { type: 'NETWORK_ERROR'; message: string }
  | { type: 'BUSINESS_ERROR'; code: string; message: string }
  | { type: 'VERSION_CONFLICT'; message: string };

export function applyOutboxEvent<A extends CommandAction>(
  item: OutboxItem<A>,
  event: OutboxEvent,
  now: number,
  retryDelayMs: number,
): OutboxItem<A> {
  switch (event.type) {
    case 'START_SYNCING':
      return { ...item, status: 'SYNCING' };

    case 'SENT_OK':
      return { ...item, status: 'SYNCED', lastError: null, lastErrorCode: null };

    case 'NETWORK_ERROR':
      // Tarmoq xatosi HECH QACHON yakuniy emas — cheksiz qayta uriniladi
      // (`07-patterns.md`dagi fon vazifasi naqshi bilan bir xil falsafa:
      // "Sikl HECH QACHON to'xtamaydi").
      return {
        ...item,
        status: 'PENDING',
        attempts: item.attempts + 1,
        nextRetryAt: now + retryDelayMs,
        lastError: event.message,
        lastErrorCode: null,
      };

    case 'BUSINESS_ERROR':
      // 4xx — validatsiya/ruxsat xatosi. Qayta urinish uni TUZATMAYDI,
      // shuning uchun YAKUNIY: xodim ko'radi, qo'lda hal qiladi.
      return {
        ...item,
        status: 'FAILED',
        attempts: item.attempts + 1,
        lastError: event.message,
        lastErrorCode: event.code,
      };

    case 'VERSION_CONFLICT':
      // 409 VERSION_CONFLICT — avtomatik QAYTA URINILMAYDI (bron holati
      // o'zgargan, xuddi shu buyruqni qayta yuborish noto'g'ri natija
      // berardi). `conflicts` do'koniga alohida yoziladi (audit §16 —
      // "Hech qachon conflictni jimgina overwrite qilmang").
      return {
        ...item,
        status: 'CONFLICT',
        attempts: item.attempts + 1,
        lastError: event.message,
        lastErrorCode: 'VERSION_CONFLICT',
      };
  }
}

/** Fon sinxronizatsiyasi shu holatlarni QAYTA URINADI. */
export function isRetryable(status: OutboxItem['status']): boolean {
  return status === 'PENDING';
}

/**
 * `SYNCING` holatidagi item — tarmoqqa so'rov yuborilgan, lekin javob
 * kelmasdan sahifa yopilgan/qulab tushgan (audit §29: "reload while
 * offline", "browser restart while offline"). `isRetryable()` bunday
 * itemni QAYTA olmaydi (faqat `PENDING`), ya'ni tozalanmasa NAVBAT
 * ABADIY qotib qoladi.
 *
 * Xavfsiz qayta urinish: `id` = `Idempotency-Key`, birinchi so'rov
 * haqiqatan serverga yetgan bo'lsa ham (faqat javob yo'qolgan), qayta
 * yuborish ikkinchi marta BAJARILMAYDI (`core/idempotency.py`) —
 * shuning uchun `PENDING`ga qaytarish xavfsiz.
 */
export function recoverInterrupted<A extends CommandAction>(
  item: OutboxItem<A>,
  now: number,
): OutboxItem<A> {
  if (item.status !== 'SYNCING') return item;
  return { ...item, status: 'PENDING', nextRetryAt: now };
}

/** Banner'da alohida ko'rsatiladigan, xodim e'tibori kerak bo'lgan holatlar. */
export function needsAttention(status: OutboxItem['status']): boolean {
  return status === 'FAILED' || status === 'CONFLICT';
}
