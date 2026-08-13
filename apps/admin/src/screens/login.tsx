import { Button, Icon, Panel, StatusLine, Wordmark } from '@playbron/ui';
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';

import { TELEGRAM_LOGIN_BOT, useSession } from '../store/session';

const FEATURES = [
  { icon: 'grid_view', title: 'Live board', text: 'Xonalar holati va taymerlar real vaqtda' },
  { icon: 'point_of_sale', title: 'Kassa', text: 'Bar buyurtmasi, hisob va chek bir joyda' },
  { icon: 'analytics', title: 'Hisobot', text: 'Tushum, xarajat va foyda kesimlari' },
];

/**
 * Konsolga kirish — **faqat Telegram**. Parol yo'q.
 *
 * Login Widget `@playbronadminbot` orqali ishlaydi: bot uchun @BotFather'da
 * `/setdomain` bilan domen belgilangan bo'lishi shart. Widget `localhost` da
 * ishlamaydi, shuning uchun lokal ishlab chiqishda pastdagi dev yo'li ochiladi.
 *
 * [TEKSHIRISH] Widget skripti va atributlari (`telegram-widget.js` versiyasi,
 * `data-telegram-login`, `data-onauth`, `data-request-access`) rasmiy
 * "Telegram Login Widget" hujjatidan tasdiqlanadi.
 */
export function LoginScreen(): ReactNode {
  const signInWidget = useSession((state) => state.signInWidget);
  const signInDev = useSession((state) => state.signInDev);

  const mount = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [widgetReady, setWidgetReady] = useState(false);

  useEffect(() => {
    const host = mount.current;
    if (!host || !TELEGRAM_LOGIN_BOT) return;

    // Widget global funksiya orqali javob qaytaradi
    const globalName = 'onPlayBronTelegramAuth';
    (window as unknown as Record<string, unknown>)[globalName] = (
      payload: Record<string, unknown>,
    ) => {
      setBusy(true);
      setError(null);
      void signInWidget(payload).catch((cause: unknown) => {
        setError(cause instanceof Error ? cause.message : 'Kirish amalga oshmadi');
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
    script.setAttribute('data-onauth', `${globalName}(user)`);
    script.onload = () => setWidgetReady(true);
    script.onerror = () => setWidgetReady(false);

    host.appendChild(script);

    return () => {
      host.replaceChildren();
      delete (window as unknown as Record<string, unknown>)[globalName];
    };
  }, [signInWidget]);

  const devLogin = (): void => {
    setBusy(true);
    setError(null);
    void signInDev().catch((cause: unknown) => {
      setError(cause instanceof Error ? cause.message : 'Kirish amalga oshmadi');
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
        padding: 'var(--gutter)',
        background: 'var(--bg-app)',
        font: 'var(--type-body)',
        color: 'var(--text-body)',
        overflow: 'hidden',
      }}
    >
      <Backdrop />

      <div className="pb-auth" style={{ position: 'relative' }}>
        <section className="pb-auth-hero" style={{ flexDirection: 'column', gap: 28, minWidth: 0 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <span style={EYEBROW}>Klub konsoli</span>
            <Wordmark width="min(420px, 100%)" />
            <span style={{ font: 'var(--type-body)', color: 'var(--text-muted)', maxWidth: 420 }}>
              PlayStation klublari uchun bron, kassa va boshqaruv tizimi. Xodim smenani
              yuritadi, klub admini butun klubni boshqaradi.
            </span>
          </div>

          <div style={{ height: 1, background: 'var(--line-1)' }} />

          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {FEATURES.map((item) => (
              <div key={item.title} style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
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
                    {item.title}
                  </span>
                  <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-dim)' }}>
                    {item.text}
                  </span>
                </span>
              </div>
            ))}
          </div>
        </section>

        <Panel title="Kirish" notch brackets glow>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
            <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-muted)' }}>
              Konsolga Telegram hisobingiz bilan kirasiz — login va parol kerak emas.
            </span>

            <div
              ref={mount}
              style={{ display: 'flex', justifyContent: 'center', minHeight: 40 }}
            />

            {busy ? (
              <StatusLine tone="neutral" icon="hourglass_top" parts="Kirish tekshirilmoqda…" />
            ) : null}

            {error ? <StatusLine tone="danger" icon="error" parts={error} /> : null}

            {!widgetReady && !busy ? (
              <StatusLine
                tone="neutral"
                icon="info"
                parts={[
                  'Telegram tugmasi ko‘rinmasa',
                  'bot domeni sozlanmagan bo‘lishi mumkin',
                ]}
              />
            ) : null}

            {import.meta.env.DEV ? (
              <>
                <div style={{ height: 1, background: 'var(--line-1)' }} />
                <span style={EYEBROW}>Lokal ishlab chiqish</span>
                <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                  Telegram Login Widget `localhost` da ishlamaydi. Bu tugma faqat dev
                  qurilishida ko‘rinadi va serverda ham faqat lokal muhitda ochiq.
                </span>
                <Button variant="secondary" size="lg" block icon="terminal" onClick={devLogin}>
                  Dev sifatida kirish
                </Button>
              </>
            ) : null}
          </div>
        </Panel>
      </div>
    </div>
  );
}

/** Fon — DS to'ri va yumshoq binafsha halo. */
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
          maskImage: 'radial-gradient(75% 65% at 50% 40%, #000 0%, transparent 100%)',
          WebkitMaskImage: 'radial-gradient(75% 65% at 50% 40%, #000 0%, transparent 100%)',
          pointerEvents: 'none',
        }}
      />
      <div
        aria-hidden
        style={{
          position: 'absolute',
          top: '-14%',
          left: '50%',
          width: 520,
          height: 320,
          transform: 'translateX(-50%)',
          boxShadow: 'var(--glow-violet-lg)',
          opacity: 0.5,
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
