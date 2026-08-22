import { ApiError, NetworkError, TimeoutError, type ApiErrorBody } from './errors';
import { isExpiring, isRefreshDead, type Session, type SessionStore } from './session';

/**
 * `fetch()` o'zi HECH QACHON timeout qilmaydi. Server sekin ishga tushsa
 * (Render bepul instansi uxlagan) yoki umuman javob bermay qolsa
 * (API va Redis boshqa regionda — konteyner start'da qotib qoladi), so'rov
 * abadiy «kutilmoqda» holatida qoladi va tugma matni («Yuborilmoqda…»)
 * o'zgarmay qotib qoladi — foydalanuvchiga hech qanday signal berilmaydi.
 *
 * 20 soniya: Render bepul rejasining sovuq boshlanishi (~30-50s) dan qisqa,
 * lekin oddiy so'rovdan ancha uzun — early false-positive bermaydi.
 */
const REQUEST_TIMEOUT_MS = 20_000;

export interface ClientOptions {
  baseUrl: string;
  store: SessionStore;
  /** Faol klub — `X-Club-Id` sarlavhasi. Konsolda klub almashganda o'zgaradi. */
  clubId?: () => number | null;
  /** Sessiya butunlay tugaganda chaqiriladi (UI kirish ekraniga qaytadi). */
  onSignedOut?: () => void;
  /**
   * Xodim (konsol) refresh tokeni HttpOnly cookie'da (audit §10) —
   * `true` bo'lsa `fetch()` `credentials: 'include'` bilan yuboriladi va
   * `refresh()`/`signOut()` tanaga xom tokenni QO'SHMAYDI (cookie o'zi
   * yetadi). Mijoz (Mini App) uchun `false` (sukut) — bugungidek body
   * orqali, cookie umuman ishlatilmaydi.
   */
  cookieRefresh?: boolean;
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  body?: unknown;
  /** Token qo'shilmaydi — `/auth/*` uchun. */
  anonymous?: boolean;
  signal?: AbortSignal;
  /** Takroriy POST'lar bir marta bajarilsin. */
  idempotencyKey?: string;
  query?: Record<string, string | number | boolean | undefined | null>;
}

export class ApiClient {
  private readonly options: ClientOptions;
  /** Bir vaqtda bitta yangilash — parallel 401 lar bitta refresh'ni kutadi. */
  private refreshing: Promise<Session | null> | null = null;

  constructor(options: ClientOptions) {
    this.options = options;
  }

  get session(): Session | null {
    return this.options.store.read();
  }

  setSession(session: Session | null): void {
    this.options.store.write(session);
  }

  signOut(): void {
    this.setSession(null);
    this.options.onSignedOut?.();
  }

  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const session = options.anonymous ? null : await this.freshSession();

    const response = await this.send(path, options, session);

    // Token orada eskirgan bo'lishi mumkin — bir marta yangilab, qayta urinamiz
    if (response.status === 401 && !options.anonymous) {
      const renewed = await this.refresh();
      if (!renewed) {
        this.signOut();
        throw await toError(response);
      }
      const retried = await this.send(path, options, renewed);
      if (!retried.ok) {
        if (retried.status === 401) this.signOut();
        throw await toError(retried);
      }
      return parse<T>(retried);
    }

    if (!response.ok) throw await toError(response);
    return parse<T>(response);
  }

  get<T>(path: string, options?: Omit<RequestOptions, 'method' | 'body'>): Promise<T> {
    return this.request<T>(path, { ...options, method: 'GET' });
  }

  post<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>(path, { ...options, method: 'POST', body });
  }

  patch<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>(path, { ...options, method: 'PATCH', body });
  }

  delete<T>(path: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(path, { ...options, method: 'DELETE' });
  }

  /** To'lov cheki kabi ikkilik (rasm) javoblar uchun — `request()`dagi
   * `parse()` har doim JSON deb hisoblaydi, bu yerda mos emas. */
  async getBlob(path: string, options?: Omit<RequestOptions, 'method' | 'body'>): Promise<Blob> {
    const session = options?.anonymous ? null : await this.freshSession();
    const response = await this.send(path, { ...options, method: 'GET' }, session);

    if (response.status === 401 && !options?.anonymous) {
      const renewed = await this.refresh();
      if (!renewed) {
        this.signOut();
        throw await toError(response);
      }
      const retried = await this.send(path, { ...options, method: 'GET' }, renewed);
      if (!retried.ok) {
        if (retried.status === 401) this.signOut();
        throw await toError(retried);
      }
      return retried.blob();
    }

    if (!response.ok) throw await toError(response);
    return response.blob();
  }

  // ── ichki ─────────────────────────────────────────────────────────────

  private async send(
    path: string,
    options: RequestOptions,
    session: Session | null,
  ): Promise<Response> {
    const headers: Record<string, string> = { Accept: 'application/json' };

    if (options.body !== undefined) headers['Content-Type'] = 'application/json';
    if (session) headers['Authorization'] = `Bearer ${session.accessToken}`;
    if (options.idempotencyKey) headers['Idempotency-Key'] = options.idempotencyKey;

    const clubId = this.options.clubId?.();
    if (clubId != null && !options.anonymous) headers['X-Club-Id'] = String(clubId);

    const timeout = AbortSignal.timeout(REQUEST_TIMEOUT_MS);
    const signal = options.signal ? AbortSignal.any([options.signal, timeout]) : timeout;

    try {
      return await fetch(this.options.baseUrl + path + queryString(options.query), {
        method: options.method ?? 'GET',
        headers,
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
        signal,
        // Faqat xodim (konsol) rejimida — refresh tokeni HttpOnly cookie'da,
        // brauzer uni shu bayroqsiz umuman yubormaydi. Mijozda (Mini App)
        // kerak emas: cookie'ning o'zi yo'q, bekorga CORS sirtini kengaytiradi.
        credentials: this.options.cookieRefresh ? 'include' : 'omit',
      });
    } catch (cause) {
      // Chaqiruvchining O'ZI bekor qilgan so'rov — xato emas
      if (options.signal?.aborted) throw cause;
      // Qolgan har qanday `AbortError` — bizning timeout'imiz ishga tushdi
      if (cause instanceof DOMException && cause.name === 'AbortError') {
        throw new TimeoutError(cause);
      }
      throw new NetworkError(cause);
    }
  }

  /** Muddati tugayotgan tokenni oldindan yangilaydi. */
  private async freshSession(): Promise<Session | null> {
    const current = this.session;
    if (!current) return null;
    if (!isExpiring(current)) return current;
    return (await this.refresh()) ?? current;
  }

  private async refresh(): Promise<Session | null> {
    if (this.refreshing) return this.refreshing;

    const current = this.session;
    if (!current || isRefreshDead(current)) {
      this.signOut();
      return null;
    }

    this.refreshing = (async () => {
      try {
        const response = await this.send(
          '/auth/refresh',
          { method: 'POST', body: { refresh_token: current.refreshToken }, anonymous: true },
          null,
        );
        if (!response.ok) {
          this.signOut();
          return null;
        }
        const body = (await response.json()) as SessionResponse;
        const next = toSession(body);
        this.setSession(next);
        return next;
      } catch {
        // Tarmoq uzilgan bo'lsa sessiyani o'chirmaymiz — qayta urinish mumkin
        return null;
      } finally {
        this.refreshing = null;
      }
    })();

    return this.refreshing;
  }
}

export interface SessionResponse {
  access_token: string;
  access_expires_at: string;
  /** `null` — xodim sessiyasida, token HttpOnly cookie'da (audit §10). */
  refresh_token: string | null;
  refresh_expires_at: string;
}

export function toSession(body: SessionResponse): Session {
  return {
    accessToken: body.access_token,
    accessExpiresAt: body.access_expires_at,
    refreshToken: body.refresh_token,
    refreshExpiresAt: body.refresh_expires_at,
  };
}

function queryString(query: RequestOptions['query']): string {
  if (!query) return '';
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue;
    params.set(key, String(value));
  }
  const encoded = params.toString();
  return encoded ? `?${encoded}` : '';
}

async function parse<T>(response: Response): Promise<T> {
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/**
 * Loyihaning O'Z xato formati (`{ error: { code, message } }`) bo'lmagan
 * javoblar uchun tushunarli zaxira matn.
 *
 * Avval hammasi uchun bitta "Xatolik yuz berdi" edi va bu SABABNI
 * yashirardi (loyiha egasining hisoboti, 2026-08-17: xodim buyurtmani
 * bekor qilolmadi — aslida API'ning eski nusxasi jonli bo'lgani uchun
 * endpoint 404 qaytargan, lekin ekranda buni bilib bo'lmasdi).
 *
 * Eng ko'p uchraydigan sabab — frontend va API deploy'lari ROSTMANA
 * ajralib qolishi: statik sayt yangi, API hali eski (yoki teskarisi).
 * Shuning uchun 404 uchun matn "sahifani yangilang" deb aytadi.
 */
function fallbackMessage(status: number): string {
  if (status === 404) return 'Amal topilmadi — sahifani yangilang (ilova yangilangan bo‘lishi mumkin)';
  if (status === 502 || status === 503 || status === 504) {
    return 'Server vaqtincha javob bermayapti — birozdan keyin urinib ko‘ring';
  }
  if (status >= 500) return `Serverda xatolik (${status})`;
  return `Xatolik yuz berdi (${status})`;
}

async function toError(response: Response): Promise<ApiError> {
  let body: ApiErrorBody = { code: 'UNKNOWN', message: fallbackMessage(response.status) };
  try {
    const parsed = (await response.json()) as { error?: ApiErrorBody };
    if (parsed.error) body = parsed.error;
  } catch {
    // JSON bo'lmagan javob (proksi xatosi, 502) — sukut xabar qoladi
  }
  return new ApiError(response.status, body);
}
