import type { ApiClient } from './client';
import { toSession } from './client';
import type { AuthSession, Entitlements, Me } from './types';

/**
 * Endpoint funksiyalari. Har biri bitta backend marshrutiga mos keladi —
 * ekranlar URL yozmaydi, shu yerdan chaqiradi.
 */

// ── Auth ──────────────────────────────────────────────────────────────────

/** Mini App: `window.Telegram.WebApp.initData` bilan kirish. */
export async function signInWithInitData(api: ApiClient, initData: string): Promise<AuthSession> {
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
  googleMapsUrl: string | null;
  yandexMapsUrl: string | null;
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
  google_maps_url: string | null;
  yandex_maps_url: string | null;
}

const fromClubApi = (row: ClubApi): ClubDto => ({
  id: row.id,
  name: row.name,
  address: row.address,
  phone: row.phone,
  about: row.about,
  coverUrl: row.cover_url,
  opensAtMin: row.opens_at_min,
  closesAtMin: row.closes_at_min,
  timezone: row.timezone,
  googleMapsUrl: row.google_maps_url,
  yandexMapsUrl: row.yandex_maps_url,
});

export const listClubs = async (api: ApiClient): Promise<ClubDto[]> => {
  const rows = await api.get<ClubApi[]>('/clubs');
  return rows.map(fromClubApi);
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
  googleMapsUrl?: string | null;
  yandexMapsUrl?: string | null;
}

export interface ClubDetailDto extends ClubDto {
  status: string;
}

/** Xodim/egasi o'z klubini status'i (draft ham) bilan ko'radi. */
export const getClub = async (api: ApiClient, clubId: number): Promise<ClubDetailDto> => {
  const row = await api.get<ClubApi & { status: string }>(`/clubs/${clubId}`);
  return { ...fromClubApi(row), status: row.status };
};

/** Draft klubni faollashtiradi — kamida bitta faol xona talab qilinadi. */
export const publishClub = (api: ApiClient, clubId: number): Promise<void> =>
  api.post<void>(`/clubs/${clubId}/publish`);

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
      google_maps_url: body.googleMapsUrl ?? null,
      yandex_maps_url: body.yandexMapsUrl ?? null,
    },
  });
  return fromClubApi(row);
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

export interface StaffUpdateIn {
  firstName: string;
  role: 'ADMIN' | 'STAFF';
}

export const updateStaffMember = async (
  api: ApiClient,
  clubId: number,
  userId: number,
  body: StaffUpdateIn,
): Promise<StaffMemberDto> => {
  const row = await api.patch<{
    user_id: number;
    login: string;
    first_name: string;
    role: string;
    status: string;
  }>(`/clubs/${clubId}/staff/${userId}`, {
    first_name: body.firstName,
    role: body.role,
  });
  return {
    userId: row.user_id,
    login: row.login,
    firstName: row.first_name,
    role: row.role,
    status: row.status,
  };
};

export const deactivateStaffMember = (api: ApiClient, clubId: number, userId: number): Promise<void> =>
  api.delete<void>(`/clubs/${clubId}/staff/${userId}`);

// ── Klub faoliyat jurnali ────────────────────────────────────────────────
// Manba: `api/src/playbron/modules/staff/router.py::list_club_logs`.
// `audit_log` (CRUD) + `auth_events` (kirish/chiqish) birlashtirilgan.

export interface ActivityLogDto {
  id: string;
  at: string;
  source: 'audit' | 'auth';
  event: string;
  target: string | null;
  actorName: string | null;
  actorLogin: string | null;
  detail: Record<string, unknown> | null;
}

export const listClubLogs = async (
  api: ApiClient,
  clubId: number,
  limit = 100,
): Promise<ActivityLogDto[]> => {
  const rows = await api.get<
    Array<{
      id: string;
      at: string;
      source: 'audit' | 'auth';
      event: string;
      target: string | null;
      actor_name: string | null;
      actor_login: string | null;
      detail: Record<string, unknown> | null;
    }>
  >(`/clubs/${clubId}/logs`, { query: { limit } });
  return rows.map((row) => ({
    id: row.id,
    at: row.at,
    source: row.source,
    event: row.event,
    target: row.target,
    actorName: row.actor_name,
    actorLogin: row.actor_login,
    detail: row.detail,
  }));
};

// ── POS: mahsulot, buyurtma, kassa, live board ─────────────────────────────
// Manba: `api/src/playbron/modules/pos/router.py`. Mijozga ochiq emas —
// faqat xodim.

export interface ProductDto {
  id: number;
  category: string;
  name: string;
  price: number;
  status: string;
}

export const listProducts = (api: ApiClient, clubId: number): Promise<ProductDto[]> =>
  api.get<ProductDto[]>(`/clubs/${clubId}/products`);

export interface ProductCreateIn {
  category: string;
  name: string;
  price: number;
}

export const createProduct = (
  api: ApiClient,
  clubId: number,
  body: ProductCreateIn,
): Promise<ProductDto> => api.post<ProductDto>(`/clubs/${clubId}/products`, body);

export interface ProductUpdateIn {
  category: string;
  name: string;
  price: number;
  status: 'active' | 'archived';
}

export const updateProduct = (
  api: ApiClient,
  clubId: number,
  productId: number,
  body: ProductUpdateIn,
): Promise<ProductDto> =>
  api.request<ProductDto>(`/clubs/${clubId}/products/${productId}`, {
    method: 'PATCH',
    body,
  });

export interface OrderItemDto {
  productName: string;
  qty: number;
  priceSnapshot: number;
}

export interface OrderDto {
  id: number;
  bookingId: number | null;
  stationCode: string | null;
  status: string;
  total: number;
  createdAt: string;
  items: OrderItemDto[];
}

const fromOrderApi = (row: {
  id: number;
  booking_id: number | null;
  station_code: string | null;
  status: string;
  total: number;
  created_at: string;
  items: Array<{ product_name: string; qty: number; price_snapshot: number }>;
}): OrderDto => ({
  id: row.id,
  bookingId: row.booking_id,
  stationCode: row.station_code,
  status: row.status,
  total: row.total,
  createdAt: row.created_at,
  items: row.items.map((item) => ({
    productName: item.product_name,
    qty: item.qty,
    priceSnapshot: item.price_snapshot,
  })),
});

export const listOrders = async (api: ApiClient, clubId: number): Promise<OrderDto[]> => {
  const rows = await api.get<Parameters<typeof fromOrderApi>[0][]>(`/clubs/${clubId}/orders`);
  return rows.map(fromOrderApi);
};

export interface OrderCreateIn {
  bookingId: number | null;
  items: { productId: number; qty: number }[];
}

export const createOrder = async (
  api: ApiClient,
  clubId: number,
  body: OrderCreateIn,
): Promise<OrderDto> => {
  const row = await api.post<Parameters<typeof fromOrderApi>[0]>(`/clubs/${clubId}/orders`, {
    booking_id: body.bookingId,
    items: body.items.map((item) => ({ product_id: item.productId, qty: item.qty })),
  });
  return fromOrderApi(row);
};

export const advanceOrder = (
  api: ApiClient,
  clubId: number,
  orderId: number,
): Promise<{ status: string }> =>
  api.post<{ status: string }>(`/clubs/${clubId}/orders/${orderId}/advance`);

export interface OpenBookingDto {
  id: number;
  stationCode: string;
  hours: number;
  rateSnapshot: number;
  startsAt: string;
  endsAt: string;
  guestLabel: string | null;
}

export const listOpenBookings = async (
  api: ApiClient,
  clubId: number,
): Promise<OpenBookingDto[]> => {
  const rows = await api.get<
    Array<{
      id: number;
      station_code: string;
      hours: number;
      rate_snapshot: number;
      starts_at: string;
      ends_at: string;
      guest_label: string | null;
    }>
  >(`/clubs/${clubId}/bookings/open`);
  return rows.map((row) => ({
    id: row.id,
    stationCode: row.station_code,
    hours: row.hours,
    rateSnapshot: row.rate_snapshot,
    startsAt: row.starts_at,
    endsAt: row.ends_at,
    guestLabel: row.guest_label,
  }));
};

export interface BillDto {
  bookingId: number;
  playAmount: number;
  ordersAmount: number;
  total: number;
}

const fromBillApi = (row: {
  booking_id: number;
  play_amount: number;
  orders_amount: number;
  total: number;
}): BillDto => ({
  bookingId: row.booking_id,
  playAmount: row.play_amount,
  ordersAmount: row.orders_amount,
  total: row.total,
});

export const getBill = async (
  api: ApiClient,
  clubId: number,
  bookingId: number,
): Promise<BillDto> => {
  const row = await api.get<Parameters<typeof fromBillApi>[0]>(
    `/clubs/${clubId}/bookings/${bookingId}/bill`,
  );
  return fromBillApi(row);
};

export const closeBill = async (
  api: ApiClient,
  clubId: number,
  bookingId: number,
  body: { paymentMethod: 'CASH' | 'TRANSFER'; paidAmount: number },
): Promise<BillDto> => {
  const row = await api.post<Parameters<typeof fromBillApi>[0]>(
    `/clubs/${clubId}/bookings/${bookingId}/close`,
    { payment_method: body.paymentMethod, paid_amount: body.paidAmount },
  );
  return fromBillApi(row);
};

export interface LiveStationDto {
  id: number;
  code: string;
  roomLabel: string;
  consoleType: string;
  rate: number;
  status: string;
  bookingId: number | null;
  endsAt: string | null;
  guestLabel: string | null;
}

export const listLiveStations = async (
  api: ApiClient,
  clubId: number,
): Promise<LiveStationDto[]> => {
  const rows = await api.get<
    Array<{
      id: number;
      code: string;
      room_label: string;
      console_type: string;
      rate: number;
      status: string;
      booking_id: number | null;
      ends_at: string | null;
      guest_label: string | null;
    }>
  >(`/clubs/${clubId}/live`);
  return rows.map((row) => ({
    id: row.id,
    code: row.code,
    roomLabel: row.room_label,
    consoleType: row.console_type,
    rate: row.rate,
    status: row.status,
    bookingId: row.booking_id,
    endsAt: row.ends_at,
    guestLabel: row.guest_label,
  }));
};

// ── Xarajatlar ───────────────────────────────────────────────────────────
// Manba: `api/src/playbron/modules/finance/router.py`, `0020_expenses.py`.
// Faqat OWNER/ADMIN (STAFF'ga ochiq emas — mahsulotdan farqi shu).

export interface ExpenseDto {
  id: number;
  /** ISO sana (`YYYY-MM-DD`). */
  spentOn: string;
  category: string;
  amount: number;
  note: string | null;
  status: 'active' | 'archived';
  createdByName: string | null;
  createdAt: string;
}

interface ExpenseApi {
  id: number;
  spent_on: string;
  category: string;
  amount: number;
  note: string | null;
  status: string;
  created_by_name: string | null;
  created_at: string;
}

const fromExpenseApi = (row: ExpenseApi): ExpenseDto => ({
  id: row.id,
  spentOn: row.spent_on,
  category: row.category,
  amount: row.amount,
  note: row.note,
  status: row.status === 'archived' ? 'archived' : 'active',
  createdByName: row.created_by_name,
  createdAt: row.created_at,
});

export const listExpenses = async (api: ApiClient, clubId: number): Promise<ExpenseDto[]> => {
  const rows = await api.get<ExpenseApi[]>(`/clubs/${clubId}/expenses`);
  return rows.map(fromExpenseApi);
};

export interface ExpenseCreateIn {
  spentOn: string;
  category: string;
  amount: number;
  note?: string | null;
}

export const createExpense = async (
  api: ApiClient,
  clubId: number,
  body: ExpenseCreateIn,
): Promise<ExpenseDto> => {
  const row = await api.post<ExpenseApi>(`/clubs/${clubId}/expenses`, {
    spent_on: body.spentOn,
    category: body.category,
    amount: body.amount,
    note: body.note ?? null,
  });
  return fromExpenseApi(row);
};

export interface ExpenseUpdateIn {
  spentOn: string;
  category: string;
  amount: number;
  note?: string | null;
  status: 'active' | 'archived';
}

export const updateExpense = async (
  api: ApiClient,
  clubId: number,
  expenseId: number,
  body: ExpenseUpdateIn,
): Promise<ExpenseDto> => {
  const row = await api.request<ExpenseApi>(`/clubs/${clubId}/expenses/${expenseId}`, {
    method: 'PATCH',
    body: {
      spent_on: body.spentOn,
      category: body.category,
      amount: body.amount,
      note: body.note ?? null,
      status: body.status,
    },
  });
  return fromExpenseApi(row);
};

// ── Smena ────────────────────────────────────────────────────────────────
// Manba: `api/src/playbron/modules/finance/router.py`, `0021_shifts.py`.

export interface ShiftMovementDto {
  id: number;
  kind: 'IN' | 'OUT';
  amount: number;
  reason: string;
  createdByName: string | null;
  createdAt: string;
}

export interface ShiftDto {
  id: number;
  staffId: number;
  openedAt: string;
  openingCash: number;
  closedAt: string | null;
  countedCash: number | null;
  status: 'open' | 'closed';
  expectedCash: number;
  variance: number | null;
  movements: ShiftMovementDto[];
}

interface ShiftMovementApi {
  id: number;
  kind: string;
  amount: number;
  reason: string;
  created_by_name: string | null;
  created_at: string;
}

interface ShiftApi {
  id: number;
  staff_id: number;
  opened_at: string;
  opening_cash: number;
  closed_at: string | null;
  counted_cash: number | null;
  status: string;
  expected_cash: number;
  variance: number | null;
  movements: ShiftMovementApi[];
}

const fromShiftApi = (row: ShiftApi): ShiftDto => ({
  id: row.id,
  staffId: row.staff_id,
  openedAt: row.opened_at,
  openingCash: row.opening_cash,
  closedAt: row.closed_at,
  countedCash: row.counted_cash,
  status: row.status === 'closed' ? 'closed' : 'open',
  expectedCash: row.expected_cash,
  variance: row.variance,
  movements: row.movements.map((m) => ({
    id: m.id,
    kind: m.kind === 'OUT' ? 'OUT' : 'IN',
    amount: m.amount,
    reason: m.reason,
    createdByName: m.created_by_name,
    createdAt: m.created_at,
  })),
});

export const getCurrentShift = async (api: ApiClient, clubId: number): Promise<ShiftDto | null> => {
  const row = await api.get<ShiftApi | null>(`/clubs/${clubId}/shifts/current`);
  return row ? fromShiftApi(row) : null;
};

export interface OpenShiftSummaryDto {
  id: number;
  staffId: number;
  staffName: string;
  openedAt: string;
  openingCash: number;
}

export const listOpenShifts = async (api: ApiClient, clubId: number): Promise<OpenShiftSummaryDto[]> => {
  const rows = await api.get<
    Array<{ id: number; staff_id: number; staff_name: string; opened_at: string; opening_cash: number }>
  >(`/clubs/${clubId}/shifts/open`);
  return rows.map((r) => ({
    id: r.id,
    staffId: r.staff_id,
    staffName: r.staff_name,
    openedAt: r.opened_at,
    openingCash: r.opening_cash,
  }));
};

export const openShift = async (
  api: ApiClient,
  clubId: number,
  openingCash: number,
): Promise<ShiftDto> => {
  const row = await api.post<ShiftApi>(`/clubs/${clubId}/shifts`, { opening_cash: openingCash });
  return fromShiftApi(row);
};

export const addShiftMovement = async (
  api: ApiClient,
  clubId: number,
  shiftId: number,
  body: { kind: 'IN' | 'OUT'; amount: number; reason: string },
): Promise<ShiftDto> => {
  const row = await api.post<ShiftApi>(`/clubs/${clubId}/shifts/${shiftId}/movements`, body);
  return fromShiftApi(row);
};

export const closeShift = async (
  api: ApiClient,
  clubId: number,
  shiftId: number,
  countedCash: number,
): Promise<ShiftDto> => {
  const row = await api.post<ShiftApi>(`/clubs/${clubId}/shifts/${shiftId}/close`, {
    counted_cash: countedCash,
  });
  return fromShiftApi(row);
};

// ── Platforma (super admin) ─────────────────────────────────────────────
// Manba: `api/src/playbron/modules/platform/router.py`. Faqat o'qish,
// cross-tenant — `docs/06-super-admin.md` §3, kichik kesim
// (`0015_platform_stats.py`).

export interface PlatformTopClubDto {
  clubId: number;
  clubName: string;
  orgName: string;
  bookings: number;
}

export interface PlatformStatsDto {
  organizationsTotal: number;
  clubsActive: number;
  clubsDraft: number;
  bookingsToday: number;
  revenueToday: number;
  bookingsThisMonth: number;
  revenueThisMonth: number;
  /** Kun (ISO, YYYY-MM-DD) → shu kundagi CONFIRMED bronlar soni. */
  dailyTrend: Record<string, number>;
  topClubs: PlatformTopClubDto[];
}

interface PlatformStatsApi {
  organizations_total: number;
  clubs_active: number;
  clubs_draft: number;
  bookings_today: number;
  revenue_today: number;
  bookings_this_month: number;
  revenue_this_month: number;
  daily_trend: Record<string, number>;
  top_clubs: { club_id: number; club_name: string; org_name: string; bookings: number }[];
}

export const getPlatformStats = async (api: ApiClient): Promise<PlatformStatsDto> => {
  const row = await api.get<PlatformStatsApi>('/platform/stats');
  return {
    organizationsTotal: row.organizations_total,
    clubsActive: row.clubs_active,
    clubsDraft: row.clubs_draft,
    bookingsToday: row.bookings_today,
    revenueToday: row.revenue_today,
    bookingsThisMonth: row.bookings_this_month,
    revenueThisMonth: row.revenue_this_month,
    dailyTrend: row.daily_trend,
    topClubs: row.top_clubs.map((r) => ({
      clubId: r.club_id,
      clubName: r.club_name,
      orgName: r.org_name,
      bookings: r.bookings,
    })),
  };
};

// ── Platforma: Klublar (qo'lda qo'shish) ────────────────────────────────
// Manba: `0016_platform_org_admin.py`.

export interface PlatformOrgDto {
  orgId: number;
  orgName: string;
  orgStatus: string;
  planCode: string | null;
  createdAt: string;
  ownerName: string;
  ownerLogin: string | null;
  clubId: number | null;
  clubName: string | null;
  clubStatus: string | null;
  stationsCount: number;
  bookings30d: number;
  /** So'nggi qo'lda kiritilgan to'lov summasi — hech qachon to'lanmagan bo'lsa `null`. */
  lastPaymentAmount: number | null;
  lastPaymentAt: string | null;
  /** `so'nggi to'lov + necha oy` — backendda hisoblanadi, ustun sifatida saqlanmaydi. */
  planExpiresAt: string | null;
}

interface PlatformOrgApi {
  org_id: number;
  org_name: string;
  org_status: string;
  plan_code: string | null;
  created_at: string;
  owner_name: string;
  owner_login: string | null;
  club_id: number | null;
  club_name: string | null;
  club_status: string | null;
  stations_count: number;
  bookings_30d: number;
  last_payment_amount: number | null;
  last_payment_at: string | null;
  plan_expires_at: string | null;
}

const fromPlatformOrgApi = (row: PlatformOrgApi): PlatformOrgDto => ({
  orgId: row.org_id,
  orgName: row.org_name,
  orgStatus: row.org_status,
  planCode: row.plan_code,
  createdAt: row.created_at,
  ownerName: row.owner_name,
  ownerLogin: row.owner_login,
  clubId: row.club_id,
  clubName: row.club_name,
  clubStatus: row.club_status,
  stationsCount: row.stations_count,
  bookings30d: row.bookings_30d,
  lastPaymentAmount: row.last_payment_amount,
  lastPaymentAt: row.last_payment_at,
  planExpiresAt: row.plan_expires_at,
});

export const listPlatformOrgs = async (api: ApiClient): Promise<PlatformOrgDto[]> => {
  const rows = await api.get<PlatformOrgApi[]>('/platform/orgs');
  return rows.map(fromPlatformOrgApi);
};

export interface PlatformOrgCreateIn {
  firstName: string;
  clubName: string;
  phone: string;
  address: string;
  login: string;
  password: string;
}

export const createPlatformOrg = (
  api: ApiClient,
  body: PlatformOrgCreateIn,
): Promise<{ login: string }> =>
  api.post<{ login: string }>('/platform/orgs', {
    first_name: body.firstName,
    club_name: body.clubName,
    phone: body.phone,
    address: body.address,
    login: body.login,
    password: body.password,
  });

export interface PlatformPaymentIn {
  amount: number;
  planCode?: string | null;
  periodMonths?: number | null;
  note?: string | null;
}

export interface PlatformPaymentDto {
  id: number;
  orgId: number;
  amount: number;
  planCode: string | null;
  periodMonths: number | null;
  paidAt: string;
  note: string | null;
}

export const recordPlatformPayment = async (
  api: ApiClient,
  orgId: number,
  body: PlatformPaymentIn,
): Promise<PlatformPaymentDto> => {
  const row = await api.post<{
    id: number;
    org_id: number;
    amount: number;
    plan_code: string | null;
    period_months: number | null;
    paid_at: string;
    note: string | null;
  }>(`/platform/orgs/${orgId}/payments`, {
    amount: body.amount,
    plan_code: body.planCode ?? null,
    period_months: body.periodMonths ?? null,
    note: body.note ?? null,
  });
  return {
    id: row.id,
    orgId: row.org_id,
    amount: row.amount,
    planCode: row.plan_code,
    periodMonths: row.period_months,
    paidAt: row.paid_at,
    note: row.note,
  };
};

export type PlatformOrgStatus = 'pending' | 'active' | 'suspended';

export interface PlatformOrgUpdateIn {
  name?: string | null;
  status?: PlatformOrgStatus | null;
}

/**
 * Nomi/holatini tahrirlash — `recordPlatformPayment` (`plan_code`) bilan
 * ATAYLAB alohida yo'l (audit topilmasi, 2026-08-16, reja #16).
 */
export const updatePlatformOrg = async (
  api: ApiClient,
  orgId: number,
  body: PlatformOrgUpdateIn,
): Promise<{ orgId: number; orgName: string; orgStatus: string }> => {
  const row = await api.patch<{ org_id: number; org_name: string; org_status: string }>(
    `/platform/orgs/${orgId}`,
    { name: body.name ?? null, status: body.status ?? null },
  );
  return { orgId: row.org_id, orgName: row.org_name, orgStatus: row.org_status };
};

export interface PlatformOrgClubDto {
  clubId: number;
  clubName: string;
  clubStatus: string;
  address: string;
  phone: string | null;
  stationsCount: number;
  bookings30d: number;
}

export interface PlatformOrgPaymentDto {
  id: number;
  amount: number;
  planCode: string | null;
  periodMonths: number | null;
  paidAt: string;
  note: string | null;
  enteredByName: string | null;
}

export interface PlatformOrgStaffDto {
  userId: number;
  firstName: string;
  login: string | null;
  role: string;
  clubId: number;
  clubName: string;
}

export interface PlatformOrgDetailDto {
  orgId: number;
  orgName: string;
  orgStatus: string;
  planCode: string | null;
  createdAt: string;
  ownerName: string;
  ownerLogin: string | null;
  clubs: PlatformOrgClubDto[];
  payments: PlatformOrgPaymentDto[];
  staff: PlatformOrgStaffDto[];
}

interface PlatformOrgDetailApi {
  org_id: number;
  org_name: string;
  org_status: string;
  plan_code: string | null;
  created_at: string;
  owner_name: string;
  owner_login: string | null;
  clubs: Array<{
    club_id: number;
    club_name: string;
    club_status: string;
    address: string;
    phone: string | null;
    stations_count: number;
    bookings_30d: number;
  }>;
  payments: Array<{
    id: number;
    amount: number;
    plan_code: string | null;
    period_months: number | null;
    paid_at: string;
    note: string | null;
    entered_by_name: string | null;
  }>;
  staff: Array<{
    user_id: number;
    first_name: string;
    login: string | null;
    role: string;
    club_id: number;
    club_name: string;
  }>;
}

/** "Ko'rish" (Preview) — klublar, TO'LIQ to'lov tarixi, xodimlar (reja #17). */
export const getPlatformOrg = async (api: ApiClient, orgId: number): Promise<PlatformOrgDetailDto> => {
  const row = await api.get<PlatformOrgDetailApi>(`/platform/orgs/${orgId}`);
  return {
    orgId: row.org_id,
    orgName: row.org_name,
    orgStatus: row.org_status,
    planCode: row.plan_code,
    createdAt: row.created_at,
    ownerName: row.owner_name,
    ownerLogin: row.owner_login,
    clubs: row.clubs.map((c) => ({
      clubId: c.club_id,
      clubName: c.club_name,
      clubStatus: c.club_status,
      address: c.address,
      phone: c.phone,
      stationsCount: c.stations_count,
      bookings30d: c.bookings_30d,
    })),
    payments: row.payments.map((p) => ({
      id: p.id,
      amount: p.amount,
      planCode: p.plan_code,
      periodMonths: p.period_months,
      paidAt: p.paid_at,
      note: p.note,
      enteredByName: p.entered_by_name,
    })),
    staff: row.staff.map((s) => ({
      userId: s.user_id,
      firstName: s.first_name,
      login: s.login,
      role: s.role,
      clubId: s.club_id,
      clubName: s.club_name,
    })),
  };
};

// ── Platforma: Hisobot ───────────────────────────────────────────────────

export type PlatformReportPeriod = 'day' | 'week' | 'month' | 'year';

export interface PlatformReportDto {
  period: PlatformReportPeriod;
  /** Chelak (ISO sana) → yig'ilgan to'lov summasi. */
  revenueByBucket: Record<string, number>;
  /** Chelak (ISO sana) → shu davrda qo'shilgan yangi tashkilotlar soni. */
  newOrgsByBucket: Record<string, number>;
  totalRevenue: number;
  totalOrganizations: number;
}

interface PlatformReportApi {
  period: string;
  revenue_by_bucket: Record<string, number>;
  new_orgs_by_bucket: Record<string, number>;
  total_revenue: number;
  total_organizations: number;
}

export const getPlatformReport = async (
  api: ApiClient,
  period: PlatformReportPeriod,
): Promise<PlatformReportDto> => {
  const row = await api.get<PlatformReportApi>('/platform/report', { query: { period } });
  return {
    period: row.period as PlatformReportPeriod,
    revenueByBucket: row.revenue_by_bucket,
    newOrgsByBucket: row.new_orgs_by_bucket,
    totalRevenue: row.total_revenue,
    totalOrganizations: row.total_organizations,
  };
};

// ── Platforma: faoliyat jurnali ─────────────────────────────────────────
// Manba: `api/src/playbron/modules/platform/router.py::platform_logs`.
// Faqat PLATFORMA darajasidagi amallar (tashkilot yaratish, to'lov) —
// bitta klub ICHIDAGI amallar `listClubLogs`da, klub egasining o'zida.

export interface PlatformLogDto {
  id: string;
  at: string;
  action: string;
  target: string | null;
  orgId: number | null;
  actorName: string | null;
  actorLogin: string | null;
  detail: Record<string, unknown> | null;
}

export const listPlatformLogs = async (api: ApiClient, limit = 100): Promise<PlatformLogDto[]> => {
  const rows = await api.get<
    Array<{
      id: string;
      at: string;
      action: string;
      target: string | null;
      org_id: number | null;
      actor_name: string | null;
      actor_login: string | null;
      detail: Record<string, unknown> | null;
    }>
  >('/platform/logs', { query: { limit } });
  return rows.map((row) => ({
    id: row.id,
    at: row.at,
    action: row.action,
    target: row.target,
    orgId: row.org_id,
    actorName: row.actor_name,
    actorLogin: row.actor_login,
    detail: row.detail,
  }));
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
