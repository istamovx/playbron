import {
  errorText,
  getPlatformReport,
  type PlatformReportDto,
  type PlatformReportPeriod,
} from '@playbron/api-client';
import { ActivityBars, Panel, SegmentedControl, StatTile, StatusLine } from '@playbron/ui';
import { useEffect, useState, type ReactNode } from 'react';

import { api } from '../lib/api';
import { S } from '../mock/data';

/** Backend `PERIOD_UNITS` bilan bir xil — har davr uchun necha chelak orqaga qaraladi. */
const LOOKBACK: Record<PlatformReportPeriod, number> = {
  day: 30,
  week: 12,
  month: 12,
  year: 5,
};

const PERIOD_OPTIONS: { id: PlatformReportPeriod; label: string }[] = [
  { id: 'day', label: 'Kunlik' },
  { id: 'week', label: 'Haftalik' },
  { id: 'month', label: 'Oylik' },
  { id: 'year', label: 'Yillik' },
];

function toIsoDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/** So'nggi `n` kunning ketma-ket ro'yxati (bugungi kun bilan tugaydi). */
function lastDays(n: number): string[] {
  const out: string[] = [];
  const now = new Date();
  for (let i = n - 1; i >= 0; i -= 1) {
    const day = new Date(now);
    day.setDate(day.getDate() - i);
    out.push(toIsoDate(day));
  }
  return out;
}

/** Dushanba bilan boshlanadigan hafta boshi (ISO hafta). */
function weekStart(date: Date): Date {
  const start = new Date(date);
  const shift = (start.getDay() + 6) % 7;
  start.setDate(start.getDate() - shift);
  return start;
}

/** So'nggi `n` haftaning boshlanish sanalari — dushanba, joriy hafta bilan tugaydi. */
function lastWeeks(n: number): string[] {
  const out: string[] = [];
  const currentStart = weekStart(new Date());
  for (let i = n - 1; i >= 0; i -= 1) {
    const start = new Date(currentStart);
    start.setDate(start.getDate() - i * 7);
    out.push(toIsoDate(start));
  }
  return out;
}

/** So'nggi `n` oyning 1-sanalari — joriy oy bilan tugaydi. */
function lastMonths(n: number): string[] {
  const out: string[] = [];
  const now = new Date();
  for (let i = n - 1; i >= 0; i -= 1) {
    out.push(toIsoDate(new Date(now.getFullYear(), now.getMonth() - i, 1)));
  }
  return out;
}

/** So'nggi `n` yilning 1-yanvarlari — joriy yil bilan tugaydi. */
function lastYears(n: number): string[] {
  const out: string[] = [];
  const now = new Date();
  for (let i = n - 1; i >= 0; i -= 1) {
    out.push(toIsoDate(new Date(now.getFullYear() - i, 0, 1)));
  }
  return out;
}

/** Davr bo'yicha kutilayotgan chelaklar ro'yxati — backend shu oynada javob beradi. */
function bucketsFor(period: PlatformReportPeriod): string[] {
  switch (period) {
    case 'day':
      return lastDays(LOOKBACK.day);
    case 'week':
      return lastWeeks(LOOKBACK.week);
    case 'month':
      return lastMonths(LOOKBACK.month);
    case 'year':
      return lastYears(LOOKBACK.year);
    default:
      return [];
  }
}

/** Ustun ostidagi qisqa yorliq: kun/hafta/oy uchun "16.08", yil uchun "2026". */
function shortLabel(period: PlatformReportPeriod, iso: string): string {
  const [year, month, day] = iso.split('-');
  if (period === 'year') return year ?? iso;
  return `${day}.${month}`;
}

/** Tooltipdagi to'liq sana: yil uchun faqat "2026", qolganlarda "16.08.2026". */
function tipDate(period: PlatformReportPeriod, iso: string): string {
  const [year, month, day] = iso.split('-');
  if (period === 'year') return year ?? iso;
  return `${day}.${month}.${year}`;
}

/**
 * Ustunlar ko'p bo'lganda (kunlik — 30, haftalik/oylik — 12) har bir tagiga
 * sana yozilsa bandlashib ketadi — faqat har 2-3-sida ko'rsatiladi
 * (`platform.tsx`dagi 14 kunlik trend grafigi bilan bir xil naqsh).
 */
function tickLabels(period: PlatformReportPeriod, buckets: string[]): string[] {
  const step = period === 'day' ? 3 : period === 'week' || period === 'month' ? 2 : 1;
  return buckets.map((bucket, index) => (index % step === 0 ? shortLabel(period, bucket) : ''));
}

function sumBucket(bucket: Record<string, number>): number {
  return Object.values(bucket).reduce((sum, value) => sum + value, 0);
}

/**
 * Super admin uchun platforma tushumi hisoboti — klublardan qo'lda
 * qayd etilgan to'lovlar yig'indisi va yangi qo'shilgan tashkilotlar soni,
 * kun/hafta/oy/yil kesimida. Klublarning bron aylanmasi BOSHQA panelda
 * (`platform.tsx`) — bu ikkalasi hech qachon aralashtirilmaydi.
 */
export function PlatformReportScreen(): ReactNode {
  const [period, setPeriod] = useState<PlatformReportPeriod>('month');
  const [report, setReport] = useState<PlatformReportDto | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    void getPlatformReport(api, period)
      .then((data) => {
        if (!cancelled) setReport(data);
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
  }, [period]);

  const config =
    PERIOD_OPTIONS.find((item) => item.id === period) ?? (PERIOD_OPTIONS[0] as (typeof PERIOD_OPTIONS)[number]);
  const buckets = bucketsFor(period);
  const ticks = tickLabels(period, buckets);

  const revenueValues = buckets.map((bucket) => report?.revenueByBucket[bucket] ?? 0);
  const newOrgsValues = buckets.map((bucket) => report?.newOrgsByBucket[bucket] ?? 0);

  const periodRevenue = report ? sumBucket(report.revenueByBucket) : 0;
  const periodNewOrgs = report ? sumBucket(report.newOrgsByBucket) : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <StatusLine
        tone="neutral"
        icon="info"
        parts={['Bu — platforma tushumi (qo‘lda kiritilgan to‘lovlar), klublar aylanmasi emas']}
      />

      <div className="ds-scroll-x">
        <SegmentedControl
          brackets
          items={PERIOD_OPTIONS.map((item) => item.label)}
          value={config.label}
          onChange={(label) => {
            const found = PERIOD_OPTIONS.find((item) => item.label === label);
            if (found) setPeriod(found.id);
          }}
        />
      </div>

      {error ? <StatusLine tone="danger" icon="error" parts={[error]} /> : null}

      <div className="pb-tiles-4">
        <StatTile
          label="Jami tushum"
          value={report ? S(report.totalRevenue) : '—'}
          unit="so‘m"
          icon="payments"
        />
        <StatTile
          label="Jami tashkilotlar"
          value={report ? String(report.totalOrganizations) : '—'}
          icon="corporate_fare"
        />
        <StatTile
          label="Shu davr tushumi"
          value={report ? S(periodRevenue) : '—'}
          unit="so‘m"
          icon="trending_up"
        />
        <StatTile
          label="Shu davrda qo‘shilgan"
          value={report ? String(periodNewOrgs) : '—'}
          unit="ta klub"
          icon="storefront"
        />
      </div>

      <Panel title={`Platforma tushumi · ${config.label}`} notch brackets>
        <div className="ds-chart">
          <ActivityBars
            bars={buckets.length}
            values={revenueValues}
            labels={ticks}
            height={180}
            tip={(value, index) => `${tipDate(period, buckets[index] as string)} · ${S(value)} so‘m`}
          />
        </div>
      </Panel>

      <Panel title="Yangi klublar" notch brackets>
        <div className="ds-chart">
          <ActivityBars
            bars={buckets.length}
            values={newOrgsValues}
            labels={ticks}
            height={140}
            tip={(value, index) => `${tipDate(period, buckets[index] as string)} · ${value} ta klub`}
          />
        </div>
      </Panel>

      {loading && !report ? <StatusLine tone="neutral" icon="hourglass_empty" parts={['Yuklanmoqda…']} /> : null}
    </div>
  );
}
