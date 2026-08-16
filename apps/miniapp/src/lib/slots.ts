import type { DayBookingDto, StationDto } from '@playbron/api-client';

/**
 * Bo'sh slot hisobi — real stansiya/bandlik ustida. Algoritm mock
 * (`mock/data.ts::freeStations` va yonidagilar) bilan bir xil, faqat
 * manba psevdo-tasodif o'rniga `GET /clubs/{id}/bookings/day` natijasi.
 *
 * Soddalashtirish: bron bir kun ICHIDA deb hisoblanadi (kecha yarmidan
 * o'tib ketmaydi) — klubning `closes_at_min` ≤ 1440 (24:00) doirasida bu
 * kifoya, xuddi mock qamrovi bilan bir xil.
 *
 * VAQT ZONASI — barcha funksiya BU YERDA `timezone` (`ClubDto.timezone`,
 * masalan `Asia/Tashkent`) parametrini QABUL QILADI va BRAUZER vaqt
 * zonasiga HECH QACHON tayanmaydi (`Date.getHours()`/`setHours()` kabi).
 * Avval tayangan edi — mijoz telefoni/brauzeri klubdan BOSHQA vaqt
 * zonasida bo'lsa (yoki server/klient soati boshqacha sozlangan bo'lsa),
 * "bo'sh" ko'ringan slot aslida band bo'lgan haqiqiy lahzaga to'g'ri
 * kelib, `409 SLOT_TAKEN` chiqardi (loyiha egasi, 2026-08-16: "mijoz
 * sifatida bron qilolmadim, vaqt tanlangan deydi"). `date-fns-tz` loyihada
 * o'rnatilmagan — native `Intl.DateTimeFormat({ timeZone })` yetarli va
 * qo'shimcha bog'liqlik talab qilmaydi.
 */

export interface TimeRange {
  from: number;
  to: number;
}

export interface SlotFilter {
  room: string;
  console: string;
}

export const ANY = 'Barchasi';
export const SLOT_STEP = 30;
/** Server `MAX_HOURS` (`modules/bookings/service.py`) bilan bir xil. */
export const DURATIONS = [1, 2, 3, 4, 5, 6];

const overlaps = (a: TimeRange, b: TimeRange): boolean => a.from < b.to && a.to > b.from;

interface ZonedParts {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
}

function zonedParts(date: Date, timezone: string): ZonedParts {
  const formatter = new Intl.DateTimeFormat('en-US', {
    timeZone: timezone,
    hourCycle: 'h23',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
  const raw: Record<string, string> = {};
  for (const part of formatter.formatToParts(date)) {
    if (part.type !== 'literal') raw[part.type] = part.value;
  }
  return {
    year: Number(raw.year),
    month: Number(raw.month),
    day: Number(raw.day),
    hour: Number(raw.hour) % 24, // "24:00" bo'lsa h23 uni "00" bermaydi, lekin ehtiyot chorasi
    minute: Number(raw.minute),
  };
}

/** `timezone` — `date` lahzasida UTC'dan necha daqiqa oldinda (musbat sharq uchun). */
function timezoneOffsetMinutes(date: Date, timezone: string): number {
  const p = zonedParts(date, timezone);
  const asUtc = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, 0);
  return (asUtc - date.getTime()) / 60_000;
}

/** Klub vaqt zonasidagi (yil, oy, kun) + kun ichidagi daqiqa → server UTC ISO lahzasi. */
function zonedDateToUtcIso(year: number, month: number, day: number, minutesOfDay: number, timezone: string): string {
  const hour = Math.floor(minutesOfDay / 60);
  const minute = minutesOfDay % 60;
  // Birinchi taxmin — devor vaqtini xuddi UTC deb hisoblab, keyin haqiqiy
  // ofset bilan tuzatiladi (Toshkentda DST yo'q, bitta o'tishning o'zi kifoya).
  const guessMs = Date.UTC(year, month - 1, day, hour, minute, 0);
  const offset = timezoneOffsetMinutes(new Date(guessMs), timezone);
  return new Date(guessMs - offset * 60_000).toISOString();
}

/** Berilgan ISO lahza — klub vaqt zonasida kun ichidagi daqiqa (0–1439). */
export function minutesOfDayInZone(iso: string, timezone: string): number {
  const p = zonedParts(new Date(iso), timezone);
  return p.hour * 60 + p.minute;
}

function toRange(booking: DayBookingDto, timezone: string): TimeRange {
  const from = minutesOfDayInZone(booking.startsAt, timezone);
  const to = minutesOfDayInZone(booking.endsAt, timezone);
  // Kechani kesib o'tgan bron (server buni odatda rad etadi, lekin himoya
  // uchun) — qolgan kunni band deb belgilaymiz, salbiy oraliq bermaymiz.
  return { from, to: to > from ? to : 24 * 60 };
}

export function matchingStations(stations: StationDto[], filter: SlotFilter): StationDto[] {
  return stations.filter(
    (station) =>
      (filter.room === ANY || station.roomLabel === filter.room) &&
      (filter.console === ANY || station.consoleType === filter.console),
  );
}

/** Berilgan oynada bo'sh xonalar — arzonidan qimmatiga. */
export function freeStations(
  stations: StationDto[],
  dayBookings: DayBookingDto[],
  from: number,
  hours: number,
  closeMin: number,
  filter: SlotFilter,
  timezone: string,
): StationDto[] {
  const window: TimeRange = { from, to: from + hours * 60 };
  if (window.to > closeMin) return [];

  return matchingStations(stations, filter)
    .filter(
      (station) =>
        !dayBookings.some(
          (b) => b.stationId === station.id && overlaps(toRange(b, timezone), window),
        ),
    )
    .sort((a, b) => a.rate - b.rate || a.code.localeCompare(b.code));
}

/** Boshlanish vaqtlari to'ri — eng qisqa seans ham yopilishgacha sig'adigan slotlargacha. */
export function slotTimes(openMin: number, closeMin: number): number[] {
  const last = closeMin - (DURATIONS[0] as number) * 60;
  if (last < openMin) return [];
  return Array.from(
    { length: (last - openMin) / SLOT_STEP + 1 },
    (_, i) => openMin + i * SLOT_STEP,
  );
}

/** O'tib ketgan slot — faqat bugungi kun uchun. */
export const isPast = (dayIndex: number, from: number, nowMin: number): boolean =>
  dayIndex === 0 && from <= nowMin;

/** Shu boshlanish vaqtidan maksimal necha soat olish mumkin. */
export function maxHours(
  stations: StationDto[],
  dayBookings: DayBookingDto[],
  from: number,
  closeMin: number,
  filter: SlotFilter,
  timezone: string,
): number {
  let best = 0;
  for (const hours of DURATIONS) {
    if (freeStations(stations, dayBookings, from, hours, closeMin, filter, timezone).length === 0)
      break;
    best = hours;
  }
  return best;
}

/** Kun tasmasidagi «N bo'sh» — shu davomiylik sig'adigan slotlar soni. */
export function freeSlotCount(
  stations: StationDto[],
  dayBookings: DayBookingDto[],
  hours: number,
  filter: SlotFilter,
  openMin: number,
  closeMin: number,
  dayIndex: number,
  nowMin: number,
  timezone: string,
): number {
  return slotTimes(openMin, closeMin).filter(
    (from) =>
      !isPast(dayIndex, from, nowMin) &&
      freeStations(stations, dayBookings, from, hours, closeMin, filter, timezone).length > 0,
  ).length;
}

/** Klubdagi xona turlari — filtr tugmalari shundan. */
export const roomTypes = (stations: StationDto[]): string[] => [
  ...new Set(stations.map((station) => station.roomLabel)),
];

export const CONSOLE_LABEL: Record<string, string> = {
  ps3: 'PS3',
  ps4: 'PS4',
  ps4pro: 'PS4 Pro',
  ps5: 'PS5',
  ps5pro: 'PS5 Pro',
};

/** Klubdagi mavjud konsollar — mavjudlik tartibida, katalogdan.
 *
 * Yangi (0023'dan keyingi, konsolsiz) xonalar bu ro'yxatga kirmaydi — ular
 * uchun konsol endi bron paytida tanlanadi, filtr sifatida emas (reja #38).
 */
export function consoleTypes(stations: StationDto[]): { id: string; label: string }[] {
  const order = Object.keys(CONSOLE_LABEL);
  const ids = [...new Set(stations.map((station) => station.consoleType))].filter(
    (id): id is string => id !== null,
  );
  return ids
    .sort((a, b) => order.indexOf(a) - order.indexOf(b))
    .map((id) => ({ id, label: CONSOLE_LABEL[id] ?? id }));
}

/** Kartadagi texnik satr — TV/pad hozircha backend'da yo'q, faqat konsol turi.
 * Konsolsiz (yangi) xonada bo'sh — bron paytida tanlanadi. */
export const stationSpec = (station: StationDto): string =>
  station.consoleType ? (CONSOLE_LABEL[station.consoleType] ?? station.consoleType) : '';

/** Hozirgi lahza — yarim tundan daqiqada, KLUB vaqt zonasida. */
export function nowMinutesOfDay(timezone: string): number {
  const p = zonedParts(new Date(), timezone);
  return p.hour * 60 + p.minute;
}

/** Klub vaqt zonasidagi "bugun" — kalendar arifmetikasi UTC ustida
 * (faqat sana, real lahza emas), keyin `dayIndex` kun qo'shiladi. */
function zonedTodayPlusDays(dayIndex: number, timezone: string): { year: number; month: number; day: number } {
  const p = zonedParts(new Date(), timezone);
  const anchor = new Date(Date.UTC(p.year, p.month - 1, p.day));
  anchor.setUTCDate(anchor.getUTCDate() + dayIndex);
  return { year: anchor.getUTCFullYear(), month: anchor.getUTCMonth() + 1, day: anchor.getUTCDate() };
}

/** `dayOptions()`dagi indeks → `YYYY-MM-DD`, server `date` so'rov parametri
 * uchun — KLUB vaqt zonasidagi kalendar sanasi. */
export function isoDateOf(dayIndex: number, timezone: string): string {
  const { year, month, day } = zonedTodayPlusDays(dayIndex, timezone);
  const pad = (n: number): string => String(n).padStart(2, '0');
  return `${year}-${pad(month)}-${pad(day)}`;
}

/** Tanlangan kun+vaqt (KLUB vaqt zonasida) → server `starts_at` uchun UTC
 * ISO lahza. */
export function startInstantIso(dayIndex: number, startMin: number, timezone: string): string {
  const { year, month, day } = zonedTodayPlusDays(dayIndex, timezone);
  return zonedDateToUtcIso(year, month, day, startMin, timezone);
}
