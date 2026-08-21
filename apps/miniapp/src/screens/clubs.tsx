import { Button, CyberLoaderOverlay, EmptyState, Icon, StatusLine } from '@playbron/ui';
import type { ReactNode } from 'react';
import { useEffect } from 'react';

import { MapButton } from '../components/map-button';
import { useT } from '../i18n';
import { hhmm } from '../lib/format';
import { useApp } from '../store/app';
import { useBooking } from '../store/booking';

/**
 * Klublar ro'yxati — real katalog (`GET /clubs`).
 *
 * RASM YO'Q. Avval har kartaning tepasida 96px balandlikdagi "Klub rasmi"
 * plasholderi turardi — hech qachon to'lmaydigan bo'sh quti edi. Loyiha
 * egasining talabi (2026-08-17): asosiy menyuda klub NOMI, MANZILI, ISH
 * VAQTI va xaritani ochadigan faqat-belgili tugma bo'lsin.
 *
 * Reyting/masofa/narx-taxmin ham ko'rsatilmaydi — backend'da geo va sharh
 * tizimi yo'q, yolg'on son ko'rsatishdan ko'ra ko'rsatmaslik ma'qul.
 */
export function ClubsScreen(): ReactNode {
  const t = useT();
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

  if (loading && clubs.length === 0) return <CyberLoaderOverlay label={t('loading')} />;

  if (error) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
        <StatusLine tone="danger" icon="wifi_off" parts={[error]} />
        <Button variant="primary" size="lg" notch block icon="refresh" onClick={() => void loadClubs()}>
          {t('retry')}
        </Button>
      </div>
    );
  }

  if (clubs.length === 0) {
    return (
      <EmptyState icon="storefront" title={t('clubsEmptyTitle')}>
        {t('clubsEmptyHint')}
      </EmptyState>
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
            padding: 'var(--card-pad)',
            background: 'var(--surface-panel)',
            border: '1px solid var(--line-1)',
            clipPath: 'var(--clip-tr)',
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--gap-tight)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
            <span
              style={{
                flex: 1,
                minWidth: 0,
                font: 'var(--fw-medium) var(--fs-lg)/1.2 var(--font-display)',
                color: 'var(--text-title)',
              }}
            >
              {club.name}
            </span>
            <MapButton club={club} />
          </div>

          <InfoLine icon="location_on" text={club.address || t('addressMissing')} />
          <InfoLine icon="schedule" text={`${hhmm(club.opensAtMin)} – ${hhmm(club.closesAtMin)}`} />
        </div>
      ))}
    </div>
  );
}

function InfoLine({ icon, text }: { icon: string; text: string }): ReactNode {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7, minWidth: 0 }}>
      <Icon name={icon} size={15} color="var(--text-dim)" />
      <span
        style={{
          minWidth: 0,
          font: 'var(--type-body-sm)',
          color: 'var(--text-muted)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {text}
      </span>
    </div>
  );
}
