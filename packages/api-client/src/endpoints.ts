import type { ApiClient } from './client';
import { toSession } from './client';
import type { AuthSession, Entitlements, Me } from './types';

/**
 * Endpoint funksiyalari. Har biri bitta backend marshrutiga mos keladi —
 * ekranlar URL yozmaydi, shu yerdan chaqiradi.
 */

// ── Auth ──────────────────────────────────────────────────────────────────

/** Mini App: `window.Telegram.WebApp.initData` bilan kirish. */
export async function signInWithInitData(
  api: ApiClient,
  initData: string,
): Promise<AuthSession> {
  const body = await api.post<AuthSession>(
    '/auth/telegram/initdata',
    { init_data: initData },
    { anonymous: true },
  );
  api.setSession(toSession(body));
  return body;
}

/** Landing: Telegram Login Widget javobi bilan kirish. */
export async function signInWithWidget(
  api: ApiClient,
  payload: Record<string, unknown>,
): Promise<AuthSession> {
  const body = await api.post<AuthSession>('/auth/telegram/widget', payload, {
    anonymous: true,
  });
  api.setSession(toSession(body));
  return body;
}

export async function signOut(api: ApiClient): Promise<void> {
  const session = api.session;
  if (session) {
    try {
      await api.post<void>('/auth/logout', { refresh_token: session.refreshToken });
    } catch {
      // Server javob bermasa ham lokal sessiya tozalanadi
    }
  }
  api.signOut();
}

// ── Xodim: Telegram bog'lash ─────────────────────────────────────────────
// Bron bildirishnomasi shu kanal bilan yetadi (`0010_staff_telegram_link.py`).
// Naqsh — bot orqali kirish bilan bir xil (deep-link + poll), lekin natija
// sessiya emas.

export interface TelegramLinkStart {
  nonce: string;
  expiresIn: number;
}

export type TelegramLinkStatus = 'pending' | 'expired' | 'ready';

export const startTelegramLink = async (api: ApiClient): Promise<TelegramLinkStart> => {
  const body = await api.post<{ nonce: string; expires_in: number }>('/auth/telegram/link/start');
  return { nonce: body.nonce, expiresIn: body.expires_in };
};

export const pollTelegramLink = async (
  api: ApiClient,
  nonce: string,
): Promise<TelegramLinkStatus> => {
  const body = await api.post<{ status: TelegramLinkStatus }>(`/auth/telegram/link/${nonce}`);
  return body.status;
};

// ── Bron ──────────────────────────────────────────────────────────────────
// Manba: `api/src/playbron/modules/bookings/router.py`. To'lovsiz oqim
// (Bosqich 1) — mijoz PENDING yuboradi, xodim tasdiqlaydi/rad etadi yoki
// o'zi qo'lda CONFIRMED bron ochadi (telefon/kelib bron qiluvchi uchun).

export interface ClubDto {
  id: number;
  name: string;
  address: string;
  phone: string | null;
  about: string;
  coverUrl: string | null;
  opensAtMin: number;
  closesAtMin: number;
  timezone: string;
}

interface ClubApi {
  id: number;
  name: string;
  address: string;
  phone: string | null;
  about: string;
  cover_url: string | null;
  opens_at_min: number;
  closes_at_min: number;
  timezone: string;
}

export const listClubs = async (api: ApiClient): Promise<ClubDto[]> => {
  const rows = await api.get<ClubApi[]>('/clubs');
  return rows.map((row) => ({
    id: row.id,
    name: row.name,
    address: row.address,
    phone: row.phone,
    about: row.about,
    coverUrl: row.cover_url,
    opensAtMin: row.opens_at_min,
    closesAtMin: row.closes_at_min,
    timezone: row.timezone,
  }));
};

export interface StationDto {
  id: number;
  code: string;
  roomLabel: string;
  consoleType: string;
  rate: number;
  status: string;
}

interface StationApi {
  id: number;
  code: string;
  room_label: string;
  console_type: string;
  rate: number;
  status: string;
}

const fromStationApi = (row: StationApi): StationDto => ({
  id: row.id,
  code: row.code,
  roomLabel: row.room_label,
  consoleType: row.console_type,
  rate: row.rate,
  status: row.status,
});

export const listStations = async (api: ApiClient, clubId: number): Promise<StationDto[]> => {
  const rows = await api.get<StationApi[]>(`/clubs/${clubId}/stations`);
  return rows.map(fromStationApi);
};

/** Boshqaruv ro'yxati — `maintenance` xonalar ham (staff/admin token talab qiladi). */
export const listStationsForManagement = async (
  api: ApiClient,
  clubId: number,
): Promise<StationDto[]> => {
  const rows = await api.get<StationApi[]>(`/clubs/${clubId}/stations/manage`);
  return rows.map(fromStationApi);
};

export interface StationCreateIn {
  code: string;
  roomLabel: string;
  consoleType: string;
  rate: number;
}

export const createStation = async (
  api: ApiClient,
  clubId: number,
  body: StationCreateIn,
): Promise<StationDto> => {
  const row = await api.post<StationApi>(`/clubs/${clubId}/stations`, {
    code: body.code,
    room_label: body.roomLabel,
    console_type: body.consoleType,
    rate: body.rate,
  });
  return fromStationApi(row);
};

export interface StationUpdateIn {
  roomLabel: string;
  consoleType: string;
  rate: number;
  status: 'active' | 'maintenance';
}

export const updateStation = async (
  api: ApiClient,
  clubId: number,
  stationId: number,
  body: StationUpdateIn,
): Promise<StationDto> => {
  const row = await api.request<StationApi>(`/clubs/${clubId}/stations/${stationId}`, {
    method: 'PATCH',
    body: {
      room_label: body.roomLabel,
      console_type: body.consoleType,
      rate: body.rate,
      status: body.status,
    },
  });
  return fromStationApi(row);
};

export interface ClubUpdateIn {
  name: string;
  address: string;
  phone: string | null;
  about: string;
  opensAtMin: number;
  closesAtMin: number;
}

export const updateClub = async (
  api: ApiClient,
  clubId: number,
  body: ClubUpdateIn,
): Promise<ClubDto> => {
  const row = await api.request<ClubApi>(`/clubs/${clubId}`, {
    method: 'PATCH',
    body: {
      name: body.name,
      address: body.address,
      phone: body.phone,
      about: body.about,
      opens_at_min: body.opensAtMin,
      closes_at_min: body.closesAtMin,
    },
  });
  return {
    id: row.id,
    name: row.name,
    address: row.address,
    phone: row.phone,
    about: row.about,
    coverUrl: row.cover_url,
    opensAtMin: row.opens_at_min,
    closesAtMin: row.closes_at_min,
    timezone: row.timezone,
  };
};

export interface PendingBookingDto {
  id: number;
  stationId: number;
  stationCode: string;
  startsAt: string;
  endsAt: string;
  hours: number;
  rateSnapshot: number;
  customerName: string | null;
  customerPhone: string | null;
}

interface PendingBookingApi {
  id: number;
  station_id: number;
  station_code: string;
  starts_at: string;
  ends_at: string;
  hours: number;
  rate_snapshot: number;
  customer_name: string | null;
  customer_phone: string | null;
}

export const listPendingBookings = async (
  api: ApiClient,
  clubId: number,
): Promise<PendingBookingDto[]> => {
  const rows = await api.get<PendingBookingApi[]>(`/clubs/${clubId}/bookings/pending`);
  return rows.map((row) => ({
    id: row.id,
    stationId: row.station_id,
    stationCode: row.station_code,
    startsAt: row.starts_at,
    endsAt: row.ends_at,
    hours: row.hours,
    rateSnapshot: row.rate_snapshot,
    customerName: row.customer_name,
    customerPhone: row.customer_phone,
  }));
};

export interface DayBookingDto {
  stationId: number;
  startsAt: string;
  endsAt: string;
  status: string;
}

interface DayBookingApi {
  station_id: number;
  starts_at: string;
  ends_at: string;
  status: string;
}

/** Berilgan kunning FAOL bandliklari — xom oraliqlar, bo'sh slot hisobi mijoz tomonida. */
export const listDayBookings = async (
  api: ApiClient,
  clubId: number,
  date: string,
): Promise<DayBookingDto[]> => {
  const rows = await api.get<DayBookingApi[]>(`/clubs/${clubId}/bookings/day`, {
    query: { date },
  });
  return rows.map((row) => ({
    stationId: row.station_id,
    startsAt: row.starts_at,
    endsAt: row.ends_at,
    status: row.status,
  }));
};

export interface CustomerBookingIn {
  stationId: number;
  startsAt: string;
  hours: number;
}

export interface BookingDto {
  id: number;
  stationId: number;
  status: string;
  startsAt: string;
  endsAt: string;
  hours: number;
  rateSnapshot: number;
}

export const createCustomerBooking = async (
  api: ApiClient,
  clubId: number,
  body: CustomerBookingIn,
): Promise<BookingDto> => {
  const row = await api.post<{
    id: number;
    station_id: number;
    status: string;
    starts_at: string;
    ends_at: string;
    hours: number;
    rate_snapshot: number;
  }>(`/clubs/${clubId}/bookings`, {
    station_id: body.stationId,
    starts_at: body.startsAt,
    hours: body.hours,
  });
  return {
    id: row.id,
    stationId: row.station_id,
    status: row.status,
    startsAt: row.starts_at,
    endsAt: row.ends_at,
    hours: row.hours,
    rateSnapshot: row.rate_snapshot,
  };
};

export interface MyBookingDto {
  id: number;
  status: string;
  hours: number;
  rateSnapshot: number;
  startsAt: string;
  endsAt: string;
  stationCode: string;
  clubName: string;
}

export const listMyBookings = async (api: ApiClient): Promise<MyBookingDto[]> => {
  const rows = await api.get<
    Array<{
      id: number;
      status: string;
      hours: number;
      rate_snapshot: number;
      starts_at: string;
      ends_at: string;
      station_code: string;
      club_name: string;
    }>
  >('/me/bookings');
  return rows.map((row) => ({
    id: row.id,
    status: row.status,
    hours: row.hours,
    rateSnapshot: row.rate_snapshot,
    startsAt: row.starts_at,
    endsAt: row.ends_at,
    stationCode: row.station_code,
    clubName: row.club_name,
  }));
};

export const confirmBooking = (api: ApiClient, clubId: number, bookingId: number): Promise<void> =>
  api.post<void>(`/clubs/${clubId}/bookings/${bookingId}/confirm`);

export const rejectBooking = (
  api: ApiClient,
  clubId: number,
  bookingId: number,
  reason?: string,
): Promise<void> => api.post<void>(`/clubs/${clubId}/bookings/${bookingId}/reject`, { reason });

export interface StaffBookingIn {
  stationId: number;
  startsAt: string;
  hours: number;
  guestName: string;
  guestPhone: string;
}

export const createStaffBooking = async (
  api: ApiClient,
  clubId: number,
  body: StaffBookingIn,
): Promise<void> => {
  await api.post(`/clubs/${clubId}/bookings/staff`, {
    station_id: body.stationId,
    starts_at: body.startsAt,
    hours: body.hours,
    guest_name: body.guestName,
    guest_phone: body.guestPhone,
  });
};

// ── Xodim ro'yxati ───────────────────────────────────────────────────────
// Manba: `api/src/playbron/modules/staff/router.py`. Rol faqat ADMIN/STAFF —
// OWNER shu yo'l bilan berilmaydi (klub bitta marta o'zi ro'yxatdan o'tadi).

export interface StaffMemberDto {
  userId: number;
  login: string;
  firstName: string;
  role: string;
  status: string;
}

export const listStaffMembers = async (
  api: ApiClient,
  clubId: number,
): Promise<StaffMemberDto[]> => {
  const rows = await api.get<
    Array<{ user_id: number; login: string; first_name: string; role: string; status: string }>
  >(`/clubs/${clubId}/staff`);
  return rows.map((row) => ({
    userId: row.user_id,
    login: row.login,
    firstName: row.first_name,
    role: row.role,
    status: row.status,
  }));
};

export interface StaffCreateIn {
  firstName: string;
  login: string;
  password: string;
  role: 'ADMIN' | 'STAFF';
}

export interface StaffCreateResult {
  userId: number;
  login: string;
  role: string;
  mustChangePassword: boolean;
}

export const createStaffMember = async (
  api: ApiClient,
  clubId: number,
  body: StaffCreateIn,
): Promise<StaffCreateResult> => {
  const row = await api.post<{
    user_id: number;
    login: string;
    role: string;
    must_change_password: boolean;
  }>(`/clubs/${clubId}/staff`, {
    first_name: body.firstName,
    login: body.login,
    password: body.password,
    role: body.role,
  });
  return {
    userId: row.user_id,
    login: row.login,
    role: row.role,
    mustChangePassword: row.must_change_password,
  };
};

// ── Me ────────────────────────────────────────────────────────────────────

export const getMe = (api: ApiClient): Promise<Me> => api.get<Me>('/me');

export const getEntitlements = (api: ApiClient): Promise<Entitlements> =>
  api.get<Entitlements>('/me/entitlements');

/** So'rov kalitlari — kesh bir joydan boshqariladi. */
export const queryKeys = {
  me: ['me'] as const,
  entitlements: (clubId: number | null) => ['me', 'entitlements', clubId] as const,
};
