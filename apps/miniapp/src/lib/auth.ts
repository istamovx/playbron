import { ApiError, signInWithInitData } from '@playbron/api-client';
import { useEffect, useState } from 'react';

import { useProfile } from '../store/app';
import { api } from './api';
import { webApp } from './telegram';

export type BootState = 'checking' | 'ready' | 'offline';

/**
 * Telegram ichida jimgina kirish.
 *
 * `initData` bo'lsa — server bilan sessiya ochiladi va profil to'ldiriladi, ya'ni
 * ro'yxatdan o'tish ekrani umuman ko'rinmaydi. Brauzerda `initData` yo'q, shuning
 * uchun mavjud lokal oqim o'zgarishsiz ishlaydi (dizayn muzlatilgan).
 *
 * Telefon bu yerda so'ralmaydi — u bot orqali `requestContact` bilan olinadi
 * (`docs/design-change-requests.md`, DCR-002).
 */
export function useTelegramAuth(): { state: BootState; error: string | null } {
  const [state, setState] = useState<BootState>('checking');
  const [error, setError] = useState<string | null>(null);

  const register = useProfile((current) => current.register);
  const signIn = useProfile((current) => current.signIn);

  useEffect(() => {
    const initData = webApp()?.initData;

    // Telegram tashqarisida — lokal rejim, hech narsa qilinmaydi
    if (!initData) {
      setState('ready');
      return;
    }

    let cancelled = false;

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
        setState('ready');
      } catch (cause) {
        if (cancelled) return;
        // Serversiz ham ilova ko'rinishi kerak — mock ma'lumot bilan davom etadi
        setError(cause instanceof ApiError ? cause.message : 'Serverga ulanib bo‘lmadi');
        setState('offline');
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [register, signIn]);

  return { state, error };
}
