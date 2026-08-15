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

function formatWhen(startsAt: string, endsAt: string): string {
  const from = new Date(startsAt);
  const to = new Date(endsAt);
  const pad = (n: number): string => String(n).padStart(2, '0');
  const date = `${pad(from.getDate())}-${pad(from.getMonth() + 1)}-${from.getFullYear()}`;
  const hm = (d: Date): string => `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  return `${date}  ${hm(from)} → ${hm(to)}`;
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
        {formatWhen(booking.startsAt, booking.endsAt)}
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
