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

// ── Me ────────────────────────────────────────────────────────────────────

export const getMe = (api: ApiClient): Promise<Me> => api.get<Me>('/me');

export const getEntitlements = (api: ApiClient): Promise<Entitlements> =>
  api.get<Entitlements>('/me/entitlements');

/** So'rov kalitlari — kesh bir joydan boshqariladi. */
export const queryKeys = {
  me: ['me'] as const,
  entitlements: (clubId: number | null) => ['me', 'entitlements', clubId] as const,
};
