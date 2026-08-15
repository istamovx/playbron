import {
  pollTelegramLink,
  startTelegramLink,
  type TelegramLinkStatus,
} from '@playbron/api-client';
import { Button, FieldLadder, FieldRow, Panel, StatusLine } from '@playbron/ui';
import { useEffect, useRef, useState, type ReactNode } from 'react';

import { api } from '../../lib/api';
import { useClub } from '../../store/club';
import { ROLE_LABEL, remainingText, useSession } from '../../store/session';

/** Ilova boti — `apps/landing/src/config.ts`dagi `appBot` bilan bir xil manba. */
const APP_BOT_URL = 'https://t.me/playbronappbot';

/** Poll oralig'i — nonce TTL (300s) ga nisbatan bemalol, foydalanuvchi botda
 * Start bosishga ulguradi. */
const POLL_INTERVAL_MS = 2000;

/**
 * Sozlamalar — klub adminining shaxsiy hisobi.
 *
 * Parol bloki yo'q: kirish faqat Telegram orqali (DCR-001), shuning uchun
 * almashtiriladigan parolning o'zi mavjud emas.
 */
export function SettingsScreen(): ReactNode {
  const session = useSession((state) => state.session);
  const signOut = useSession((state) => state.signOut);
  const resetClub = useClub((state) => state.reset);

  const [confirmReset, setConfirmReset] = useState(false);

  if (!session) return null;

  return (
    <div className="ds-split" style={{ alignItems: 'start' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)', minWidth: 0 }}>
        <Panel title="Hisob" notch brackets>
          <FieldLadder>
            <FieldRow label="Ism" value={session.name} />
            <FieldRow label="Kirish" value="Telegram" />
            <FieldRow label="Rol" value={ROLE_LABEL[session.role]} />
            <FieldRow label="Klublar" value={String(session.clubs.length)} />
            <FieldRow label="Sessiya tugashiga" value={remainingText(session.expiresAt)} />
          </FieldLadder>

          <div style={{ marginTop: 'var(--gap-block)' }}>
            <Button variant="secondary" icon="logout" onClick={signOut}>
              Chiqish
            </Button>
          </div>
        </Panel>

        <Panel title="Xavfsizlik" notch>
          <StatusLine
            tone="neutral"
            icon="verified_user"
            parts={[
              'Kirish faqat Telegram orqali',
              'Parol saqlanmaydi, o‘g‘irlanadigan sir yo‘q',
            ]}
          />
        </Panel>

        <TelegramLinkPanel />
      </div>

      <Panel title="Ma’lumotlar" notch dashed>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
          <StatusLine
            tone="neutral"
            icon="database"
            parts={['Klub ma’lumoti qurilmada saqlanadi', 'Server ulanganda sinxronlanadi']}
          />

          {confirmReset ? (
            <>
              <StatusLine
                tone="danger"
                icon="warning"
                parts={['Xona, tarif, mahsulot va xarajatlar', 'boshlang‘ich holatga qaytadi']}
              />
              <div style={{ display: 'flex', gap: 'var(--gap-tight)', flexWrap: 'wrap' }}>
                <Button
                  variant="danger"
                  notch
                  icon="restart_alt"
                  onClick={() => {
                    resetClub();
                    setConfirmReset(false);
                  }}
                >
                  Qaytarish
                </Button>
                <Button variant="ghost" onClick={() => setConfirmReset(false)}>
                  Bekor
                </Button>
              </div>
            </>
          ) : (
            <Button variant="ghost" icon="restart_alt" onClick={() => setConfirmReset(true)}>
              Boshlang‘ich holatga qaytarish
            </Button>
          )}
        </div>
      </Panel>
    </div>
  );
}

type LinkState = 'idle' | 'waiting' | 'ready' | 'expired' | 'error';

/**
 * Bron bildirishnomasi uchun xodimning o'z Telegram'ini ulashi.
 *
 * Naqsh — deep-link + poll (`botlogin.py`dagi bilan bir xil): nonce olinadi,
 * bot yangi bo'shliqda ochiladi (`t.me/...?start=<nonce>`), foydalanuvchi
 * botda **Start** bosgach konsol pollab natijani biladi. OAuth oynasi yo'q.
 *
 * Holat sahifa yangilanganda saqlanmaydi — server "ulanganmi" so'rovini
 * hozircha bermaydi (`GET /me` kengaymagan). Har safar qayta bosish
 * xavfsiz: bog'lash `ON CONFLICT (user_id) DO UPDATE`.
 */
function TelegramLinkPanel(): ReactNode {
  const [state, setState] = useState<LinkState>('idle');
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = (): void => {
    if (timer.current !== null) {
      clearInterval(timer.current);
      timer.current = null;
    }
  };

  useEffect(() => stopPolling, []);

  const start = async (): Promise<void> => {
    stopPolling();
    setState('waiting');
    try {
      const { nonce } = await startTelegramLink(api);
      window.open(`${APP_BOT_URL}?start=${nonce}`, '_blank', 'noopener');

      timer.current = setInterval(() => {
        void pollTelegramLink(api, nonce)
          .then((status: TelegramLinkStatus) => {
            if (status === 'pending') return;
            stopPolling();
            setState(status);
          })
          .catch(() => {
            stopPolling();
            setState('error');
          });
      }, POLL_INTERVAL_MS);
    } catch {
      setState('error');
    }
  };

  return (
    <Panel title="Bildirishnoma" notch>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
        <StatusLine
          tone="neutral"
          icon="notifications_active"
          parts={['Yangi bron kelganda Telegram botda xabar beriladi']}
        />

        {state === 'ready' ? (
          <StatusLine tone="ok" icon="check_circle" parts={['Ulandi']} />
        ) : state === 'expired' ? (
          <StatusLine tone="warn" icon="schedule" parts={['Havola eskirdi — qaytadan urining']} />
        ) : state === 'error' ? (
          <StatusLine tone="danger" icon="error" parts={['Ulanmadi — qaytadan urining']} />
        ) : null}

        <Button
          variant="secondary"
          icon="link"
          disabled={state === 'waiting'}
          onClick={() => void start()}
        >
          {state === 'waiting' ? 'Botda Start bosing…' : 'Telegram botga ulash'}
        </Button>
      </div>
    </Panel>
  );
}
