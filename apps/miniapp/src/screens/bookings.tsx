import type { MyBookingDto } from '@playbron/api-client';
import type { ReactNode } from 'react';
import { useEffect } from 'react';

import { S } from '../mock/data';
import { useBooking } from '../store/booking';

const STATUS_LABEL: Record<string, string> = {
  PENDING: 'Kutilmoqda',
  CONFIRMED: 'Tasdiqlangan',
  CANCELLED: 'Bekor qilingan',
};

const STATUS_TONE: Record<string, string> = {
  PENDING: 'var(--yellow-100)',
  CONFIRMED: 'var(--secondary-500)',
  CANCELLED: 'var(--fg-4)',
};

const STATUS_LINE: Record<string, string> = {
  PENDING: 'var(--yellow-100)',
  CONFIRMED: 'var(--line-1)',
  CANCELLED: 'var(--line-1)',
};

/** Vaqt KLUB zonasida ko'rsatiladi (`clubs.timezone`), telefonnikida emas.
 * Avval `Date.getHours()` ishlatilardi va boshqa zonadagi (yoki soati
 * noto'g'ri) telefonda mijoz o'z bronini boshqa soatda ko'rardi — bron
 * qilgan vaqti bilan ro'yxatdagi vaqt mos kelmasdi (audit topilmasi,
 * 2026-08-16). CLAUDE.md qoidasi: "UI'da Asia/Tashkent". */
function formatWhen(startsAt: string, endsAt: string, timezone: string): string {
  const parts = (iso: string): Record<string, string> => {
    const raw: Record<string, string> = {};
    for (const part of new Intl.DateTimeFormat('en-GB', {
      timeZone: timezone,
      hourCycle: 'h23',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).formatToParts(new Date(iso))) {
      if (part.type !== 'literal') raw[part.type] = part.value;
    }
    return raw;
  };

  const from = parts(startsAt);
  const to = parts(endsAt);
  return `${from.day}-${from.month}-${from.year}  ${from.hour}:${from.minute} → ${to.hour}:${to.minute}`;
}

/** Bronlarim — real `GET /me/bookings`. */
export function BookingsScreen(): ReactNode {
  const bookings = useBooking((state) => state.myBookings);
  const loading = useBooking((state) => state.myBookingsLoading);
  const error = useBooking((state) => state.myBookingsError);
  const load = useBooking((state) => state.loadMyBookings);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) {
    return <div style={{ font: 'var(--type-body-sm)', color: 'var(--red-100)' }}>{error}</div>;
  }

  if (!loading && bookings.length === 0) {
    return (
      <div style={{ font: 'var(--type-body-sm)', color: 'var(--text-muted)' }}>
        Hali bron yo‘q — klub tanlab bron qiling.
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      {bookings.map((booking) => (
        <BookingCard key={booking.id} booking={booking} />
      ))}
    </div>
  );
}

function BookingCard({ booking }: { booking: MyBookingDto }): ReactNode {
  const accent = STATUS_TONE[booking.status] ?? 'var(--text-muted)';
  const line = STATUS_LINE[booking.status] ?? 'var(--line-1)';

  return (
    <div
      style={{
        padding: 'var(--card-pad)',
        background: 'var(--surface-panel)',
        border: `1px solid ${line}`,
        boxShadow: `inset 3px 0 0 ${accent}`,
        clipPath: 'var(--clip-tr)',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
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
        <span style={{ font: 'var(--type-section)', color: 'var(--text-title)', whiteSpace: 'nowrap' }}>
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
          {STATUS_LABEL[booking.status] ?? booking.status}
        </span>
      </div>

      <div style={{ font: 'var(--type-data-xs)', color: 'var(--text-muted)' }}>
        {formatWhen(booking.startsAt, booking.endsAt, booking.timezone)}
      </div>

      <div style={{ height: 1, background: 'var(--line-1)' }} />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
          {`${booking.hours} soat`}
        </span>
        <span style={{ font: 'var(--type-data)', color: 'var(--text-title)' }}>
          {`${S(booking.rateSnapshot * booking.hours)} so‘m`}
        </span>
      </div>
    </div>
  );
}
