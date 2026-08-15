import { Panel, StatusLine } from '@playbron/ui';
import type { ReactNode } from 'react';

import { useBooking } from '../store/booking';

/**
 * Bron yuborilgandan keyingi holat — `ScreenId` da hali `'qr'` (kirishdagi
 * navigatsiya/tab xaritasini o'zgartirmaslik uchun), lekin mazmuni endi
 * "tasdiq kutilmoqda": to'lovsiz oqimda (Bosqich 1) darhol kirish huquqi
 * yo'q, xodim tasdiqlashi kerak.
 */
export function SentScreen(): ReactNode {
  const booking = useBooking((s) => s.lastBooking);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <Panel title="Bron yuborildi" notch glow>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'center', padding: '8px 0' }}>
          <span style={{ font: 'var(--fs-2xl) var(--fw-bold)/1 var(--font-display)', color: 'var(--text-title)' }}>
            #{booking?.id ?? '—'}
          </span>
          <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-muted)', textAlign: 'center' }}>
            Xodim tasdiqlagach botga xabar keladi
          </span>
        </div>
      </Panel>

      <StatusLine
        tone="warn"
        icon="pending"
        parts={['Holat: kutilmoqda', 'Tasdiqlangach shu yerda ko‘rinadi']}
      />
    </div>
  );
}
