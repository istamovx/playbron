import { Button, Icon, NO_SHOW_MIN } from '@playbron/ui';
import type { ReactNode } from 'react';

import { BILL_SUMMARY, CLK, CLOSED_BILL_CODE, MY_BOOKINGS } from '../mock/data';
import { useNow } from '../store/app';

/** Bronlarim — `PlayBron Mijoz.dc.html` BRONLARIM ekrani. */
export function BookingsScreen(): ReactNode {
  const now = useNow();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      {/* Bot xabari — hisob yopilgach Telegram'ga keladigan yakun */}
      <div
        style={{
          border: '1px solid var(--line-1)',
          background: 'var(--surface-panel)',
          clipPath: 'var(--clip-tr)',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '10px var(--card-pad)',
            borderBottom: '1px solid var(--line-1)',
            color: 'var(--text-muted)',
          }}
        >
          <Icon name="notifications" size={15} />
          <span
            style={{
              flex: 1,
              font: 'var(--type-label)',
              letterSpacing: 'var(--ls-label)',
              textTransform: 'uppercase',
            }}
          >
            Neon Arena · bot
          </span>
          <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>{CLK(now)}</span>
        </div>

        <div
          style={{
            padding: 'var(--card-pad)',
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--gap-tight)',
          }}
        >
          <span style={{ font: 'var(--type-section)', color: 'var(--text-title)' }}>
            Hisob yopildi · {CLOSED_BILL_CODE}
          </span>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {BILL_SUMMARY.map((field) => (
              <div
                key={field.k}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 12,
                  minHeight: 'var(--field-h)',
                  padding: '4px 10px',
                  background: 'var(--surface-field)',
                  border: '1px solid var(--line-1)',
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
                  {field.k}
                </span>
                <span style={{ font: 'var(--type-data)', color: field.tone }}>{field.v}</span>
              </div>
            ))}
          </div>

          <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-muted)' }}>
            Rahmat! Seans haqida sharh qoldirsangiz — 50 bonus ball.
          </span>

          <Button variant="secondary" size="lg" block icon="star">
            Sharh qoldirish
          </Button>
        </div>
      </div>

      {MY_BOOKINGS.map((booking) => (
        <div
          key={booking.code}
          style={{
            padding: 'var(--card-pad)',
            background: 'var(--surface-panel)',
            border: `1px solid ${booking.ln}`,
            boxShadow: `inset 3px 0 0 ${booking.acc}`,
            clipPath: 'var(--clip-tr)',
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
          }}
        >
          {/* Tor ekranda status pastki qatorga tushadi — klub nomi sinmaydi */}
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
              {booking.club}
            </span>
            <span
              style={{
                font: 'var(--type-label)',
                letterSpacing: 'var(--ls-label)',
                textTransform: 'uppercase',
                color: booking.acc,
                whiteSpace: 'nowrap',
              }}
            >
              {booking.status}
            </span>
          </div>

          <div style={{ font: 'var(--type-data-xs)', color: 'var(--text-muted)' }}>
            {booking.when}
          </div>

          <div style={{ height: 1, background: 'var(--line-1)' }} />

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 8,
              flexWrap: 'wrap',
            }}
          >
            <span style={{ font: 'var(--type-data)', color: 'var(--purple-100)' }}>
              {booking.code}
            </span>
            <span style={{ font: 'var(--type-data)', color: 'var(--text-title)' }}>
              {booking.amount}
            </span>
          </div>

          {/* Kelmaslik qoidasi faqat kutilayotgan bronlarda ko'rsatiladi */}
          {booking.cancellable ? (
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 7,
                font: 'var(--type-body-sm)',
                color: 'var(--text-dim)',
              }}
            >
              <span style={{ flex: 'none', display: 'flex', color: 'var(--yellow-100)' }}>
                <Icon name="timer" size={15} />
              </span>
              <span>
                Kechikish limiti {NO_SHOW_MIN} daqiqa — kelmasangiz bron to‘lovi qaytarilmaydi va
                hisobingiz kuzatuvga tushadi.
              </span>
            </div>
          ) : null}

          {booking.cancellable ? (
            <Button variant="ghost" block icon="close">
              Bekor qilish
            </Button>
          ) : null}
        </div>
      ))}
    </div>
  );
}
