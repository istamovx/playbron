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

/**
 * Marketing sayti — kirish ekranidagi «saytga qaytish» havolasi shu manzilga.
 * Odatiy yo'l: landing → «Ilovaga kirish» → shu ekran, shuning uchun orqaga
 * qaytish yo'li ham bo'lishi kerak.
 *
 * `playbron.uz` hali hech qayerga yo'naltirilmagan, shuning uchun sukut qiymat
 * sifatida ishlatilmaydi — lokalda landing dev serveri, prod'da esa Render
 * manzili. Domen ulangach `VITE_LANDING_URL` playbron.uz ga o'zgartiriladi.
 */
const LANDING_URL: string =
  (import.meta.env['VITE_LANDING_URL'] as string | undefined) ??
  (import.meta.env.DEV ? 'http://localhost:5175' : 'https://playbron-landing.onrender.com');

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
  const [online, setOnline] = useState(true);
  // Bekor qilish va unmount poll siklini shu belgi orqali to'xtatadi
  const run = useRef<{ stop: boolean } | null>(null);
  const resumed = useRef(false);

  useEffect(
    () => () => {
      if (run.current) run.current.stop = true;
    },
    [],
  );

  // Holat qatoridagi ulanish indikatori — soxta emas, brauzerdan
  useEffect(() => {
    const sync = (): void => setOnline(navigator.onLine);
    sync();
    window.addEventListener('online', sync);
    window.addEventListener('offline', sync);
    return () => {
      window.removeEventListener('online', sync);
      window.removeEventListener('offline', sync);
    };
  }, []);

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
        while (!marker.stop && Date.now() < deadline) {
          await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
          if (marker.stop) return;

          try {
            const status = await pollTelegramLogin(nonce);
            if (status === 'ready') {
              clearAttempt();
              return;
            }
            if (status === 'expired') {
              fail('startExpired', null);
              return;
            }
          } catch {
            // Vaqtinchalik xato (API restart, tarmoq uzilishi, sovuq start) —
            // kutish davom etadi. Muddat (deadline) baribir chegaralaydi.
          }
        }
        fail('startExpired', null);
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
        nonce = await beginTelegramLogin(lang);
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
    <div style={SHELL}>
      <Backdrop />

      <header className="pb-auth-top">
        <div className="pb-auth-back">
          <a className="pb-auth-back__link" href={LANDING_URL} aria-label={t('backToSite')}>
            <Icon name="arrow_back" size={14} />
            {/* Tor ekranda matn olib turiladi — til almashtirgichi bilan sig'masdi */}
            <span className="pb-auth-back__label">{t('backToSite')}</span>
          </a>
          <span className="pb-auth-eyebrow" style={EYEBROW}>
            {t('eyebrow')}
          </span>
        </div>

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
        {/* Brend va ulanish holati */}
        <section className="pb-auth-brand">
          <Wordmark width="min(330px, 78vw)" />

          <p style={TAGLINE}>{t('tagline')}</p>

          <StatusLine
            tone={online ? 'ok' : 'danger'}
            icon={online ? 'sensors' : 'sensors_off'}
            parts={[t(online ? 'statusOnline' : 'statusOffline'), t('authMethodLabel')]}
          />
        </section>

        {/* Modullar — desktopda brend ostida, telefonda panel ortida */}
        <div className="pb-auth-features">
          <span style={EYEBROW}>{t('modulesLabel')}</span>
          {FEATURES.map((item) => (
            <div key={item.title} className="pb-auth-mod">
              <span style={MOD_ICON}>
                <Icon name={item.icon} size={17} />
              </span>
              <span style={{ display: 'grid', gap: 3, minWidth: 0 }}>
                <span style={{ font: 'var(--type-section)', color: 'var(--text-title)' }}>
                  {t(item.title)}
                </span>
                <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-dim)' }}>
                  {t(item.text)}
                </span>
              </span>
            </div>
          ))}
        </div>

        {/* Kirish paneli */}
        <Panel
          title={t('signInTitle')}
          notch
          brackets
          glow
          style={{
            position: 'relative',
            overflow: 'hidden',
            width: '100%',
            minWidth: 0,
            gridArea: 'panel',
          }}
        >
          <span className="pb-scan" aria-hidden />

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
            <span style={PROMPT}>
              <span style={{ color: 'var(--text-accent)' }}>{'> '}</span>
              {t('signInHint')}
              <i className="pb-caret" aria-hidden />
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
              <div style={WAITING}>
                <StatusLine tone="accent" icon="hourglass_top" parts={t('confirmInTelegram')} />
                {tmeLink ? (
                  <a
                    href={tmeLink}
                    target="_blank"
                    rel="noreferrer"
                    style={{ font: 'var(--type-body-sm)', color: 'var(--text-accent)' }}
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
          maskImage: 'radial-gradient(78% 68% at 50% 34%, #000 0%, transparent 100%)',
          WebkitMaskImage: 'radial-gradient(78% 68% at 50% 34%, #000 0%, transparent 100%)',
          pointerEvents: 'none',
        }}
      />
      <div
        aria-hidden
        style={{
          ...HALO,
          top: '-24%',
          left: '50%',
          width: 1080,
          height: 520,
          transform: 'translateX(-50%)',
        }}
      />
      <div
        aria-hidden
        style={{ ...HALO, bottom: '-20%', right: '-10%', width: 520, height: 320, opacity: 0.5 }}
      />
    </>
  );
}

const SHELL: CSSProperties = {
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
};

/**
 * Yumshoq binafsha yorug'lik.
 *
 * `--glow-violet-lg` (box-shadow) ishlatilmaydi: soya shaffof blokning CHETIGA
 * tushadi, natijada fonda to'rtburchakning to'rt burchagi ko'rinib qoladi.
 * Radial gradientning cheti umuman yo'q.
 */
const HALO: CSSProperties = {
  position: 'absolute',
  background:
    'radial-gradient(50% 50% at 50% 50%, color-mix(in srgb, var(--primary-100) 22%, transparent) 0%, transparent 72%)',
  pointerEvents: 'none',
};

const EYEBROW: CSSProperties = {
  font: 'var(--type-label)',
  letterSpacing: 'var(--ls-label)',
  textTransform: 'uppercase',
  color: 'var(--text-label)',
};

const TAGLINE: CSSProperties = {
  margin: 0,
  maxWidth: '46ch',
  font: 'var(--type-body)',
  color: 'var(--text-muted)',
};

/** Terminal qatori — mono, aksent prefiksi va miltillovchi kursor bilan. */
const PROMPT: CSSProperties = {
  font: 'var(--type-data-xs)',
  lineHeight: 'var(--lh-normal)',
  color: 'var(--text-muted)',
};

const MOD_ICON: CSSProperties = {
  flex: 'none',
  width: 34,
  height: 34,
  display: 'grid',
  placeItems: 'center',
  background: 'var(--surface-inset)',
  border: '1px solid var(--line-1)',
  clipPath: 'var(--clip-tr)',
  color: 'var(--purple-100)',
};

const WAITING: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 'var(--gap-tight)',
  padding: 'var(--gap-block)',
  background: 'var(--surface-inset)',
  border: '1px dashed var(--line-1)',
  clipPath: 'var(--clip-tr)',
};
