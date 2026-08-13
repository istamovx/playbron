import { Button, FieldLadder, FieldRow, Panel, StatusLine } from '@playbron/ui';
import { useState, type ReactNode } from 'react';

import { useClub } from '../../store/club';
import { ROLE_LABEL, remainingText, useSession } from '../../store/session';

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
