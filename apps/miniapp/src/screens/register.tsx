import { Button, StatusLine, TextField } from '@playbron/ui';
import { useState, type ReactNode } from 'react';

import { useProfile } from '../store/app';

/**
 * Bir martalik ro'yxatdan o'tish. Mijoz keyin hech qachon qayta kirmaydi —
 * profil qurilmada saqlanadi (`playbron.customer`).
 */
export function RegisterScreen(): ReactNode {
  const register = useProfile((state) => state.register);
  const profile = useProfile((state) => state.profile);
  const signIn = useProfile((state) => state.signIn);
  const forget = useProfile((state) => state.forget);
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('+998');
  const [error, setError] = useState<string | null>(null);

  // Profildan chiqilgan, lekin hisob qurilmada qolgan — bir bosishda qaytiladi
  if (profile) {
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
          <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-muted)' }}>
            Hisobingiz saqlanib qoldi — qayta ro‘yxatdan o‘tish shart emas.
          </span>
        </div>

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

        <Button variant="primary" size="lg" notch block icon="login" onClick={signIn}>
          Kirish
        </Button>

        <Button variant="ghost" size="lg" block icon="person_add" onClick={forget}>
          Boshqa raqam bilan
        </Button>
      </div>
    );
  }

  const submit = (): void => {
    if (name.trim().length < 2) {
      setError('Ismingizni kiriting');
      return;
    }
    if (!/^\+998\d{9}$/.test(phone.replace(/[\s()-]/g, ''))) {
      setError('Telefon +998XXXXXXXXX shaklida bo‘lishi kerak');
      return;
    }
    setError(null);
    register({ name: name.trim(), phone: phone.replace(/[\s()-]/g, '') });
  };

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
        <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-muted)' }}>
          Bir marta ro‘yxatdan o‘tasiz — keyingi safar to‘g‘ridan-to‘g‘ri kirasiz.
        </span>
      </div>

      <TextField label="Ism" value={name} onChange={setName} icon="person" placeholder="Jasur" />
      <TextField
        label="Telefon"
        value={phone}
        onChange={setPhone}
        icon="call"
        inputMode="tel"
        onSubmitKey={submit}
      />

      {error ? <StatusLine tone="danger" icon="error" parts={error} /> : null}

      <Button variant="primary" size="lg" notch block icon="check" onClick={submit}>
        Davom etish
      </Button>

      <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
        Ma’lumotlaringiz faqat bron va bildirishnoma uchun ishlatiladi.
      </span>
    </div>
  );
}
