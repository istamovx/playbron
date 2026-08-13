import { useEffect, useState, type ReactNode } from 'react';

import { CLUB_TIMEZONE, formatDuration } from '../format';

/** Har sekundda yangilanadigan soat. */
function useTick(intervalMs = 1_000): number {
  const [tick, setTick] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setTick(Date.now()), intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs]);
  return tick;
}

export function ServerClock({ timeZone = CLUB_TIMEZONE }: { timeZone?: string }): ReactNode {
  const tick = useTick();
  const formatted = new Intl.DateTimeFormat('uz-UZ', {
    timeZone,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(new Date(tick));

  return (
    <div style={{ display: 'grid', justifyItems: 'end', gap: 2 }}>
      <span
        style={{
          font: 'var(--type-label)',
          letterSpacing: 'var(--ls-label)',
          textTransform: 'uppercase',
          color: 'var(--text-label)',
        }}
      >
        Klub vaqti
      </span>
      <span style={{ font: 'var(--type-data)', color: 'var(--text-title)' }}>{formatted}</span>
    </div>
  );
}

export type TimerTone = 'normal' | 'soon' | 'overtime';

export function toneForRemaining(remainingSeconds: number): TimerTone {
  if (remainingSeconds < 0) return 'overtime';
  if (remainingSeconds < 15 * 60) return 'soon';
  return 'normal';
}

const TIMER_COLOR: Record<TimerTone, string> = {
  normal: 'var(--text-title)',
  soon: 'var(--status-warn)',
  overtime: 'var(--status-danger)',
};

/**
 * Qolgan vaqt. Overtime manfiy vaqtni `+0:14:40` shaklida qizil ko'rsatadi,
 * 15 daqiqadan kam qolganda sariq.
 */
export function Countdown({ until }: { until: string | Date }): ReactNode {
  const tick = useTick();
  const target = typeof until === 'string' ? new Date(until) : until;
  const remaining = Math.round((target.getTime() - tick) / 1000);
  const tone = toneForRemaining(remaining);

  return (
    <span style={{ font: 'var(--type-data)', color: TIMER_COLOR[tone] }}>
      {formatDuration(remaining < 0 ? remaining : remaining)}
    </span>
  );
}

/** Sana/vaqt — `HH:MM`, klub mintaqasida. */
export function ClubTime({
  value,
  timeZone = CLUB_TIMEZONE,
  withDate = false,
}: {
  value: string | Date;
  timeZone?: string;
  withDate?: boolean;
}): ReactNode {
  const date = typeof value === 'string' ? new Date(value) : value;
  const formatted = new Intl.DateTimeFormat('uz-UZ', {
    timeZone,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    ...(withDate ? { day: '2-digit', month: '2-digit' } : {}),
  }).format(date);

  return <span style={{ font: 'var(--type-data)' }}>{formatted}</span>;
}
