/**
 * Telegram OAuth — custom tugma uchun.
 *
 * Rasmiy iframe tugmasi (`data-telegram-login`) tashqi domendan yuklanadi va
 * stillanmaydi. `telegram-widget.js` esa `Telegram.Login.auth()` ni ham beradi:
 * xuddi shu OAuth oynasi, lekin istalgan o'z tugmadan ochiladi — payload
 * `data-onauth` bilan butunlay bir xil, backend farqni sezmaydi.
 *
 * Talab: bot uchun @BotFather'da `/setdomain` qilingan bo'lishi (iframe bilan
 * bir xil shart) va botning **raqamli ID'si** (`bot_id`) — token'ning `:` dan
 * oldingi qismi. ID sir emas, lekin frontend build'iga env orqali keladi.
 */

interface TelegramLoginApi {
  auth: (
    options: { bot_id: string; request_access?: string; lang?: string },
    callback: (user: Record<string, unknown> | false) => void,
  ) => void;
}

declare global {
  interface Window {
    Telegram?: { Login?: TelegramLoginApi };
  }
}

const WIDGET_SRC = 'https://telegram.org/js/telegram-widget.js?22';

let loader: Promise<TelegramLoginApi> | null = null;

/** Skriptni bir marta yuklaydi. Xatoda kesh tozalanadi — qayta urinish mumkin. */
export function loadTelegramLogin(): Promise<TelegramLoginApi> {
  loader ??= new Promise<TelegramLoginApi>((resolve, reject) => {
    const ready = window.Telegram?.Login;
    if (ready) {
      resolve(ready);
      return;
    }

    const script = document.createElement('script');
    script.src = WIDGET_SRC;
    script.async = true;
    script.onload = () => {
      const login = window.Telegram?.Login;
      if (login) {
        resolve(login);
      } else {
        loader = null;
        reject(new Error('Telegram.Login mavjud emas'));
      }
    };
    script.onerror = () => {
      loader = null;
      script.remove();
      reject(new Error('telegram-widget.js yuklanmadi'));
    };
    document.head.appendChild(script);
  });
  return loader;
}

/**
 * OAuth oynasini ochadi. Foydalanuvchi tasdiqlasa payload, bekor qilsa `null`.
 * Skript yuklanmasa reject bo'ladi — chaqiruvchi xatoni ko'rsatadi.
 */
export async function telegramAuth(
  botId: string,
  lang: string,
): Promise<Record<string, unknown> | null> {
  const login = await loadTelegramLogin();
  return new Promise((resolve) => {
    login.auth({ bot_id: botId, request_access: 'write', lang }, (user) => {
      resolve(user === false ? null : user);
    });
  });
}
