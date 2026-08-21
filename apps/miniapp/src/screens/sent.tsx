import { Panel, StatusLine } from '@playbron/ui';
import type { ReactNode } from 'react';

import { useT } from '../i18n';
import { useBooking } from '../store/booking';

/**
 * Bron yuborilgandan keyingi holat: "tasdiq kutilmoqda". To'lovsiz oqimda
 * (Bosqich 1) darhol kirish huquqi yo'q — xodim tasdiqlashi kerak.
 */
export function SentScreen(): ReactNode {
  const t = useT();
  const booking = useBooking((s) => s.lastBooking);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <Panel title={t('sentTitle')} notch glow>
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
            alignItems: 'center',
            padding: '8px 0',
          }}
        >
          <span
            style={{
              font: 'var(--fs-2xl) var(--fw-bold)/1 var(--font-display)',
              color: 'var(--text-title)',
            }}
          >
            {booking ? `#${booking.id}` : '—'}
          </span>
          <span
            style={{
              font: 'var(--type-body-sm)',
              color: 'var(--text-muted)',
              textAlign: 'center',
            }}
          >
            {t('sentHint')}
          </span>
        </div>
      </Panel>

      <StatusLine tone="warn" icon="pending" parts={[t('sentStatus'), t('sentWhere')]} />
    </div>
  );
}
