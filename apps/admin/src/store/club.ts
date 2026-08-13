import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import {
  CLUB_INIT,
  DEVICES_INIT,
  EXPENSES_INIT,
  PRODUCTS_INIT,
  ROOMS_INIT,
  STAFF_INIT,
  TARIFFS_INIT,
  type ClubInfo,
  type Device,
  type Expense,
  type Product,
  type Room,
  type StaffMember,
  type Tariff,
} from '../mock/club';

/**
 * Klub admini kiritadigan hamma narsa shu yerda. CRUD amallari qurilmada
 * saqlanadi — backend ulanganda har biri bitta so'rovga almashadi.
 */
interface ClubState {
  club: ClubInfo;
  tariffs: Tariff[];
  rooms: Room[];
  devices: Device[];
  staff: StaffMember[];
  products: Product[];
  expenses: Expense[];

  setClub: (patch: Partial<ClubInfo>) => void;

  saveTariff: (tariff: Tariff) => void;
  removeTariff: (id: string) => void;

  saveRoom: (room: Room) => void;
  removeRoom: (id: string) => void;

  saveDevice: (device: Device) => void;
  removeDevice: (id: string) => void;

  saveStaff: (member: StaffMember) => void;
  removeStaff: (id: string) => void;

  saveProduct: (product: Product) => void;
  removeProduct: (id: string) => void;
  /** Kirim qo'shish — reestrda boshlang'ich miqdor oshadi. */
  restock: (id: string, amount: number) => void;

  saveExpense: (expense: Expense) => void;
  removeExpense: (id: string) => void;

  /** Boshlang'ich holatga qaytarish. */
  reset: () => void;
}

/** Mavjud bo'lsa almashtiradi, bo'lmasa oxiriga qo'shadi. */
function upsert<T extends { id: string }>(list: T[], item: T): T[] {
  const index = list.findIndex((row) => row.id === item.id);
  if (index < 0) return [...list, item];
  return list.map((row, i) => (i === index ? item : row));
}

let counter = 0;

/** Yangi yozuv uchun id — `Math.random()` siz, barqaror. */
export function nextId(prefix: string): string {
  counter += 1;
  return `${prefix}${Date.now().toString(36)}${counter}`;
}

const INITIAL = {
  club: CLUB_INIT,
  tariffs: TARIFFS_INIT,
  rooms: ROOMS_INIT,
  devices: DEVICES_INIT,
  staff: STAFF_INIT,
  products: PRODUCTS_INIT,
  expenses: EXPENSES_INIT,
};

export const useClub = create<ClubState>()(
  persist(
    (set) => ({
      ...INITIAL,

      setClub: (patch) => set((state) => ({ club: { ...state.club, ...patch } })),

      saveTariff: (tariff) => set((state) => ({ tariffs: upsert(state.tariffs, tariff) })),
      removeTariff: (id) =>
        set((state) => ({ tariffs: state.tariffs.filter((row) => row.id !== id) })),

      saveRoom: (room) => set((state) => ({ rooms: upsert(state.rooms, room) })),
      removeRoom: (id) =>
        set((state) => ({
          rooms: state.rooms.filter((row) => row.id !== id),
          // Xona o'chsa qurilmalar zaxiraga o'tadi, yo'qolmaydi
          devices: state.devices.map((device) =>
            device.roomId === id ? { ...device, roomId: '', status: 'SPARE' as const } : device,
          ),
        })),

      saveDevice: (device) => set((state) => ({ devices: upsert(state.devices, device) })),
      removeDevice: (id) =>
        set((state) => ({ devices: state.devices.filter((row) => row.id !== id) })),

      saveStaff: (member) => set((state) => ({ staff: upsert(state.staff, member) })),
      removeStaff: (id) => set((state) => ({ staff: state.staff.filter((row) => row.id !== id) })),

      saveProduct: (product) => set((state) => ({ products: upsert(state.products, product) })),
      removeProduct: (id) =>
        set((state) => ({ products: state.products.filter((row) => row.id !== id) })),
      restock: (id, amount) =>
        set((state) => ({
          products: state.products.map((row) =>
            row.id === id ? { ...row, start: row.start + amount } : row,
          ),
        })),

      saveExpense: (expense) => set((state) => ({ expenses: upsert(state.expenses, expense) })),
      removeExpense: (id) =>
        set((state) => ({ expenses: state.expenses.filter((row) => row.id !== id) })),

      reset: () => set({ ...INITIAL }),
    }),
    { name: 'playbron.club' },
  ),
);
