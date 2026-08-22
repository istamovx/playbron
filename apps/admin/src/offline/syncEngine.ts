import { ApiError, NetworkError, TimeoutError } from '@playbron/api-client';

import { useBoard } from '../store/board';
import { emit, subscribe } from './bus';
import { COMMAND_EXECUTORS, labelFor } from './commands';
import { isOnline } from './connectivity';
import { listOutboxItems, putConflict, putOutboxItem, pruneSyncedOlderThan } from './db';
import { nextRetryDelayMs } from './backoff';
import { applyOutboxEvent, isRetryable, recoverInterrupted, type OutboxEvent } from './outboxReducer';
import type { CommandAction, CommandPayloadMap, CommandResultMap, OutboxItem } from './types';

/**
 * Sync Engine — audit §6. To'liq shartlar `runCommand()` docstring'ida.
 * Qisqacha: online+muvaffaqiyat — bugungidek, hech narsa navbatga
 * yozilmaydi; online+biznes xato — bugungidek `throw`; faqat tarmoq
 * xatosi (yoki oldindan offline) navbatga tushadi va fon jarayoni
 * (`drainQueue()`/`startSyncEngine()`) uni keyinroq qayta uradi.
 */

const SYNCED_RETENTION_MS = 7 * 24 * 60 * 60 * 1000; // 7 kun

let draining = false;
let timerId: ReturnType<typeof setTimeout> | null = null;

function classify(error: unknown): OutboxEvent {
  if (error instanceof NetworkError || error instanceof TimeoutError) {
    return { type: 'NETWORK_ERROR', message: error.message };
  }
  if (error instanceof ApiError) {
    // 5xx — server vaqtincha yiqilgan, o'zi TUZALADI. Business xato emas.
    if (error.status >= 500) return { type: 'NETWORK_ERROR', message: error.message };
    // Ikkita brauzer tab'i (yoki tab + fon jarayoni) bir xil `Idempotency-Key`
    // qatorini bir vaqtda band qilishga urinsa server shu kodni qaytaradi
    // (`core/idempotency.py::begin()` — "invariant, oddiy oqim emas", lekin
    // ko'p tab holatida amalda yuz beradi). Bu YUTUQSIZLIK emas — boshqa
    // tab hozir aynan shu amalni bajarmoqda — shuning uchun QAYTA URINISH
    // kerak, `FAILED`ga chiqarib tashlash noto'g'ri (amal aslida muvaffaqiyatli
    // bo'lgan bo'lishi mumkin).
    if (error.code === 'IDEMPOTENCY_IN_PROGRESS') {
      return { type: 'NETWORK_ERROR', message: error.message };
    }
    if (error.code === 'VERSION_CONFLICT') {
      return { type: 'VERSION_CONFLICT', message: error.message };
    }
    return { type: 'BUSINESS_ERROR', code: error.code, message: error.message };
  }
  return { type: 'NETWORK_ERROR', message: error instanceof Error ? error.message : String(error) };
}

async function send<A extends CommandAction>(
  item: OutboxItem<A>,
): Promise<{ ok: true; result: CommandResultMap[A] } | { ok: false; error: unknown }> {
  try {
    const executor = COMMAND_EXECUTORS[item.action];
    const result = await executor(item.payload, item.id);
    return { ok: true, result };
  } catch (error) {
    return { ok: false, error };
  }
}

/** Bitta itemni yuborishga urinadi, holatni yozadi va bus'ga xabar beradi. */
async function attemptOne<A extends CommandAction>(
  item: OutboxItem<A>,
): Promise<{ synced: true; result: CommandResultMap[A] } | { synced: false; error?: unknown }> {
  const syncing = applyOutboxEvent(item, { type: 'START_SYNCING' }, Date.now(), 0);
  await putOutboxItem(syncing);
  emit();

  const outcome = await send(syncing);

  if (outcome.ok) {
    await putOutboxItem(applyOutboxEvent(syncing, { type: 'SENT_OK' }, Date.now(), 0));
    emit();
    return { synced: true, result: outcome.result };
  }

  const event = classify(outcome.error);
  const delay = event.type === 'NETWORK_ERROR' ? nextRetryDelayMs(syncing.attempts) : 0;
  const next = applyOutboxEvent(syncing, event, Date.now(), delay);
  await putOutboxItem(next);

  if (event.type === 'VERSION_CONFLICT') {
    await putConflict({
      id: item.id,
      action: item.action,
      label: labelFor(item.action),
      reason: event.message,
      createdAt: Date.now(),
    });
  }

  emit();
  return { synced: false, error: outcome.error };
}

/**
 * UI'ning yagona kirish nuqtasi.
 *
 * Muhim: bu ODDIY (online, muvaffaqiyatli) holatda IndexedDB'ga HECH
 * NARSA YOZMAYDI — faqat ikkita holatda yozadi:
 *   1. Chaqiruv boshlanishidan OLDIN allaqachon offline bo'lsa.
 *   2. Urinish TARMOQ xatosi bilan tugasa (so'rov serverga yetdimi —
 *      noma'lum, keyinroq QAYTA urinish kerak).
 *
 * Biznes xato (masalan `EXTEND_RANGE_INVALID`) va `VERSION_CONFLICT`
 * ODDIY TASHLANADI (queue'ga yozilmasdan) — bular so'rov haqiqatan
 * serverga YETGANI va rad etilgani ma'lum bo'lgan holatlar, xodim buni
 * DARHOL, sinxron tarzda ko'rishi kerak — audit banner'i bunday holatni
 * "keyinroq ko'rib chiqiladigan navbat" sifatida ko'rsatishi noto'g'ri
 * bo'lardi (u allaqachon ko'rsatilgan). `meta.clubId`/`meta.userId` —
 * faqat ko'rsatish uchun saqlanadi, RLS baribir server tomonida.
 */
export async function runCommand<A extends CommandAction>(
  action: A,
  payload: CommandPayloadMap[A],
  meta: { clubId: number; userId: number | null },
): Promise<{ synced: true; result: CommandResultMap[A] } | { synced: false }> {
  // Bitta ID boshidan oxirigacha — agar keyinroq navbatga tushib qayta
  // yuborilsa, xuddi shu `Idempotency-Key` bilan: so'rov birinchi
  // urinishda ALLAQACHON serverga yetgan (faqat javob yo'qolgan) bo'lsa,
  // qayta yuborish ikkinchi marta BAJARILMAYDI — `core/idempotency.py`
  // aynan shu holat uchun.
  const id = crypto.randomUUID();

  const buildItem = (): OutboxItem<A> => ({
    id,
    clubId: meta.clubId,
    userId: meta.userId,
    action,
    payload,
    createdAt: Date.now(),
    attempts: 0,
    nextRetryAt: Date.now(),
    status: 'PENDING',
    lastError: null,
    lastErrorCode: null,
    label: labelFor(action),
  });

  if (!isOnline()) {
    await putOutboxItem(buildItem());
    emit();
    return { synced: false };
  }

  try {
    const result = await COMMAND_EXECUTORS[action](payload, id);
    return { synced: true, result };
  } catch (error) {
    const event = classify(error);
    if (event.type === 'BUSINESS_ERROR' || event.type === 'VERSION_CONFLICT') {
      throw error; // aynan bugungidek — chaqiruvchi ekran o'zi `catch` qiladi
    }
    // Faqat NETWORK_ERROR shu yerga yetadi — navbatga yoziladi va fon
    // sinxronizatsiyasi keyinroq qayta uradi.
    const queued = applyOutboxEvent(buildItem(), event, Date.now(), nextRetryDelayMs(0));
    await putOutboxItem(queued);
    emit();
    return { synced: false };
  }
}

/** Barcha QAYTA URINISHGA TAYYOR itemlarni ketma-ket yuboradi. */
export async function drainQueue(): Promise<void> {
  if (draining) return; // ikki nusxa bir vaqtda ishlamasin
  draining = true;
  try {
    if (!isOnline()) return;
    const now = Date.now();

    // Oldingi seansda "yuborilmoqda" holatida qolib ketgan itemlar
    // (sahifa reload/qulash — audit §29) — `isRetryable()` ularni
    // ko'rmaydi, shu sabab har drain boshida `PENDING`ga tiklanadi.
    const before = await listOutboxItems();
    for (const item of before) {
      if (item.status !== 'SYNCING') continue;
      await putOutboxItem(recoverInterrupted(item, now));
    }

    // Faol klub o'zgargan bo'lishi mumkin (navbatga qo'yilgandan beri) —
    // `X-Club-Id` sarlavhasi YUBORISH PAYTIDAGI faol klubdan olinadi
    // (`lib/api.ts`), item esa YARATILGAN paytdagi klubni saqlaydi. Mos
    // kelmasa `403 CLUB_MISMATCH` bilan yiqilib, doimiy `FAILED`ga
    // o'tib ketardi — o'sha klub qayta faollashguncha shunchaki KUTILADI.
    const activeClubId = useBoard.getState().activeClubId;

    const items = await listOutboxItems();
    for (const item of items) {
      if (!isRetryable(item.status)) continue;
      if (item.nextRetryAt > now) continue;
      if (item.clubId !== activeClubId) continue;
      if (!isOnline()) break; // aylanish davomida ulanish uzilishi mumkin
      await attemptOne(item);
    }
    await pruneSyncedOlderThan(Date.now() - SYNCED_RETENTION_MS);
  } finally {
    draining = false;
  }
}

const POLL_INTERVAL_MS = 5000;

/** Ilova ishga tushishida BIR MARTA chaqiriladi. */
export function startSyncEngine(): () => void {
  // `connectivity.ts` onlayn/offlayn o'zgarganda `bus.emit()` chaqiradi —
  // shu orqali ulanish qaytganda navbat DARHOL tortiladi (5s polling'ni
  // kutmasdan).
  const onBusChange = (): void => {
    if (isOnline()) void drainQueue();
  };
  const unsubscribe = subscribe(onBusChange);

  void drainQueue();
  timerId = setInterval(() => void drainQueue(), POLL_INTERVAL_MS);

  return () => {
    unsubscribe();
    if (timerId !== null) clearInterval(timerId);
    timerId = null;
  };
}
