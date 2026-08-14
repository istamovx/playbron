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
} as const satisfies Record<string, Record<Lang, string>>;

export type MsgKey = keyof typeof STRINGS;

function isLang(value: string | null | undefined): value is Lang {
  return value === 'uz' || value === 'ru' || value === 'en';
}

/** Saqlangan tanlov → brauzer tili → uz. */
function detect(): Lang {
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
