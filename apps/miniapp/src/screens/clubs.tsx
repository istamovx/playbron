import { Chip, Icon } from '@playbron/ui';
import type { ReactNode } from 'react';

import { CLUBS, SORT_CHIPS } from '../mock/data';
import { useApp } from '../store/app';

/** Klublar ro'yxati — `PlayBron Mijoz.dc.html` KLUBLAR ekrani. */
export function ClubsScreen(): ReactNode {
  const sort = useApp((state) => state.sort);
  const setSort = useApp((state) => state.setSort);
  const go = useApp((state) => state.go);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <div style={{ display: 'flex', gap: 6, overflow: 'auto', paddingBottom: 2 }}>
        {SORT_CHIPS.map((label) => (
          <span key={label} style={{ flex: 'none', whiteSpace: 'nowrap' }}>
            <Chip selected={sort === label} onClick={() => setSort(label)}>
              {label}
            </Chip>
          </span>
        ))}
      </div>

      {CLUBS.map((club) => {
        const tone = club.free ? 'var(--slot-free)' : 'var(--red-100)';

        return (
          <div
            key={club.id}
            role="button"
            tabIndex={0}
            onClick={() => go('club')}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') go('club');
            }}
            style={{
              cursor: 'pointer',
              background: 'var(--surface-panel)',
              border: '1px solid var(--line-1)',
              clipPath: 'var(--clip-tr)',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                height: 96,
                background: 'var(--surface-inset)',
                borderBottom: '1px solid var(--line-1)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                position: 'relative',
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
                Klub rasmi
              </span>
              <span
                style={{
                  position: 'absolute',
                  top: 8,
                  left: 8,
                  padding: '4px 8px',
                  whiteSpace: 'nowrap',
                  background: 'var(--surface-pop)',
                  border: `1px solid ${tone}`,
                  font: 'var(--type-label)',
                  letterSpacing: 'var(--ls-label)',
                  textTransform: 'uppercase',
                  color: tone,
                }}
              >
                {club.free ? `${club.free} joy bo‘sh` : 'Joy yo‘q'}
              </span>
            </div>

            <div
              style={{
                padding: 'var(--card-pad)',
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--gap-tight)',
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
                <span
                  style={{
                    font: 'var(--fw-medium) var(--fs-lg)/1.2 var(--font-display)',
                    color: 'var(--text-title)',
                  }}
                >
                  {club.name}
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
                  {club.rating}
                </span>
              </div>

              <div style={{ font: 'var(--type-body-sm)', color: 'var(--text-muted)' }}>
                {club.addr}
              </div>

              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 8,
                  paddingTop: 8,
                  borderTop: '1px solid var(--line-1)',
                }}
              >
                <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                  {club.dist}
                </span>
                <span style={{ font: 'var(--type-data)', color: 'var(--text-title)' }}>
                  {club.price}
                </span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
