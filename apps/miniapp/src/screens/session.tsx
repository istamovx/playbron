import {
  Button,
  CyberLoaderOverlay,
  EmptyState,
  GRACE_MIN,
  Icon,
  NOTIFY_BEFORE_MIN,
  Panel,
  StatusLine,
  formatDuration,
} from '@playbron/ui';
import type { MyBookingDto } from '@playbron/api-client';
import { useEffect, useRef, type ReactNode } from 'react';

import { useT, type Translate } from '../i18n';
import { activeSession, nextBooking, timePhase, type TimePhase } from '../lib/booking-state';
import { formatClockAt, formatWindow } from '../lib/slots';
import { haptic } from '../lib/telegram';
import { useApp, useNowMs, useProfile } from '../store/app';
import { useBooking } from '../store/booking';

/**
 * Aktiv seans — REAL bron ustida (`GET /me/bookings`).
 *
 * Avval bu ekran butunlay simulyatsiya edi: seans vaqti `mock/data.ts`
 * dagi `SESSION_START`/`SESSION_END` konstantalaridan, bar menyusi
 * `MENU` massividan, buyurtma holati esa "yuborilgandan beri o'tgan
 * vaqt" dan hisoblanardi. Backendda mijoz uchun bar buyurtmasi ham,
 * hisob ham YO'Q, shuning uchun ular olib tashlandi — qolgani serverdan
 * keladigan ma'lumot: qaysi bron hozir yuryapti va qachon tugaydi.
 *
 * Seans oynasi tugashi bilan bu ekran o'zi bo'shab qoladi — bron
 * «Bronlarim» dagi tarixga o'tadi.
 */
export function SessionScreen(): ReactNode {
  const t = useT();
  const nowMs = useNowMs();
  const bookings = useBooking((state) => state.myBookings);
  const loading = useBooking((state) => state.myBookingsLoading);
  const error = useBooking((state) => state.myBookingsError);
  const load = useBooking((state) => state.loadMyBookings);
  const tab = useApp((state) => state.tab);

  useEffect(() => {
    void load();
  }, [load]);

  const active = activeSession(bookings, nowMs);
  const next = nextBooking(bookings, nowMs);

  if (loading && bookings.length === 0) return <CyberLoaderOverlay label={t('loading')} />;

  if (error) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
        <StatusLine tone="danger" icon="wifi_off" parts={[error]} />
        <Button variant="primary" size="lg" notch block icon="refresh" onClick={() => void load()}>
          {t('retry')}
        </Button>
      </div>
    );
  }

  if (active) return <ActiveSession booking={active} nowMs={nowMs} t={t} />;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <EmptyState
        icon="sports_esports"
        title={t('sessionEmptyTitle')}
        action={
          next ? null : (
            <Button variant="primary" size="md" notch icon="add" onClick={() => tab('clubs')}>
              {t('newBooking')}
            </Button>
          )
        }
      >
        {t('sessionEmptyHint')}
      </EmptyState>

      {next ? <NextBooking booking={next} nowMs={nowMs} t={t} /> : null}
    </div>
  );
}

/** Yurayotgan seans — taymer va tugash vaqti. */
function ActiveSession({
  booking,
  nowMs,
  t,
}: {
  booking: MyBookingDto;
  nowMs: number;
  t: Translate;
}): ReactNode {
  const notify = useProfile((state) => state.notify);
  const haptics = useProfile((state) => state.haptics);
  const fired = useRef<Set<string>>(new Set());

  const from = new Date(booking.startsAt).getTime();
  const to = new Date(booking.endsAt).getTime();
  const remain = Math.round((to - nowMs) / 1000);
  const phase = timePhase(booking, nowMs);

  // Ogohlantirish bir martadan ko'p tebranmaydi; profilda o'chirilgan
  // bo'lsa umuman tebranmaydi. Kalit BRON bo'yicha — ikkinchi seansda
  // hisob qaytadan boshlanadi.
  useEffect(() => {
    if (!notify || !haptics) return;
    for (const at of NOTIFY_BEFORE_MIN) {
      const key = `${booking.id}:before-${at}`;
      if (remain > 0 && remain <= at * 60 && !fired.current.has(key)) {
        fired.current.add(key);
        haptic('tap');
        return;
      }
    }
    const ended = `${booking.id}:ended`;
    if (remain <= 0 && !fired.current.has(ended)) {
      fired.current.add(ended);
      haptic('error');
    }
  }, [notify, haptics, remain, booking.id]);

  const pct = Math.max(0, Math.min(100, ((nowMs - from) / (to - from)) * 100));
  const tone =
    remain < 0
      ? 'var(--red-100)'
      : remain < 15 * 60
        ? 'var(--red-100)'
        : remain < 30 * 60
          ? 'var(--yellow-100)'
          : 'var(--text-title)';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <Notice phase={phase} remain={remain} t={t} />

      <Panel notch brackets glow>
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 8,
            padding: '6px 0',
          }}
        >
          <span
            style={{
              font: 'var(--type-label)',
              letterSpacing: 'var(--ls-label)',
              textTransform: 'uppercase',
              color: 'var(--text-label)',
              textAlign: 'center',
            }}
          >
            {`${t('remainingLabel')} · ${booking.clubName} · ${booking.stationCode}`}
          </span>
          <span
            style={{
              font: 'var(--fw-medium) var(--fs-metric-fluid)/1 var(--font-mono)',
              color: tone,
              letterSpacing: '.04em',
            }}
          >
            {formatDuration(remain)}
          </span>
          <div
            style={{
              width: '100%',
              height: 4,
              background: 'var(--chart-track)',
              position: 'relative',
              marginTop: 4,
            }}
          >
            <div
              className="pb-fill"
              style={{
                position: 'absolute',
                inset: '0 auto 0 0',
                width: `${pct}%`,
                background: remain < 0 ? 'var(--red-100)' : 'var(--primary-100)',
                boxShadow: remain < 0 ? 'var(--glow-risk)' : 'var(--glow-violet-sm)',
              }}
            />
          </div>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              width: '100%',
              font: 'var(--type-data-xs)',
              color: 'var(--text-dim)',
            }}
          >
            <span>{formatClockAt(booking.startsAt, booking.timezone)}</span>
            <span>{formatClockAt(booking.endsAt, booking.timezone)}</span>
          </div>
        </div>
      </Panel>

      {/* Bar buyurtmasi va hisob mijoz uchun backendda YO'Q — bu yerda
          ularni ko'rsatgandan ko'ra qayerda yopilishini aytamiz. */}
      <StatusLine tone="neutral" icon="receipt_long" parts={[t('billAtDeskNote')]} />
    </div>
  );
}

/** Keyingi bron — hali boshlanmagan. */
function NextBooking({
  booking,
  nowMs,
  t,
}: {
  booking: MyBookingDto;
  nowMs: number;
  t: Translate;
}): ReactNode {
  const untilStart = Math.round((new Date(booking.startsAt).getTime() - nowMs) / 1000);
  // `formatDuration` soatlarda sanaydi — bir necha kun qolganda `120:00:00`
  // chiqib o'qilmay qolardi. Sanoq faqat bir sutka ichida ko'rsatiladi,
  // undan uzoqda oynaning o'zi (sana bilan) yetarli.
  const showCountdown = untilStart <= 24 * 3600;

  return (
    <Panel title={t('nextBookingTitle')} notch>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <span style={{ font: 'var(--type-section)', color: 'var(--text-title)' }}>
          {`${booking.clubName} · ${booking.stationCode}`}
        </span>
        <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-muted)' }}>
          {formatWindow(booking.startsAt, booking.endsAt, booking.timezone)}
        </span>
        {showCountdown ? (
          <div
            style={{
              display: 'flex',
              alignItems: 'baseline',
              justifyContent: 'space-between',
              gap: 8,
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
              {t('startsInLabel')}
            </span>
            <span style={{ font: 'var(--type-data)', color: 'var(--text-title)' }}>
              {formatDuration(untilStart)}
            </span>
          </div>
        ) : null}
      </div>
    </Panel>
  );
}

/** Vaqt holatiga qarab ogohlantirish. */
function Notice({
  phase,
  remain,
  t,
}: {
  phase: TimePhase;
  remain: number;
  t: Translate;
}): ReactNode {
  const minutes = Math.ceil(Math.abs(remain) / 60);

  const notice =
    phase === 'grace'
      ? {
          icon: 'timer_off',
          tone: 'var(--red-100)',
          text: t('sessionGraceNotice', { minutes: GRACE_MIN }),
        }
      : remain <= 15 * 60
        ? {
            icon: 'notifications_active',
            tone: 'var(--red-100)',
            text: t('sessionSoonNotice', { minutes }),
          }
        : remain <= 30 * 60
          ? {
              icon: 'notifications',
              tone: 'var(--yellow-100)',
              text: t('sessionSoonNotice', { minutes }),
            }
          : null;

  if (!notice) return null;

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: 'var(--card-pad)',
        background: 'var(--surface-inset)',
        border: `1px solid ${notice.tone}`,
        clipPath: 'var(--clip-tr)',
        color: notice.tone,
      }}
    >
      <Icon name={notice.icon} size={18} />
      <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-body)' }}>{notice.text}</span>
    </div>
  );
}
