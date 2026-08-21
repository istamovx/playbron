import {
  CLUB_TIMEZONE,
  CyberLoader,
  EmptyState,
  Icon,
  NOTIFY_BEFORE_MIN,
  NO_SHOW_MIN,
  Panel,
  StatusLine,
} from '@playbron/ui';
import { getMyStats, type MyStatsDto } from '@playbron/api-client';
import { useEffect, useState, type ReactNode } from 'react';

import { LANGS, useI18n, useLocale, useT, type MsgKey } from '../i18n';
import { api } from '../lib/api';
import { useProfile } from '../store/app';

type Section = 'personal' | 'notify' | 'ui' | 'exit';

const MENU: { id: Section; icon: string; label: MsgKey; tone?: string }[] = [
  { id: 'personal', icon: 'badge', label: 'sectionPersonal' },
  { id: 'notify', icon: 'notifications', label: 'sectionNotify' },
  { id: 'ui', icon: 'tune', label: 'sectionInterface' },
  { id: 'exit', icon: 'logout', label: 'sectionExit', tone: 'var(--red-100)' },
];

/**
 * Profil. To'rt bo'limli menyu; bosilgan bo'lim joyida ochiladi, shuning
 * uchun Telegram BackButton mantig'i buzilmaydi.
 */
export function ProfileScreen(): ReactNode {
  const t = useT();
  const locale = useLocale();
  const state = useProfile();
  const profile = state.profile;
  const [open, setOpen] = useState<Section | null>(null);
  // Ko'rsatkichlar REAL bronlardan (`GET /me/stats`). Avval
  // `mock/data.ts::PROFILE_STATS` qotirilgan edi va HAR BIR foydalanuvchida
  // bir xil "18 seans / 41 soat" ko'rinardi (loyiha egasining topilmasi,
  // 2026-08-16: "mijoz rolida seed va mock data qolib ketgan").
  const [stats, setStats] = useState<MyStatsDto | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);
  // «Chiqish» ochiladigan bo'lim emas — bosilishi bilan profildan chiqadi
  const expandable = (id: Section): boolean => id !== 'exit';

  useEffect(() => {
    let cancelled = false;
    void getMyStats(api)
      .then((data) => {
        if (!cancelled) setStats(data);
      })
      .catch(() => {
        // Tarmoq xatosi — plitalar o'rniga bo'sh holat (soxta nol emas)
      })
      .finally(() => {
        if (!cancelled) setStatsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!profile) return null;

  const name = profile.name.trim() || t('customer');
  const statTiles: { label: string; value: string }[] = stats
    ? [
        { label: t('statSessions'), value: String(stats.sessions) },
        { label: t('statHours'), value: String(stats.hours) },
        { label: t('statUpcoming'), value: String(stats.upcoming) },
        { label: t('statCancelled'), value: String(stats.cancelled) },
      ]
    : [];

  // Sana KLUB mintaqasida — brauzer zonasiga tayanmaydi (`CLAUDE.md` §Vaqt).
  const since = new Intl.DateTimeFormat(locale, {
    timeZone: CLUB_TIMEZONE,
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(new Date(profile.registeredAt));

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
            {name.charAt(0).toLocaleUpperCase('uz-UZ')}
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
              {name}
            </span>
            <span style={{ font: 'var(--type-data)', color: 'var(--text-muted)' }}>
              {profile.phone || t('phoneMissing')}
            </span>
            <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
              {t('since', { date: since })}
            </span>
          </div>
        </div>
      </Panel>

      {statsLoading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '4px 0' }}>
          <CyberLoader label={t('loading')} />
        </div>
      ) : statTiles.length === 0 ? (
        <EmptyState icon="query_stats">{t('statsEmpty')}</EmptyState>
      ) : (
        // Ikki qatorli yorliq bo'lsa ham raqamlar bir sathda turadi.
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--gap-tight)' }}>
          {statTiles.map((stat) => (
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
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-tight)' }}>
        {MENU.map((item) => {
          const on = open === item.id;
          return (
            <div key={item.id} style={{ display: 'flex', flexDirection: 'column' }}>
              <button
                type="button"
                aria-expanded={expandable(item.id) ? on : undefined}
                onClick={() =>
                  expandable(item.id) ? setOpen(on ? null : item.id) : state.signOut()
                }
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
                <span style={{ flex: 1, minWidth: 0 }}>{t(item.label)}</span>
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

/**
 * 1 — Shaxsiy ma'lumotlar. FAQAT KO'RSATISH.
 *
 * Avval bu yerda "Saqlash" tugmali forma turardi va bosilganda "Saqlandi"
 * deb yozardi — aslida hech qayerga yubormasdi: `PATCH /me` endpoint'i
 * YO'Q, ism va telefon botdagi `requestContact` orqali bir marta olinadi
 * (DCR-002). Mijozga o'zgardi deb ko'rsatish soxta ma'lumotning o'zi edi.
 */
function PersonalSection(): ReactNode {
  const t = useT();
  const profile = useProfile((state) => state.profile);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
      <Field label={t('fieldName')} value={profile?.name.trim() || t('customer')} icon="person" />
      <Field label={t('fieldPhone')} value={profile?.phone || t('phoneMissing')} icon="call" />
      <StatusLine tone="neutral" icon="info" parts={[t('personalNote')]} />
    </div>
  );
}

function Field({ label, value, icon }: { label: string; value: string; icon: string }): ReactNode {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
      <span
        style={{
          font: 'var(--type-label)',
          letterSpacing: 'var(--ls-label)',
          textTransform: 'uppercase',
          color: 'var(--text-label)',
        }}
      >
        {label}
      </span>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          minHeight: 'var(--field-h)',
          padding: '5px 10px',
          background: 'var(--surface-field)',
          border: '1px solid var(--line-1)',
        }}
      >
        <Icon name={icon} size={15} color="var(--text-dim)" />
        <span style={{ minWidth: 0, font: 'var(--type-data)', color: 'var(--text-title)' }}>
          {value}
        </span>
      </div>
    </div>
  );
}

/** 2 — Bildirishnomalar. */
function NotifySection(): ReactNode {
  const t = useT();
  const state = useProfile();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
      <Toggle
        label={t('toggleAlerts')}
        hint={t('toggleAlertsHint', { minutes: NOTIFY_BEFORE_MIN.join(' / ') })}
        on={state.notify}
        onToggle={() => state.setNotify(!state.notify)}
      />

      <StatusLine
        tone="neutral"
        icon="info"
        parts={[t('noShowNote', { minutes: NO_SHOW_MIN }), t('noShowHint')]}
      />
    </div>
  );
}

/** 3 — Interfeys sozlamalari. */
function InterfaceSection(): ReactNode {
  const t = useT();
  const state = useProfile();
  const lang = useI18n((i18n) => i18n.lang);
  const setLang = useI18n((i18n) => i18n.setLang);

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
          {t('labelLanguage')}
        </span>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {LANGS.map((option) => {
            const on = lang === option.id;
            return (
              <button
                key={option.id}
                type="button"
                aria-pressed={on}
                onClick={() => setLang(option.id)}
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
                {option.label}
              </button>
            );
          })}
        </div>
      </div>

      <Toggle
        label={t('toggleHaptics')}
        hint={t('toggleHapticsHint')}
        on={state.haptics}
        onToggle={() => state.setHaptics(!state.haptics)}
      />

      <StatusLine tone="neutral" icon="dark_mode" parts={[t('themeNote'), t('themeNoteHint')]} />
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
