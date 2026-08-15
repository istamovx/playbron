import { Button, StatusLine } from '@playbron/ui';
import type { ReactNode } from 'react';

import type { BootState } from '../lib/auth';
import { useProfile } from '../store/app';

/**
 * Kirish qo'lda emas — bu ekran ikki holatni ko'rsatadi, forma yo'q:
 *
 *   `no_telegram` — bot tashqarisida ochilgan (`initData` yo'q). Bu holat
 *                    to'g'ri oqimda umuman YUZ BERMASLIGI kerak: ilova
 *                    FAQAT botning "Ilovani ochish" tugmasi orqali ochiladi
 *                    (`modules/bot/customer.py::_send_open_app`), u esa
 *                    haqiqiy `initData` bilan keladi. Shu sabab bu yerda
 *                    hech qanday CTA yo'q — faqat neytral holat, chalkash
 *                    "botni oching" havolasi mijozni ikkinchi marta
 *                    botga qaytarib yubormaydi.
 *   `offline`     — `initData` bor (botdan to'g'ri ochilgan), lekin kirish
 *                    vaqtincha muvaffaqiyatsiz (tarmoq/server) — bu HAQIQIY
 *                    holat, qayta urinish tugmasi qoladi.
 */
export function BootScreen({ state, error, onRetry }: { state: BootState; error: string | null; onRetry: () => void }): ReactNode {
  const profile = useProfile((current) => current.profile);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--gap-panel)',
        justifyContent: 'center',
        minHeight: '100%',
      }}
    >
      <div style={{ display: 'grid', gap: 6 }}>
        <span
          style={{
            font: 'var(--fw-bold) var(--fs-2xl)/1.1 var(--font-display)',
            color: 'var(--text-title)',
          }}
        >
          PLAYBRON
        </span>
      </div>

      {state === 'no_telegram' ? null : (
        <>
          {profile ? (
            <div
              style={{
                padding: 'var(--card-pad)',
                background: 'var(--surface-card)',
                border: '1px solid var(--line-1)',
                clipPath: 'var(--clip-tr)',
                display: 'flex',
                alignItems: 'center',
                gap: 12,
              }}
            >
              <span
                style={{
                  flex: 'none',
                  width: 44,
                  height: 44,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: 'var(--surface-selected)',
                  border: '1px solid var(--primary-100)',
                  clipPath: 'var(--clip-tr)',
                  font: 'var(--fw-medium) var(--fs-xl)/1 var(--font-display)',
                  color: 'var(--text-title)',
                }}
              >
                {profile.name.trim().charAt(0).toLocaleUpperCase('uz-UZ')}
              </span>
              <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
                <span style={{ font: 'var(--type-section)', color: 'var(--text-title)' }}>
                  {profile.name}
                </span>
                <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-muted)' }}>
                  {profile.phone}
                </span>
              </div>
            </div>
          ) : null}

          <StatusLine tone="danger" icon="wifi_off" parts={[error ?? 'Ulanib bo‘lmadi']} />

          <Button variant="primary" size="lg" notch block icon="refresh" onClick={onRetry}>
            Qayta urinish
          </Button>
        </>
      )}
    </div>
  );
}
