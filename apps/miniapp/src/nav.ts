import type { MsgKey } from './i18n';

/**
 * Ekranlar va pastki tab paneli.
 *
 * Avval `mock/data.ts` da edi — sarlavhalar qotirilgan uzbekcha matn bilan
 * ("Aktiv seans · Neon Arena · 1-xona" kabi soxta subtitrlar bilan birga).
 * Endi bu yerda faqat TUZILMA turadi, ko'rinadigan matn i18n kalitlari orqali
 * keladi.
 */

export type ScreenId =
  | 'clubs'
  | 'club'
  | 'slots'
  | 'confirm'
  | 'sent'
  | 'session'
  | 'bookings'
  | 'profile';

/** Ekran sarlavhasining i18n kaliti. */
export const TITLE_KEY: Record<ScreenId, MsgKey> = {
  clubs: 'titleClubs',
  club: 'titleClub',
  slots: 'titleSlots',
  confirm: 'titleConfirm',
  sent: 'titleSent',
  session: 'titleSession',
  bookings: 'titleBookings',
  profile: 'titleProfile',
};

export const TABS: { id: ScreenId; icon: string; label: MsgKey }[] = [
  { id: 'clubs', icon: 'storefront', label: 'tabClubs' },
  { id: 'session', icon: 'sports_esports', label: 'tabSession' },
  { id: 'bookings', icon: 'event_note', label: 'tabBookings' },
  { id: 'profile', icon: 'person', label: 'tabProfile' },
];

/** Ichki ekran qaysi tabga tegishli. */
export const TAB_ROOT: Partial<Record<ScreenId, ScreenId>> = {
  club: 'clubs',
  slots: 'clubs',
  confirm: 'clubs',
  sent: 'bookings',
};
