import { ApiError, signInWithInitData } from '@playbron/api-client';
import { useCallback, useEffect, useState } from 'react';

import { useProfile } from '../store/app';
import { api } from './api';
import { webApp } from './telegram';

/**
 * `no_telegram`   — `initData` yo'q: bot tashqarisida ochilgan, hech qanday
 *                    shaxsni tasdiqlash yo'li yo'q.
 * `offline`       — `initData` bor, lekin serverga ulanish/kirish
 *                    muvaffaqiyatsiz (tarmoq, server vaqtincha o'chgan).
 * `authenticated` — kirish muvaffaqiyatli, profil serverdan keldi.
 */
export type BootState = 'checking' | 'authenticated' | 'no_telegram' | 'offline';

/**
 * Telegram ichida JIMGINA kirish — qo'lda forma YO'Q.
 *
 * Ism va telefon mijozdan BIR MARTA, botda so'raladi (`modules/bot/customer.py`,
 * `requestContact` — DCR-002). Mini App shu ma'lumotni `initData` orqali oladi,
 * qayta so'ramaydi: ikkinchi (mahalliy, serversiz) forma faqat chalkashlik va
 * ishonchsiz nusxa yaratardi — mijoz haqiqatan kim ekanini FAQAT server biladi.
 */
export function useTelegramAuth(): {
  state: BootState;
  error: string | null;
  retry: () => void;
} {
  const [state, setState] = useState<BootState>('checking');
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  const register = useProfile((current) => current.register);
  const signIn = useProfile((current) => current.signIn);

  useEffect(() => {
    const initData = webApp()?.initData;

    if (!initData) {
      setState('no_telegram');
      return;
    }

    let cancelled = false;
    setState('checking');
    setError(null);

    void (async () => {
      try {
        const session = await signInWithInitData(api, initData);
        if (cancelled) return;

        const name = [session.user.first_name, session.user.last_name]
          .filter(Boolean)
          .join(' ')
          .trim();

        register({ name: name || 'Mijoz', phone: session.user.phone ?? '' });
        signIn();
        setState('authenticated');
      } catch (cause) {
        if (cancelled) return;
        setError(cause instanceof ApiError ? cause.message : 'Serverga ulanib bo‘lmadi');
        setState('offline');
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [register, signIn, attempt]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  return { state, error, retry };
}
