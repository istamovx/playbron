/**
 * Klub admini yuzasining ma'lumot qatlami.
 * CRUD holati `store/club.ts` da saqlanadi — bu yerda faqat boshlang'ich qiymatlar,
 * turlar va sof hisob funksiyalari.
 */

import { CONSOLES, consoleLabel } from './data';

export { CONSOLES, consoleLabel };

// ─────────────────────────── klub ma'lumoti ───────────────────────────

export interface ClubInfo {
  name: string;
  address: string;
  phone: string;
  /** Cover rasm — data URL yoki tashqi manzil. Bo'sh bo'lsa placeholder. */
  cover: string;
  /** Ish vaqti, yarim tundan daqiqada. */
  opensAt: number;
  closesAt: number;
  about: string;
}

export const CLUB_INIT: ClubInfo = {
  name: 'Neon Arena',
  address: 'Toshkent, Chilonzor, 8-kvartal, 42-uy',
  phone: '+998 71 200-40-40',
  cover: '',
  opensAt: 10 * 60,
  closesAt: 26 * 60,
  about: 'Alohida xonalar, turnir zali va ikkita VIP. Bar buyurtmasi Mini App orqali.',
};

// ─────────────────────────── tariflar ───────────────────────────

/**
 * Tarif — vaqt oynasi va koeffitsiyent. Xonaning soatlik summasi shu
 * koeffitsiyentga ko'paytiriladi, shuning uchun narxni bir joydan boshqariladi.
 */
export interface Tariff {
  id: string;
  label: string;
  from: number;
  to: number;
  factor: number;
}

export const TARIFFS_INIT: Tariff[] = [
  { id: 't1', label: 'Kunduzi', from: 10 * 60, to: 18 * 60, factor: 0.8 },
  { id: 't2', label: 'Kechqurun', from: 18 * 60, to: 24 * 60, factor: 1 },
  { id: 't3', label: 'Tungi', from: 24 * 60, to: 26 * 60, factor: 1.2 },
];

// ─────────────────────────── xonalar ───────────────────────────

export interface Room {
  id: string;
  name: string;
  /** Qavat — bir qavatli klubda ham 1 bo'ladi. */
  floor: number;
  kind: string;
  console: string;
  tv: number;
  pads: number;
  /** Bazaviy soatlik summa, so'm. */
  rate: number;
}

export const ROOM_KINDS = ['Standart', 'Turnir', 'VIP'];

export const ROOMS_INIT: Room[] = [
  { id: 'r1', name: '1-xona', floor: 1, kind: 'Standart', console: 'ps5', tv: 55, pads: 2, rate: 40000 },
  { id: 'r2', name: '2-xona', floor: 1, kind: 'Standart', console: 'ps5', tv: 55, pads: 4, rate: 40000 },
  { id: 'r3', name: '3-xona', floor: 1, kind: 'Standart', console: 'ps5', tv: 55, pads: 2, rate: 40000 },
  { id: 'r4', name: '4-xona', floor: 1, kind: 'Standart', console: 'ps4', tv: 43, pads: 2, rate: 25000 },
  { id: 'r5', name: '5-xona', floor: 1, kind: 'Standart', console: 'ps5', tv: 55, pads: 2, rate: 40000 },
  { id: 'r6', name: '6-xona', floor: 1, kind: 'Standart', console: 'ps3', tv: 40, pads: 2, rate: 18000 },
  { id: 'r7', name: '7-xona', floor: 2, kind: 'Standart', console: 'ps5', tv: 55, pads: 2, rate: 40000 },
  { id: 'r8', name: '8-xona', floor: 2, kind: 'Turnir', console: 'ps5', tv: 65, pads: 4, rate: 50000 },
  { id: 'r9', name: 'VIP-1', floor: 2, kind: 'VIP', console: 'ps5pro', tv: 75, pads: 4, rate: 60000 },
  { id: 'r10', name: 'VIP-2', floor: 2, kind: 'VIP', console: 'ps5pro', tv: 75, pads: 4, rate: 60000 },
];

/** Tarif qo'llangan soatlik summa. */
export const rateWith = (room: Room, tariff: Tariff): number =>
  Math.round((room.rate * tariff.factor) / 1000) * 1000;

// ─────────────────────────── qurilmalar ───────────────────────────

export type DeviceStatus = 'OK' | 'REPAIR' | 'SPARE';

export const DEVICE_STATUS: Record<DeviceStatus, { label: string; tone: string }> = {
  OK: { label: 'Ishlayapti', tone: 'var(--secondary-500)' },
  REPAIR: { label: 'Ta’mirda', tone: 'var(--yellow-100)' },
  SPARE: { label: 'Zaxira', tone: 'var(--text-dim)' },
};

export type DeviceKind = 'console' | 'pad' | 'tv';

export const DEVICE_KIND: Record<DeviceKind, string> = {
  console: 'Konsol',
  pad: 'Joystik',
  tv: 'Ekran',
};

export interface Device {
  id: string;
  kind: DeviceKind;
  /** Konsol uchun `CONSOLES` id'si, qolganlari uchun model nomi. */
  model: string;
  serial: string;
  /** Biriktirilgan xona id'si yoki bo'sh. */
  roomId: string;
  status: DeviceStatus;
}

export const DEVICES_INIT: Device[] = [
  { id: 'd1', kind: 'console', model: 'ps5', serial: 'PS5-8841', roomId: 'r1', status: 'OK' },
  { id: 'd2', kind: 'console', model: 'ps5', serial: 'PS5-8842', roomId: 'r2', status: 'OK' },
  { id: 'd3', kind: 'console', model: 'ps4', serial: 'PS4-2210', roomId: 'r4', status: 'OK' },
  { id: 'd4', kind: 'console', model: 'ps3', serial: 'PS3-1104', roomId: 'r6', status: 'OK' },
  { id: 'd5', kind: 'console', model: 'ps5pro', serial: 'PRO-0071', roomId: 'r9', status: 'OK' },
  { id: 'd6', kind: 'pad', model: 'DualSense', serial: 'DS-4417', roomId: 'r1', status: 'REPAIR' },
  { id: 'd7', kind: 'pad', model: 'DualSense', serial: 'DS-4418', roomId: '', status: 'SPARE' },
  { id: 'd8', kind: 'tv', model: 'LG 55" OLED', serial: 'LG-9930', roomId: 'r1', status: 'OK' },
];

// ─────────────────────────── xodimlar ───────────────────────────

export type StaffStatus = 'ACTIVE' | 'OFF' | 'BLOCKED';

export const STAFF_STATUS: Record<StaffStatus, { label: string; tone: string }> = {
  ACTIVE: { label: 'Ishlayapti', tone: 'var(--secondary-500)' },
  OFF: { label: 'Dam olishda', tone: 'var(--text-dim)' },
  BLOCKED: { label: 'Bloklangan', tone: 'var(--red-100)' },
};

export interface StaffMember {
  id: string;
  name: string;
  phone: string;
  login: string;
  /** `Kunduzi` / `Kechqurun` / `Tungi`. */
  shift: string;
  status: StaffStatus;
  /** Shu oydagi yopilgan hisoblar soni. */
  bills: number;
  /** Shu oyda kassaga tushgan summa. */
  revenue: number;
}

export const SHIFTS = ['Kunduzi', 'Kechqurun', 'Tungi'];

export const STAFF_INIT: StaffMember[] = [
  { id: 's1', name: 'Kamola Rustamova', phone: '+998 90 771-20-14', login: 'kamola', shift: 'Kechqurun', status: 'ACTIVE', bills: 148, revenue: 18400000 },
  { id: 's2', name: 'Doston Ergashev', phone: '+998 93 220-45-08', login: 'doston', shift: 'Kunduzi', status: 'ACTIVE', bills: 121, revenue: 12900000 },
  { id: 's3', name: 'Ulug‘bek Xolmatov', phone: '+998 88 410-33-77', login: 'ulugbek', shift: 'Tungi', status: 'OFF', bills: 96, revenue: 11200000 },
  { id: 's4', name: 'Nigora Sattorova', phone: '+998 94 505-18-62', login: 'nigora', shift: 'Kechqurun', status: 'ACTIVE', bills: 134, revenue: 15800000 },
];

// ─────────────────────────── mahsulotlar ───────────────────────────

export const PRODUCT_CATS = ['Ichimliklar', 'Snack', 'Ovqat'];

export interface Product {
  id: string;
  cat: string;
  name: string;
  /** Sotib olish narxi — foyda shundan hisoblanadi. */
  cost: number;
  price: number;
  /** Kirim qilingan miqdor. */
  start: number;
  /** Sotilgani — kassadan avtomatik to'ladi. */
  sold: number;
}

export const PRODUCTS_INIT: Product[] = [
  { id: 'p1', cat: 'Ichimliklar', name: 'Pepsi 0.5', cost: 7000, price: 12000, start: 48, sold: 17 },
  { id: 'p2', cat: 'Ichimliklar', name: 'Coca-Cola 0.5', cost: 7000, price: 12000, start: 42, sold: 9 },
  { id: 'p3', cat: 'Ichimliklar', name: 'Fuse Tea', cost: 8500, price: 14000, start: 18, sold: 6 },
  { id: 'p4', cat: 'Ichimliklar', name: 'Adrenaline', cost: 11000, price: 18000, start: 12, sold: 6 },
  { id: 'p5', cat: 'Ichimliklar', name: 'Red Bull', cost: 17000, price: 26000, start: 12, sold: 3 },
  { id: 'p6', cat: 'Snack', name: "Lay's", cost: 6000, price: 10000, start: 30, sold: 12 },
  { id: 'p7', cat: 'Snack', name: 'Popcorn', cost: 6500, price: 12000, start: 24, sold: 7 },
  { id: 'p8', cat: 'Snack', name: 'Snickers', cost: 5500, price: 9000, start: 30, sold: 11 },
  { id: 'p9', cat: 'Snack', name: 'Pista', cost: 14000, price: 22000, start: 10, sold: 6 },
  { id: 'p10', cat: 'Ovqat', name: 'Lavash', cost: 20000, price: 32000, start: 14, sold: 5 },
  { id: 'p11', cat: 'Ovqat', name: 'Burger', cost: 24000, price: 38000, start: 12, sold: 4 },
  { id: 'p12', cat: 'Ovqat', name: 'Mini pitsa', cost: 42000, price: 65000, start: 8, sold: 3 },
];

export interface StockRow {
  product: Product;
  left: number;
  revenue: number;
  profit: number;
  /** Qoldiq boshlang'ichning necha foizi. */
  percent: number;
  low: boolean;
}

/** Reestr qatori — qoldiq va foyda sotuvdan chiqadi, qo'lda kiritilmaydi. */
export function stockRow(product: Product): StockRow {
  const left = Math.max(0, product.start - product.sold);
  return {
    product,
    left,
    revenue: product.sold * product.price,
    profit: product.sold * (product.price - product.cost),
    percent: product.start === 0 ? 0 : (left / product.start) * 100,
    low: left <= Math.max(3, Math.round(product.start * 0.15)),
  };
}

// ─────────────────────────── xarajatlar ───────────────────────────

export const EXPENSE_CATS = ['Elektr', 'Suv', 'Ijara', 'Internet', 'Maosh', 'Ta’mir', 'Boshqa'];

export interface Expense {
  id: string;
  /** `DD-MM-YYYY`. */
  date: string;
  cat: string;
  amount: number;
  note: string;
}

export const EXPENSES_INIT: Expense[] = [
  { id: 'e1', date: '01-08-2026', cat: 'Ijara', amount: 9000000, note: 'Avgust ijarasi' },
  { id: 'e2', date: '03-08-2026', cat: 'Elektr', amount: 2450000, note: 'Iyul hisobi' },
  { id: 'e3', date: '05-08-2026', cat: 'Internet', amount: 480000, note: '500 Mbit tarif' },
  { id: 'e4', date: '07-08-2026', cat: 'Ta’mir', amount: 620000, note: '2 ta DualSense almashtirildi' },
  { id: 'e5', date: '10-08-2026', cat: 'Suv', amount: 190000, note: 'Iyul hisobi' },
  { id: 'e6', date: '10-08-2026', cat: 'Maosh', amount: 14200000, note: 'Avans — 4 xodim' },
  { id: 'e7', date: '12-08-2026', cat: 'Boshqa', amount: 340000, note: 'Tozalash vositalari' },
];

// ─────────────────────────── hisobot ───────────────────────────

export type PeriodId = 'day' | 'week' | 'month' | 'year';

export const PERIODS: { id: PeriodId; label: string; bars: number; unit: string }[] = [
  { id: 'day', label: 'Kunlik', bars: 16, unit: 'soat' },
  { id: 'week', label: 'Haftalik', bars: 7, unit: 'kun' },
  { id: 'month', label: 'Oylik', bars: 30, unit: 'kun' },
  { id: 'year', label: 'Yillik', bars: 12, unit: 'oy' },
];

export const PERIOD_LABELS: Record<PeriodId, string[]> = {
  day: ['10:00', '14:00', '18:00', '22:00', '02:00'],
  week: ['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sha', 'Ya'],
  month: ['1', '8', '15', '22', '30'],
  year: ['Yan', 'Apr', 'Iyl', 'Okt'],
};

function hash(value: string): number {
  let h = 2166136261;
  for (let i = 0; i < value.length; i += 1) {
    h ^= value.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/** Barqaror qiymatlar — bir xil davr har safar bir xil grafikni beradi. */
export function seriesFor(period: PeriodId, bars: number): number[] {
  return Array.from({ length: bars }, (_, index) => {
    const raw = hash(`${period}|${index}`) % 1000;
    return 0.35 + (raw / 1000) * 0.65;
  });
}

export interface PeriodTotals {
  revenue: number;
  play: number;
  bar: number;
  expenses: number;
  profit: number;
  sessions: number;
  hours: number;
  /** O'rtacha bandlik, foiz. */
  occupancy: number;
}

const BASE_TOTALS: Record<PeriodId, { revenue: number; sessions: number; occupancy: number }> = {
  day: { revenue: 4180000, sessions: 34, occupancy: 62 },
  week: { revenue: 27400000, sessions: 221, occupancy: 58 },
  month: { revenue: 112600000, sessions: 946, occupancy: 61 },
  year: { revenue: 1284000000, sessions: 10820, occupancy: 57 },
};

/** Davr yakunlari — xarajatlar haqiqiy ro'yxatdan olinadi. */
export function totalsFor(period: PeriodId, expenses: number): PeriodTotals {
  const base = BASE_TOTALS[period];
  const bar = Math.round(base.revenue * 0.22);
  const play = base.revenue - bar;

  return {
    revenue: base.revenue,
    play,
    bar,
    expenses,
    profit: base.revenue - expenses,
    sessions: base.sessions,
    hours: Math.round(base.sessions * 2.1),
    occupancy: base.occupancy,
  };
}

/** Xarajatlarning davrga tegishli ulushi — oylik ro'yxatdan chiqariladi. */
export const EXPENSE_SHARE: Record<PeriodId, number> = {
  day: 1 / 30,
  week: 7 / 30,
  month: 1,
  year: 12,
};
