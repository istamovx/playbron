/**
 * Mijoz Mini App mock ma'lumoti — `docs/designs/PlayBron Mijoz.dc.html` dan
 * aynan ko'chirilgan. Qiymatlar o'zgartirilmaydi.
 */

export const BASE = 20 * 3600 + 14 * 60 + 32;
export const SESSION_START = 19 * 3600 + 30 * 60;
export const SESSION_END = 21 * 3600 + 30 * 60;
export const SESSION_ROOM = '1-xona';
/** Uzaytirish qadamining uzunligi, daqiqa. */
export const EXTEND_STEP_MIN = 60;

export interface MockClub {
  id: number;
  name: string;
  addr: string;
  dist: string;
  rating: string;
  price: string;
  free: number;
}

export const CLUBS: MockClub[] = [
  { id: 1, name: 'Neon Arena', addr: 'Chilonzor, 8-kvartal, 42-uy', dist: '1.2 km', rating: '4.8', price: '25 000 dan', free: 2 },
  { id: 2, name: 'Pixel Club', addr: 'Yunusobod, Amir Temur ko‘chasi 108', dist: '3.4 km', rating: '4.6', price: '25 000 dan', free: 4 },
  { id: 3, name: 'Respawn Zone', addr: 'Mirzo Ulug‘bek, Buyuk Ipak Yo‘li 24', dist: '5.1 km', rating: '4.9', price: '35 000 dan', free: 0 },
  { id: 4, name: 'GG Station', addr: 'Sergeli, Yangi Sergeli 12-mavze', dist: '7.8 km', rating: '4.4', price: '22 000 dan', free: 5 },
];

/**
 * Konsol turlari katalogi — qotirilgan ro'yxat emas.
 * Superadmin klub yaratayotganda qaysi konsollar borligini shu ro'yxatdan
 * belgilaydi; yangi avlod (masalan PS6) chiqsa faqat shu yerga bitta qator
 * qo'shiladi, ekranlarning hech biri o'zgarmaydi.
 */
export interface ConsoleType {
  id: string;
  label: string;
  /** Ro'yxatdagi tartib — eskisidan yangisiga. */
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
  code: string;
  room: string;
  /** `CONSOLES` dagi id. */
  console: string;
  tv: number;
  pads: number;
  rate: number;
}

export const STATIONS: MockStation[] = [
  { code: '1-xona', room: 'Standart', console: 'ps5', tv: 55, pads: 2, rate: 40000 },
  { code: '2-xona', room: 'Standart', console: 'ps5', tv: 55, pads: 4, rate: 40000 },
  { code: '3-xona', room: 'Standart', console: 'ps4pro', tv: 50, pads: 2, rate: 30000 },
  { code: '4-xona', room: 'Standart', console: 'ps4', tv: 43, pads: 2, rate: 25000 },
  { code: '5-xona', room: 'Standart', console: 'ps4', tv: 43, pads: 2, rate: 25000 },
  { code: '6-xona', room: 'Standart', console: 'ps3', tv: 40, pads: 2, rate: 18000 },
  { code: '8-xona', room: 'Turnir', console: 'ps5', tv: 65, pads: 4, rate: 50000 },
  { code: 'VIP-1', room: 'VIP', console: 'ps5pro', tv: 75, pads: 4, rate: 60000 },
  { code: 'VIP-2', room: 'VIP', console: 'ps5pro', tv: 75, pads: 4, rate: 60000 },
];

/** Kartalardagi texnik satr: `PS5 · 55" · 2 pad`. */
export const stationSpec = (station: MockStation): string =>
  `${consoleLabel(station.console)} · ${station.tv}" · ${station.pads} pad`;

/** Klubda mavjud konsollar — teglar va filtrlar shundan chiqadi. */
export const clubConsoles = (): ConsoleType[] =>
  CONSOLES.filter((type) => STATIONS.some((station) => station.console === type.id)).sort(
    (a, b) => a.order - b.order,
  );

export interface MockMenuItem {
  id: string;
  cat: string;
  name: string;
  price: number;
}

export const MENU: MockMenuItem[] = [
  { id: 'm1', cat: 'Ichimliklar', name: 'Pepsi 0.5', price: 12000 },
  { id: 'm3', cat: 'Ichimliklar', name: 'Fuse Tea', price: 14000 },
  { id: 'm4', cat: 'Ichimliklar', name: 'Adrenaline', price: 18000 },
  { id: 'm6', cat: 'Ichimliklar', name: 'Ko‘k choy', price: 8000 },
  { id: 'm7', cat: 'Snack', name: "Lay's", price: 10000 },
  { id: 'm8', cat: 'Snack', name: 'Popcorn', price: 12000 },
  { id: 'm9', cat: 'Snack', name: 'Snickers', price: 9000 },
  { id: 'm11', cat: 'Ovqat', name: 'Lavash', price: 32000 },
  { id: 'm13', cat: 'Ovqat', name: 'Mini pitsa', price: 65000 },
  { id: 'm14', cat: 'Ovqat', name: 'Burger', price: 38000 },
];

// ─────────────────────────── bar buyurtmalari ───────────────────────────

export type OrderStatus = 'NEW' | 'ACCEPTED' | 'PREPARING' | 'DELIVERED';

/** Barga yuborilgan buyurtma. Holat `at` dan beri o'tgan vaqtdan hisoblanadi. */
export interface CustomerOrder {
  code: string;
  /** Yuborilgan lahza — yarim tundan soniyada. */
  at: number;
  lines: { id: string; qty: number }[];
  amount: number;
}

/**
 * Buyurtma bosqichlari — xodim kassasidagi `ORDER_FLOW` ning o'zi.
 * Mock'da holat yuborilgandan beri o'tgan vaqtdan hisoblanadi; backend ulanganda
 * shu funksiya o'rnini real status egallaydi, ekranlar o'zgarmaydi.
 */
export const ORDER_FLOW: OrderStatus[] = ['NEW', 'ACCEPTED', 'PREPARING', 'DELIVERED'];

export const ORDER_LABEL: Record<OrderStatus, string> = {
  NEW: 'Yuborildi',
  ACCEPTED: 'Qabul qilindi',
  PREPARING: 'Tayyorlanmoqda',
  DELIVERED: 'Yetkazildi',
};

export const ORDER_TONE: Record<OrderStatus, string> = {
  NEW: 'var(--yellow-100)',
  ACCEPTED: 'var(--primary-100)',
  PREPARING: 'var(--purple-100)',
  DELIVERED: 'var(--secondary-500)',
};

/** Bosqichga o'tish uchun yuborilgandan beri kerakli vaqt, soniya. */
const ORDER_AFTER = [0, 45, 120, 300];

export function orderStatusAt(elapsed: number): OrderStatus {
  let status: OrderStatus = 'NEW';
  for (let i = 0; i < ORDER_FLOW.length; i += 1) {
    if (elapsed >= (ORDER_AFTER[i] as number)) status = ORDER_FLOW[i] as OrderStatus;
  }
  return status;
}

/** Bonus ball kursi: 1 ball = 100 so'm. */
export const POINT_RATE = 100;
export const BONUS_POINTS = 120;

export const DOW = ['Ya', 'Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sha'];

const MONTHS = ['yan', 'fev', 'mar', 'apr', 'may', 'iyn', 'iyl', 'avg', 'sen', 'okt', 'noy', 'dek'];

// ─────────────────────── bandlik va bo'sh slotlar ───────────────────────

/** Klub ish vaqti (yarim tundan daqiqada) va slot qadami. */
export const OPEN_MIN = 10 * 60;
export const CLOSE_MIN = 24 * 60;
export const SLOT_STEP = 30;

/** Mijoz tanlay oladigan davomiyliklar, soatda. */
export const DURATIONS = [1, 2, 3, 4, 5];

/** Oldindan bron qilish oynasi — bugundan boshlab necha kun. */
export const DAYS_AHEAD = 14;

export interface TimeRange {
  from: number;
  to: number;
}

export interface DayOption {
  /** 0 — bugun. */
  index: number;
  dow: string;
  day: number;
  /** `Bugun` / `Ertaga` / `15 avg`. */
  label: string;
  /** `13-08-2026`. */
  date: string;
}

const overlaps = (a: TimeRange, b: TimeRange): boolean => a.from < b.to && a.to > b.from;

function hash(value: string): number {
  let h = 2166136261;
  for (let i = 0; i < value.length; i += 1) {
    h ^= value.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/** Barqaror psevdo-tasodif — bir xil kun va xona doim bir xil bandlikni beradi. */
function rng(seed: number): () => number {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const bookedCache = new Map<string, TimeRange[]>();

/**
 * Xonaning ma'lum kundagi band oraliqlari.
 * Backend ulanganda faqat shu funksiya API chaqiruviga almashadi —
 * qolgan hisob-kitob o'zgarmaydi.
 */
export function bookedRanges(dayIndex: number, code: string): TimeRange[] {
  const key = `${dayIndex}|${code}`;
  const cached = bookedCache.get(key);
  if (cached) return cached;

  const next = rng(hash(key));
  const slots = (CLOSE_MIN - OPEN_MIN) / SLOT_STEP;
  const ranges: TimeRange[] = [];

  for (let i = 0; i < 5; i += 1) {
    const from = OPEN_MIN + Math.floor(next() * slots) * SLOT_STEP;
    const range = { from, to: from + (1 + Math.floor(next() * 3)) * 60 };
    if (range.to > CLOSE_MIN) continue;
    if (ranges.some((busy) => overlaps(busy, range))) continue;
    ranges.push(range);
  }

  ranges.sort((a, b) => a.from - b.from);
  bookedCache.set(key, ranges);
  return ranges;
}

/** Hozir band bo'lgan xonalar — klub sahifasidagi bandlik shundan. */
export const isBusyNow = (code: string, nowMin: number): boolean =>
  bookedRanges(0, code).some((busy) => nowMin >= busy.from && nowMin < busy.to);

export interface SlotFilter {
  /** `Barchasi` yoki xona turi. */
  room: string;
  /** `Barchasi` yoki `CONSOLES` dagi id. */
  console: string;
}

export const ANY = 'Barchasi';

export const matchingStations = (filter: SlotFilter): MockStation[] =>
  STATIONS.filter(
    (station) =>
      (filter.room === ANY || station.room === filter.room) &&
      (filter.console === ANY || station.console === filter.console),
  );

/** Berilgan oynada bo'sh xonalar — arzonidan qimmatiga. */
export function freeStations(
  dayIndex: number,
  from: number,
  hours: number,
  filter: SlotFilter,
): MockStation[] {
  const window = { from, to: from + hours * 60 };
  if (window.to > CLOSE_MIN) return [];

  return matchingStations(filter)
    .filter((station) => !bookedRanges(dayIndex, station.code).some((busy) => overlaps(busy, window)))
    .sort((a, b) => a.rate - b.rate || a.code.localeCompare(b.code));
}

/**
 * Boshlanish vaqtlari to'ri — eng qisqa seans ham yopilishgacha sig'adigan
 * slotlargacha (oxirgisi `CLOSE_MIN − 1 soat`).
 */
export const slotTimes = (): number[] => {
  const last = CLOSE_MIN - (DURATIONS[0] as number) * 60;
  return Array.from({ length: (last - OPEN_MIN) / SLOT_STEP + 1 }, (_, i) => OPEN_MIN + i * SLOT_STEP);
};

/** O'tib ketgan slot — faqat bugungi kun uchun. */
export const isPast = (dayIndex: number, from: number, nowMin: number): boolean =>
  dayIndex === 0 && from <= nowMin;

/**
 * Shu boshlanish vaqtidan maksimal necha soat olish mumkin.
 * Davomiylik tugmalari shu chegaradan keyin o'chadi.
 */
export function maxHours(dayIndex: number, from: number, filter: SlotFilter): number {
  let best = 0;
  for (const hours of DURATIONS) {
    if (freeStations(dayIndex, from, hours, filter).length === 0) break;
    best = hours;
  }
  return best;
}

/** Kun tasmasidagi «N bo'sh» — shu davomiylik sig'adigan slotlar soni. */
export function freeSlotCount(
  dayIndex: number,
  hours: number,
  filter: SlotFilter,
  nowMin: number,
): number {
  return slotTimes().filter(
    (from) =>
      !isPast(dayIndex, from, nowMin) && freeStations(dayIndex, from, hours, filter).length > 0,
  ).length;
}

/** Bugundan boshlab `DAYS_AHEAD` kunlik tasma. */
export function dayOptions(count = DAYS_AHEAD): DayOption[] {
  const today = new Date();
  return Array.from({ length: count }, (_, index) => {
    const date = new Date(today.getFullYear(), today.getMonth(), today.getDate() + index);
    const day = date.getDate();
    const month = date.getMonth();
    return {
      index,
      dow: DOW[date.getDay()] as string,
      day,
      label: index === 0 ? 'Bugun' : index === 1 ? 'Ertaga' : `${day} ${MONTHS[month] as string}`,
      date: `${String(day).padStart(2, '0')}-${String(month + 1).padStart(2, '0')}-${date.getFullYear()}`,
    };
  });
}

export type ScreenId =
  | 'clubs'
  | 'club'
  | 'slots'
  | 'confirm'
  | 'qr'
  | 'session'
  | 'bill'
  | 'bookings'
  | 'profile';

export const TITLES: Record<ScreenId, [string, string]> = {
  clubs: ['PlayBron', 'Toshkent · 24 klub'],
  club: ['Neon Arena', 'Chilonzor · Reyting 4.8'],
  slots: ['Vaqt tanlash', 'Neon Arena'],
  confirm: ['Tasdiqlash', 'Neon Arena'],
  qr: ['Bron tayyor', 'Kirishda ko‘rsating'],
  session: ['Aktiv seans', 'Neon Arena · 1-xona'],
  bill: ['Hisob', 'Neon Arena · 1-xona'],
  bookings: ['Bronlarim', '3 ta aktiv'],
  profile: ['Profil', 'Sozlamalar'],
};

export const TABS: { id: ScreenId; icon: string; label: string }[] = [
  { id: 'clubs', icon: 'storefront', label: 'Klublar' },
  { id: 'session', icon: 'sports_esports', label: 'Seans' },
  { id: 'bookings', icon: 'event_note', label: 'Bronlar' },
  { id: 'profile', icon: 'person', label: 'Profil' },
];

/** Interfeys tillari — i18n resurslari shu kalitlar bo'yicha yuklanadi. */
export const LANGS = [
  { id: 'uz', label: 'O‘zbek' },
  { id: 'ru', label: 'Русский' },
  { id: 'en', label: 'English' },
];

/** Ichki ekran qaysi tabga tegishli. */
export const TAB_ROOT: Partial<Record<ScreenId, ScreenId>> = {
  club: 'clubs',
  slots: 'clubs',
  confirm: 'clubs',
  qr: 'bookings',
  bill: 'session',
};

export const SORT_CHIPS = ['Yaqin', 'Reyting', 'Bo‘sh joy', 'Arzon'];

export const CLUB_DESC =
  'Alohida xonalar: PS3 dan PS5 Pro gacha, turnir uchun kattaroq ekran va ikkita VIP. Seans ichida bar buyurtmasi Mini App orqali yuboriladi, hisob chiqishda yopiladi.';

const ROOM_ORDER = ['Standart', 'Turnir', 'VIP'];
const ROOM_LABEL: Record<string, string> = {
  Standart: 'Standart xona',
  Turnir: 'Turnir xonasi',
  VIP: 'VIP xona',
};

export interface ClubRoom {
  name: string;
  price: string;
  spec: string;
  pct: string;
  free: string;
}

/**
 * Xonalar va narxlar stansiyalardan hosil qilinadi — qo'lda yozilmaydi.
 * Superadmin yangi konsol turini qo'shsa yoki stansiya kiritsa, bu ro'yxat
 * o'zi yangilanadi.
 */
export function clubRooms(nowMin: number): ClubRoom[] {
  return ROOM_ORDER.filter((room) => STATIONS.some((station) => station.room === room)).map(
    (room) => {
      const group = STATIONS.filter((station) => station.room === room);
      const rates = [...new Set(group.map((station) => station.rate))].sort((a, b) => a - b);
      const consoles = [...new Set(group.map((station) => station.console))]
        .map((id) => ({ id, order: CONSOLES.find((type) => type.id === id)?.order ?? 0 }))
        .sort((a, b) => a.order - b.order)
        .map((item) => consoleLabel(item.id));
      const screens = [...new Set(group.map((station) => station.tv))].sort((a, b) => a - b);
      const busy = group.filter((station) => isBusyNow(station.code, nowMin)).length;
      const free = group.length - busy;

      // Ko'p xil bo'lsa oraliq ko'rsatiladi — mobil kenglikda satr sinmasin
      const range = (values: string[]): string =>
        values.length > 2 ? `${values[0]}–${values[values.length - 1]}` : values.join(' · ');

      return {
        name: ROOM_LABEL[room] ?? room,
        price:
          rates.length === 1
            ? `${S(rates[0] as number)} / soat`
            : `${S(rates[0] as number)}–${S(rates[rates.length - 1] as number)} / soat`,
        spec: `${range(consoles)} · ${screens.length > 1 ? `${screens[0]}–${screens[screens.length - 1]}"` : `${screens[0]}"`} · ${group.length} xona`,
        pct: `${Math.round((busy / group.length) * 100)}%`,
        free: free === 0 ? 'Band' : `${free} bo‘sh`,
      };
    },
  );
}

/** Klubdagi xona turlari — filtr tugmalari shundan. */
export const clubRoomTypes = (): string[] =>
  ROOM_ORDER.filter((room) => STATIONS.some((station) => station.room === room));

/** Klub teglari — xona soni, VIP borligi va mavjud konsollardan. */
export function clubTags(): { label: string; tone: 'neutral' | 'violet' }[] {
  const tags: { label: string; tone: 'neutral' | 'violet' }[] = [
    { label: `${STATIONS.length} xona`, tone: 'neutral' },
  ];
  if (STATIONS.some((station) => station.room === 'VIP')) {
    tags.push({ label: 'VIP xona', tone: 'violet' });
  }
  tags.push({ label: 'Bar', tone: 'neutral' });
  for (const type of clubConsoles()) tags.push({ label: type.label, tone: 'neutral' });
  return tags;
}

export const REVIEWS = [
  { name: 'Sardor R.', rating: '5', text: 'Joystiklar yangi, internet tez. Bron qilib borgan yaxshi — navbat yo‘q.', date: '09-08-2026' },
  { name: 'Nodira Q.', rating: '4', text: 'VIP xona toza va tinch. Bar narxlari biroz qimmat.', date: '05-08-2026' },
  { name: 'Bekzod Y.', rating: '5', text: 'Bron to‘lovi umumiy hisobga o‘tgani qulay ekan.', date: '01-08-2026' },
];

export const MY_BOOKINGS = [
  { club: 'Neon Arena · 1-xona', when: '12-08-2026  19:30 → 21:30', code: '482013', amount: '80 000 so‘m', status: 'Ichkarida', acc: 'var(--secondary-500)', ln: 'var(--line-1)', cancellable: false },
  { club: 'Neon Arena · VIP-2', when: '15-08-2026  20:00 → 23:00', code: '519204', amount: '180 000 so‘m', status: 'Tasdiqlangan', acc: 'var(--primary-100)', ln: 'var(--line-1)', cancellable: true },
  { club: 'Pixel Club · 5-xona', when: '18-08-2026  18:00 → 20:00', code: '603117', amount: '50 000 so‘m', status: 'To‘lov kutilmoqda', acc: 'var(--yellow-100)', ln: 'var(--yellow-100)', cancellable: true },
  { club: 'Respawn Zone · 2-xona', when: '28-07-2026  22:00 → 00:00', code: '451204', amount: '0 so‘m', status: 'Bekor qilingan', acc: 'var(--fg-4)', ln: 'var(--line-1)', cancellable: false },
];

/** Profil statistikasi — yopilgan seanslardan yig'iladi. */
export const PROFILE_STATS = [
  { label: 'Seanslar', value: '18' },
  { label: 'O‘ynagan soat', value: '41' },
  { label: 'Bekor qilingan', value: '1' },
  { label: 'Kelmagan', value: '0' },
];

/** O'tkazma uchun klub rekvizitlari. */
export const CARD_FIELDS = [
  { k: 'Karta', v: '8600 1234 5678 9012', tone: 'var(--text-title)' },
  { k: 'Egasi', v: 'NEON ARENA MCHJ', tone: 'var(--text-body)' },
];

export const CASH_NOTE =
  'Chiqishda kassaga naqd to‘laysiz. Xodim hisobni yopgach Telegram‘ga tasdiq keladi.';

export const TRANSFER_NOTE =
  'Ilova orqali o‘tkazing, so‘ng chek rasmini shu yerga yuklang. Xodim tasdiqlagach hisob yopiladi.';

/**
 * Yopilgan hisob — bot xabarida ko'rinadi.
 * Summalar bron to'lovi modeliga mos: 80 000 + 34 000 − 40 000 − 12 000 = 62 000.
 */
export const BILL_SUMMARY = [
  { k: 'Xona', v: '1-xona', tone: 'var(--text-body)' },
  { k: 'O‘ynagan vaqt', v: '2 soat', tone: 'var(--text-body)' },
  { k: 'O‘yin', v: '80 000', tone: 'var(--text-body)' },
  { k: 'Bar', v: '34 000', tone: 'var(--text-body)' },
  { k: 'To‘landi', v: '62 000', tone: 'var(--text-title)' },
  { k: 'Bonus', v: '+62 ball', tone: 'var(--secondary-500)' },
];

export const CLOSED_BILL_CODE = 'CS-2049';

export const PLAY_AMOUNT = 80000;

// ─────────────────────────── formatlash ───────────────────────────

export const S = (n: number): string => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');

export const HM = (m: number): string =>
  `${String(Math.floor(m / 60) % 24).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;

/** Telegram yuqori panelidagi soat — `HH:MM`. */
export const CLK = (seconds: number): string => {
  const s = ((seconds % 86400) + 86400) % 86400;
  return [Math.floor(s / 3600), Math.floor(s / 60) % 60]
    .map((n) => String(n).padStart(2, '0'))
    .join(':');
};

export const DUR = (seconds: number): string => {
  const negative = seconds < 0;
  const s = Math.abs(seconds);
  return `${negative ? '+' : ''}${Math.floor(s / 3600)}:${String(Math.floor(s / 60) % 60).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
};
