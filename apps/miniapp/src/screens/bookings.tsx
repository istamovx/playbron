import { Button, CyberLoaderOverlay, EmptyState, StatusLine } from '@playbron/ui';
import type { MyBookingDto } from '@playbron/api-client';
import type { ReactNode } from 'react';
import { useEffect, useMemo } from 'react';

import { useT, type Translate } from '../i18n';
import { money } from '../lib/format';
import { isHistory, statusAccent, statusKey } from '../lib/booking-state';
import { formatWindow } from '../lib/slots';
import { useApp, useNowMs } from '../store/app';
import { useBooking } from '../store/booking';

/**
 * Bronlarim — real `GET /me/bookings`, ikki bo'limga ajratilgan.
 *
 * TUGAGAN VA BEKOR QILINGAN BRON O'ZI TARIXGA TUSHADI: bo'limlar HOZIRGI
 * lahzaga qarab har soniya qayta hisoblanadi (`lib/booking-state.ts`),
 * shuning uchun yakunlangan seans "aktiv" bo'lib qolib ketmaydi (loyiha
 * egasi, 2026-08-17).
 */
export function BookingsScreen(): ReactNode {
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

  const { active, history } = useMemo(() => {
    const past: MyBookingDto[] = [];
    const live: MyBookingDto[] = [];
    for (const booking of bookings) (isHistory(booking, nowMs) ? past : live).push(booking);
    live.sort((a, b) => new Date(a.startsAt).getTime() - new Date(b.startsAt).getTime());
    past.sort((a, b) => new Date(b.startsAt).getTime() - new Date(a.startsAt).getTime());
    return { active: live, history: past };
  }, [bookings, nowMs]);

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

  if (bookings.length === 0) {
    return (
      <EmptyState
        icon="event_note"
        title={t('bookingsEmptyTitle')}
        action={
          <Button variant="primary" size="md" notch icon="add" onClick={() => tab('clubs')}>
            {t('newBooking')}
          </Button>
        }
      >
        {t('bookingsEmptyHint')}
      </EmptyState>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <Section title={t('bookingsActive')}>
        {active.length === 0 ? (
          <EmptyState icon="event_available" title={t('bookingsActiveEmptyTitle')}>
            {t('bookingsActiveEmptyHint')}
          </EmptyState>
        ) : (
          active.map((booking) => (
            <BookingCard key={booking.id} booking={booking} nowMs={nowMs} t={t} />
          ))
        )}
      </Section>

      <Section title={t('bookingsHistory')}>
        {history.length === 0 ? (
          <EmptyState icon="history" title={t('bookingsHistoryEmptyTitle')}>
            {t('bookingsHistoryEmptyHint')}
          </EmptyState>
        ) : (
          history.map((booking) => (
            <BookingCard key={booking.id} booking={booking} nowMs={nowMs} t={t} muted />
          ))
        )}
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }): ReactNode {
  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-tight)' }}>
      <span
        style={{
          font: 'var(--type-label)',
          letterSpacing: 'var(--ls-label)',
          textTransform: 'uppercase',
          color: 'var(--text-dim)',
        }}
      >
        {title}
      </span>
      {children}
    </section>
  );
}

function BookingCard({
  booking,
  nowMs,
  t,
  muted,
}: {
  booking: MyBookingDto;
  nowMs: number;
  t: Translate;
  muted?: boolean;
}): ReactNode {
  const accent = statusAccent(booking, nowMs);

  return (
    <div
      style={{
        padding: 'var(--card-pad)',
        background: 'var(--surface-panel)',
        border: '1px solid var(--line-1)',
        boxShadow: `inset 3px 0 0 ${accent}`,
        clipPath: 'var(--clip-tr)',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        opacity: muted ? 0.72 : 1,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '2px 8px',
        }}
      >
        <span
          style={{
            font: 'var(--type-section)',
            color: 'var(--text-title)',
            whiteSpace: 'nowrap',
          }}
        >
          {`${booking.clubName} · ${booking.stationCode}`}
        </span>
        <span
          style={{
            font: 'var(--type-label)',
            letterSpacing: 'var(--ls-label)',
            textTransform: 'uppercase',
            color: accent,
            whiteSpace: 'nowrap',
          }}
        >
          {t(statusKey(booking, nowMs))}
        </span>
      </div>

      {/* Vaqt KLUB zonasida (`clubs.timezone`), telefonnikida emas — avval
          `Date.getHours()` ishlatilardi va boshqa zonadagi telefonda mijoz
          o'z bronini boshqa soatda ko'rardi (audit topilmasi, 2026-08-16). */}
      <div style={{ font: 'var(--type-data-xs)', color: 'var(--text-muted)' }}>
        {formatWindow(booking.startsAt, booking.endsAt, booking.timezone)}
      </div>

      <div style={{ height: 1, background: 'var(--line-1)' }} />

      <div
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}
      >
        <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
          {t('hoursUnit', { hours: booking.hours })}
        </span>
        {/* Oynaning TO'LIQ summasi — server hisoblagan `play_amount`.
            `rateSnapshot × hours` KO'PAYTIRILMAYDI: tarif oyna ichida
            o'zgarsa ular teng bo'lmaydi (`CLAUDE.md` §Pul). */}
        <span style={{ font: 'var(--type-data)', color: 'var(--text-title)' }}>
          {money(booking.playAmount)}
        </span>
      </div>
    </div>
  );
}
