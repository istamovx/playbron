import { useSyncExternalStore, type ReactNode } from 'react';

import { Icon } from './primitives';

/**
 * Global bildirishnoma navbati — zustand emas: `packages/ui` hech qanday
 * store kutubxonasiga bog'liq emas, `useSyncExternalStore` (React'ning
 * o'zi) yetarli. `toast.success(...)` HAR QAYERDAN (hodisa ishlovchisidan,
 * componentdan tashqari ham) chaqiriladi; `<ToastHost />` ildizda BIR
 * MARTA joylashadi.
 */

export type ToastTone = 'ok' | 'danger' | 'warn' | 'neutral';

interface ToastItem {
  id: number;
  tone: ToastTone;
  message: string;
}

let items: ToastItem[] = [];
let nextId = 1;
const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) listener();
}

const AUTO_DISMISS_MS = 4500;

function push(tone: ToastTone, message: string): void {
  const id = nextId;
  nextId += 1;
  items = [...items, { id, tone, message }];
  emit();
  setTimeout(() => {
    items = items.filter((item) => item.id !== id);
    emit();
  }, AUTO_DISMISS_MS);
}

export const toast = {
  success: (message: string): void => push('ok', message),
  error: (message: string): void => push('danger', message),
  warn: (message: string): void => push('warn', message),
  info: (message: string): void => push('neutral', message),
};

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot(): ToastItem[] {
  return items;
}

const ICON: Record<ToastTone, string> = {
  ok: 'check_circle',
  danger: 'error',
  warn: 'warning',
  neutral: 'info',
};

const COLOR: Record<ToastTone, string> = {
  ok: 'var(--secondary-500)',
  danger: 'var(--red-100)',
  warn: 'var(--yellow-100)',
  neutral: 'var(--text-dim)',
};

function dismiss(id: number): void {
  items = items.filter((item) => item.id !== id);
  emit();
}

/** Ilova ildizida BIR MARTA joylashadi (masalan `App()` ichida, eng tashqi div'da). */
export function ToastHost(): ReactNode {
  const list = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  if (list.length === 0) return null;

  return (
    <div
      style={{
        position: 'fixed',
        zIndex: 100,
        top: 16,
        right: 16,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        maxWidth: 'min(360px, calc(100vw - 32px))',
        pointerEvents: 'none',
      }}
    >
      {list.map((item) => (
        <div
          key={item.id}
          role="status"
          onClick={() => dismiss(item.id)}
          style={{
            pointerEvents: 'auto',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'flex-start',
            gap: 8,
            padding: '10px 12px',
            background: 'var(--surface-pop)',
            border: `1px solid ${COLOR[item.tone]}`,
            boxShadow: 'var(--shadow-pop)',
            clipPath: 'var(--clip-tr)',
          }}
        >
          <span style={{ flex: 'none', color: COLOR[item.tone], display: 'flex', marginTop: 1 }}>
            <Icon name={ICON[item.tone]} size={16} />
          </span>
          <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-body)' }}>
            {item.message}
          </span>
        </div>
      ))}
    </div>
  );
}
