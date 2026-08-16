import { errorText } from '@playbron/api-client';
import { Button, FieldLadder, FieldRow, Panel, StatusLine, TextField, toast } from '@playbron/ui';
import { useState, type ReactNode } from 'react';

import { ROLE_LABEL, remainingText, useSession } from '../store/session';

/** Super admin/egasi parolining eng qisqa uzunligi — `login.tsx`dagi `OWNER_PASSWORD_MIN` bilan bir xil. */
const PASSWORD_MIN = 14;

/**
 * Sozlamalar — super adminning shaxsiy hisobi.
 *
 * Klub adminining `admin/settings.tsx`siga o'xshaydi, lekin bitta farq bilan:
 * super admin login va parol bilan kiradi (Telegram emas), shuning uchun
 * bu yerda parolni almashtirish paneli bor.
 */
export function PlatformSettingsScreen(): ReactNode {
  const session = useSession((state) => state.session);
  const signOut = useSession((state) => state.signOut);

  if (!session) return null;

  return (
    <div className="ds-split" style={{ alignItems: 'start' }}>
      <Panel title="Hisob" notch brackets>
        <FieldLadder>
          <FieldRow label="Ism" value={session.name} />
          <FieldRow label="Kirish" value="Login va parol" />
          <FieldRow label="Login" value={session.login ?? '—'} />
          <FieldRow label="Rol" value={ROLE_LABEL[session.role]} />
          <FieldRow label="Sessiya tugashiga" value={remainingText(session.expiresAt)} />
        </FieldLadder>

        <div style={{ marginTop: 'var(--gap-block)' }}>
          <Button variant="secondary" icon="logout" onClick={signOut}>
            Chiqish
          </Button>
        </div>
      </Panel>

      <PasswordPanel />
    </div>
  );
}

/** Parolni almashtirish — ixtiyoriy, majburiy almashtirish `login.tsx`dagi `ChangePanel` bilan bir xil chaqiruvni ishlatadi. */
function PasswordPanel(): ReactNode {
  const changePassword = useSession((state) => state.changePassword);

  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (): Promise<void> => {
    if (next.length < PASSWORD_MIN) {
      setError(`Yangi parol kamida ${PASSWORD_MIN} belgi bo‘lsin`);
      return;
    }
    if (next !== confirm) {
      setError('Parollar mos kelmadi');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await changePassword(current, next);
      setCurrent('');
      setNext('');
      setConfirm('');
      toast.success('Parol almashtirildi');
    } catch (cause) {
      const message = errorText(cause);
      setError(message);
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Panel title="Parolni almashtirish" notch>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
        <TextField
          label="Joriy parol"
          value={current}
          onChange={setCurrent}
          type="password"
          revealable
          icon="lock"
          autoComplete="current-password"
          disabled={submitting}
        />
        <TextField
          label="Yangi parol"
          value={next}
          onChange={setNext}
          type="password"
          revealable
          icon="lock_reset"
          autoComplete="new-password"
          disabled={submitting}
        />
        <TextField
          label="Yangi parolni takrorlang"
          value={confirm}
          onChange={setConfirm}
          type="password"
          revealable
          icon="lock_reset"
          autoComplete="new-password"
          disabled={submitting}
          onSubmitKey={() => void submit()}
        />

        <Button
          variant="primary"
          notch
          icon="check"
          disabled={submitting || !current || !next || !confirm}
          onClick={() => void submit()}
        >
          {submitting ? 'Saqlanmoqda…' : 'Almashtirish'}
        </Button>

        {error ? <StatusLine tone="danger" icon="error" parts={[error]} /> : null}
      </div>
    </Panel>
  );
}
