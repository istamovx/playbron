import {
  createCustomerBooking,
  errorText,
  listClubs,
  listDayBookings,
  listMyBookings,
  listStations,
  type BookingDto,
  type ClubDto,
  type DayBookingDto,
  type MyBookingDto,
  type StationDto,
} from '@playbron/api-client';
import { create } from 'zustand';

import { api } from '../lib/api';

/**
 * Real bron ma'lumoti — `store/app.ts`dagi (seans, bar, hisob) simulyatordan
 * ATAYLAB ajratilgan: bu yerdagi hammasi haqiqiy backend'ga boradi
 * (`api/src/playbron/modules/bookings/*`), u yerdagi hech narsa hali yo'q.
 */
interface BookingState {
  clubs: ClubDto[];
  clubsLoading: boolean;
  clubsError: string | null;
  loadClubs: () => Promise<void>;

  stations: StationDto[];
  stationsLoading: boolean;
  stationsError: string | null;
  loadStations: (clubId: number) => Promise<void>;

  /** Kalit — `YYYY-MM-DD`. Kun almashganda qayta yuklanadi. */
  dayBookings: Record<string, DayBookingDto[]>;
  dayLoading: boolean;
  dayError: string | null;
  loadDay: (clubId: number, dateKey: string) => Promise<void>;

  submitting: boolean;
  submitError: string | null;
  lastBooking: BookingDto | null;
  submitBooking: (
    clubId: number,
    stationId: number,
    startsAtIso: string,
    hours: number,
    /** Xona konsolsiz (0023'dan keyingi) bo'lsa MAJBURIY — aks holda
     * server 400 `CONSOLE_TYPE_REQUIRED` qaytaradi (audit topilmasi,
     * 2026-08-16: yangi klublarda mijoz umuman bron qila olmasdi). */
    consoleType?: string,
  ) => Promise<boolean>;
  clearSubmitError: () => void;

  myBookings: MyBookingDto[];
  myBookingsLoading: boolean;
  myBookingsError: string | null;
  loadMyBookings: () => Promise<void>;
}

export const useBooking = create<BookingState>()((set) => ({
  clubs: [],
  clubsLoading: false,
  clubsError: null,
  loadClubs: async () => {
    set({ clubsLoading: true, clubsError: null });
    try {
      const clubs = await listClubs(api);
      set({ clubs, clubsLoading: false });
    } catch (cause) {
      set({ clubsLoading: false, clubsError: errorText(cause) });
    }
  },

  stations: [],
  stationsLoading: false,
  stationsError: null,
  loadStations: async (clubId) => {
    set({ stationsLoading: true, stationsError: null });
    try {
      const stations = await listStations(api, clubId);
      set({ stations, stationsLoading: false });
    } catch (cause) {
      set({ stationsLoading: false, stationsError: errorText(cause) });
    }
  },

  dayBookings: {},
  dayLoading: false,
  dayError: null,
  loadDay: async (clubId, dateKey) => {
    set({ dayLoading: true, dayError: null });
    try {
      const rows = await listDayBookings(api, clubId, dateKey);
      set((state) => ({ dayBookings: { ...state.dayBookings, [dateKey]: rows }, dayLoading: false }));
    } catch (cause) {
      set({ dayLoading: false, dayError: errorText(cause) });
    }
  },

  submitting: false,
  submitError: null,
  lastBooking: null,
  submitBooking: async (clubId, stationId, startsAtIso, hours, consoleType) => {
    set({ submitting: true, submitError: null });
    try {
      const booking = await createCustomerBooking(api, clubId, {
        stationId,
        startsAt: startsAtIso,
        hours,
        consoleType,
      });
      set({ submitting: false, lastBooking: booking });
      return true;
    } catch (cause) {
      set({ submitting: false, submitError: errorText(cause) });
      return false;
    }
  },
  clearSubmitError: () => set({ submitError: null }),

  myBookings: [],
  myBookingsLoading: false,
  myBookingsError: null,
  loadMyBookings: async () => {
    set({ myBookingsLoading: true, myBookingsError: null });
    try {
      const rows = await listMyBookings(api);
      set({ myBookings: rows, myBookingsLoading: false });
    } catch (cause) {
      set({ myBookingsLoading: false, myBookingsError: errorText(cause) });
    }
  },
}));

// Modul darajasida bitta doimiy massiv — har chaqiruvda yangi `[]` qaytarilsa
// zustand'ning `useSyncExternalStore` snapshot'i har render YANGI referens
// deb hisoblab, cheksiz render tsikliga olib kelardi.
const EMPTY_DAY_BOOKINGS: DayBookingDto[] = [];

/** `dayBookings` keshidan joriy kunni o'qiydi — topilmasa bo'sh ro'yxat. */
export function useDayBookings(dateKey: string): DayBookingDto[] {
  return useBooking((state) => state.dayBookings[dateKey] ?? EMPTY_DAY_BOOKINGS);
}
