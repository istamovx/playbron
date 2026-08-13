import { Icon, Panel, Tag } from '@playbron/ui';
import type { ReactNode } from 'react';

import { CLUB_DESC, REVIEWS, clubRooms, clubTags } from '../mock/data';
import { useNow } from '../store/app';

/** Klub sahifasi — `PlayBron Mijoz.dc.html` KLUB ekrani. */
export function ClubScreen(): ReactNode {
  const nowMin = Math.floor(useNow() / 60);
  const rooms = clubRooms(nowMin);
  const tags = clubTags();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <div
        style={{
          height: 150,
          background: 'var(--surface-inset)',
          border: '1px solid var(--line-1)',
          clipPath: 'var(--clip-tr)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <span
          style={{
            font: 'var(--type-label)',
            letterSpacing: 'var(--ls-label)',
            textTransform: 'uppercase',
            color: 'var(--text-dim)',
          }}
        >
          Klub galereyasi
        </span>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {tags.map((tag) => (
          <Tag key={tag.label} tone={tag.tone}>
            {tag.label}
          </Tag>
        ))}
      </div>

      <div style={{ font: 'var(--type-body)', color: 'var(--text-body)' }}>{CLUB_DESC}</div>

      <Panel title="Xonalar va narxlar" notch>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {rooms.map((room) => (
            <div
              key={room.name}
              style={{
                padding: 'var(--card-pad)',
                background: 'var(--surface-card)',
                border: '1px solid var(--line-1)',
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
              }}
            >
              {/* Tor ekranda narx pastki qatorga tushadi — xona nomi sinmaydi */}
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
                  {room.name}
                </span>
                <span
                  style={{
                    font: 'var(--type-data)',
                    color: 'var(--purple-100)',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {room.price}
                </span>
              </div>

              <div style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                {room.spec}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div
                  style={{
                    flex: 1,
                    height: 3,
                    background: 'var(--chart-track)',
                    position: 'relative',
                  }}
                >
                  <div
                    className="pb-fill"
                    style={{
                      position: 'absolute',
                      inset: '0 auto 0 0',
                      width: room.pct,
                      background:
                        parseInt(room.pct, 10) >= 100
                          ? 'var(--red-100)'
                          : parseInt(room.pct, 10) >= 70
                            ? 'var(--yellow-100)'
                            : 'var(--secondary-500)',
                    }}
                  />
                </div>
                <span
                  style={{
                    font: 'var(--type-data-xs)',
                    color: 'var(--text-muted)',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {room.free}
                </span>
              </div>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="Sharhlar (86)" notch>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {REVIEWS.map((review) => (
            <div
              key={review.name}
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 5,
                paddingBottom: 10,
                borderBottom: '1px solid var(--line-1)',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'baseline',
                  justifyContent: 'space-between',
                  gap: 8,
                }}
              >
                <span style={{ font: 'var(--type-section)', color: 'var(--text-title)' }}>
                  {review.name}
                </span>
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    font: 'var(--type-data)',
                    color: 'var(--yellow-100)',
                    whiteSpace: 'nowrap',
                  }}
                >
                  <Icon name="star" size={13} />
                  {review.rating}
                </span>
              </div>

              <div style={{ font: 'var(--type-body-sm)', color: 'var(--text-muted)' }}>
                {review.text}
              </div>

              <div style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                {review.date}
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
