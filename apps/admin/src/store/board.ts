import { prepayAmount } from '@playbron/ui';
import { useEffect } from 'react';
import { create } from 'zustand';

import {
  BASE,
  BONUS,
  CARTS,
  MENU,
  ORDERS,
  ORDER_FLOW,
  S,
  ST,
  type MockOrder,
  type ScreenId,
} from '../mock/data';

/** POS chekining tarkibi (prototipdagi `closed`). */
export interface ClosedBill {
  code: string;
  room: string;
  guest: string;
  hours: string;
  play: string;
  bar: string;
  total: string;
  method: string;
  at: string;
  points: number;
}

/**
 * Xodim konsolining holati — prototipdagi `Component.state` ning aynan o'zi
 * (`docs/designs/PlayBron Xodim.dc.html`). Server manbai ulanganda shu kalitlar
 * o'rnini TanStack Query egallaydi.
 */
interface BoardState {
  screen: ScreenId;
  /** Faol klub — API'ga `X-Club-Id` sarlavhasida ketadi va RLS kontekstini belgilaydi. */
  activeClubId: number | null;
  /** Tanlangan stansiya (Live board). */
  sel: number;
  /** Har sekundda o'sadi — soat va taymerlar shundan. */
  tick: number;
  menuCat: string;
  /** Katalog qidiruvi — bo'sh bo'lmasa barcha kategoriyalar bo'ylab qidiriladi. */
  search: string;
  day: string;
  drawerOpen: boolean;
  nsMarked: boolean;
  /** Reestrda sanalgan qoldiq: menu id → soni. */
  counted: Record<string, number>;
  pay: 'Naqd' | 'O‘tkazma';
  receipt: 'waiting' | 'uploaded' | 'confirmed' | 'rejected';
  extendFor: number | null;
  extendMin: number;
  /** Stansiya id → qo'shilgan daqiqa. */
  extended: Record<number, number>;
  posSel: number;
  /** Yopilgan chek (POS) — prototipdagi `closed` obyektining o'zi. */
  closed: ClosedBill | null;
  /** Yopilgan xona → o'ynagan oyna (timeline tarixiga tushadi). */
  closedRooms: Record<number, { from: number; to: number }>;
  carts: Record<number, Record<string, number>>;
  orders: MockOrder[];

  setScreen: (screen: ScreenId) => void;
  setActiveClub: (activeClubId: number | null) => void;
  select: (id: number) => void;
  setMenuCat: (cat: string) => void;
  setSearch: (query: string) => void;
  setDay: (day: string) => void;
  setDrawer: (open: boolean) => void;
  setPay: (pay: 'Naqd' | 'O‘tkazma') => void;
  setReceipt: (receipt: 'waiting' | 'uploaded' | 'confirmed' | 'rejected') => void;
  setPosSel: (id: number) => void;
  markNoShow: () => void;
  openExtend: (id: number) => void;
  closeExtend: () => void;
  setExtendMin: (minutes: number) => void;
  confirmExtend: () => void;
  /** Buyurtmani zanjir bo'ylab keyingi holatga suradi. */
  advance: (id: string) => void;
  /** Reestr sanog'i: joriy qiymatga `delta` qo'shadi (0 dan pastga tushmaydi). */
  count: (id: string, expected: number, delta: number) => void;
  /** Savat qadami. */
  bump: (menuId: string, delta: number) => void;
  /** Hisobni yopadi: chek yaratiladi, xona bo'shaydi, keyingi ochiq hisob tanlanadi. */
  closeBill: (at: string) => void;
  newBill: () => void;
  tickOnce: () => void;
}

export const useBoard = create<BoardState>()((set) => ({
  screen: 'live',
  activeClubId: null,
  sel: 1,
  tick: 0,
  menuCat: 'Ichimliklar',
  search: '',
  day: 'Bugun',
  drawerOpen: false,
  nsMarked: false,
  counted: {},
  pay: 'O‘tkazma',
  receipt: 'uploaded',
  extendFor: null,
  extendMin: 60,
  extended: {},
  posSel: 1,
  closed: null,
  closedRooms: {},
  carts: CARTS,
  orders: ORDERS,

  setScreen: (screen) => set({ screen, drawerOpen: false }),
  setActiveClub: (activeClubId) => set({ activeClubId }),
  select: (sel) => set({ sel }),
  setMenuCat: (menuCat) => set({ menuCat, search: '' }),
  setSearch: (search) => set({ search }),
  setDay: (day) => set({ day }),
  setDrawer: (drawerOpen) => set({ drawerOpen }),
  setPay: (pay) => set({ pay }),
  setReceipt: (receipt) => set({ receipt }),
  setPosSel: (posSel) => set({ posSel }),
  markNoShow: () => set({ nsMarked: true }),

  openExtend: (id) => set({ extendFor: id, extendMin: 60 }),
  closeExtend: () => set({ extendFor: null }),
  setExtendMin: (extendMin) => set({ extendMin }),
  confirmExtend: () =>
    set((state) => {
      if (state.extendFor === null) return state;
      const extended = { ...state.extended };
      extended[state.extendFor] = (extended[state.extendFor] ?? 0) + state.extendMin;
      return { extended, extendFor: null };
    }),

  advance: (id) =>
    set((state) => ({
      orders: state.orders.map((order) => {
        if (order.id !== id) return order;
        const index = ORDER_FLOW.indexOf(order.status);
        return index < 3 ? { ...order, status: ORDER_FLOW[index + 1] as MockOrder['status'] } : order;
      }),
    })),

  count: (id, expected, delta) =>
    set((state) => {
      const counted = { ...state.counted };
      const current = counted[id] === undefined ? expected : counted[id];
      counted[id] = Math.max(0, (current as number) + delta);
      return { counted };
    }),

  bump: (menuId, delta) =>
    set((state) => {
      const carts = { ...state.carts };
      const cart = { ...(carts[state.posSel] ?? {}) };
      cart[menuId] = (cart[menuId] ?? 0) + delta;
      if ((cart[menuId] as number) <= 0) delete cart[menuId];
      carts[state.posSel] = cart;
      return { carts };
    }),

  closeBill: (at) =>
    set((state) => {
      const station = ST.find((item) => item.id === state.posSel);
      if (!station) return state;

      const cart = state.carts[state.posSel] ?? {};
      const bar = Object.entries(cart).reduce(
        (sum, [id, qty]) => sum + (MENU.find((item) => item.id === id)?.price ?? 0) * qty,
        0,
      );
      const extra = state.extended[station.id] ?? 0;
      const hours = (station.b + extra - station.a) / 60;
      const play = Math.round(hours * station.rate);
      const prepaid = prepayAmount(station.rate);
      const bonus = BONUS[station.id] ?? 0;
      const total = Math.max(0, play + bar - prepaid - bonus);

      const closedRooms = {
        ...state.closedRooms,
        [state.posSel]: { from: station.a, to: station.b + extra },
      };
      const stillOpen = ST.filter(
        (item) => item.status === 'OCCUPIED' && item.id !== state.posSel && !closedRooms[item.id],
      );

      return {
        closedRooms,
        posSel: stillOpen.length ? (stillOpen[0] as (typeof ST)[number]).id : state.posSel,
        closed: {
          code: `CS-${2040 + state.posSel}`,
          room: station.code,
          guest: station.guest ?? '',
          hours: `${hours.toFixed(1).replace('.0', '')} soat`,
          play: S(play),
          bar: S(bar),
          total: S(total),
          method: state.pay,
          at,
          points: Math.floor(total / 1000),
        },
      };
    }),

  newBill: () => set({ closed: null }),
  tickOnce: () => set((state) => ({ tick: state.tick + 1 })),
}));

/**
 * Joriy vaqt — yarim tundan sekundlarda, brauzer soatidan (klub mintaqasi).
 * Har sekundda `tick` o'zgargani uchun komponentlar qayta render bo'ladi.
 */
export function useNow(): number {
  useBoard((state) => state.tick);
  const now = new Date();
  return now.getHours() * 3600 + now.getMinutes() * 60 + now.getSeconds();
}

/** Prototipdagi qotirilgan lahza (20:14:32) — solishtirish kerak bo'lsa. */
export const MOCK_NOW = BASE;

/** Soatni bir marta ishga tushiradi (shell'da chaqiriladi). */
export function useClock(): void {
  const tickOnce = useBoard((state) => state.tickOnce);
  useEffect(() => {
    const timer = setInterval(tickOnce, 1000);
    return () => clearInterval(timer);
  }, [tickOnce]);
}
