import type { ReactNode } from 'react';
import { useEffect } from 'react';

import { useApp } from '../store/app';
import { useBooking } from '../store/booking';

/**
 * Klublar ro'yxati — real katalog (`GET /clubs`).
 *
 * Mock prototipida reyting/masofa/narx-taxmin bor edi — backend'da hali yo'q
 * (geo va sharh tizimi qurilmagan), shuning uchun ATAYLAB ko'rsatilmaydi:
 * yolg'on son ko'rsatishdan ko'ra ko'rsatmaslik ma'qul.
 */
export function ClubsScreen(): ReactNode {
  const clubs = useBooking((state) => state.clubs);
  const loading = useBooking((state) => state.clubsLoading);
  const error = useBooking((state) => state.clubsError);
  const loadClubs = useBooking((state) => state.loadClubs);
  const setClubId = useApp((state) => state.setClubId);
  const go = useApp((state) => state.go);

  useEffect(() => {
    void loadClubs();
  }, [loadClubs]);

  const open = (id: number): void => {
    setClubId(id);
    go('club');
  };

  if (error) {
    return (
      <div style={{ font: 'var(--type-body-sm)', color: 'var(--red-100)' }}>{error}</div>
    );
  }

  if (!loading && clubs.length === 0) {
    return (
      <div style={{ font: 'var(--type-body-sm)', color: 'var(--text-muted)' }}>
        Hozircha faol klub yo‘q.
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      {clubs.map((club) => (
        <div
          key={club.id}
          role="button"
          tabIndex={0}
          onClick={() => open(club.id)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') open(club.id);
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
          </div>

          <div
            style={{
              padding: 'var(--card-pad)',
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--gap-tight)',
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

            {club.address ? (
              <div style={{ font: 'var(--type-body-sm)', color: 'var(--text-muted)' }}>
                {club.address}
              </div>
            ) : null}
          </div>
        </div>
      ))}
    </div>
  );
}
