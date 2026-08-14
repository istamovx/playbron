import {
  Button,
  Icon,
  Panel,
  SegmentedControl,
  StatusLine,
  TextField,
  Wordmark,
} from '@playbron/ui';
import { useEffect, useState, type CSSProperties, type ReactNode } from 'react';

import { useI18n, useT, type Lang, type MsgKey } from '../i18n';
import { useSession } from '../store/session';

/** Til kodi ↔ segment yorlig'i. Kod — matn emas, tarjima qilinmaydi. */
const LANG_LABELS: Record<Lang, string> = { uz: 'UZ', ru: 'RU', en: 'EN' };
const LABEL_LANGS: Record<string, Lang> = { UZ: 'uz', RU: 'ru', EN: 'en' };

/**
 * Marketing sayti. `playbron.uz` domeni ulanmaguncha sukut qiymat Render
 * manzili — o'lik domenga yuborilmasin.
 */
const LANDING_URL: string =
  (import.meta.env['VITE_LANDING_URL'] as string | undefined) ??
  (import.meta.env.DEV ? 'http://localhost:5175' : 'https://playbron-landing.onrender.com');

const FEATURES: { icon: string; title: MsgKey; text: MsgKey }[] = [
  { icon: 'grid_view', title: 'featLiveTitle', text: 'featLiveText' },
  { icon: 'point_of_sale', title: 'featPosTitle', text: 'featPosText' },
  { icon: 'analytics', title: 'featReportTitle', text: 'featReportText' },
];

/**
 * Ilovaga kirish — **login va parol**.
 *
 * Telegram bu ekranda qatnashmaydi: u faqat ilovani ochadigan yuza. Login va
 * parolni klub egasi beradi; birov bergan parol bir martalik va birinchi
 * kirishda majburan almashtiriladi (`docs/05-auth-redesign.md` Ilova C).
 */
export function LoginScreen(): ReactNode {
  const mustChange = useSession((state) => state.mustChangePassword);
  const lang = useI18n((state) => state.lang);
  const setLang = useI18n((state) => state.setLang);
  const t = useT();

  const [online, setOnline] = useState(true);

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
        <section className="pb-auth-brand">
          <Wordmark width="min(330px, 78vw)" />
          <p style={TAGLINE}>{t('tagline')}</p>
          <StatusLine
            tone={online ? 'ok' : 'danger'}
            icon={online ? 'sensors' : 'sensors_off'}
            parts={[t(online ? 'statusOnline' : 'statusOffline'), t('authMethodLabel')]}
          />
        </section>

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

        {mustChange ? <ChangePanel /> : <SignInPanel />}
      </div>
    </div>
  );
}

/** Login + parol. */
function SignInPanel(): ReactNode {
  const signIn = useSession((state) => state.signIn);
  const loading = useSession((state) => state.loading);
  const t = useT();

  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);

  const submit = (): void => {
    if (!login.trim() || !password || loading) return;
    setError(null);
    void signIn(login, password).catch((cause: unknown) => {
      setError(cause instanceof Error && cause.message ? cause.message : t('signInFailed'));
    });
  };

  return (
    <Panel title={t('signInTitle')} notch brackets glow style={PANEL}>
      <span className="pb-scan" aria-hidden />

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
        <span style={PROMPT}>
          <span style={{ color: 'var(--text-accent)' }}>{'> '}</span>
          {t('signInHint')}
          <i className="pb-caret" aria-hidden />
        </span>

        <TextField
          label={t('loginLabel')}
          value={login}
          onChange={setLogin}
          placeholder={t('loginPlaceholder')}
          icon="person"
          name="username"
          autoComplete="username"
          disabled={loading}
          onSubmitKey={submit}
        />

        <TextField
          label={t('passwordLabel')}
          value={password}
          onChange={setPassword}
          type="password"
          revealable
          icon="lock"
          name="current-password"
          autoComplete="current-password"
          disabled={loading}
          onSubmitKey={submit}
        />

        <Button
          variant="primary"
          size="lg"
          block
          notch
          icon="login"
          disabled={loading || !login.trim() || !password}
          onClick={submit}
        >
          {loading ? t('signingIn') : t('signInButton')}
        </Button>

        {error ? <StatusLine tone="danger" icon="error" parts={error} /> : null}

        <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
          {t('forgot')}
        </span>
      </div>
    </Panel>
  );
}

/**
 * Birov bergan parolni almashtirish.
 *
 * Bu ekran chetlab o'tilmaydi: `must_change` holatida boshqa hech qanday
 * marshrut ochilmaydi (§7.3) — aks holda vaqtinchalik holatdagi hisob mijoz
 * ma'lumotlarini va hisobotlarni o'qiy olardi.
 */
function ChangePanel(): ReactNode {
  const changePassword = useSession((state) => state.changePassword);
  const loading = useSession((state) => state.loading);
  const t = useT();

  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [repeat, setRepeat] = useState('');
  const [error, setError] = useState<string | null>(null);

  const mismatch = repeat.length > 0 && next !== repeat;
  const ready = current.length > 0 && next.length > 0 && next === repeat && !loading;

  const submit = (): void => {
    if (!ready) return;
    setError(null);
    void changePassword(current, next).catch((cause: unknown) => {
      setError(cause instanceof Error && cause.message ? cause.message : t('signInFailed'));
    });
  };

  return (
    <Panel title={t('changeTitle')} notch brackets glow style={PANEL}>
      <span className="pb-scan" aria-hidden />

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
        <StatusLine tone="warn" icon="key" parts={t('changeHint')} />

        <TextField
          label={t('currentPassword')}
          value={current}
          onChange={setCurrent}
          type="password"
          revealable
          icon="lock"
          autoComplete="current-password"
          disabled={loading}
        />
        <TextField
          label={t('newPassword')}
          value={next}
          onChange={setNext}
          type="password"
          revealable
          icon="lock_reset"
          autoComplete="new-password"
          disabled={loading}
        />
        <TextField
          label={t('repeatPassword')}
          value={repeat}
          onChange={setRepeat}
          type="password"
          revealable
          icon="lock_reset"
          autoComplete="new-password"
          disabled={loading}
          error={mismatch ? t('mismatch') : undefined}
          onSubmitKey={submit}
        />

        <Button
          variant="primary"
          size="lg"
          block
          notch
          icon="check"
          disabled={!ready}
          onClick={submit}
        >
          {t('saveButton')}
        </Button>

        {error ? <StatusLine tone="danger" icon="error" parts={error} /> : null}
      </div>
    </Panel>
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

const PANEL: CSSProperties = {
  position: 'relative',
  overflow: 'hidden',
  width: '100%',
  minWidth: 0,
  gridArea: 'panel',
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
