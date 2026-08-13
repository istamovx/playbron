/**
 * Telegram Mini App integratsiyasi rasmiy `telegram-web-app.js` global obyekti orqali —
 * qo'shimcha SDK paketisiz, versiya farqi xavfi yo'q.
 *
 * MainButton va BackButton native ishlatiladi, o'z tugmalarimiz bilan dublikat qilinmaydi.
 */
interface TelegramButton {
  setText: (text: string) => void;
  show: () => void;
  hide: () => void;
  enable: () => void;
  disable: () => void;
  onClick: (handler: () => void) => void;
  offClick: (handler: () => void) => void;
  setParams: (params: { color?: string; text_color?: string; is_active?: boolean }) => void;
}

interface TelegramWebApp {
  initData: string;
  colorScheme: 'light' | 'dark';
  themeParams: Record<string, string>;
  MainButton: TelegramButton;
  BackButton: Pick<TelegramButton, 'show' | 'hide' | 'onClick' | 'offClick'>;
  HapticFeedback: {
    impactOccurred: (style: 'light' | 'medium' | 'heavy') => void;
    notificationOccurred: (type: 'error' | 'success' | 'warning') => void;
  };
  ready: () => void;
  expand: () => void;
  close: () => void;
  openLink: (url: string) => void;
  setHeaderColor?: (color: string) => void;
  setBackgroundColor?: (color: string) => void;
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp };
  }
}

export function webApp(): TelegramWebApp | null {
  return window.Telegram?.WebApp ?? null;
}

export function initTelegram(): void {
  forceDarkTheme();

  const app = webApp();
  if (!app) return;
  app.ready();
  app.expand();

  // Telegram chrome'i ham ilova foniga mos bo'lsin (eski mijozlarda metod yo'q)
  app.setHeaderColor?.('#0A0A0D');
  app.setBackgroundColor?.('#07070A');
}

/**
 * Mijoz yuzasi doim dark: SystemX ranglari o'zgarmaydi.
 * Telegram'ning light temasi ham, `themeParams` ranglari ham qo'llanmaydi.
 */
function forceDarkTheme(): void {
  const root = document.documentElement;
  root.dataset.theme = 'dark';
  root.style.colorScheme = 'dark';
}

export function haptic(type: 'success' | 'error' | 'tap'): void {
  const app = webApp();
  if (!app) return;
  if (type === 'tap') app.HapticFeedback.impactOccurred('light');
  else app.HapticFeedback.notificationOccurred(type);
}

export interface MainButtonConfig {
  text: string;
  onClick: () => void;
  enabled?: boolean;
  visible?: boolean;
}

/** MainButton holatini boshqarish. Disabled holatda matn sababni aytadi. */
export function setMainButton(config: MainButtonConfig | null): () => void {
  const app = webApp();
  if (!app) return () => undefined;

  if (!config || config.visible === false) {
    app.MainButton.hide();
    return () => undefined;
  }

  app.MainButton.setText(config.text);
  app.MainButton.show();
  if (config.enabled === false) app.MainButton.disable();
  else app.MainButton.enable();

  app.MainButton.onClick(config.onClick);
  return () => app.MainButton.offClick(config.onClick);
}

export function setBackButton(handler: (() => void) | null): () => void {
  const app = webApp();
  if (!app) return () => undefined;

  if (!handler) {
    app.BackButton.hide();
    return () => undefined;
  }

  app.BackButton.show();
  app.BackButton.onClick(handler);
  return () => {
    app.BackButton.offClick(handler);
    app.BackButton.hide();
  };
}
