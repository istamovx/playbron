import { CLUB_TIMEZONE } from '@playbron/ui';
import { useEffect } from 'react';
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import { ANY } from '../lib/slots';
import type { ScreenId } from '../nav';

/**
 * Mijoz ilovasining KO'RINISH holati — navigatsiya va bron oqimidagi tanlov.
 *
 * Bu yerda ma'lumot SAQLANMAYDI: klublar, xonalar, bandlik va bronlar
 * `store/booking.ts` orqali serverdan keladi. Avval shu faylda savat, bar
 * buyurtmalari va "aktiv seans" simulyatsiyasi ham bor edi (`mock/data.ts`
 * konstantalaridan) — mijoz rolida ular soxta hisob ko'rsatardi, shuning
 * uchun butunlay olib tashlandi (loyiha egasi, 2026-08-17).
 */
interface AppState {
  screen: ScreenId;
  /** Push navigatsiya tarixi — «orqaga» shundan ishlaydi. */
  stack: ScreenId[];
  /** Soniyalik takt — taymer va soat shu bilan qayta chiziladi. */
  tick: number;
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

  go: (screen: ScreenId) => void;
  back: () => void;
  tab: (screen: ScreenId) => void;
  setClubId: (clubId: number) => void;
  setRoom: (room: string) => void;
  setConsole: (console: string) => void;
  setHours: (hours: number) => void;
  setDay: (day: number) => void;
  setStart: (start: number) => void;
  setStation: (station: number | null) => void;
  setBookingConsole: (consoleType: string) => void;
  tickOnce: () => void;
}

export const useApp = create<AppState>()((set) => ({
  screen: 'clubs',
  stack: [],
  tick: 0,
  clubId: null,
  room: ANY,
  console: ANY,
  hours: 2,
  day: 0,
  // Klub yuklangach `slots.tsx` uni birinchi BO'SH slotga tuzatadi.
  start: 20 * 60,
  station: null,
  bookingConsole: '',

  go: (screen) => set((state) => ({ screen, stack: [...state.stack, state.screen] })),
  back: () =>
    set((state) =>
      state.stack.length
        ? {
            screen: state.stack[state.stack.length - 1] as ScreenId,
            stack: state.stack.slice(0, -1),
          }
        : state,
    ),
  tab: (screen) => set({ screen, stack: [] }),

  setClubId: (clubId) => set({ clubId, station: null, bookingConsole: '' }),
  setRoom: (room) => set({ room }),
  setConsole: (console) => set({ console }),
  setHours: (hours) => set({ hours }),
  setDay: (day) => set({ day }),
  setStart: (start) => set({ start }),
  // Konsol tanlovi HAR stansiya almashganda tozalanadi: konsolsiz
  // stansiyada 'ps5' tanlab, keyin ps4 stansiyaga o'tilsa narx ps5
  // tarifi bo'yicha so'ralib, bron ps4 bo'yicha yaratilardi.
  setStation: (station) => set({ station, bookingConsole: '' }),
  setBookingConsole: (bookingConsole) => set({ bookingConsole }),

  tickOnce: () => set((state) => ({ tick: state.tick + 1 })),
}));

/**
 * Mijoz profili — Telegram orqali bir marta olinadi va qurilmada qoladi.
 *
 * Ism va telefon SERVERNIKI (`initData` → `signInWithInitData`): bu yerda
 * ular faqat ko'rsatish uchun saqlanadi, tahrirlanmaydi — `PATCH /me`
 * endpoint'i yo'q va avvalgi "Saqlash" tugmasi hech qayerga yubormasdi.
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
  /** Seans tugashidan oldingi ILOVA ICHIDAGI ogohlantirish. */
  notify: boolean;
  /** Haptik javob — Telegram ichida seziladi. */
  haptics: boolean;

  register: (profile: Omit<Profile, 'registeredAt'>) => void;
  setNotify: (notify: boolean) => void;
  setHaptics: (haptics: boolean) => void;
  /** Profildan chiqish — ma'lumot o'chmaydi, bir bosishda qaytiladi. */
  signOut: () => void;
  signIn: () => void;
}

export const useProfile = create<ProfileState>()(
  persist(
    (set) => ({
      profile: null,
      signedIn: true,
      notify: true,
      haptics: true,

      register: (profile) =>
        set((state) => ({
          // `registeredAt` — BIRINCHI kirish sanasi; har ochilishda
          // yangilansa "N dan beri" doim bugungi kunni ko'rsatardi.
          profile: {
            ...profile,
            registeredAt: state.profile?.registeredAt ?? new Date().toISOString(),
          },
          signedIn: true,
        })),
      setNotify: (notify) => set({ notify }),
      setHaptics: (haptics) => set({ haptics }),
      signOut: () => set({ signedIn: false }),
      signIn: () => set({ signedIn: true }),
    }),
    { name: 'playbron.customer' },
  ),
);

/**
 * Hozirgi lahza — yarim tundan SONIYADA, berilgan vaqt zonasida.
 *
 * Avval `BASE + tick` edi, ya'ni soat DOIM 20:14:32 dan sanardi
 * (prototip qoldig'i) va header'da HAR BIR ekranda noto'g'ri vaqt
 * ko'rinardi — vaqt tanlaydigan ilovada bu bevosita chalg'ituvchi
 * (audit topilmasi, 2026-08-16). `tick` faqat qayta render uchun
 * o'qiladi; qiymat esa har chaqiruvda haqiqiy soatdan olinadi.
 */
export function useNow(timezone: string = CLUB_TIMEZONE): number {
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

/** Hozirgi lahza, epoch millisekund. Taymerlar shu bilan sanaydi —
 * lahzalar taqqoslashda vaqt zonasi qatnashmaydi. */
export function useNowMs(): number {
  useApp((state) => state.tick);
  return Date.now();
}

export function useClock(): void {
  const tickOnce = useApp((state) => state.tickOnce);
  useEffect(() => {
    const timer = setInterval(tickOnce, 1000);
    return () => clearInterval(timer);
  }, [tickOnce]);
}
