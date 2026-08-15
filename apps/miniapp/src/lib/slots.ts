import type { DayBookingDto, StationDto } from '@playbron/api-client';

/**
 * Bo'sh slot hisobi — real stansiya/bandlik ustida. Algoritm mock
 * (`mock/data.ts::freeStations` va yonidagilar) bilan bir xil, faqat
 * manba psevdo-tasodif o'rniga `GET /clubs/{id}/bookings/day` natijasi.
 *
 * Soddalashtirish: bron bir kun ICHIDA deb hisoblanadi (kecha yarmidan
 * o'tib ketmaydi) — klubning `closes_at_min` ≤ 1440 (24:00) doirasida bu
 * kifoya, xuddi mock qamrovi bilan bir xil.
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

function minutesOfDay(iso: string): number {
  const d = new Date(iso);
  return d.getHours() * 60 + d.getMinutes();
}

function toRange(booking: DayBookingDto): TimeRange {
  const from = minutesOfDay(booking.startsAt);
  const to = minutesOfDay(booking.endsAt);
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
): StationDto[] {
  const window: TimeRange = { from, to: from + hours * 60 };
  if (window.to > closeMin) return [];

  return matchingStations(stations, filter)
    .filter(
      (station) =>
        !dayBookings.some((b) => b.stationId === station.id && overlaps(toRange(b), window)),
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
): number {
  let best = 0;
  for (const hours of DURATIONS) {
    if (freeStations(stations, dayBookings, from, hours, closeMin, filter).length === 0) break;
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
): number {
  return slotTimes(openMin, closeMin).filter(
    (from) =>
      !isPast(dayIndex, from, nowMin) &&
      freeStations(stations, dayBookings, from, hours, closeMin, filter).length > 0,
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

/** Klubdagi mavjud konsollar — mavjudlik tartibida, katalogdan. */
export function consoleTypes(stations: StationDto[]): { id: string; label: string }[] {
  const order = Object.keys(CONSOLE_LABEL);
  return [...new Set(stations.map((station) => station.consoleType))]
    .sort((a, b) => order.indexOf(a) - order.indexOf(b))
    .map((id) => ({ id, label: CONSOLE_LABEL[id] ?? id }));
}

/** Kartadagi texnik satr — TV/pad hozircha backend'da yo'q, faqat konsol turi. */
export const stationSpec = (station: StationDto): string =>
  CONSOLE_LABEL[station.consoleType] ?? station.consoleType;

/** Hozirgi lahza — yarim tundan daqiqada, BRAUZER (haqiqiy) vaqti. */
export function nowMinutesOfDay(): number {
  const now = new Date();
  return now.getHours() * 60 + now.getMinutes();
}

/** `dayOptions()`dagi indeks → `YYYY-MM-DD`, server `date` so'rov parametri uchun. */
export function isoDateOf(dayIndex: number): string {
  const d = new Date();
  d.setDate(d.getDate() + dayIndex);
  const pad = (n: number): string => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Tanlangan kun+vaqt → server `starts_at` uchun ISO lahza (brauzer zonasida). */
export function startInstantIso(dayIndex: number, startMin: number): string {
  const d = new Date();
  d.setDate(d.getDate() + dayIndex);
  d.setHours(Math.floor(startMin / 60), startMin % 60, 0, 0);
  return d.toISOString();
}
