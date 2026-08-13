import { prepayAmount } from '@playbron/ui';

import { BONUS_POINTS, MENU, POINT_RATE, type CustomerOrder } from '../mock/data';

export interface Bill {
  /** O'yin summasi. */
  play: number;
  /** Bar buyurtmalari. */
  bar: number;
  /** Bron uchun oldindan to'langan 1 soatlik summa. */
  prepaid: number;
  /** Bonus ball ekvivalenti. */
  bonus: number;
  /** Klubda to'lanadigan qoldiq. */
  total: number;
}

/** Hisob — mijoz va xodim bir xil formuladan foydalanadi. */
export function billOf(hours: number, rate: number, bar: number): Bill {
  const play = Math.round(hours * rate);
  const prepaid = prepayAmount(rate);
  const bonus = BONUS_POINTS * POINT_RATE;
  return { play, bar, prepaid, bonus, total: Math.max(0, play + bar - prepaid - bonus) };
}

export const orderTotal = (orders: CustomerOrder[]): number =>
  orders.reduce((sum, order) => sum + order.amount, 0);

export const cartTotal = (cart: Record<string, number>): number =>
  Object.entries(cart).reduce(
    (sum, [id, qty]) => sum + (MENU.find((item) => item.id === id)?.price ?? 0) * qty,
    0,
  );

export const cartCount = (cart: Record<string, number>): number =>
  Object.values(cart).reduce((sum, qty) => sum + qty, 0);
