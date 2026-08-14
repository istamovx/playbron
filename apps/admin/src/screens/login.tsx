import { Button, Icon, Panel, SegmentedControl, StatusLine, Wordmark } from '@playbron/ui';
import { useCallback, useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';

import { useI18n, useT, type Lang, type MsgKey } from '../i18n';
import { TELEGRAM_LOGIN_BOT, useSession } from '../store/session';

/** Til kodi ↔ segment yorlig'i. Kod — matn emas, tarjima qilinmaydi. */
const LANG_LABELS: Record<Lang, string> = { uz: 'UZ', ru: 'RU', en: 'EN' };
const LABEL_LANGS: Record<string, Lang> = { UZ: 'uz', RU: 'ru', EN: 'en' };

const FEATURES: { icon: string; title: MsgKey; text: MsgKey }[] = [
  { icon: 'grid_view', title: 'featLiveTitle', text: 'featLiveText' },
  { icon: 'point_of_sale', title: 'featPosTitle', text: 'featPosText' },
  { icon: 'analytics', title: 'featReportTitle', text: 'featReportText' },
];

const POLL_INTERVAL_MS = 2_000;
// Nonce TTL bilan bir xil — 5 daqiqa
const POLL_TIMEOUT_MS = 300_000;
// Ilova ochilmagan bo'lsa t.me zaxira havolasi shuncha kutib ko'rsatiladi
const FALLBACK_DELAY_MS = 2_500;

/**
 * Kutilayotgan urinish `sessionStorage`da — foydalanuvchi Telegram'ga o'tib
 * kelguncha sahifani yangilab yuborsa, poll yo'qolmasin: qayta ochilganda
 * shu yozuvdan davom etadi. Tab yopilsa o'zi tozalanadi.
 */
const ATTEMPT_KEY = 'playbron.tgstart';

interface Attempt {
  nonce: string;
  deadline: number;
}

function saveAttempt(attempt: Attempt): void {
  try {
    sessionStorage.setItem(ATTEMPT_KEY, JSON.stringify(attempt));
  } catch {
    // Saqlab bo'lmasa oqim baribir ishlaydi — faqat yangilashga chidamsiz bo'ladi
  }
}

function loadAttempt(): Attempt | null {
  try {
    const raw = sessionStorage.getItem(ATTEMPT_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (
      typeof parsed === 'object' &&
      parsed !== null &&
      typeof (parsed as Attempt).nonce === 'string' &&
      typeof (parsed as Attempt).deadline === 'number'
    ) {
      return parsed as Attempt;
    }
    return null;
  } catch {
    return null;
  }
}

function clearAttempt(): void {
  try {
    sessionStorage.removeItem(ATTEMPT_KEY);
  } catch {
    // Tozalab bo'lmasa keyingi o'qishda muddat tekshiruvi baribir rad etadi
  }
}

/**
 * Konsolga kirish — **faqat Telegram**. Parol yo'q, OAuth oynasi ham yo'q.
 *
 * Tugma `tg://resolve?domain=<bot>&start=<nonce>` deep-link bilan Telegram
 * desktop/mobil ilovasini ochadi. Foydalanuvchi botda **Start** bosadi,
 * konsol esa nonce'ni poll qilib sessiyani oladi. Ilova o'rnatilmagan bo'lsa
 * bir necha soniyadan keyin `t.me` zaxira havolasi chiqadi.
 *
 * Bu oqim @BotFather'dagi `/setdomain` ni talab qilmaydi; lokal ishlab
 * chiqishda esa webhook prod'ga qaragani uchun pastdagi dev yo'li ishlatiladi.
 */
export function LoginScreen(): ReactNode {
  const beginTelegramLogin = useSession((state) => state.beginTelegramLogin);
  const pollTelegramLogin = useSession((state) => state.pollTelegramLogin);
  const signInDev = useSession((state) => state.signInDev);
  const lang = useI18n((state) => state.lang);
  const setLang = useI18n((state) => state.setLang);
  const t = useT();

  // Backend'dan kelgan xato matni; `errorKey` esa render paytida tarjima
  // qilinadi — til almashsa xabar ham almashadi
  const [error, setError] = useState<string | null>(null);
  const [errorKey, setErrorKey] = useState<MsgKey | null>(null);
  const [busy, setBusy] = useState(false);
  const [tmeLink, setTmeLink] = useState<string | null>(null);
  // Bekor qilish va unmount poll siklini shu belgi orqali to'xtatadi
  const run = useRef<{ stop: boolean } | null>(null);
  const resumed = useRef(false);

  useEffect(
    () => () => {
      if (run.current) run.current.stop = true;
    },
    [],
  );

  /** Nonce tasdiqlanishini kutadi. `ready` — sessiya o'rnatiladi, App almashadi. */
  const watch = useCallback(
    (nonce: string, deadline: number): void => {
      const marker = { stop: false };
      run.current = marker;
      setBusy(true);
      setError(null);
      setErrorKey(null);

      const fail = (key: MsgKey | null, text: string | null): void => {
        if (marker.stop) return;
        marker.stop = true;
        clearAttempt();
        setErrorKey(key);
        setError(text);
        setBusy(false);
        setTmeLink(null);
      };

      void (async () => {
        try {
          while (!marker.stop && Date.now() < deadline) {
            await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
            if (marker.stop) return;

            const status = await pollTelegramLogin(nonce);
            if (status === 'ready') {
              clearAttempt();
              return;
            }
            if (status === 'expired') break;
          }
          fail('startExpired', null);
        } catch (cause) {
          const text = cause instanceof Error && cause.message ? cause.message : null;
          fail(text ? null : 'signInFailed', text);
        }
      })();
    },
    [pollTelegramLogin],
  );

  // Sahifa yangilangan bo'lsa — saqlangan urinishdan davom etamiz
  useEffect(() => {
    if (resumed.current) return;
    resumed.current = true;

    const stored = loadAttempt();
    if (!stored || stored.deadline <= Date.now()) {
      clearAttempt();
      return;
    }
    setTmeLink(`https://t.me/${TELEGRAM_LOGIN_BOT}?start=${stored.nonce}`);
    watch(stored.nonce, stored.deadline);
  }, [watch]);

  const stopLogin = (): void => {
    if (run.current) run.current.stop = true;
    clearAttempt();
    setBusy(false);
    setTmeLink(null);
  };

  const telegramLogin = (): void => {
    setBusy(true);
    setError(null);
    setErrorKey(null);
    setTmeLink(null);

    void (async () => {
      let nonce: string;
      try {
        nonce = await beginTelegramLogin();
      } catch (cause) {
        setError(cause instanceof Error && cause.message ? cause.message : '');
        setBusy(false);
        return;
      }

      const deadline = Date.now() + POLL_TIMEOUT_MS;
      saveAttempt({ nonce, deadline });
      watch(nonce, deadline);

      // Deep-link: ilova o'rnatilgan bo'lsa OS Telegram'ga o'tadi, sahifa qoladi
      window.location.href = `tg://resolve?domain=${TELEGRAM_LOGIN_BOT}&start=${nonce}`;

      const marker = run.current;
      setTimeout(() => {
        if (marker && !marker.stop) {
          setTmeLink(`https://t.me/${TELEGRAM_LOGIN_BOT}?start=${nonce}`);
        }
      }, FALLBACK_DELAY_MS);
    })();
  };

  const devLogin = (): void => {
    setBusy(true);
    setError(null);
    void signInDev().catch((cause: unknown) => {
      setError(cause instanceof Error && cause.message ? cause.message : '');
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

            <Button
              variant="primary"
              size="lg"
              block
              notch
              icon="send"
              disabled={busy}
              onClick={telegramLogin}
            >
              {t('telegramButton')}
            </Button>

            {busy ? (
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 'var(--gap-tight)',
                  padding: 'var(--gap-block)',
                  background: 'var(--surface-inset)',
                  border: '1px dashed var(--line-1)',
                  clipPath: 'var(--clip-tr)',
                }}
              >
                <StatusLine tone="accent" icon="hourglass_top" parts={t('confirmInTelegram')} />
                {tmeLink ? (
                  <a
                    href={tmeLink}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      font: 'var(--type-body-sm)',
                      color: 'var(--text-accent)',
                    }}
                  >
                    {t('openViaTme')}
                  </a>
                ) : null}
                <Button variant="ghost" size="sm" icon="close" onClick={stopLogin}>
                  {t('cancel')}
                </Button>
              </div>
            ) : null}

            {(error !== null || errorKey !== null) && !busy ? (
              <StatusLine
                tone="danger"
                icon="error"
                parts={error ?? t(errorKey ?? 'signInFailed')}
              />
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
