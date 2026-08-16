import {
  errorText,
  getClubReport,
  type ClubReportDto,
  type ClubReportPeriod,
} from '@playbron/api-client';
import { ActivityBars, Panel, ProgressMeter, SegmentedControl, StatTile, StatusLine } from '@playbron/ui';
import { useCallback, useEffect, useState, type ReactNode } from 'react';

import { api } from '../../lib/api';
import { S } from '../../mock/data';
import { useBoard } from '../../store/board';
import { useSession } from '../../store/session';
import { CARD, LABEL, VALUE } from './parts';

/**
 * Hisobot — kunlik, haftalik, oylik va yillik kesim.
 *
 * Reja #27 (2026-08-16, loyiha egasi): to'liq `useClub()` mock do'konidan
 * REAL agregatsiyaga (`GET /clubs/{id}/reports`, `finance/reports.py`)
 * ko'chirildi. "Tushum dinamikasi" grafigi `LineChart` o'rniga
 * `ActivityBars`ga o'tkazildi (reja #30, loyiha egasining topilmasi) —
 * alohida BarChart komponenti kerak emas, `ActivityBars` allaqachon
 * ustunli grafik.
 */

const PERIODS: { id: ClubReportPeriod; label: string }[] = [
  { id: 'day', label: 'Kunlik' },
  { id: 'week', label: 'Haftalik' },
  { id: 'month', label: 'Oylik' },
  { id: 'year', label: 'Yillik' },
];

function bucketLabel(iso: string, period: ClubReportPeriod): string {
  const d = new Date(iso);
  if (period === 'day') return `${String(d.getHours()).padStart(2, '0')}:00`;
  if (period === 'year') return d.toLocaleDateString('uz-UZ', { month: 'short' });
  return d.toLocaleDateString('uz-UZ', { day: '2-digit', month: '2-digit' });
}

export function ReportsScreen(): ReactNode {
  const session = useSession((state) => state.session);
  // Faol klub — header'dagi almashtirgichdan (`store/board.ts::activeClubId`);
  // hali sinxronlanmagan bo'lsa (App() darhol sozlaydi) birinchi a'zolikka tushadi.
  const activeClubId = useBoard((state) => state.activeClubId);
  const clubId = activeClubId ?? session?.clubs[0]?.id ?? null;

  const [period, setPeriod] = useState<ClubReportPeriod>('day');
  const [report, setReport] = useState<ClubReportDto | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const reload = useCallback(async (): Promise<void> => {
    if (clubId === null) return;
    setLoading(true);
    setLoadError(null);
    try {
      setReport(await getClubReport(api, clubId, period));
    } catch (cause) {
      setLoadError(errorText(cause));
    } finally {
      setLoading(false);
    }
  }, [clubId, period]);

  useEffect(() => {
    void reload();
  }, [reload]);

  if (loading && report === null) {
    return <StatusLine tone="neutral" icon="hourglass_empty" parts="Yuklanmoqda…" />;
  }
  if (loadError && report === null) {
    return <StatusLine tone="danger" icon="error" parts={[loadError]} />;
  }
  if (report === null) {
    return null;
  }

  const margin = report.revenue === 0 ? 0 : (report.profit / report.revenue) * 100;
  const seriesValues = report.revenueSeries.map((b) => b.amount);
  const peak = Math.max(1, ...seriesValues);
  const normalized = seriesValues.map((v) => v / peak);
  const labelStep = Math.max(1, Math.floor(report.revenueSeries.length / 6));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <div className="ds-scroll-x">
        <SegmentedControl
          brackets
          items={PERIODS.map((item) => item.label)}
          value={PERIODS.find((item) => item.id === period)?.label ?? PERIODS[0]!.label}
          onChange={(label) => {
            const found = PERIODS.find((item) => item.label === label);
            if (found) setPeriod(found.id);
          }}
        />
      </div>

      <div className="pb-tiles-4">
        <StatTile label="Tushum" value={S(report.revenue)} unit="so‘m" icon="payments" />
        <StatTile label="Xarajat" value={S(report.expenses)} unit="so‘m" icon="trending_down" />
        <StatTile label="Sof foyda" value={S(report.profit)} unit="so‘m" icon="trending_up" />
        <StatTile label="Rentabellik" value={margin.toFixed(1)} unit="%" icon="percent" />
      </div>

      <Panel title={`Tushum dinamikasi · ${PERIODS.find((item) => item.id === period)?.label}`} notch brackets>
        {report.revenueSeries.every((b) => b.amount === 0) ? (
          <StatusLine tone="neutral" icon="show_chart" parts="Bu davrda tushum yo‘q" />
        ) : (
          <div className="ds-chart">
            <ActivityBars
              bars={report.revenueSeries.length}
              values={normalized}
              height={120}
              labels={report.revenueSeries
                .filter((_, i) => i % labelStep === 0)
                .map((b) => bucketLabel(b.bucket, period))}
              tip={(_value, index) => `${S(report.revenueSeries[index]?.amount ?? 0)} so‘m`}
            />
          </div>
        )}
      </Panel>

      <div className="ds-split" style={{ alignItems: 'start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)', minWidth: 0 }}>
          <Panel title="Tushum tarkibi" notch>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
              <Breakdown label="O‘yin" amount={report.playRevenue} total={report.revenue} />
              <Breakdown label="Bar" amount={report.barRevenue} total={report.revenue} color="var(--purple-100)" />
            </div>

            <div style={{ marginTop: 'var(--gap-panel)', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--gap-tight)' }}>
              <div style={CARD}>
                <span style={LABEL}>Seanslar</span>
                <span style={VALUE}>{report.sessions}</span>
              </div>
              <div style={CARD}>
                <span style={LABEL}>O‘ynalgan soat</span>
                <span style={VALUE}>{report.hours}</span>
              </div>
              <div style={CARD}>
                <span style={LABEL}>O‘rtacha bandlik</span>
                <span style={VALUE}>{report.occupancy}%</span>
              </div>
              <div style={CARD}>
                <span style={LABEL}>Xona soni</span>
                <span style={VALUE}>{report.stationCount}</span>
              </div>
            </div>
          </Panel>

          <Panel title="Eng ko‘p sotilgan" notch>
            {report.topProducts.length === 0 ? (
              <StatusLine tone="neutral" icon="local_cafe" parts="Bu davrda sotuv yo‘q" />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {report.topProducts.map((row) => (
                  <div key={row.productName} style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                    <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10 }}>
                      <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-body)' }}>
                        {row.productName}
                      </span>
                      <span style={{ font: 'var(--type-data)', color: 'var(--text-title)', whiteSpace: 'nowrap' }}>
                        {S(row.revenue)}
                      </span>
                    </div>
                    <ProgressMeter
                      percent={
                        report.topProducts[0] && report.topProducts[0].revenue > 0
                          ? (row.revenue / report.topProducts[0].revenue) * 100
                          : 0
                      }
                      tip={() => `${row.productName} · ${S(row.revenue)}`}
                    />
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </div>

        <Panel title="Xarajat taqsimoti" notch brackets>
          {report.expenseByCategory.length === 0 ? (
            <StatusLine tone="neutral" icon="pie_chart" parts="Bu davrda xarajat yo‘q" />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
              {report.expenseByCategory.map((row) => (
                <Breakdown
                  key={row.category}
                  label={row.category}
                  amount={row.amount}
                  total={report.expenses}
                  color="var(--red-100)"
                />
              ))}
            </div>
          )}

          <div style={{ marginTop: 'var(--gap-panel)' }}>
            <StatusLine
              tone={report.profit > 0 ? 'ok' : 'danger'}
              icon={report.profit > 0 ? 'trending_up' : 'trending_down'}
              parts={[
                `${PERIODS.find((item) => item.id === period)?.label} foyda ${S(report.profit)} so‘m`,
                `Rentabellik ${margin.toFixed(1)}%`,
              ]}
            />
          </div>
        </Panel>
      </div>
    </div>
  );
}

function Breakdown({
  label,
  amount,
  total,
  color,
}: {
  label: string;
  amount: number;
  total: number;
  color?: string;
}): ReactNode {
  const percent = total === 0 ? 0 : (amount / total) * 100;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10 }}>
        <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-body)' }}>{label}</span>
        <span style={{ font: 'var(--type-data)', color: 'var(--text-title)', whiteSpace: 'nowrap' }}>
          {S(amount)} · {percent.toFixed(0)}%
        </span>
      </div>
      <ProgressMeter
        percent={percent}
        color={color}
        tip={() => `${label} · ${S(amount)} (${percent.toFixed(0)}%)`}
      />
    </div>
  );
}
