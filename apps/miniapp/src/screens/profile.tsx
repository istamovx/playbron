import {
  Button,
  Icon,
  NOTIFY_BEFORE_MIN,
  NO_SHOW_MIN,
  Panel,
  StatusLine,
  TextField,
} from '@playbron/ui';
import { useState, type ReactNode } from 'react';

import { LANGS, PROFILE_STATS } from '../mock/data';
import { useProfile } from '../store/app';

type Section = 'personal' | 'notify' | 'ui' | 'exit';

const MENU: { id: Section; icon: string; label: string; tone?: string }[] = [
  { id: 'personal', icon: 'badge', label: 'Shaxsiy ma’lumotlar' },
  { id: 'notify', icon: 'notifications', label: 'Bildirishnomalar' },
  { id: 'ui', icon: 'tune', label: 'Interfeys sozlamalari' },
  { id: 'exit', icon: 'logout', label: 'Chiqish', tone: 'var(--red-100)' },
];

/**
 * Profil — balans o'rniga. To'rt bo'limli menyu; bosilgan bo'lim joyida ochiladi,
 * shuning uchun Telegram BackButton mantig'i buzilmaydi.
 */
export function ProfileScreen(): ReactNode {
  const state = useProfile();
  const profile = state.profile;
  const [open, setOpen] = useState<Section | null>(null);
  // «Chiqish» ochiladigan bo'lim emas — bosilishi bilan profildan chiqadi
  const expandable = (id: Section): boolean => id !== 'exit';

  if (!profile) return null;

  const registered = new Date(profile.registeredAt);
  const since = `${String(registered.getDate()).padStart(2, '0')}-${String(registered.getMonth() + 1).padStart(2, '0')}-${registered.getFullYear()}`;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <Panel notch brackets>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span
            style={{
              flex: 'none',
              width: 52,
              height: 52,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'var(--surface-selected)',
              border: '1px solid var(--primary-100)',
              clipPath: 'var(--clip-tr)',
              font: 'var(--fw-medium) var(--fs-2xl)/1 var(--font-display)',
              color: 'var(--text-title)',
            }}
          >
            {profile.name.trim().charAt(0).toLocaleUpperCase('uz-UZ')}
          </span>

          <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
            <span
              style={{
                font: 'var(--fw-medium) var(--fs-lg)/1.2 var(--font-display)',
                color: 'var(--text-title)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {profile.name}
            </span>
            <span style={{ font: 'var(--type-data)', color: 'var(--text-muted)' }}>
              {profile.phone}
            </span>
            <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
              {since} dan beri
            </span>
          </div>
        </div>
      </Panel>

      {/* Ikki qatorli yorliq bo'lsa ham raqamlar bir sathda turadi */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--gap-tight)' }}>
        {PROFILE_STATS.map((stat) => (
          <div
            key={stat.label}
            style={{
              padding: 'var(--card-pad)',
              background: 'var(--surface-card)',
              border: '1px solid var(--line-1)',
              display: 'flex',
              flexDirection: 'column',
              gap: 4,
            }}
          >
            <span
              style={{
                font: 'var(--type-label)',
                letterSpacing: 'var(--ls-label)',
                textTransform: 'uppercase',
                color: 'var(--text-label)',
              }}
            >
              {stat.label}
            </span>
            <span
              style={{
                marginTop: 'auto',
                font: 'var(--fw-medium) var(--fs-2xl)/1 var(--font-mono)',
                color: 'var(--text-title)',
              }}
            >
              {stat.value}
            </span>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-tight)' }}>
        {MENU.map((item) => {
          const on = open === item.id;
          return (
            <div key={item.id} style={{ display: 'flex', flexDirection: 'column' }}>
              <button
                type="button"
                aria-expanded={expandable(item.id) ? on : undefined}
                onClick={() => (expandable(item.id) ? setOpen(on ? null : item.id) : state.signOut())}
                style={{
                  cursor: 'pointer',
                  minHeight: 48,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '0 var(--card-pad)',
                  background: on ? 'var(--surface-selected)' : 'var(--surface-card)',
                  border: `1px solid ${on ? 'var(--primary-100)' : 'var(--line-1)'}`,
                  color: item.tone ?? 'var(--text-body)',
                  font: 'var(--type-body)',
                  textAlign: 'left',
                  transition: 'var(--t-control)',
                }}
              >
                <Icon name={item.icon} size={18} />
                <span style={{ flex: 1, minWidth: 0 }}>{item.label}</span>
                <Icon name={on && expandable(item.id) ? 'expand_less' : 'chevron_right'} size={18} />
              </button>

              {on && expandable(item.id) ? (
                <div
                  style={{
                    padding: 'var(--card-pad)',
                    background: 'var(--surface-panel)',
                    borderLeft: '1px solid var(--line-1)',
                    borderRight: '1px solid var(--line-1)',
                    borderBottom: '1px solid var(--line-1)',
                  }}
                >
                  {item.id === 'personal' ? <PersonalSection /> : null}
                  {item.id === 'notify' ? <NotifySection /> : null}
                  {item.id === 'ui' ? <InterfaceSection /> : null}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** 1 — Shaxsiy ma'lumotlar. */
function PersonalSection(): ReactNode {
  const profile = useProfile((state) => state.profile);
  const update = useProfile((state) => state.update);

  const [name, setName] = useState(profile?.name ?? '');
  const [phone, setPhone] = useState(profile?.phone ?? '+998');
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const save = (): void => {
    if (name.trim().length < 2) {
      setError('Ismingizni kiriting');
      return;
    }
    if (!/^\+998\d{9}$/.test(phone.replace(/[\s()-]/g, ''))) {
      setError('Telefon +998XXXXXXXXX shaklida bo‘lishi kerak');
      return;
    }
    update({ name: name.trim(), phone: phone.replace(/[\s()-]/g, '') });
    setError(null);
    setSaved(true);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
      <TextField
        label="Ism"
        value={name}
        onChange={(value) => {
          setName(value);
          setSaved(false);
        }}
        icon="person"
        placeholder="Aziz Karimov"
      />
      <TextField
        label="Telefon"
        value={phone}
        onChange={(value) => {
          setPhone(value);
          setSaved(false);
        }}
        icon="call"
        inputMode="tel"
        placeholder="+998 90 123 45 67"
        onSubmitKey={save}
      />

      {error ? <StatusLine tone="danger" icon="error" parts={error} /> : null}
      {saved && !error ? (
        <StatusLine tone="ok" icon="check_circle" parts="Saqlandi" />
      ) : null}

      <Button variant="primary" size="lg" notch block icon="check" onClick={save}>
        Saqlash
      </Button>

      <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
        Telefon raqam bron tasdig‘i va klub bilan bog‘lanish uchun ishlatiladi.
      </span>
    </div>
  );
}

/** 2 — Bildirishnomalar. */
function NotifySection(): ReactNode {
  const state = useProfile();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
      <Toggle
        label="Seans ogohlantirishlari"
        hint={`${NOTIFY_BEFORE_MIN.join(' va ')} daqiqa qolganda xabar keladi`}
        on={state.notify}
        onToggle={() => state.setNotify(!state.notify)}
      />
      <Toggle
        label="Bron eslatmasi"
        hint="Bron boshlanishidan oldin eslatib turadi"
        on={state.remind}
        onToggle={() => state.setRemind(!state.remind)}
      />

      <StatusLine
        tone="neutral"
        icon="info"
        parts={[
          `Kechikish limiti ${NO_SHOW_MIN} daqiqa`,
          'Kelmasangiz bron to‘lovi qaytarilmaydi',
        ]}
      />
    </div>
  );
}

/** 3 — Interfeys sozlamalari. */
function InterfaceSection(): ReactNode {
  const state = useProfile();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <span
          style={{
            font: 'var(--type-label)',
            letterSpacing: 'var(--ls-label)',
            textTransform: 'uppercase',
            color: 'var(--text-label)',
          }}
        >
          Til
        </span>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {LANGS.map((lang) => {
            const on = state.lang === lang.id;
            return (
              <button
                key={lang.id}
                type="button"
                aria-pressed={on}
                onClick={() => state.setLang(lang.id)}
                style={{
                  cursor: 'pointer',
                  height: 'var(--control-h)',
                  padding: '0 12px',
                  background: on ? 'var(--surface-selected)' : 'var(--surface-inset)',
                  border: `1px solid ${on ? 'var(--primary-100)' : 'var(--line-1)'}`,
                  color: on ? 'var(--text-title)' : 'var(--text-muted)',
                  font: 'var(--type-body-sm)',
                  transition: 'var(--t-control)',
                }}
              >
                {lang.label}
              </button>
            );
          })}
        </div>
      </div>

      <Toggle
        label="Haptik javob"
        hint="Ogohlantirishlarda tebranish"
        on={state.haptics}
        onToggle={() => state.setHaptics(!state.haptics)}
      />

      <StatusLine
        tone="neutral"
        icon="dark_mode"
        parts={['Mavzu — doim qorong‘i', 'Telegram temasidan mustaqil']}
      />
    </div>
  );
}

function Toggle({
  label,
  hint,
  on,
  onToggle,
}: {
  label: string;
  hint: string;
  on: boolean;
  onToggle: () => void;
}): ReactNode {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      onClick={onToggle}
      style={{
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: 0,
        background: 'transparent',
        border: 'none',
        textAlign: 'left',
      }}
    >
      <span style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
        <span style={{ font: 'var(--type-body)', color: 'var(--text-body)' }}>{label}</span>
        <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>{hint}</span>
      </span>

      <span
        style={{
          flex: 'none',
          width: 44,
          height: 24,
          position: 'relative',
          background: on ? 'var(--primary-100)' : 'var(--surface-inset)',
          border: `1px solid ${on ? 'var(--primary-100)' : 'var(--line-2)'}`,
          transition: 'var(--t-control)',
        }}
      >
        <span
          style={{
            position: 'absolute',
            top: 2,
            left: on ? 22 : 2,
            width: 18,
            height: 18,
            background: on ? 'var(--text-on-accent)' : 'var(--fg-4)',
            transition: 'left 140ms cubic-bezier(.22,.61,.36,1)',
          }}
        />
      </span>
    </button>
  );
}
