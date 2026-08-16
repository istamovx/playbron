import { errorText, getPlatformStats, type PlatformStatsDto } from '@playbron/api-client';
import { EntityTable, LineChart, Panel, StatTile, StatusLine } from '@playbron/ui';
import { useEffect, useState, type ReactNode } from 'react';

import { api } from '../lib/api';
import { S } from '../mock/data';

const TREND_DAYS = 14;

function shortDate(iso: string): string {
  const [, m, d] = iso.split('-');
  return `${d}.${m}`;
}

/** So'nggi `TREND_DAYS` kunning ketma-ket ro'yxati (bo'sh kunlar 0 bilan). */
function lastDays(n: number): string[] {
  const out: string[] = [];
  const now = new Date();
  for (let i = n - 1; i >= 0; i -= 1) {
    const day = new Date(now);
    day.setDate(day.getDate() - i);
    out.push(day.toISOString().slice(0, 10));
  }
  return out;
}

/**
 * Platforma paneli — super admin uchun cross-tenant statistika (faqat
 * o'qish). Manba: `docs/06-super-admin.md` §3, kichik kesim
 * (`0015_platform_stats.py`). Glass rejimi, TOTP, tashkilotlar boshqaruvi,
 * billing, CMS — hujjatning katta qismi, hali qurilmagan (alohida bosqich).
 */
export function PlatformScreen(): ReactNode {
  const [stats, setStats] = useState<PlatformStatsDto | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void getPlatformStats(api)
      .then((data) => {
        if (!cancelled) setStats(data);
      })
      .catch((cause: unknown) => {
        if (!cancelled) setError(errorText(cause));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return <StatusLine tone="danger" icon="error" parts={[error]} />;
  }

  const days = lastDays(TREND_DAYS);
  const trendValues = days.map((day) => stats?.dailyTrend[day] ?? 0);
  // Har bir nuqta ostida joy ajratiladi — bandlashib ketmasligi uchun
  // faqat juft indekslarga sana yoziladi, qolganlari bo'sh.
  const ticks = days.map((day, index) => (index % 2 === 0 ? shortDate(day) : ''));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <div className="pb-tiles-4">
        <StatTile
          label="Jami tashkilotlar"
          value={stats ? String(stats.organizationsTotal) : '—'}
          icon="corporate_fare"
        />
        <StatTile
          label="Faol klublar"
          value={stats ? String(stats.clubsActive) : '—'}
          unit={stats && stats.clubsDraft > 0 ? `+${stats.clubsDraft} draft` : undefined}
          icon="storefront"
        />
        <StatTile
          label="Bugungi bronlar"
          value={stats ? String(stats.bookingsToday) : '—'}
          icon="event_available"
        />
        <StatTile
          label="Shu oy bronlar"
          value={stats ? String(stats.bookingsThisMonth) : '—'}
          icon="calendar_month"
        />
      </div>

      <Panel
        title="Klublar aylanmasi"
        notch
        brackets
        action={
          <span
            style={{
              font: 'var(--type-label)',
              letterSpacing: 'var(--ls-label)',
              textTransform: 'uppercase',
              color: 'var(--text-dim)',
            }}
          >
            Platforma tushumi emas
          </span>
        }
      >
        {/* Bu klublarning bron summasi — platformaning o'z obuna/tushumi
            EMAS (`docs/06-super-admin.md` §5.1). Platformada hali
            subscriptions/to'lov tizimi yo'q. */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
          <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
            <FieldStat label="Bugun" value={stats ? `${S(stats.revenueToday)} so‘m` : '—'} />
            <FieldStat
              label="Shu oy"
              value={stats ? `${S(stats.revenueThisMonth)} so‘m` : '—'}
            />
          </div>
          <div className="ds-chart">
            <LineChart
              points={TREND_DAYS}
              values={trendValues}
              labels={ticks}
              height={264}
              tip={(value, index) => `${shortDate(days[index] as string)} · ${Math.round(value)} bron`}
            />
          </div>
        </div>
      </Panel>

      <Panel title="Eng faol klublar (30 kun)" notch brackets>
        <EntityTable
          rows={stats?.topClubs ?? []}
          rowKey={(row) => String(row.clubId)}
          empty={loading ? 'Yuklanmoqda…' : 'Hali bron yo‘q'}
          columns={[
            {
              key: 'club',
              header: 'Klub',
              render: (row) => (
                <span style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
                  <span style={{ color: 'var(--text-title)' }}>{row.clubName}</span>
                  <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                    {row.orgName}
                  </span>
                </span>
              ),
            },
            {
              key: 'bookings',
              header: 'Bronlar',
              align: 'right',
              render: (row) => (
                <span style={{ font: 'var(--type-data)', color: 'var(--text-title)' }}>
                  {row.bookings}
                </span>
              ),
            },
          ]}
        />
      </Panel>
    </div>
  );
}

function FieldStat({ label, value }: { label: string; value: string }): ReactNode {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
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
      <span style={{ font: 'var(--type-data)', color: 'var(--text-title)' }}>{value}</span>
    </div>
  );
}
