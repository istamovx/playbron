/**
 * Exponential backoff + jitter — audit §6 ("Retry"): 1s/2s/4s/8s/16s/30s/60s,
 * yuqori chegara bilan, tasodifiy jitter qo'shilgan.
 *
 * Sof funksiya — DB'siz, DOM'siz, `random` INJECTSIYA qilinadi (test
 * determinizmi uchun). Sukut manba `Math.random()` EMAS —
 * `crypto.getRandomValues()` (loyihada `Math.random` cheklangan,
 * `screens/admin/staff.tsx`dagi bilan bir xil sabab).
 */

const STEPS_MS = [1000, 2000, 4000, 8000, 16_000, 30_000, 60_000] as const;
const JITTER_RATIO = 0.2;
const MIN_DELAY_MS = 500;

function randomUnit(): number {
  const bytes = new Uint32Array(1);
  crypto.getRandomValues(bytes);
  return (bytes[0] ?? 0) / 2 ** 32;
}

export function nextRetryDelayMs(attempts: number, random: () => number = randomUnit): number {
  const stepIndex = Math.max(0, Math.min(attempts, STEPS_MS.length - 1));
  const base = STEPS_MS[stepIndex] ?? STEPS_MS[0];
  // `random()` [0,1) → [-1,1) ga ko'chiriladi, ±20% jitter beradi.
  const jitter = base * JITTER_RATIO * (random() * 2 - 1);
  return Math.max(MIN_DELAY_MS, Math.round(base + jitter));
}
