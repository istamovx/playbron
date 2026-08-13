/**
 * Backend'ning yagona xato formati: `{"error": {"code", "message", "details"}}`.
 * Frontend hech qachon HTTP statusiga emas, barqaror `code` ga qaraydi.
 */

export interface ApiErrorBody {
  code: string;
  message: string;
  details?: Record<string, unknown>;
  request_id?: string;
}

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: Record<string, unknown>;
  readonly requestId: string | undefined;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message || 'Xatolik yuz berdi');
    this.name = 'ApiError';
    this.code = body.code || 'UNKNOWN';
    this.status = status;
    this.details = body.details ?? {};
    this.requestId = body.request_id;
  }

  /** Sessiya tugadi yoki token yaroqsiz — qayta kirish kerak. */
  get isAuth(): boolean {
    return this.status === 401;
  }

  /** Ruxsat yo'q: rol yetmaydi yoki tarif imkoniyati yopiq. */
  get isForbidden(): boolean {
    return this.status === 403;
  }

  /** Tarif limiti tugagan — UI «tarifni ko'tarish» holatini ko'rsatadi. */
  get isLimit(): boolean {
    return this.code === 'LIMIT_REACHED' || this.code === 'FEATURE_NOT_IN_PLAN';
  }

  /** Bron to'qnashuvi — slotni qayta yuklash kerak. */
  get isSlotTaken(): boolean {
    return this.code === 'SLOT_TAKEN';
  }
}

/** Tarmoq uzilishi, timeout, CORS — server javob bermagan holat. */
export class NetworkError extends Error {
  constructor(cause?: unknown) {
    super('Tarmoq bilan bog‘lanib bo‘lmadi');
    this.name = 'NetworkError';
    this.cause = cause;
  }
}

/** Foydalanuvchiga ko'rsatiladigan matn — mavjud dizayn tilida. */
export function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    switch (error.code) {
      case 'TOKEN_EXPIRED':
      case 'UNAUTHORIZED':
      case 'NO_TOKEN':
        return 'Sessiya muddati tugadi — qayta kiring';
      case 'SLOT_TAKEN':
        return 'Bu vaqt band qilindi, boshqasini tanlang';
      case 'LIMIT_REACHED':
        return 'Tarif limiti tugagan';
      case 'FEATURE_NOT_IN_PLAN':
        return 'Bu imkoniyat tarifingizda yo‘q';
      case 'CLUB_FORBIDDEN':
      case 'ROLE_FORBIDDEN':
        return 'Bu amal uchun ruxsat yo‘q';
      default:
        return error.message;
    }
  }
  if (error instanceof NetworkError) return 'Internet aloqasi yo‘q';
  return 'Kutilmagan xatolik';
}
