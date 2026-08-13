import { useCallback } from 'react';
import { create } from 'zustand';

/**
 * Konsol i18n — uz/ru/en.
 *
 * Kichik va qaram-liksiz: lug'at shu faylda, tanlov `localStorage` da saqlanadi.
 * Telegram Login Widget ham shu tildan foydalanadi (`data-lang`), shuning uchun
 * til almashganda widget qayta o'rnatiladi (login ekranidagi effekt buni qiladi).
 */

export type Lang = 'uz' | 'ru' | 'en';

export const LANGS: readonly Lang[] = ['uz', 'ru', 'en'] as const;

const STORAGE_KEY = 'playbron.lang';

const STRINGS = {
  eyebrow: {
    uz: 'Klub konsoli',
    ru: 'Консоль клуба',
    en: 'Club console',
  },
  tagline: {
    uz: 'PlayStation klublari uchun bron, kassa va boshqaruv tizimi. Xodim smenani yuritadi, klub admini butun klubni boshqaradi.',
    ru: 'Система бронирования, кассы и управления для PlayStation-клубов. Сотрудник ведёт смену, админ управляет всем клубом.',
    en: 'Booking, POS and management for PlayStation clubs. Staff run the shift, the club admin runs the whole club.',
  },

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
    uz: 'Konsolga Telegram hisobingiz bilan kirasiz — login va parol kerak emas.',
    ru: 'В консоль входят через аккаунт Telegram — логин и пароль не нужны.',
    en: 'Sign in to the console with your Telegram account — no login or password.',
  },
  signInChecking: {
    uz: 'Kirish tekshirilmoqda…',
    ru: 'Проверяем вход…',
    en: 'Checking sign-in…',
  },
  signInFailed: {
    uz: 'Kirish amalga oshmadi',
    ru: 'Войти не удалось',
    en: 'Sign-in failed',
  },

  widgetLoading: {
    uz: 'Telegram tugmasi yuklanmoqda…',
    ru: 'Кнопка Telegram загружается…',
    en: 'Loading the Telegram button…',
  },
  widgetError: {
    uz: 'Telegram tugmasi yuklanmadi — tarmoqni tekshirib qayta urining',
    ru: 'Кнопка Telegram не загрузилась — проверьте сеть и попробуйте ещё раз',
    en: 'The Telegram button failed to load — check your network and retry',
  },
  widgetHint: {
    uz: 'Tugma ko‘rinmasa, bot domeni sozlanmagan bo‘lishi mumkin',
    ru: 'Если кнопки нет, возможно, у бота не настроен домен',
    en: 'If the button is missing, the bot domain may not be configured',
  },
  retry: { uz: 'Qayta urinish', ru: 'Повторить', en: 'Retry' },

  devEyebrow: {
    uz: 'Lokal ishlab chiqish',
    ru: 'Локальная разработка',
    en: 'Local development',
  },
  devHint: {
    uz: 'Telegram Login Widget localhost da ishlamaydi. Bu tugma faqat dev qurilishida ko‘rinadi.',
    ru: 'Telegram Login Widget не работает на localhost. Кнопка видна только в dev-сборке.',
    en: 'The Telegram Login Widget does not work on localhost. This button only appears in dev builds.',
  },
  devButton: {
    uz: 'Dev sifatida kirish',
    ru: 'Войти как Dev',
    en: 'Sign in as Dev',
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
