/**
 * Prototip mock ma'lumoti — `docs/designs/PlayBron Xodim.dc.html` dan aynan ko'chirilgan.
 * Qiymatlar o'zgartirilmaydi: ekranlar dizayn bilan 1:1 bo'lishi shundan kelib chiqadi.
 */

/** Kunning boshlang'ich lahzasi: 20:14:32. */
export const BASE = 20 * 3600 + 14 * 60 + 32;
export const DAY_START = 10 * 60;
export const DAY_END = 26 * 60;

export type StationStatus = 'OCCUPIED' | 'FREE' | 'RESERVED' | 'MAINTENANCE';

/**
 * Konsol turlari — klub sozlamasi, kod ichida qotirilmagan.
 * Superadmin klub yaratayotganda ro'yxatni belgilaydi; PS6 chiqsa shu yerga
 * bitta qator qo'shiladi va barcha ekranlar o'zi yangilanadi.
 */
export interface ConsoleType {
  id: string;
  label: string;
  order: number;
}

export const CONSOLES: ConsoleType[] = [
  { id: 'ps3', label: 'PS3', order: 1 },
  { id: 'ps4', label: 'PS4', order: 2 },
  { id: 'ps4pro', label: 'PS4 Pro', order: 3 },
  { id: 'ps5', label: 'PS5', order: 4 },
  { id: 'ps5pro', label: 'PS5 Pro', order: 5 },
  // Kelajakda: { id: 'ps6', label: 'PS6', order: 6 }
];

export const consoleLabel = (id: string): string =>
  CONSOLES.find((item) => item.id === id)?.label ?? id;

export interface MockStation {
  id: number;
  code: string;
  room: string;
  /** `CONSOLES` dagi id. */
  cons: string;
  tv: number;
  pads: number;
  status: StationStatus;
  guest?: string;
  phone?: string;
  code6?: string;
  note?: string;
  priorNoShow?: number;
  /** Boshlanish va tugash — yarim tundan daqiqada. */
  a: number;
  b: number;
  rate: number;
  bar: number;
  hist: [number, number, string][];
}

export const ST: MockStation[] = [
  { id: 1, code: '1-xona', room: 'Standart', cons: 'ps5', tv: 55, pads: 2, status: 'OCCUPIED', guest: 'Jasur Aliyev', phone: '+998 90 123-45-67', code6: '482013', a: 19 * 60 + 30, b: 21 * 60 + 30, rate: 40000, bar: 34000, hist: [[12 * 60, 14 * 60, 'Otabek'], [16 * 60, 18 * 60, 'Ravshan']] },
  { id: 2, code: '2-xona', room: 'Standart', cons: 'ps5', tv: 55, pads: 4, status: 'OCCUPIED', guest: 'Sardor Rahimov', phone: '+998 93 774-10-02', code6: '731905', a: 20 * 60, b: 22 * 60, rate: 40000, bar: 32000, hist: [[15 * 60, 17 * 60, 'Doston']] },
  { id: 3, code: '3-xona', room: 'Standart', cons: 'ps5', tv: 55, pads: 2, status: 'FREE', a: 0, b: 0, rate: 40000, bar: 0, hist: [[14 * 60, 16 * 60, 'Mansur']] },
  { id: 4, code: '4-xona', room: 'Standart', cons: 'ps4', tv: 43, pads: 2, status: 'RESERVED', guest: 'Diyor Saidov', phone: '+998 97 300-55-41', code6: '205774', a: 21 * 60, b: 23 * 60, rate: 25000, bar: 0, hist: [[11 * 60, 13 * 60, 'Zafar']] },
  { id: 5, code: '5-xona', room: 'Standart', cons: 'ps5', tv: 55, pads: 2, status: 'OCCUPIED', guest: 'Aziz Karimov', phone: '+998 91 445-20-18', code6: '660321', a: 18 * 60, b: 20 * 60, rate: 40000, bar: 18000, hist: [] },
  { id: 6, code: '6-xona', room: 'Standart', cons: 'ps3', tv: 40, pads: 2, status: 'RESERVED', guest: 'Kamron Halilov', phone: '+998 95 220-14-08', code6: '776120', a: 19 * 60 + 50, b: 21 * 60 + 50, rate: 25000, bar: 0, priorNoShow: 2, hist: [[16 * 60, 19 * 60, 'Ulug‘bek']] },
  { id: 7, code: '7-xona', room: 'Standart', cons: 'ps5', tv: 55, pads: 2, status: 'MAINTENANCE', note: ' 2-dzhoystik ta’mirda'.trim(), a: 0, b: 0, rate: 40000, bar: 0, hist: [] },
  { id: 8, code: '8-xona', room: 'Turnir', cons: 'ps5', tv: 65, pads: 4, status: 'OCCUPIED', guest: 'Bekzod Yusupov', phone: '+998 88 210-77-90', code6: '914268', a: 20 * 60 + 10, b: 21 * 60 + 10, rate: 50000, bar: 18000, hist: [[13 * 60, 15 * 60, 'Shahzod']] },
  { id: 9, code: 'VIP-1', room: 'VIP', cons: 'ps5pro', tv: 75, pads: 4, status: 'OCCUPIED', guest: 'Nodira Qodirova', phone: '+998 90 908-31-12', code6: '337150', a: 19 * 60, b: 22 * 60, rate: 60000, bar: 78000, hist: [] },
  { id: 10, code: 'VIP-2', room: 'VIP', cons: 'ps5pro', tv: 75, pads: 4, status: 'RESERVED', guest: 'Shohrux Tursunov', phone: '+998 94 512-08-33', code6: '108492', a: 21 * 60 + 30, b: 23 * 60 + 30, rate: 60000, bar: 0, hist: [[15 * 60, 18 * 60, 'Nigora']] },
];

/**
 * Prototipdagi LIVE hisobi: no-show, yopilgan xona va uzaytirish qo'llanadi.
 *
 * `screens/live-board.tsx` endi real `GET /clubs/{id}/live`dan o'qiydi —
 * bu funksiya faqat `screens/timeline.tsx` (kunlik gantt) uchun qoladi, u
 * hali real bandlikka ko'chirilmagan.
 */
export function liveStations(
  nsMarked: boolean,
  closedRooms: Record<number, { from: number; to: number }>,
  extended: Record<number, number>,
): MockStation[] {
  return ST.map((station) => {
    if (nsMarked && station.id === 6) {
      return { ...station, status: 'FREE' as const, guest: undefined, a: 0, b: 0 };
    }

    const shut = closedRooms[station.id];
    if (shut) {
      return {
        ...station,
        status: 'FREE' as const,
        guest: undefined,
        a: 0,
        b: 0,
        hist: [...station.hist, [shut.from, shut.to, (station.guest ?? '').split(' ')[0] ?? '']] as [
          number,
          number,
          string,
        ][],
      };
    }
    if (extended[station.id]) {
      return { ...station, b: station.b + (extended[station.id] as number) };
    }
    return station;
  });
}

export interface MockMenuItem {
  id: string;
  cat: string;
  name: string;
  price: number;
  /** null = cheksiz qoldiq */
  stock: number | null;
}

export const MENU: MockMenuItem[] = [
  { id: 'm1', cat: 'Ichimliklar', name: 'Pepsi 0.5', price: 12000, stock: 42 },
  { id: 'm2', cat: 'Ichimliklar', name: 'Coca-Cola 0.5', price: 12000, stock: 38 },
  { id: 'm3', cat: 'Ichimliklar', name: 'Fuse Tea', price: 14000, stock: 12 },
  { id: 'm4', cat: 'Ichimliklar', name: 'Adrenaline', price: 18000, stock: 6 },
  { id: 'm5', cat: 'Ichimliklar', name: 'Suv 0.5', price: 6000, stock: null },
  { id: 'm6', cat: 'Ichimliklar', name: 'Ko‘k choy', price: 8000, stock: null },
  { id: 'm7', cat: 'Snack', name: "Lay's", price: 10000, stock: 24 },
  { id: 'm8', cat: 'Snack', name: 'Popcorn', price: 12000, stock: 18 },
  { id: 'm9', cat: 'Snack', name: 'Snickers', price: 9000, stock: 30 },
  { id: 'm10', cat: 'Snack', name: 'Pista', price: 22000, stock: 4 },
  { id: 'm11', cat: 'Ovqat', name: 'Lavash', price: 32000, stock: 9 },
  { id: 'm12', cat: 'Ovqat', name: 'Hot-dog', price: 22000, stock: 14 },
  { id: 'm13', cat: 'Ovqat', name: 'Mini pitsa', price: 65000, stock: 5 },
  { id: 'm14', cat: 'Ovqat', name: 'Burger', price: 38000, stock: 7 },
  { id: 'm15', cat: 'Ovqat', name: 'Fri kartoshka', price: 18000, stock: 16 },
  // Katalog kengaytirildi — real klubda pozitsiyalar ko'p bo'ladi, shuning uchun izlash kerak.
  { id: 'm16', cat: 'Ichimliklar', name: 'Sprite 0.5', price: 12000, stock: 26 },
  { id: 'm17', cat: 'Ichimliklar', name: 'Fanta 0.5', price: 12000, stock: 22 },
  { id: 'm18', cat: 'Ichimliklar', name: 'Red Bull', price: 26000, stock: 9 },
  { id: 'm19', cat: 'Ichimliklar', name: 'Kofe amerikano', price: 15000, stock: null },
  { id: 'm20', cat: 'Ichimliklar', name: 'Kapuchino', price: 20000, stock: null },
  { id: 'm21', cat: 'Ichimliklar', name: 'Ayron', price: 9000, stock: 14 },
  { id: 'm22', cat: 'Snack', name: 'Doritos', price: 14000, stock: 16 },
  { id: 'm23', cat: 'Snack', name: 'Sudorak', price: 8000, stock: 20 },
  { id: 'm24', cat: 'Snack', name: 'Bodom tuzli', price: 26000, stock: 7 },
  { id: 'm25', cat: 'Snack', name: 'Chipsi qalampirli', price: 11000, stock: 12 },
  { id: 'm26', cat: 'Snack', name: 'Twix', price: 10000, stock: 18 },
  { id: 'm27', cat: 'Ovqat', name: 'Shaurma tovuqli', price: 34000, stock: 11 },
  { id: 'm28', cat: 'Ovqat', name: 'Klub sendvich', price: 30000, stock: 6 },
  { id: 'm29', cat: 'Ovqat', name: 'Nagets 9 dona', price: 28000, stock: 10 },
  { id: 'm30', cat: 'Ovqat', name: 'Pitsa pepperoni', price: 72000, stock: 4 },
];

/**
 * Reestr admin kiritgan boshlang'ich miqdordan (`start`) shakllanadi.
 * `soldBefore` — smena boshidan shu daqiqagacha yopilgan hisoblarda sotilgani.
 * Joriy sotuv avtomatik qo'shiladi: yetkazilgan buyurtmalar + kassadagi savatlar
 * (`soldQty`). Xodim hech narsa kiritmaydi, faqat sanaydi.
 */
export const STOCK: { id: string; start: number; soldBefore: number }[] = [
  { id: 'm1', start: 48, soldBefore: 14 },
  { id: 'm2', start: 42, soldBefore: 9 },
  { id: 'm3', start: 18, soldBefore: 6 },
  { id: 'm4', start: 12, soldBefore: 6 },
  { id: 'm7', start: 30, soldBefore: 11 },
  { id: 'm8', start: 24, soldBefore: 7 },
  { id: 'm10', start: 10, soldBefore: 6 },
  { id: 'm11', start: 14, soldBefore: 5 },
  { id: 'm13', start: 8, soldBefore: 3 },
  { id: 'm16', start: 30, soldBefore: 4 },
  { id: 'm18', start: 12, soldBefore: 3 },
  { id: 'm22', start: 20, soldBefore: 4 },
  { id: 'm24', start: 10, soldBefore: 3 },
  { id: 'm27', start: 14, soldBefore: 3 },
  { id: 'm30', start: 6, soldBefore: 2 },
];

export const TONE: Record<StationStatus, string> = {
  OCCUPIED: 'var(--primary-100)',
  FREE: 'var(--slot-free)',
  RESERVED: 'var(--yellow-100)',
  MAINTENANCE: 'var(--fg-4)',
};

export const LABEL: Record<StationStatus, string> = {
  OCCUPIED: 'Band',
  FREE: 'Bo‘sh',
  RESERVED: 'Rezerv',
  MAINTENANCE: 'Ta’mirda',
};

export type ScreenId =
  // Xodim
  | 'live'
  | 'timeline'
  | 'orders'
  | 'bookings'
  | 'pos'
  | 'shift'
  | 'blacklist'
  // Klub admini
  | 'dashboard'
  | 'staff'
  | 'products'
  | 'reports'
  | 'expenses'
  | 'settings'
  // Super admin
  | 'platform'
  | 'platform-clubs'
  | 'platform-report'
  | 'platform-logs'
  | 'platform-settings';

export interface NavItem {
  id: ScreenId;
  icon: string;
  label: string;
  count?: number;
}

export const NAV_STAFF: NavItem[] = [
  { id: 'live', icon: 'grid_view', label: 'Live board' },
  { id: 'timeline', icon: 'calendar_view_week', label: 'Timeline' },
  { id: 'orders', icon: 'receipt_long', label: 'Buyurtmalar', count: 5 },
  { id: 'bookings', icon: 'event_available', label: 'Bronlar' },
  { id: 'pos', icon: 'point_of_sale', label: 'Kassa' },
  { id: 'shift', icon: 'savings', label: 'Smena' },
  { id: 'blacklist', icon: 'person_off', label: 'Qora ro‘yxat', count: 3 },
];

// Bronlar — faqat xodim (`NAV_STAFF`) ishlaydi. Klub admini kunlik bron
// operatsiyasi bilan shug'ullanmaydi (loyiha egasining so'rovi, 2026-08-16).
export const NAV_ADMIN: NavItem[] = [
  { id: 'dashboard', icon: 'space_dashboard', label: 'Boshqaruv paneli' },
  { id: 'staff', icon: 'group', label: 'Xodimlar' },
  { id: 'products', icon: 'inventory_2', label: 'Mahsulotlar' },
  { id: 'reports', icon: 'analytics', label: 'Hisobot' },
  { id: 'expenses', icon: 'payments', label: 'Xarajatlar' },
  { id: 'settings', icon: 'settings', label: 'Sozlamalar' },
];

export const NAV_SUPER_ADMIN: NavItem[] = [
  { id: 'platform', icon: 'hub', label: 'Platforma' },
  { id: 'platform-clubs', icon: 'storefront', label: 'Klublar' },
  { id: 'platform-report', icon: 'analytics', label: 'Hisobot' },
  { id: 'platform-logs', icon: 'history', label: 'Jurnal' },
  { id: 'platform-settings', icon: 'settings', label: 'Sozlamalar' },
];

export const TITLES: Record<ScreenId, [string, string[]]> = {
  live: ['Live board', ['Neon Arena', 'A-blok', '10 xona']],
  timeline: ['Kunlik timeline', ['Neon Arena', '10 xona', '10:00 – 02:00']],
  orders: ['Buyurtmalar', ['Bar', '5 aktiv', 'O‘rtacha 6 daqiqa']],
  bookings: ['Bronlar', ['Mijoz va qo‘lda bron', 'Tasdiq — botda xabar']],
  pos: ['Kassa', ['Kechki smena', 'Kamola R.', '14 hisob']],
  shift: ['Smena', ['12-08-2026', '18:00 dan', 'Kamola R.']],
  blacklist: ['Qora ro‘yxat', ['Neon Arena', '3 bloklangan', '4 kuzatuvda']],

  dashboard: ['Boshqaruv paneli', ['Neon Arena', 'Bugun']],
  staff: ['Xodimlar', ['Neon Arena', 'Smenalar va kirish']],
  products: ['Mahsulotlar', ['Katalog va reestr']],
  reports: ['Hisobot', ['Tushum, xarajat va foyda']],
  expenses: ['Xarajatlar', ['Kommunal, ijara va maosh']],
  settings: ['Sozlamalar', ['Hisob, klub va xonalar']],

  platform: ['Platforma', ['Barcha tashkilotlar', 'Cross-tenant, faqat o‘qish']],
  'platform-clubs': ['Klublar', ['Barcha tashkilotlar', 'Qo‘lda qo‘shish va to‘lov']],
  'platform-report': ['Hisobot', ['Platforma tushumi', 'Kunlik — yillik kesim']],
  'platform-logs': ['Jurnal', ['Platforma darajasidagi amallar']],
  'platform-settings': ['Sozlamalar', ['Super admin hisobi']],
};

/** Stansiya id → yig'ilgan bonus. */
export const BONUS: Record<number, number> = { 1: 12000, 9: 24000 };

export const EXT_ITEMS = ['30 daq', '1 soat', '1,5 soat', '2 soat'];
export const EXT_MIN = [30, 60, 90, 120];

export type OrderStatus = 'NEW' | 'ACCEPTED' | 'PREPARING' | 'DELIVERED';

export const ORDER_FLOW: OrderStatus[] = ['NEW', 'ACCEPTED', 'PREPARING', 'DELIVERED'];

export const ORDER_COL: Record<OrderStatus, string> = {
  NEW: 'Yangi',
  ACCEPTED: 'Qabul qilindi',
  PREPARING: 'Tayyorlanmoqda',
  DELIVERED: 'Yetkazildi',
};

export const ORDER_NEXT: Partial<Record<OrderStatus, string>> = {
  NEW: 'Qabul qilish',
  ACCEPTED: 'Tayyorlashga',
  PREPARING: 'Yetkazildi',
};

export const ORDER_LN: Record<OrderStatus, string> = {
  NEW: 'var(--yellow-100)',
  ACCEPTED: 'var(--line-2)',
  PREPARING: 'var(--primary-100)',
  DELIVERED: 'var(--line-1)',
};

export interface MockOrder {
  id: string;
  station: string;
  guest: string;
  status: OrderStatus;
  ago: string;
  note?: string;
  lines: { name: string; qty: string }[];
  total: number;
}

export const ORDERS: MockOrder[] = [
  { id: 'ORD-1041', station: '2-xona', guest: 'Sardor Rahimov', status: 'NEW', ago: '2 daqiqa', note: 'Muzsiz', lines: [{ name: 'Pepsi 0.5', qty: '×2' }, { name: "Lay's", qty: '×1' }], total: 34000 },
  { id: 'ORD-1042', station: 'VIP-2', guest: 'Shohrux Tursunov', status: 'NEW', ago: '1 daqiqa', lines: [{ name: 'Mini pitsa', qty: '×1' }], total: 65000 },
  { id: 'ORD-1040', station: 'VIP-1', guest: 'Nodira Qodirova', status: 'ACCEPTED', ago: '6 daqiqa', lines: [{ name: 'Lavash', qty: '×2' }, { name: 'Ko‘k choy', qty: '×2' }], total: 80000 },
  { id: 'ORD-1039', station: '8-xona', guest: 'Bekzod Yusupov', status: 'PREPARING', ago: '9 daqiqa', lines: [{ name: 'Adrenaline', qty: '×1' }], total: 18000 },
  { id: 'ORD-1038', station: '1-xona', guest: 'Jasur Aliyev', status: 'DELIVERED', ago: '21 daqiqa', lines: [{ name: 'Hot-dog', qty: '×1' }, { name: 'Coca-Cola 0.5', qty: '×1' }], total: 34000 },
];

/** Savatlar: stansiya id → {menu id: soni}. */
export const CARTS: Record<number, Record<string, number>> = {
  1: { m1: 2, m7: 1 },
  2: { m1: 2, m11: 1 },
  5: { m4: 1 },
  8: { m4: 1 },
  9: { m11: 2, m6: 2 },
};

// ─────────────────────── timeline: kunlar ───────────────────────

export type DayId = 'Kecha' | 'Bugun' | 'Ertaga';

export const DAY_ITEMS: DayId[] = ['Kecha', 'Bugun', 'Ertaga'];

export interface DayBooking {
  /** Stansiya id. */
  station: number;
  from: number;
  to: number;
  guest: string;
  /** done — o'tgan seans, booked — tasdiqlangan bron, noshow — kelmagan. */
  kind: 'done' | 'booked' | 'noshow';
}

/** Kecha yopilgan seanslar — hammasi tugagan. */
export const YESTERDAY: DayBooking[] = [
  { station: 1, from: 11 * 60, to: 13 * 60, guest: 'Otabek', kind: 'done' },
  { station: 1, from: 18 * 60, to: 21 * 60, guest: 'Jasur', kind: 'done' },
  { station: 2, from: 14 * 60, to: 16 * 60, guest: 'Doston', kind: 'done' },
  { station: 2, from: 19 * 60, to: 22 * 60, guest: 'Sardor', kind: 'done' },
  { station: 3, from: 12 * 60, to: 15 * 60, guest: 'Mansur', kind: 'done' },
  { station: 4, from: 20 * 60, to: 23 * 60, guest: 'Zafar', kind: 'noshow' },
  { station: 5, from: 16 * 60, to: 19 * 60, guest: 'Aziz', kind: 'done' },
  { station: 6, from: 13 * 60, to: 15 * 60, guest: 'Kamron', kind: 'noshow' },
  { station: 8, from: 17 * 60, to: 20 * 60, guest: 'Shahzod', kind: 'done' },
  { station: 8, from: 21 * 60, to: 24 * 60, guest: 'Bekzod', kind: 'done' },
  { station: 9, from: 15 * 60, to: 18 * 60, guest: 'Nodira', kind: 'done' },
  { station: 9, from: 19 * 60, to: 23 * 60, guest: 'Kamola', kind: 'done' },
  { station: 10, from: 18 * 60, to: 21 * 60, guest: 'Nigora', kind: 'done' },
];

/** Ertaga — tasdiqlangan bronlar. */
export const TOMORROW: DayBooking[] = [
  { station: 1, from: 12 * 60, to: 14 * 60, guest: 'Ulug‘bek', kind: 'booked' },
  { station: 1, from: 19 * 60, to: 22 * 60, guest: 'Jasur', kind: 'booked' },
  { station: 2, from: 16 * 60, to: 18 * 60, guest: 'Sanjar', kind: 'booked' },
  { station: 3, from: 20 * 60, to: 23 * 60, guest: 'Diyor', kind: 'booked' },
  { station: 4, from: 11 * 60, to: 13 * 60, guest: 'Rustam', kind: 'booked' },
  { station: 5, from: 18 * 60, to: 21 * 60, guest: 'Aziz', kind: 'booked' },
  { station: 6, from: 21 * 60, to: 24 * 60, guest: 'Islom', kind: 'booked' },
  { station: 8, from: 14 * 60, to: 17 * 60, guest: 'Bekzod', kind: 'booked' },
  { station: 9, from: 19 * 60, to: 23 * 60, guest: 'Nodira', kind: 'booked' },
  { station: 10, from: 20 * 60, to: 25 * 60, guest: 'Shohrux', kind: 'booked' },
];

// ─────────────────────── qoldiq hisobi ───────────────────────

/** Buyurtma satrlari nom bilan keladi — menyu id'siga bog'lash uchun. */
const MENU_ID_BY_NAME: Record<string, string> = Object.fromEntries(
  MENU.map((item) => [item.name, item.id]),
);

/** `×2` → 2. */
function parseQty(value: string): number {
  const parsed = Number(value.replace(/\D/g, ''));
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
}

/**
 * Mahsulot bo'yicha joriy sotuv:
 *   yetkazilgan buyurtmalar (DELIVERED) + kassadagi ochiq savatlar.
 * Buyurtma mijozga topshirilgan zahoti qoldiq avtomatik kamayadi.
 */
export function soldNow(
  id: string,
  orders: readonly MockOrder[],
  carts: Readonly<Record<number, Record<string, number>>>,
): number {
  const delivered = orders
    .filter((order) => order.status === 'DELIVERED')
    .reduce((sum, order) => {
      const line = order.lines.find((entry) => MENU_ID_BY_NAME[entry.name] === id);
      return sum + (line ? parseQty(line.qty) : 0);
    }, 0);

  const inCarts = Object.values(carts).reduce((sum, cart) => sum + (cart[id] ?? 0), 0);

  return delivered + inCarts;
}

/** Reestr qatori — admin kiritgan `start` dan avtomatik hisoblanadi. */
export function stockRow(
  id: string,
  orders: readonly MockOrder[],
  carts: Readonly<Record<number, Record<string, number>>>,
): { start: number; sold: number; expected: number } | null {
  const entry = STOCK.find((row) => row.id === id);
  if (!entry) return null;

  const sold = entry.soldBefore + soldNow(id, orders, carts);
  return { start: entry.start, sold, expected: entry.start - sold };
}

// ─────────────────────────── formatlash ───────────────────────────

/** 3 xonali guruh, bo'sh joy bilan. */
export const S = (n: number): string => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');

/** Daqiqa → `HH:MM` (24 dan oshsa ham ko'rsatiladi: `26:00`). */
export const HM = (m: number): string =>
  `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;

/** Sekund → `HH:MM:SS` sutka ichida. */
export const CLK = (seconds: number): string => {
  const s = ((seconds % 86400) + 86400) % 86400;
  return [Math.floor(s / 3600), Math.floor(s / 60) % 60, s % 60]
    .map((n) => String(n).padStart(2, '0'))
    .join(':');
};

/** Davomiylik `1:45:20`; manfiy — overtime, `+` bilan. */
export const DUR = (seconds: number): string => {
  const negative = seconds < 0;
  const s = Math.abs(seconds);
  return `${negative ? '+' : ''}${Math.floor(s / 3600)}:${String(Math.floor(s / 60) % 60).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
};
