import { Button } from '@playbron/ui';
import type { CSSProperties, ReactNode } from 'react';

/**
 * CRUD formalari uchun moslashuvchan to'r — tor ekranda bir ustunga tushadi.
 *
 * `gap` ixtiyoriy — sukut `--gap-block` (16px). Markazda chiquvchi kichik
 * modallar (4 talik forma: xodim, xona, to'lov) elementlar yopishib
 * qolmasligi uchun `--gap-panel` (24px) bilan chaqiradi — token, hardcode
 * qiymat emas (loyiha egasining topilmasi, 2026-08-16).
 */
export function FormGrid({
  children,
  gap = 'var(--gap-block)',
}: {
  children: ReactNode;
  gap?: string;
}): ReactNode {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(min(200px, 100%), 1fr))',
        gap,
        alignItems: 'end',
      }}
    >
      {children}
    </div>
  );
}

/**
 * `Select` ustidagi yorliq — `TextField` bilan bir xil ko'rinishda.
 * DS'dagi `Select` ning o'zida yorliq yo'q, shuning uchun forma qatorlari
 * tekis turishi uchun shu o'ram ishlatiladi.
 */
export function Labeled({ label, children }: { label: string; children: ReactNode }): ReactNode {
  return (
    <span style={{ display: 'grid', gap: 6, minWidth: 0 }}>
      <span
        style={{
          font: 'var(--type-label)',
          letterSpacing: 'var(--ls-label)',
          textTransform: 'uppercase',
          color: 'var(--text-label)',
        }}
      >
        {label}
      </span>
      {children}
    </span>
  );
}

/** Jadval qatoridagi tahrirlash va o'chirish tugmalari. */
export function RowActions({
  onEdit,
  onRemove,
}: {
  onEdit: () => void;
  onRemove: () => void;
}): ReactNode {
  return (
    <span style={{ display: 'inline-flex', gap: 4, justifyContent: 'flex-end' }}>
      <Button variant="ghost" size="sm" icon="edit" onClick={onEdit}>
        Tahrir
      </Button>
      <Button variant="ghost" size="sm" icon="delete" onClick={onRemove}>
        O‘chirish
      </Button>
    </span>
  );
}

/** Panel ichidagi ajratgich — forma bilan ro'yxat orasida. */
export function Divider(): ReactNode {
  return <div style={{ height: 1, background: 'var(--line-1)', margin: 'var(--gap-block) 0' }} />;
}

export const CARD: CSSProperties = {
  padding: 'var(--card-pad)',
  background: 'var(--surface-card)',
  border: '1px solid var(--line-1)',
  display: 'flex',
  flexDirection: 'column',
  gap: 6,
  minWidth: 0,
};

export const LABEL: CSSProperties = {
  font: 'var(--type-label)',
  letterSpacing: 'var(--ls-label)',
  textTransform: 'uppercase',
  color: 'var(--text-label)',
};

export const VALUE: CSSProperties = {
  font: 'var(--type-data)',
  color: 'var(--text-title)',
  whiteSpace: 'nowrap',
};

/** `19:30` — daqiqadan. */
export const hm = (minutes: number): string =>
  `${String(Math.floor(minutes / 60) % 24).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;

/** `19:30` → 1170. Noto'g'ri format bo'lsa `null`. */
export function parseHm(value: string): number | null {
  const match = /^(\d{1,2}):(\d{2})$/.exec(value.trim());
  if (!match) return null;
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  if (hours > 26 || minutes > 59) return null;
  return hours * 60 + minutes;
}

/**
 * Joriy soat 10:00 dan boshlanadigan oynada nechanchi ustunga tushadi.
 * Oyna tashqarisida (02:00–10:00) `undefined` — urg'u ko'rsatilmaydi.
 */
export function hourSlot(bars: number, windowHours = 16): number | undefined {
  const hour = new Date().getHours() + new Date().getMinutes() / 60;
  const offset = hour >= 10 ? hour - 10 : hour + 14;
  if (offset < 0 || offset >= windowHours) return undefined;
  return Math.min(bars - 1, Math.floor((offset / windowHours) * bars));
}

/** Bugungi sana — `DD-MM-YYYY`. */
export function today(): string {
  const now = new Date();
  return `${String(now.getDate()).padStart(2, '0')}-${String(now.getMonth() + 1).padStart(2, '0')}-${now.getFullYear()}`;
}
