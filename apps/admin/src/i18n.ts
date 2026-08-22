import { useCallback } from 'react';
import { create } from 'zustand';

/**
 * Konsol i18n — uz/ru/en.
 *
 * Kichik va qaram-liksiz: lug'at shu faylda, tanlov `localStorage` da saqlanadi.
 */

export type Lang = 'uz' | 'ru' | 'en';

export const LANGS: readonly Lang[] = ['uz', 'ru', 'en'] as const;

const STORAGE_KEY = 'playbron.lang';

const STRINGS = {
  eyebrow: {
    uz: 'Klub ilovasi',
    ru: 'Приложение клуба',
    en: 'Club app',
  },
  tagline: {
    uz: 'PlayStation klublari uchun bron, kassa va boshqaruv tizimi. Xodim smenani yuritadi, klub admini butun klubni boshqaradi.',
    ru: 'Система бронирования, кассы и управления для PlayStation-клубов. Сотрудник ведёт смену, админ управляет всем клубом.',
    en: 'Booking, POS and management for PlayStation clubs. Staff run the shift, the club admin runs the whole club.',
  },

  backToSite: { uz: 'Saytga qaytish', ru: 'На сайт', en: 'Back to site' },

  statusOnline: { uz: 'Tizim onlayn', ru: 'Система онлайн', en: 'System online' },
  statusOffline: { uz: 'Ulanish yo‘q', ru: 'Нет связи', en: 'Offline' },
  authMethodLabel: { uz: 'Kirish: login', ru: 'Вход: логин', en: 'Auth: login' },
  modulesLabel: { uz: 'Modullar', ru: 'Модули', en: 'Modules' },

  featLiveTitle: { uz: 'Live board', ru: 'Live-панель', en: 'Live board' },
  featLiveText: {
    uz: 'Xonalar holati va taymerlar real vaqtda',
    ru: 'Статусы комнат и таймеры в реальном времени',
    en: 'Room status and timers in real time',
  },
  featPosTitle: { uz: 'Kassa', ru: 'Касса', en: 'POS' },
  featPosText: {
    uz: 'Bar buyurtmasi, hisob va chek bir joyda',
    ru: 'Заказы бара, счёт и чек в одном месте',
    en: 'Bar orders, bill and receipt in one place',
  },
  featReportTitle: { uz: 'Hisobot', ru: 'Отчёты', en: 'Reports' },
  featReportText: {
    uz: 'Tushum, xarajat va foyda kesimlari',
    ru: 'Выручка, расходы и прибыль в разрезах',
    en: 'Revenue, expenses and profit breakdowns',
  },

  signInTitle: { uz: 'Kirish', ru: 'Вход', en: 'Sign in' },
  signInHint: {
    uz: 'Login va parolingizni kiriting. Ularni klub egangiz beradi.',
    ru: 'Введите логин и пароль. Их выдаёт владелец клуба.',
    en: 'Enter your login and password. Your club owner issues them.',
  },
  signInFailed: {
    uz: 'Kirish amalga oshmadi',
    ru: 'Войти не удалось',
    en: 'Sign-in failed',
  },

  loginLabel: { uz: 'Login', ru: 'Логин', en: 'Login' },
  passwordLabel: { uz: 'Parol', ru: 'Пароль', en: 'Password' },
  signInButton: { uz: 'Kirish', ru: 'Войти', en: 'Sign in' },
  signingIn: { uz: 'Kirilmoqda…', ru: 'Вход…', en: 'Signing in…' },
  loginPlaceholder: { uz: 'aziz.arena', ru: 'aziz.arena', en: 'aziz.arena' },
  forgot: {
    uz: 'Parolni unutdingizmi? Klub egangizga murojaat qiling.',
    ru: 'Забыли пароль? Обратитесь к владельцу клуба.',
    en: 'Forgot your password? Ask your club owner.',
  },

  changeTitle: { uz: 'Parolni almashtiring', ru: 'Смените пароль', en: 'Change your password' },
  changeHint: {
    uz: 'Bu parolni sizga boshqa odam bergan. Davom etish uchun o‘zingiznikini qo‘ying.',
    ru: 'Этот пароль вам выдал другой человек. Чтобы продолжить, задайте свой.',
    en: 'Someone else set this password. Set your own to continue.',
  },
  currentPassword: { uz: 'Joriy parol', ru: 'Текущий пароль', en: 'Current password' },
  newPassword: { uz: 'Yangi parol', ru: 'Новый пароль', en: 'New password' },
  repeatPassword: {
    uz: 'Yangi parolni takrorlang',
    ru: 'Повторите новый пароль',
    en: 'Repeat new password',
  },
  mismatch: { uz: 'Parollar mos kelmadi', ru: 'Пароли не совпадают', en: 'Passwords do not match' },
  saveButton: { uz: 'Saqlash', ru: 'Сохранить', en: 'Save' },

  // ── Klub egasining ro'yxatdan o'tishi ────────────────────────────────
  signUpLink: {
    uz: 'Klub egasimisiz? Ro‘yxatdan o‘ting',
    ru: 'Владелец клуба? Зарегистрируйтесь',
    en: 'Club owner? Create an account',
  },
  signUpTitle: { uz: 'Ro‘yxatdan o‘tish', ru: 'Регистрация', en: 'Create account' },
  signUpHint: {
    uz: 'Klubingizni qo‘shing. Login va parolni o‘zingiz tanlaysiz.',
    ru: 'Добавьте свой клуб. Логин и пароль вы выбираете сами.',
    en: 'Add your club. You choose your own login and password.',
  },
  signUpButton: { uz: 'Ro‘yxatdan o‘tish', ru: 'Зарегистрироваться', en: 'Create account' },
  signingUp: { uz: 'Yuborilmoqda…', ru: 'Отправка…', en: 'Submitting…' },
  signUpFailed: {
    uz: 'Ro‘yxatdan o‘tish amalga oshmadi',
    ru: 'Регистрация не удалась',
    en: 'Sign-up failed',
  },
  backToSignIn: { uz: 'Kirishga qaytish', ru: 'Вернуться ко входу', en: 'Back to sign in' },
  signedUpNowSignIn: {
    uz: 'Hisobingiz yaratildi. Qayta ro‘yxatdan o‘tmang — shu login bilan kiring.',
    ru: 'Аккаунт создан. Не регистрируйтесь заново — войдите с этим логином.',
    en: 'Your account was created. Do not sign up again — sign in with this login.',
  },
  // Parol almashtirish ekranidagi «yangi parolni takrorlang» bu yerda
  // noto'g'ri o'qiladi — ro'yxatdan o'tishda «yangi» paroli yo'q.
  repeatPasswordPlain: {
    uz: 'Parolni takrorlang',
    ru: 'Повторите пароль',
    en: 'Repeat password',
  },

  nameLabel: { uz: 'Ismingiz', ru: 'Ваше имя', en: 'Your name' },
  namePlaceholder: { uz: 'Aziz', ru: 'Азиз', en: 'Aziz' },
  clubNameLabel: { uz: 'Klub nomi', ru: 'Название клуба', en: 'Club name' },
  clubNamePlaceholder: { uz: 'Neon Arena', ru: 'Neon Arena', en: 'Neon Arena' },
  phoneLabel: { uz: 'Telefon raqami', ru: 'Номер телефона', en: 'Phone number' },
  addressLabel: { uz: 'Manzil', ru: 'Адрес', en: 'Address' },
  addressPlaceholder: {
    uz: 'Toshkent, Chilonzor 12',
    ru: 'Ташкент, Чиланзар 12',
    en: 'Tashkent, Chilanzar 12',
  },
  ownerPasswordHint: {
    uz: 'Kamida 14 belgi.',
    ru: 'Не менее 14 символов.',
    en: 'At least 14 characters.',
  },
  clubVisibleNote: {
    uz: 'Klub nomi, telefon va manzil mijozlarga ko‘rinadi.',
    ru: 'Название клуба, телефон и адрес видны клиентам.',
    en: 'Club name, phone and address are visible to customers.',
  },

  // ── To'lov turi — kassada ham, xarajatda ham bir xil so'z ─────────────
  payMethodCash: { uz: 'Naqd', ru: 'Наличные', en: 'Cash' },
  payMethodTransfer: { uz: 'O‘tkazma', ru: 'Перевод', en: 'Transfer' },
  payMethodNone: { uz: 'Belgilanmagan', ru: 'Не указан', en: 'Not set' },
  payMethodLabel: { uz: 'To‘lov usuli', ru: 'Способ оплаты', en: 'Payment method' },

  // ── Kassa: hisob farqi (chegirma / qarz / choychaqa) ──────────────────
  // Manba: `api/src/playbron/modules/pos/service.py::close_bill()`.
  posReceivedLabel: { uz: 'Olingan summa', ru: 'Полученная сумма', en: 'Amount received' },
  posBillTotal: { uz: 'Jami hisob', ru: 'Итого по счёту', en: 'Bill total' },
  posPaidLabel: { uz: 'Olindi', ru: 'Получено', en: 'Received' },
  posAmountInvalid: {
    uz: 'Summani butun so‘mda kiriting',
    ru: 'Введите сумму целым числом сумов',
    en: 'Enter the amount in whole so‘m',
  },
  posShortfallLabel: { uz: 'Kam to‘landi', ru: 'Недоплата', en: 'Short' },
  posOverpayLabel: { uz: 'Ortiqcha to‘landi', ru: 'Переплата', en: 'Overpaid' },
  posShortfallReason: {
    uz: 'Kam to‘langan summaning sababi',
    ru: 'Причина недоплаты',
    en: 'Reason for the shortfall',
  },
  posOverpayReason: {
    uz: 'Ortiqcha summaning sababi',
    ru: 'Причина переплаты',
    en: 'Reason for the overpayment',
  },
  posReasonDiscount: { uz: 'Chegirma', ru: 'Скидка', en: 'Discount' },
  posReasonDebt: { uz: 'Qarz', ru: 'Долг', en: 'Debt' },
  posReasonTip: { uz: 'Choychaqa', ru: 'Чаевые', en: 'Tip' },
  posReasonRequired: {
    uz: 'Farq sababini tanlang',
    ru: 'Выберите причину расхождения',
    en: 'Pick a reason for the difference',
  },
  posShiftRequired: {
    uz: 'Naqd to‘lovni qabul qilish uchun avval smenani oching',
    ru: 'Чтобы принять наличные, сначала откройте смену',
    en: 'Open a shift before you take cash',
  },
  posBillChanged: {
    uz: 'Hisob o‘zgardi — olingan summani qayta tekshiring',
    ru: 'Счёт изменился — проверьте полученную сумму',
    en: 'The bill changed — check the received amount',
  },

  // ── Xarajat: naqd pul qaysi smenadan chiqadi ─────────────────────────
  // Manba: `api/src/playbron/modules/finance/service.py::create_expense()`.
  expenseShiftLabel: { uz: 'Qaysi smenadan', ru: 'Из какой смены', en: 'From which shift' },
  expenseShiftMine: { uz: 'meniki', ru: 'моя', en: 'mine' },
  expenseShiftUnset: { uz: 'Tanlanmagan', ru: 'Не выбрана', en: 'Not selected' },
  expenseShiftPick: {
    uz: 'Naqd xarajat qaysi smenadan chiqqanini tanlang',
    ru: 'Выберите, из какой смены взяты наличные',
    en: 'Pick the shift the cash comes from',
  },
  expenseNoOpenShift: {
    uz: 'Ochiq smena yo‘q — naqd xarajat uchun avval smena ochilsin',
    ru: 'Нет открытой смены — для наличного расхода сначала откройте смену',
    en: 'No open shift — open one before recording a cash expense',
  },
  expenseCashNote: {
    uz: 'Naqd xarajat kassadan chiqadi va smena hisobidan ayiriladi',
    ru: 'Наличный расход выходит из кассы и вычитается из смены',
    en: 'A cash expense leaves the till and is deducted from the shift',
  },
  expenseMethodLocked: {
    uz: 'To‘lov usuli faqat yozuv qo‘shilayotganda tanlanadi',
    ru: 'Способ оплаты выбирается только при создании записи',
    en: 'The payment method is set only when the record is created',
  },

  // ── Narxlar: xonalar va tariflar ─────────────────────────────────────
  // `screens/admin/pricing.tsx`. Ekranda matn literali yo'q (`CLAUDE.md`,
  // §Frontend) — hammasi shu yerdan.
  pricingNav: { uz: 'Narxlar', ru: 'Тарифы', en: 'Pricing' },
  pricingTitle: { uz: 'Narxlar', ru: 'Тарифы', en: 'Pricing' },
  pricingMeta: {
    uz: 'Xonalar va soatlik tariflar',
    ru: 'Комнаты и почасовые тарифы',
    en: 'Rooms and hourly rates',
  },
  pricingNoClub: { uz: 'Klub tanlanmagan', ru: 'Клуб не выбран', en: 'No club selected' },
  pricingLoading: { uz: 'Yuklanmoqda…', ru: 'Загрузка…', en: 'Loading…' },

  roomsPanel: { uz: 'Xonalar', ru: 'Комнаты', en: 'Rooms' },
  roomsEmpty: { uz: 'Xona qo‘shilmagan', ru: 'Комнат нет', en: 'No rooms yet' },
  roomAdd: { uz: 'Xona qo‘shish', ru: 'Добавить комнату', en: 'Add room' },
  roomFormNew: { uz: 'Xona qo‘shish', ru: 'Новая комната', en: 'New room' },
  roomFormEdit: { uz: 'Xonani tahrirlash', ru: 'Изменить комнату', en: 'Edit room' },
  roomSaved: { uz: 'Xona saqlandi', ru: 'Комната сохранена', en: 'Room saved' },

  tariffsPanel: { uz: 'Tariflar', ru: 'Тарифы', en: 'Tariffs' },
  tariffsEmpty: { uz: 'Tarif qo‘shilmagan', ru: 'Тарифов нет', en: 'No tariffs yet' },
  tariffAdd: { uz: 'Tarif qo‘shish', ru: 'Добавить тариф', en: 'Add tariff' },
  tariffFormNew: { uz: 'Tarif qo‘shish', ru: 'Новый тариф', en: 'New tariff' },
  tariffFormEdit: { uz: 'Tarifni tahrirlash', ru: 'Изменить тариф', en: 'Edit tariff' },
  tariffSaved: { uz: 'Tarif saqlandi', ru: 'Тариф сохранён', en: 'Tariff saved' },
  tariffsHint: {
    uz: 'Tarif bo‘lmasa narx xonaning o‘z qiymatidan olinadi. Vaqti kesishgan tariflardan ustunligi yuqorisi qo‘llanadi.',
    ru: 'Без тарифов цена берётся из самой комнаты. Если окна пересекаются, применяется тариф с большим приоритетом.',
    en: 'With no tariffs the price falls back to the station rate. Where windows overlap, the higher priority wins.',
  },

  colRoom: { uz: 'Xona', ru: 'Комната', en: 'Room' },
  colKind: { uz: 'Turi', ru: 'Тип', en: 'Kind' },
  colOrder: { uz: 'Tartib', ru: 'Порядок', en: 'Order' },
  colState: { uz: 'Holat', ru: 'Статус', en: 'Status' },
  colTariff: { uz: 'Tarif', ru: 'Тариф', en: 'Tariff' },
  colDays: { uz: 'Kunlar', ru: 'Дни', en: 'Days' },
  colWindow: { uz: 'Oyna', ru: 'Окно', en: 'Window' },
  colPerHour: { uz: 'Soatiga', ru: 'За час', en: 'Per hour' },
  colPriority: { uz: 'Ustunlik', ru: 'Приоритет', en: 'Priority' },
  colScope: { uz: 'Qamrov', ru: 'Область', en: 'Scope' },

  stateActive: { uz: 'Faol', ru: 'Активен', en: 'Active' },
  stateArchived: { uz: 'Arxiv', ru: 'Архив', en: 'Archived' },
  countActive: { uz: 'Faol', ru: 'Активные', en: 'Active' },
  unitPieces: { uz: 'ta', ru: 'шт', en: 'pcs' },

  fieldName: { uz: 'Nomi', ru: 'Название', en: 'Name' },
  fieldKind: { uz: 'Turi', ru: 'Тип', en: 'Kind' },
  fieldOrder: { uz: 'Tartib', ru: 'Порядок', en: 'Sort order' },
  fieldDays: { uz: 'Hafta kunlari', ru: 'Дни недели', en: 'Days of week' },
  fieldFrom: { uz: 'Boshlanish (SS:DD)', ru: 'Начало (ЧЧ:ММ)', en: 'From (HH:MM)' },
  fieldTo: { uz: 'Tugash (SS:DD)', ru: 'Окончание (ЧЧ:ММ)', en: 'To (HH:MM)' },
  fieldPerHour: { uz: 'Soatlik narx', ru: 'Цена за час', en: 'Price per hour' },
  fieldPriority: { uz: 'Ustunlik', ru: 'Приоритет', en: 'Priority' },
  fieldConsole: { uz: 'Konsol', ru: 'Консоль', en: 'Console' },
  fieldRoomKind: { uz: 'Xona turi', ru: 'Тип комнаты', en: 'Room kind' },
  scopeAny: { uz: 'Har qanday', ru: 'Любой', en: 'Any' },
  overnightNote: {
    uz: 'Yarim tundan o‘tsa tugash vaqti 24:00 dan katta yoziladi — 02:00 uchun 26:00.',
    ru: 'Если окно переходит за полночь, окончание пишется больше 24:00 — для 02:00 это 26:00.',
    en: 'For a window crossing midnight write the end past 24:00 — 02:00 becomes 26:00.',
  },

  dayMon: { uz: 'Du', ru: 'Пн', en: 'Mon' },
  dayTue: { uz: 'Se', ru: 'Вт', en: 'Tue' },
  dayWed: { uz: 'Chu', ru: 'Ср', en: 'Wed' },
  dayThu: { uz: 'Pa', ru: 'Чт', en: 'Thu' },
  dayFri: { uz: 'Ju', ru: 'Пт', en: 'Fri' },
  daySat: { uz: 'Sh', ru: 'Сб', en: 'Sat' },
  daySun: { uz: 'Ya', ru: 'Вс', en: 'Sun' },
  daysEvery: { uz: 'Har kuni', ru: 'Каждый день', en: 'Every day' },
  daysWorkdays: { uz: 'Ish kunlari', ru: 'Будни', en: 'Weekdays' },
  daysWeekend: { uz: 'Dam olish', ru: 'Выходные', en: 'Weekend' },

  actionCancel: { uz: 'Bekor', ru: 'Отмена', en: 'Cancel' },
  actionSaving: { uz: 'Saqlanmoqda…', ru: 'Сохранение…', en: 'Saving…' },
  actionArchive: { uz: 'Arxivlash', ru: 'В архив', en: 'Archive' },
  actionRestore: { uz: 'Qaytarish', ru: 'Вернуть', en: 'Restore' },
  rowArchived: { uz: 'Arxivlandi', ru: 'Отправлено в архив', en: 'Archived' },
  rowRestored: { uz: 'Qayta faollashtirildi', ru: 'Снова активен', en: 'Restored' },

  errNameRequired: { uz: 'Nomini kiriting', ru: 'Введите название', en: 'Enter a name' },
  errPricePositive: {
    uz: 'Narx musbat butun son bo‘lsin',
    ru: 'Цена — целое положительное число',
    en: 'Price must be a positive whole number',
  },
  errDaysRequired: {
    uz: 'Kamida bitta kun tanlang',
    ru: 'Выберите хотя бы один день',
    en: 'Pick at least one day',
  },
  errTimeFormat: {
    uz: 'Vaqt SS:DD ko‘rinishida bo‘lsin',
    ru: 'Время в формате ЧЧ:ММ',
    en: 'Time must be HH:MM',
  },
  errWindowOrder: {
    uz: 'Tugash vaqti boshlanishdan keyin bo‘lsin',
    ru: 'Окончание должно быть позже начала',
    en: 'End must be after the start',
  },
  errStartWithinDay: {
    uz: 'Boshlanish vaqti bir sutka ichida bo‘lsin',
    ru: 'Начало должно быть в пределах суток',
    en: 'The start must be within one day',
  },
  errWholeNumber: {
    uz: 'Butun va manfiy bo‘lmagan son bo‘lsin',
    ru: 'Целое неотрицательное число',
    en: 'Must be a whole, non-negative number',
  },

  // ── Offline sinxronizatsiya — `offline/` moduli, audit §25 ────────────
  offlineSyncing: { uz: 'Yuborilmoqda', ru: 'Отправка', en: 'Syncing' },
  offlinePendingLabel: { uz: 'Navbatda', ru: 'В очереди', en: 'Pending' },
  offlineFailedLabel: { uz: 'Xato', ru: 'Ошибка', en: 'Failed' },
  offlineConflictLabel: { uz: 'Ziddiyat', ru: 'Конфликт', en: 'Conflict' },
  offlineDrawerTitle: { uz: 'Sinxronizatsiya', ru: 'Синхронизация', en: 'Sync' },
  offlineNoItems: { uz: 'Navbat bo‘sh', ru: 'Очередь пуста', en: 'Queue is empty' },
  offlineDismiss: { uz: 'Yopish', ru: 'Закрыть', en: 'Dismiss' },
  offlineQueuedToast: {
    uz: 'Lokal saqlandi — internet qaytganda yuboriladi',
    ru: 'Сохранено локально — отправится при восстановлении связи',
    en: 'Saved locally — will send once connection returns',
  },
  offlineConflictNote: {
    uz: 'Boshqa xodim shu amalni allaqachon bajargan bo‘lishi mumkin. Ekranni yangilang va kerak bo‘lsa qaytadan bajaring.',
    ru: 'Другой сотрудник мог уже выполнить это действие. Обновите экран и при необходимости повторите.',
    en: 'Another staff member may have already done this. Refresh the screen and redo it if needed.',
  },
} as const satisfies Record<string, Record<Lang, string>>;

export type MsgKey = keyof typeof STRINGS;

function isLang(value: string | null | undefined): value is Lang {
  return value === 'uz' || value === 'ru' || value === 'en';
}

/**
 * `?lang=` → saqlangan tanlov → brauzer tili → uz.
 *
 * `?lang=` ENG YUQORI ustuvorlikda: `playbron.uz` va `app.playbron.uz` —
 * turli origin, `localStorage` ular orasida bo'lishilmaydi. Landingda
 * tanlangan til shu query orqali keladi (`config.ts::consoleWithLang`),
 * aks holda ilova brauzer tiliga (odatda tizim tiliga) qaytib, foydalanuvchi
 * ro'yxatdan o'tish o'rtasida til almashib qolgandek his qilardi.
 */
function detect(): Lang {
  try {
    const fromLink = new URLSearchParams(window.location.search).get('lang');
    if (isLang(fromLink)) {
      // Saqlanadi: `?lang=` faqat BIRINCHI yuklanishda keladi, keyingi
      // navigatsiya (masalan parol almashtirishdan keyin) query'siz bo'ladi
      try {
        localStorage.setItem(STORAGE_KEY, fromLink);
      } catch {
        // Saqlab bo'lmasa ham joriy sessiya uchun ishlayveradi
      }
      return fromLink;
    }
  } catch {
    // URL o'qib bo'lmasa keyingi manbaga o'tamiz
  }
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (isLang(stored)) return stored;
  } catch {
    // localStorage yopiq (private mode) — brauzer tiliga o'tamiz
  }
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
        // Saqlab bo'lmasa ham til sessiya davomida ishlayveradi
      }
      document.documentElement.lang = lang;
      set({ lang });
    },
  };
});

/** Joriy til uchun tarjima funksiyasi. Til almashsa komponent qayta chiziladi. */
export function useT(): (key: MsgKey) => string {
  const lang = useI18n((state) => state.lang);
  return useCallback((key: MsgKey) => STRINGS[key][lang], [lang]);
}
