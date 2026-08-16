import { useEffect } from 'react';
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import { BASE, EXTEND_STEP_MIN, MENU, SESSION_END, type CustomerOrder, type ScreenId } from '../mock/data';
import { ANY } from '../lib/slots';

/**
 * Mijoz ilovasining holati — prototipdagi `Component.state` ning o'zi
 * (`docs/designs/PlayBron Mijoz.dc.html`).
 */
interface AppState {
  screen: ScreenId;
  /** Push navigatsiya tarixi — BackButton shundan ishlaydi. */
  stack: ScreenId[];
  tick: number;
  sort: string;
  /** Ko'rilayotgan/tanlangan klub — `clubs.tsx`da tanlanadi, `null` — hali yo'q. */
  clubId: number | null;
  /** Slot filtri: xona turi va konsol (`ANY` — barchasi). */
  room: string;
  console: string;
  /** Tanlangan davomiylik, soatda. */
  hours: number;
  /** Tanlangan kun — bugundan boshlab indeks. */
  day: number;
  /** Tanlangan boshlanish vaqti — yarim tundan daqiqada. */
  start: number;
  /** Tanlangan stansiya ID'si (`null` — hali yo'q). */
  station: number | null;
  /** Bron uchun tanlangan konsol turi (`''` — hali yo'q).
   *
   * FILTRDAGI `console`dan FARQ QILADI: u qidiruv filtri (`ANY` bo'lishi
   * mumkin), bu esa bronga YOZILADIGAN aniq qiymat. Xona konsolsiz
   * (0023'dan keyingi) bo'lsa server uni MAJBURIY talab qiladi
   * (`CONSOLE_TYPE_REQUIRED`) — audit topilmasi, 2026-08-16: shusiz
   * yangi klublarda mijoz umuman bron qila olmasdi. */
  bookingConsole: string;
  pay: string;
  cat: string;
  payFinal: string;
  receipt: 'none' | 'sent';
  cart: Record<string, number>;
  /** Aktiv seansga qo'shilgan vaqt, daqiqa. */
  extendMin: number;
  /** Yuborilgan bildirishnomalar — takrorlanmasligi uchun. */
  notified: string[];
  /** Barga yuborilgan buyurtmalar. */
  orders: CustomerOrder[];

  go: (screen: ScreenId) => void;
  back: () => void;
  tab: (screen: ScreenId) => void;
  bump: (id: string, delta: number) => void;
  setSort: (sort: string) => void;
  setClubId: (clubId: number) => void;
  setRoom: (room: string) => void;
  setConsole: (console: string) => void;
  setHours: (hours: number) => void;
  setDay: (day: number) => void;
  setStart: (start: number) => void;
  setStation: (station: number | null) => void;
  setBookingConsole: (consoleType: string) => void;
  setPay: (pay: string) => void;
  setCat: (cat: string) => void;
  setPayFinal: (pay: string) => void;
  setReceipt: (receipt: 'none' | 'sent') => void;
  extend: () => void;
  markNotified: (key: string) => void;
  /** Savatni barga yuboradi va bo'shatadi. */
  sendOrder: () => void;
  tickOnce: () => void;
}

export const useApp = create<AppState>()((set) => ({
  screen: 'clubs',
  stack: [],
  tick: 0,
  sort: 'Yaqin',
  clubId: null,
  room: ANY,
  console: ANY,
  hours: 2,
  day: 0,
  start: 21 * 60 + 30,
  station: null,
  bookingConsole: '',
  pay: 'Payme',
  cat: 'Ichimliklar',
  payFinal: 'Naqd',
  receipt: 'none',
  // Savat BO'SH boshlanadi. Avval `{ m1: 2, m7: 1 }` edi — prototip
  // qoldig'i: ilova har ochilganda savatda "2× Pepsi + 1× Lay's"
  // oldindan turardi (audit topilmasi, 2026-08-16).
  cart: {},
  extendMin: 0,
  notified: [],
  orders: [],

  go: (screen) => set((state) => ({ screen, stack: [...state.stack, state.screen] })),
  back: () =>
    set((state) =>
      state.stack.length
        ? { screen: state.stack[state.stack.length - 1] as ScreenId, stack: state.stack.slice(0, -1) }
        : state,
    ),
  tab: (screen) => set({ screen, stack: [] }),

  bump: (id, delta) =>
    set((state) => {
      const cart = { ...state.cart };
      cart[id] = Math.max(0, (cart[id] ?? 0) + delta);
      if (!cart[id]) delete cart[id];
      return { cart };
    }),

  setSort: (sort) => set({ sort }),
  setClubId: (clubId) => set({ clubId, station: null, bookingConsole: '' }),
  setRoom: (room) => set({ room }),
  setConsole: (console) => set({ console }),
  setHours: (hours) => set({ hours }),
  setDay: (day) => set({ day }),
  setStart: (start) => set({ start }),
  setStation: (station) => set({ station }),
  setBookingConsole: (bookingConsole) => set({ bookingConsole }),
  setPay: (pay) => set({ pay }),
  setCat: (cat) => set({ cat }),
  setPayFinal: (payFinal) => set({ payFinal }),
  setReceipt: (receipt) => set({ receipt }),

  // Uzaytirilgach ogohlantirishlar yangi tugash vaqti bo'yicha qaytadan yuboriladi
  extend: () =>
    set((state) => ({ extendMin: state.extendMin + EXTEND_STEP_MIN, notified: [] })),
  markNotified: (key) =>
    set((state) => (state.notified.includes(key) ? state : { notified: [...state.notified, key] })),

  sendOrder: () =>
    set((state) => {
      const lines = Object.entries(state.cart)
        .filter(([, qty]) => qty > 0)
        .map(([id, qty]) => ({ id, qty }));
      if (lines.length === 0) return state;

      const amount = lines.reduce(
        (sum, line) => sum + (MENU.find((item) => item.id === line.id)?.price ?? 0) * line.qty,
        0,
      );

      return {
        cart: {},
        orders: [
          ...state.orders,
          {
            code: `B-${101 + state.orders.length}`,
            at: BASE + state.tick,
            lines,
            amount,
          },
        ],
      };
    }),

  tickOnce: () => set((state) => ({ tick: state.tick + 1 })),
}));

/**
 * Mijoz profili — bir marta ro'yxatdan o'tadi va saqlanib qoladi.
 * Xodimdan farqli o'laroq bu yerda qayta kirish va sessiya muddati yo'q.
 */
export interface Profile {
  name: string;
  phone: string;
  registeredAt: string;
}

interface ProfileState {
  /** Hisob — chiqilganda ham qurilmada qoladi. */
  profile: Profile | null;
  /** Profilga kirilganmi. Chiqish faqat shuni o'chiradi. */
  signedIn: boolean;
  /** Interfeys tili — `LANGS` dagi id. */
  lang: string;
  /** Seans bildirishnomalari yoqilganmi. */
  notify: boolean;
  /** Bron boshlanishidan oldingi eslatma. */
  remind: boolean;
  /** Haptik javob — Telegram ichida seziladi. */
  haptics: boolean;

  register: (profile: Omit<Profile, 'registeredAt'>) => void;
  update: (patch: Partial<Omit<Profile, 'registeredAt'>>) => void;
  setLang: (lang: string) => void;
  setNotify: (notify: boolean) => void;
  setRemind: (remind: boolean) => void;
  setHaptics: (haptics: boolean) => void;
  /** Profildan chiqish — ma'lumot o'chmaydi, bir bosishda qaytiladi. */
  signOut: () => void;
  signIn: () => void;
  /** Boshqa raqam bilan boshlash — saqlangan hisob o'chadi. */
  forget: () => void;
}

export const useProfile = create<ProfileState>()(
  persist(
    (set) => ({
      profile: null,
      signedIn: true,
      lang: 'uz',
      notify: true,
      remind: true,
      haptics: true,

      register: (profile) =>
        set({ profile: { ...profile, registeredAt: new Date().toISOString() }, signedIn: true }),
      update: (patch) =>
        set((state) => (state.profile ? { profile: { ...state.profile, ...patch } } : state)),
      setLang: (lang) => set({ lang }),
      setNotify: (notify) => set({ notify }),
      setRemind: (remind) => set({ remind }),
      setHaptics: (haptics) => set({ haptics }),
      signOut: () => set({ signedIn: false }),
      signIn: () => set({ signedIn: true }),
      forget: () => set({ profile: null, signedIn: true }),
    }),
    { name: 'playbron.customer' },
  ),
);

/**
 * Hozirgi lahza — yarim tundan SONIYADA, KLUB vaqt zonasida.
 *
 * Avval `BASE + tick` edi, ya'ni soat DOIM 20:14:32 dan sanardi
 * (prototip qoldig'i) va header'da HAR BIR ekranda noto'g'ri vaqt
 * ko'rinardi — vaqt tanlaydigan ilovada bu bevosita chalg'ituvchi
 * (audit topilmasi, 2026-08-16). `tick` faqat qayta render uchun
 * o'qiladi; qiymat esa har chaqiruvda haqiqiy soatdan olinadi.
 */
export function useNow(timezone = 'Asia/Tashkent'): number {
  useApp((state) => state.tick);
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: timezone,
    hourCycle: 'h23',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).formatToParts(new Date());
  const raw: Record<string, string> = {};
  for (const part of parts) {
    if (part.type !== 'literal') raw[part.type] = part.value;
  }
  return (Number(raw.hour) % 24) * 3600 + Number(raw.minute) * 60 + Number(raw.second);
}

/** Uzaytirishlarni hisobga olgan seans tugash lahzasi. */
export function useSessionEnd(): number {
  return SESSION_END + useApp((state) => state.extendMin) * 60;
}

export function useClock(): void {
  const tickOnce = useApp((state) => state.tickOnce);
  useEffect(() => {
    const timer = setInterval(tickOnce, 1000);
    return () => clearInterval(timer);
  }, [tickOnce]);
}
