import { useCallback } from 'react';
import { create } from 'zustand';

import { webApp } from './lib/telegram';

/**
 * Mijoz Mini App i18n — uz/ru/en.
 *
 * Konsoldagi naqshning o'zi (`apps/admin/src/i18n.ts`): lug'at shu faylda,
 * tanlov `localStorage` da. Ikki farq bor:
 *   1. Til birinchi navbatda TELEGRAM foydalanuvchisidan olinadi
 *      (`initDataUnsafe.user.language_code`) — Mini App'da bu brauzer
 *      tilidan ishonchliroq manba.
 *   2. `t()` `{name}` o'rinbosarlarini qabul qiladi: "2 soatga bo'sh xona
 *      yo'q" kabi jumlalarni bo'laklab yopishtirish rus tilida noto'g'ri
 *      tartib berardi.
 */

export type Lang = 'uz' | 'ru' | 'en';

export const LANGS: readonly { id: Lang; label: string }[] = [
  { id: 'uz', label: 'O‘zbek' },
  { id: 'ru', label: 'Русский' },
  { id: 'en', label: 'English' },
] as const;

/** `Intl` uchun to'liq lokal — hafta kuni va oy nomlari shundan keladi. */
export const LOCALE: Record<Lang, string> = { uz: 'uz-UZ', ru: 'ru-RU', en: 'en-GB' };

const STORAGE_KEY = 'playbron.lang';

const STRINGS = {
  // ── Umumiy ────────────────────────────────────────────────────────────
  loading: { uz: 'Yuklanmoqda…', ru: 'Загрузка…', en: 'Loading…' },
  retry: { uz: 'Qayta urinish', ru: 'Повторить', en: 'Retry' },
  back: { uz: 'Orqaga', ru: 'Назад', en: 'Back' },
  connectFailed: {
    uz: 'Serverga ulanib bo‘lmadi',
    ru: 'Не удалось подключиться к серверу',
    en: 'Could not reach the server',
  },
  customer: { uz: 'Mijoz', ru: 'Клиент', en: 'Customer' },
  hoursUnit: { uz: '{hours} soat', ru: '{hours} ч', en: '{hours} h' },
  perHour: { uz: '{sum} so‘m/soat', ru: '{sum} сум/час', en: '{sum} UZS/hour' },
  openInMaps: { uz: 'Xaritada ochish', ru: 'Открыть на карте', en: 'Open in maps' },

  // ── Navigatsiya ───────────────────────────────────────────────────────
  tabClubs: { uz: 'Klublar', ru: 'Клубы', en: 'Clubs' },
  tabSession: { uz: 'Seans', ru: 'Сеанс', en: 'Session' },
  tabBookings: { uz: 'Bronlar', ru: 'Брони', en: 'Bookings' },
  tabProfile: { uz: 'Profil', ru: 'Профиль', en: 'Profile' },

  titleClubs: { uz: 'Klublar', ru: 'Клубы', en: 'Clubs' },
  titleClub: { uz: 'Klub', ru: 'Клуб', en: 'Club' },
  titleSlots: { uz: 'Vaqt tanlash', ru: 'Выбор времени', en: 'Pick a time' },
  titleConfirm: { uz: 'Tasdiqlash', ru: 'Подтверждение', en: 'Confirm' },
  titleSent: { uz: 'Bron yuborildi', ru: 'Бронь отправлена', en: 'Booking sent' },
  titleSession: { uz: 'Aktiv seans', ru: 'Активный сеанс', en: 'Active session' },
  titleBookings: { uz: 'Bronlarim', ru: 'Мои брони', en: 'My bookings' },
  titleProfile: { uz: 'Profil', ru: 'Профиль', en: 'Profile' },

  // ── Klublar ro'yxati ──────────────────────────────────────────────────
  clubsEmptyTitle: {
    uz: 'Hozircha faol klub yo‘q',
    ru: 'Пока нет активных клубов',
    en: 'No active clubs yet',
  },
  clubsEmptyHint: {
    uz: 'Klub qo‘shilgach shu yerda ko‘rinadi.',
    ru: 'Как только клуб появится, он будет здесь.',
    en: 'Clubs appear here as soon as they are added.',
  },
  addressMissing: { uz: 'Manzil ko‘rsatilmagan', ru: 'Адрес не указан', en: 'No address given' },

  // ── Klub sahifasi ─────────────────────────────────────────────────────
  clubNotSelected: { uz: 'Klub tanlanmagan', ru: 'Клуб не выбран', en: 'No club selected' },
  roomsTitle: { uz: 'Xonalar va narxlar', ru: 'Комнаты и цены', en: 'Rooms and rates' },
  roomsEmptyTitle: { uz: 'Xona qo‘shilmagan', ru: 'Комнаты не добавлены', en: 'No rooms yet' },
  roomsEmptyHint: {
    uz: 'Klub xonalarni qo‘shgach bron qilish ochiladi.',
    ru: 'Бронирование откроется, когда клуб добавит комнаты.',
    en: 'Booking opens once the club adds rooms.',
  },
  roomsCount: { uz: '{count} xona', ru: '{count} комн.', en: '{count} rooms' },
  freeCount: { uz: '{count} bo‘sh', ru: '{count} свободно', en: '{count} free' },
  allBusy: { uz: 'Band', ru: 'Занято', en: 'Busy' },
  bookAction: { uz: 'Bron qilish', ru: 'Забронировать', en: 'Book' },

  // ── Slot tanlash ──────────────────────────────────────────────────────
  labelDate: { uz: 'Sana', ru: 'Дата', en: 'Date' },
  labelRoomType: { uz: 'Xona turi', ru: 'Тип комнаты', en: 'Room type' },
  labelConsole: { uz: 'Konsol', ru: 'Консоль', en: 'Console' },
  labelDuration: { uz: 'Davomiylik', ru: 'Длительность', en: 'Duration' },
  filterAny: { uz: 'Barchasi', ru: 'Все', en: 'All' },
  durationLimit: {
    uz: 'Bu vaqtdan {hours} soatgacha',
    ru: 'С этого времени до {hours} ч',
    en: 'Up to {hours} h from this time',
  },
  freeTimeTitle: { uz: 'Bo‘sh vaqt', ru: 'Свободное время', en: 'Free time' },
  freeTimeEmptyTitle: { uz: 'Bo‘sh vaqt yo‘q', ru: 'Свободного времени нет', en: 'No free time' },
  freeTimeEmptyHint: {
    uz: 'Boshqa sana yoki xona turini tanlang.',
    ru: 'Выберите другую дату или тип комнаты.',
    en: 'Pick another date or room type.',
  },
  freeRoomsTitle: {
    uz: 'Bo‘sh xonalar · {from} → {to}',
    ru: 'Свободные комнаты · {from} → {to}',
    en: 'Free rooms · {from} → {to}',
  },
  freeRoomsEmptyTitle: { uz: 'Bo‘sh xona yo‘q', ru: 'Свободных комнат нет', en: 'No free rooms' },
  freeRoomsEmptyHint: {
    uz: '{hours} soatga joy topilmadi — davomiylikni qisqartiring.',
    ru: 'На {hours} ч мест нет — сократите длительность.',
    en: 'Nothing fits {hours} h — shorten the duration.',
  },
  slotRooms: { uz: '{count} xona', ru: '{count} комн.', en: '{count} rooms' },
  slotFits: { uz: '{hours} soat', ru: '{hours} ч', en: '{hours} h' },
  slotBusy: { uz: 'band', ru: 'занято', en: 'busy' },
  consoleRequired: { uz: 'Tanlanishi shart', ru: 'Обязательно', en: 'Required' },
  today: { uz: 'Bugun', ru: 'Сегодня', en: 'Today' },
  tomorrow: { uz: 'Ertaga', ru: 'Завтра', en: 'Tomorrow' },

  // ── Tasdiqlash ────────────────────────────────────────────────────────
  confirmTitle: { uz: 'Bron xulosasi', ru: 'Сводка брони', en: 'Booking summary' },
  fieldClub: { uz: 'Klub', ru: 'Клуб', en: 'Club' },
  fieldRoom: { uz: 'Xona', ru: 'Комната', en: 'Room' },
  fieldDate: { uz: 'Sana', ru: 'Дата', en: 'Date' },
  fieldTime: { uz: 'Vaqt', ru: 'Время', en: 'Time' },
  fieldTotal: { uz: 'Jami', ru: 'Итого', en: 'Total' },
  quoteLoading: { uz: 'Hisoblanmoqda…', ru: 'Расчёт…', en: 'Calculating…' },
  fieldRate: { uz: 'Tarif', ru: 'Тариф', en: 'Rate' },
  // Yakuniy summani SERVER hisoblaydi (`modules/bookings/pricing.py`) —
  // tarif kun ichida o'zgarishi mumkin, shuning uchun ilova `rate × soat`
  // ni umumiy summa deb ko'rsatmaydi.
  finalAmountNote: {
    uz: 'Yakuniy summa klub tarifi bo‘yicha hisoblanadi',
    ru: 'Итоговая сумма считается по тарифу клуба',
    en: 'The final amount is calculated from the club tariff',
  },
  payAtClub: { uz: 'To‘lov klubda, kelganingizda', ru: 'Оплата в клубе, при визите', en: 'You pay at the club' },
  payAtClubHint: {
    uz: 'Bron to‘lovsiz yuboriladi',
    ru: 'Бронь отправляется без оплаты',
    en: 'The booking is sent without payment',
  },
  staffConfirms: { uz: 'Yuborilgach xodim tasdiqlaydi', ru: 'После отправки бронь подтверждает сотрудник', en: 'Staff confirm it after you send' },
  botNotice: { uz: 'Tasdiqlangach botda xabar keladi', ru: 'После подтверждения придёт сообщение в бот', en: 'The bot messages you once confirmed' },
  roomNotSelected: {
    uz: 'Xona tanlanmagan — orqaga qaytib tanlang.',
    ru: 'Комната не выбрана — вернитесь и выберите.',
    en: 'No room selected — go back and pick one.',
  },
  submitBooking: { uz: 'Bronni yuborish', ru: 'Отправить бронь', en: 'Send booking' },
  submitting: { uz: 'Yuborilmoqda…', ru: 'Отправка…', en: 'Sending…' },
  pickFreeTime: { uz: 'Bo‘sh vaqtni tanlang', ru: 'Выберите свободное время', en: 'Pick a free slot' },
  pickConsole: { uz: 'Konsolni tanlang', ru: 'Выберите консоль', en: 'Pick a console' },

  // ── Yuborildi ─────────────────────────────────────────────────────────
  sentTitle: { uz: 'Bron yuborildi', ru: 'Бронь отправлена', en: 'Booking sent' },
  sentHint: {
    uz: 'Xodim tasdiqlagach botga xabar keladi',
    ru: 'Когда сотрудник подтвердит, придёт сообщение в бот',
    en: 'The bot messages you once staff confirm it',
  },
  sentStatus: { uz: 'Holat: kutilmoqda', ru: 'Статус: ожидание', en: 'Status: pending' },
  sentWhere: {
    uz: 'Tasdiqlangach «Bronlarim» da ko‘rinadi',
    ru: 'После подтверждения появится в «Моих бронях»',
    en: 'It shows up under “My bookings” once confirmed',
  },
  goBookings: { uz: 'Bronlarim', ru: 'Мои брони', en: 'My bookings' },

  // ── Aktiv seans ───────────────────────────────────────────────────────
  remainingLabel: { uz: 'Qolgan vaqt', ru: 'Осталось', en: 'Time left' },
  startsInLabel: { uz: 'Boshlanishiga', ru: 'До начала', en: 'Starts in' },
  sessionEmptyTitle: { uz: 'Aktiv seans yo‘q', ru: 'Активного сеанса нет', en: 'No active session' },
  sessionEmptyHint: {
    uz: 'Bron boshlangach taymer shu yerda yuradi.',
    ru: 'Таймер появится здесь, когда начнётся бронь.',
    en: 'The timer appears here once your booking starts.',
  },
  nextBookingTitle: { uz: 'Keyingi bron', ru: 'Следующая бронь', en: 'Next booking' },
  sessionGraceNotice: {
    uz: 'Vaqt tugadi. Xona {minutes} daqiqa saqlanadi — xodimga murojaat qiling.',
    ru: 'Время вышло. Комната держится ещё {minutes} мин — обратитесь к сотруднику.',
    en: 'Time is up. The room is held for {minutes} min — talk to the staff.',
  },
  sessionSoonNotice: {
    uz: 'Seans tugashiga {minutes} daqiqa qoldi.',
    ru: 'До конца сеанса {minutes} мин.',
    en: '{minutes} min left in the session.',
  },
  billAtDeskNote: {
    uz: 'Yakuniy hisob (o‘yin + bar) klub kassasida yopiladi',
    ru: 'Итоговый счёт (игра + бар) закрывается на кассе клуба',
    en: 'The final bill (play + bar) is settled at the club desk',
  },

  // ── Bronlarim ─────────────────────────────────────────────────────────
  bookingsActive: { uz: 'Aktiv va kutilayotgan', ru: 'Активные и предстоящие', en: 'Active and upcoming' },
  bookingsHistory: { uz: 'Tarix', ru: 'История', en: 'History' },
  bookingsEmptyTitle: { uz: 'Hali bron yo‘q', ru: 'Броней пока нет', en: 'No bookings yet' },
  bookingsEmptyHint: {
    uz: 'Klub tanlab birinchi bronni qiling.',
    ru: 'Выберите клуб и создайте первую бронь.',
    en: 'Pick a club and make your first booking.',
  },
  bookingsActiveEmptyTitle: { uz: 'Aktiv bron yo‘q', ru: 'Активных броней нет', en: 'No active bookings' },
  bookingsActiveEmptyHint: {
    uz: 'Yangi bron qilsangiz shu yerda turadi.',
    ru: 'Новая бронь появится здесь.',
    en: 'A new booking will show up here.',
  },
  bookingsHistoryEmptyTitle: { uz: 'Tarix bo‘sh', ru: 'История пуста', en: 'History is empty' },
  bookingsHistoryEmptyHint: {
    uz: 'Tugagan va bekor qilingan bronlar shu yerga o‘tadi.',
    ru: 'Завершённые и отменённые брони уходят сюда.',
    en: 'Finished and cancelled bookings move here.',
  },
  statusPending: { uz: 'Kutilmoqda', ru: 'Ожидает', en: 'Pending' },
  statusConfirmed: { uz: 'Tasdiqlangan', ru: 'Подтверждена', en: 'Confirmed' },
  statusCancelled: { uz: 'Bekor qilingan', ru: 'Отменена', en: 'Cancelled' },
  statusDone: { uz: 'Yakunlangan', ru: 'Завершена', en: 'Finished' },
  statusExpired: { uz: 'O‘tib ketgan', ru: 'Просрочена', en: 'Expired' },
  statusLive: { uz: 'Ichkarida', ru: 'Идёт', en: 'In progress' },
  newBooking: { uz: 'Yangi bron', ru: 'Новая бронь', en: 'New booking' },

  // ── Profil ────────────────────────────────────────────────────────────
  sectionPersonal: { uz: 'Shaxsiy ma’lumotlar', ru: 'Личные данные', en: 'Personal details' },
  sectionNotify: { uz: 'Bildirishnomalar', ru: 'Уведомления', en: 'Notifications' },
  sectionInterface: { uz: 'Interfeys sozlamalari', ru: 'Настройки интерфейса', en: 'Interface settings' },
  sectionExit: { uz: 'Chiqish', ru: 'Выйти', en: 'Sign out' },
  fieldName: { uz: 'Ism', ru: 'Имя', en: 'Name' },
  fieldPhone: { uz: 'Telefon', ru: 'Телефон', en: 'Phone' },
  phoneMissing: { uz: 'Botda ulashilmagan', ru: 'Не передан в боте', en: 'Not shared in the bot' },
  // Ism va telefonni Mini App'dan o'zgartirib bo'lmaydi: `PATCH /me`
  // endpoint'i YO'Q, ular botdagi `requestContact` orqali BIR MARTA
  // olinadi (DCR-002). Avval bu yerda forma turardi va "Saqlandi" deb
  // yozardi — hech qayerga yuborilmasdi.
  personalNote: {
    uz: 'Ism va telefon Telegram orqali olinadi. O‘zgartirish uchun botga /start yozing.',
    ru: 'Имя и телефон берутся из Telegram. Чтобы изменить, отправьте боту /start.',
    en: 'Name and phone come from Telegram. Send /start to the bot to change them.',
  },
  since: { uz: '{date} dan beri', ru: 'с {date}', en: 'since {date}' },
  statSessions: { uz: 'Seanslar', ru: 'Сеансы', en: 'Sessions' },
  statHours: { uz: 'O‘ynagan soat', ru: 'Часов игры', en: 'Hours played' },
  statUpcoming: { uz: 'Kutilmoqda', ru: 'Предстоит', en: 'Upcoming' },
  statCancelled: { uz: 'Bekor qilingan', ru: 'Отменено', en: 'Cancelled' },
  statsEmpty: {
    uz: 'Ko‘rsatkichlar bron qilgandan keyin paydo bo‘ladi.',
    ru: 'Показатели появятся после первой брони.',
    en: 'Stats appear after your first booking.',
  },
  toggleAlerts: { uz: 'Seans ogohlantirishlari', ru: 'Предупреждения о сеансе', en: 'Session alerts' },
  toggleAlertsHint: {
    uz: '{minutes} daqiqa qolganda ilovada ogohlantiradi',
    ru: 'Предупреждает в приложении за {minutes} мин',
    en: 'Warns in the app {minutes} min before the end',
  },
  toggleHaptics: { uz: 'Haptik javob', ru: 'Вибро-отклик', en: 'Haptics' },
  toggleHapticsHint: {
    uz: 'Ogohlantirishlarda tebranish',
    ru: 'Вибрация при предупреждениях',
    en: 'Vibrates on alerts',
  },
  labelLanguage: { uz: 'Til', ru: 'Язык', en: 'Language' },
  themeNote: { uz: 'Mavzu — doim qorong‘i', ru: 'Тема — всегда тёмная', en: 'Theme is always dark' },
  themeNoteHint: {
    uz: 'Telegram temasidan mustaqil',
    ru: 'Не зависит от темы Telegram',
    en: 'Independent of the Telegram theme',
  },
  noShowNote: {
    uz: 'Kechikish limiti {minutes} daqiqa',
    ru: 'Лимит опоздания — {minutes} мин',
    en: 'Late arrival limit is {minutes} min',
  },
  noShowHint: {
    uz: 'Kelmasangiz bron bekor qilinishi mumkin',
    ru: 'При неявке бронь могут отменить',
    en: 'No-shows may have the booking cancelled',
  },
} as const;

export type MsgKey = keyof typeof STRINGS;

function isLang(value: string | null | undefined): value is Lang {
  return value === 'uz' || value === 'ru' || value === 'en';
}

/** Saqlangan tanlov → Telegram foydalanuvchisining tili → brauzer tili → uz. */
function detect(): Lang {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (isLang(stored)) return stored;
  } catch {
    // `localStorage` yopiq (private mode) — keyingi manbaga o'tamiz
  }

  const telegram = webApp()?.initDataUnsafe?.user?.language_code?.slice(0, 2).toLowerCase();
  if (isLang(telegram)) return telegram;

  const nav = navigator.language.slice(0, 2).toLowerCase();
  return isLang(nav) ? nav : 'uz';
}

interface I18nState {
  lang: Lang;
  setLang: (lang: Lang) => void;
}

export const useI18n = create<I18nState>()((set) => {
  const initial = detect();
  document.documentElement.lang = initial;

  return {
    lang: initial,
    setLang: (lang) => {
      try {
        localStorage.setItem(STORAGE_KEY, lang);
      } catch {
        // Saqlab bo'lmasa ham til shu sessiya davomida ishlayveradi
      }
      document.documentElement.lang = lang;
      set({ lang });
    },
  };
});

/** `{name}` o'rinbosarlarini to'ldiradi — bo'lak-bo'lak yopishtirishdan farqli
 * o'laroq so'z tartibi har tilda o'z lug'atida qoladi. */
function fill(template: string, vars?: Record<string, string | number>): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (match: string, name: string) =>
    name in vars ? String(vars[name]) : match,
  );
}

export type Translate = (key: MsgKey, vars?: Record<string, string | number>) => string;

/** Joriy til uchun tarjima funksiyasi. Til almashsa komponent qayta chiziladi. */
export function useT(): Translate {
  const lang = useI18n((state) => state.lang);
  return useCallback<Translate>((key, vars) => fill(STRINGS[key][lang], vars), [lang]);
}

/** `Intl` chaqiruvlari uchun joriy lokal. */
export function useLocale(): string {
  return LOCALE[useI18n((state) => state.lang)];
}
