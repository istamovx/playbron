import { Button, Icon, Panel, SegmentedControl, StatusLine, Wordmark } from '@playbron/ui';
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';

import { useI18n, useT, type Lang, type MsgKey } from '../i18n';
import { loadTelegramLogin, telegramAuth } from '../lib/telegram-login';
import { TELEGRAM_LOGIN_BOT, TELEGRAM_LOGIN_BOT_ID, useSession } from '../store/session';

/** Til kodi ↔ segment yorlig'i. Kod — matn emas, tarjima qilinmaydi. */
const LANG_LABELS: Record<Lang, string> = { uz: 'UZ', ru: 'RU', en: 'EN' };
const LABEL_LANGS: Record<string, Lang> = { UZ: 'uz', RU: 'ru', EN: 'en' };

const FEATURES: { icon: string; title: MsgKey; text: MsgKey }[] = [
  { icon: 'grid_view', title: 'featLiveTitle', text: 'featLiveText' },
  { icon: 'point_of_sale', title: 'featPosTitle', text: 'featPosText' },
  { icon: 'analytics', title: 'featReportTitle', text: 'featReportText' },
];

type WidgetState = 'loading' | 'ready' | 'error';

/**
 * Konsolga kirish — **faqat Telegram**. Parol yo'q.
 *
 * Login Widget `@playbronadminbot` orqali ishlaydi: bot uchun @BotFather'da
 * `/setdomain` bilan domen belgilangan bo'lishi shart. Widget `localhost` da
 * ishlamaydi, shuning uchun lokal ishlab chiqishda pastdagi dev yo'li ochiladi.
 *
 * Til (uz/ru/en) yuqori o'ng burchakdagi almashtirgichdan tanlanadi; widget
 * `data-lang` ni faqat o'rnatilishda o'qiydi, shuning uchun til almashganda
 * skript qayta yuklanadi.
 */
export function LoginScreen(): ReactNode {
  const signInWidget = useSession((state) => state.signInWidget);
  const signInDev = useSession((state) => state.signInDev);
  const lang = useI18n((state) => state.lang);
  const setLang = useI18n((state) => state.setLang);
  const t = useT();

  const mount = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [widget, setWidget] = useState<WidgetState>('loading');
  // Qayta urinish tugmasi shu hisoblagichni oshiradi — effekt qayta ishlaydi
  const [attempt, setAttempt] = useState(0);

  // ── Custom tugma yo'li: skript oldindan yuklanadi, tugma o'zimizniki ──
  useEffect(() => {
    if (!TELEGRAM_LOGIN_BOT_ID) return;

    let alive = true;
    setWidget('loading');
    loadTelegramLogin()
      .then(() => alive && setWidget('ready'))
      .catch(() => alive && setWidget('error'));

    return () => {
      alive = false;
    };
  }, [attempt]);

  // ── Zaxira yo'l: bot ID berilmagan — standart iframe widget ──
  useEffect(() => {
    const host = mount.current;
    if (TELEGRAM_LOGIN_BOT_ID || !host || !TELEGRAM_LOGIN_BOT) return;

    setWidget('loading');

    // Widget global funksiya orqali javob qaytaradi
    const globalName = 'onPlayBronTelegramAuth';
    (window as unknown as Record<string, unknown>)[globalName] = (
      payload: Record<string, unknown>,
    ) => {
      setBusy(true);
      setError(null);
      void signInWidget(payload).catch((cause: unknown) => {
        setError(cause instanceof Error ? cause.message : '');
        setBusy(false);
      });
    };

    const script = document.createElement('script');
    script.src = 'https://telegram.org/js/telegram-widget.js?22';
    script.async = true;
    script.setAttribute('data-telegram-login', TELEGRAM_LOGIN_BOT);
    script.setAttribute('data-size', 'large');
    script.setAttribute('data-radius', '2');
    script.setAttribute('data-request-access', 'write');
    script.setAttribute('data-lang', lang);
    script.setAttribute('data-onauth', `${globalName}(user)`);
    script.onload = () => setWidget('ready');
    script.onerror = () => setWidget('error');

    host.appendChild(script);

    return () => {
      host.replaceChildren();
      delete (window as unknown as Record<string, unknown>)[globalName];
    };
  }, [signInWidget, lang, attempt]);

  /** Custom tugma bosildi — OAuth oynasi ochiladi. */
  const telegramLogin = (): void => {
    setBusy(true);
    setError(null);
    void telegramAuth(TELEGRAM_LOGIN_BOT_ID, lang)
      .then((payload) => {
        // Oyna yopildi, tasdiq yo'q — jim qaytamiz, xato emas
        if (!payload) {
          setBusy(false);
          return;
        }
        return signInWidget(payload);
      })
      .catch((cause: unknown) => {
        setError(cause instanceof Error ? cause.message : '');
        setBusy(false);
      });
  };

  const devLogin = (): void => {
    setBusy(true);
    setError(null);
    void signInDev().catch((cause: unknown) => {
      setError(cause instanceof Error ? cause.message : null);
      setBusy(false);
    });
  };

  return (
    <div
      style={{
        position: 'relative',
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 'calc(var(--gutter) + 44px) var(--gutter) var(--gutter)',
        background: 'var(--bg-app)',
        font: 'var(--type-body)',
        color: 'var(--text-body)',
        overflow: 'hidden',
      }}
    >
      <Backdrop />

      <header className="pb-auth-top">
        <span style={EYEBROW}>{t('eyebrow')}</span>
        <SegmentedControl
          size="sm"
          brackets
          items={Object.values(LANG_LABELS)}
          value={LANG_LABELS[lang]}
          onChange={(label) => {
            const next = LABEL_LANGS[label];
            if (next) setLang(next);
          }}
        />
      </header>

      <div className="pb-auth">
        <section
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 14,
            textAlign: 'center',
          }}
        >
          <Wordmark width="min(360px, 86vw)" />
          <p
            style={{
              margin: 0,
              font: 'var(--type-body)',
              color: 'var(--text-muted)',
              maxWidth: 560,
            }}
          >
            {t('tagline')}
          </p>
        </section>

        <Panel
          title={t('signInTitle')}
          notch
          brackets
          glow
          style={{ width: 'min(460px, 100%)' }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
            <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-muted)' }}>
              {t('signInHint')}
            </span>

            {TELEGRAM_LOGIN_BOT_ID ? (
              // Custom tugma — DS uslubida, OAuth oynasini o'zi ochadi
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-tight)' }}>
                <Button
                  variant="primary"
                  size="lg"
                  block
                  notch
                  icon="send"
                  disabled={busy || widget !== 'ready'}
                  onClick={telegramLogin}
                >
                  {t('telegramButton')}
                </Button>

                {widget === 'loading' && !busy ? (
                  <StatusLine tone="neutral" icon="hourglass_empty" parts={t('widgetLoading')} />
                ) : null}

                {widget === 'error' && !busy ? (
                  <>
                    <StatusLine tone="danger" icon="wifi_off" parts={t('widgetError')} />
                    <Button
                      variant="secondary"
                      size="sm"
                      icon="refresh"
                      onClick={() => setAttempt((n) => n + 1)}
                    >
                      {t('retry')}
                    </Button>
                  </>
                ) : null}

                {busy ? (
                  <StatusLine tone="accent" icon="hourglass_top" parts={t('signInChecking')} />
                ) : null}
              </div>
            ) : (
              // Zaxira: iframe widget yashaydigan ramka — yuklanish, xato va
              // band holatlar shu yerda almashinadi, tugma «sakrab» qolmaydi
              <div
                style={{
                  position: 'relative',
                  minHeight: 64,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 'var(--gap-tight)',
                  padding: 'var(--gap-block)',
                  background: 'var(--surface-inset)',
                  border: `1px ${widget === 'ready' ? 'solid' : 'dashed'} var(--line-1)`,
                  clipPath: 'var(--clip-tr)',
                }}
              >
                <div
                  ref={mount}
                  style={{
                    display: busy || widget === 'error' ? 'none' : 'flex',
                    justifyContent: 'center',
                  }}
                />

                {widget === 'loading' && !busy ? (
                  <StatusLine tone="neutral" icon="hourglass_empty" parts={t('widgetLoading')} />
                ) : null}

                {widget === 'error' && !busy ? (
                  <>
                    <StatusLine tone="danger" icon="wifi_off" parts={t('widgetError')} />
                    <Button
                      variant="secondary"
                      size="sm"
                      icon="refresh"
                      onClick={() => setAttempt((n) => n + 1)}
                    >
                      {t('retry')}
                    </Button>
                  </>
                ) : null}

                {busy ? (
                  <StatusLine tone="accent" icon="hourglass_top" parts={t('signInChecking')} />
                ) : null}
              </div>
            )}

            {error !== null ? (
              <StatusLine tone="danger" icon="error" parts={error || t('signInFailed')} />
            ) : null}

            {widget === 'ready' && !busy && !error ? (
              <StatusLine tone="neutral" icon="info" parts={t('widgetHint')} />
            ) : null}

            {import.meta.env.DEV ? (
              <>
                <div style={{ height: 1, background: 'var(--line-1)' }} />
                <span style={EYEBROW}>{t('devEyebrow')}</span>
                <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                  {t('devHint')}
                </span>
                <Button variant="secondary" size="lg" block icon="terminal" onClick={devLogin}>
                  {t('devButton')}
                </Button>
              </>
            ) : null}
          </div>
        </Panel>

        <section className="pb-auth-features">
          {FEATURES.map((item) => (
            <div
              key={item.title}
              style={{
                display: 'flex',
                gap: 12,
                alignItems: 'flex-start',
                padding: 'var(--card-pad)',
                background: 'var(--surface-card)',
                border: '1px solid var(--line-1)',
                clipPath: 'var(--clip-tr)',
                minWidth: 0,
              }}
            >
              <span
                style={{
                  flex: 'none',
                  width: 34,
                  height: 34,
                  display: 'grid',
                  placeItems: 'center',
                  background: 'var(--surface-inset)',
                  border: '1px solid var(--line-1)',
                  clipPath: 'var(--clip-tr)',
                  color: 'var(--purple-100)',
                }}
              >
                <Icon name={item.icon} size={17} />
              </span>
              <span style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
                <span style={{ font: 'var(--type-section)', color: 'var(--text-title)' }}>
                  {t(item.title)}
                </span>
                <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-dim)' }}>
                  {t(item.text)}
                </span>
              </span>
            </div>
          ))}
        </section>
      </div>
    </div>
  );
}

/** Fon — DS to'ri va ikki yumshoq binafsha halo. */
function Backdrop(): ReactNode {
  return (
    <>
      <div
        aria-hidden
        style={{
          position: 'absolute',
          inset: 0,
          background: 'var(--bg-grid)',
          backgroundSize: '52px 52px',
          maskImage: 'radial-gradient(75% 65% at 50% 38%, #000 0%, transparent 100%)',
          WebkitMaskImage: 'radial-gradient(75% 65% at 50% 38%, #000 0%, transparent 100%)',
          pointerEvents: 'none',
        }}
      />
      <div
        aria-hidden
        style={{
          position: 'absolute',
          top: '-12%',
          left: '50%',
          width: 520,
          height: 300,
          transform: 'translateX(-50%)',
          boxShadow: 'var(--glow-violet-lg)',
          opacity: 0.5,
          pointerEvents: 'none',
        }}
      />
      <div
        aria-hidden
        style={{
          position: 'absolute',
          bottom: '-18%',
          right: '-6%',
          width: 380,
          height: 240,
          boxShadow: 'var(--glow-violet-lg)',
          opacity: 0.22,
          pointerEvents: 'none',
        }}
      />
    </>
  );
}

const EYEBROW: CSSProperties = {
  font: 'var(--type-label)',
  letterSpacing: 'var(--ls-label)',
  textTransform: 'uppercase',
  color: 'var(--text-label)',
};
