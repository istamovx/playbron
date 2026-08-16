import { LineChart, Panel, ProgressMeter, SegmentedControl, StatTile, StatusLine } from '@playbron/ui';
import { useState, type ReactNode } from 'react';

import {
  EXPENSE_SHARE,
  PERIODS,
  PERIOD_LABELS,
  seriesFor,
  stockRow,
  totalsFor,
  type PeriodId,
} from '../../mock/club';
import { S } from '../../mock/data';
import { useClub } from '../../store/club';
import { CARD, LABEL, VALUE } from './parts';

/** Hisobot — kunlik, haftalik, oylik va yillik kesim. */
export function ReportsScreen(): ReactNode {
  const [period, setPeriod] = useState<PeriodId>('day');
  const expenses = useClub((state) => state.expenses);
  const products = useClub((state) => state.products);
  const rooms = useClub((state) => state.rooms);

  const config = PERIODS.find((item) => item.id === period) ?? (PERIODS[0] as (typeof PERIODS)[number]);
  const monthExpenses = expenses.reduce((sum, row) => sum + row.amount, 0);
  const periodExpenses = Math.round(monthExpenses * EXPENSE_SHARE[period]);
  const totals = totalsFor(period, periodExpenses);

  const series = seriesFor(period, config.bars);
  const total = series.reduce((sum, value) => sum + value, 0);
  const margin = totals.revenue === 0 ? 0 : (totals.profit / totals.revenue) * 100;

  const byCat = expenses.reduce<Record<string, number>>((acc, row) => {
    acc[row.cat] = (acc[row.cat] ?? 0) + row.amount;
    return acc;
  }, {});
  const catRows = Object.entries(byCat)
    .map(([cat, amount]) => ({ cat, amount: Math.round(amount * EXPENSE_SHARE[period]) }))
    .sort((a, b) => b.amount - a.amount);

  const topProducts = products
    .map(stockRow)
    .sort((a, b) => b.revenue - a.revenue)
    .slice(0, 5);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <div className="ds-scroll-x">
        <SegmentedControl
          brackets
          items={PERIODS.map((item) => item.label)}
          value={config.label}
          onChange={(label) => {
            const found = PERIODS.find((item) => item.label === label);
            if (found) setPeriod(found.id);
          }}
        />
      </div>

      <div className="pb-tiles-4">
        <StatTile label="Tushum" value={S(totals.revenue)} unit="so‘m" icon="payments" />
        <StatTile label="Xarajat" value={S(totals.expenses)} unit="so‘m" icon="trending_down" />
        <StatTile label="Sof foyda" value={S(totals.profit)} unit="so‘m" icon="trending_up" />
        <StatTile label="Rentabellik" value={margin.toFixed(1)} unit="%" icon="percent" />
      </div>

      <Panel title={`Tushum dinamikasi · ${config.label}`} notch brackets>
        {/* Chiziq barqaror: bir xil davr har safar bir xil grafikni beradi */}
        <div className="ds-chart">
          <LineChart
            points={series.length}
            values={series}
            labels={PERIOD_LABELS[period] ?? []}
            height={120}
            tip={(value) => `${S(Math.round(totals.revenue * (value / total)))} so‘m`}
          />
        </div>
      </Panel>

      <div className="ds-split" style={{ alignItems: 'start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)', minWidth: 0 }}>
          <Panel title="Tushum tarkibi" notch>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
              <Breakdown label="O‘yin" amount={totals.play} total={totals.revenue} />
              <Breakdown
                label="Bar"
                amount={totals.bar}
                total={totals.revenue}
                color="var(--purple-100)"
              />
            </div>

            <div style={{ marginTop: 'var(--gap-panel)', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--gap-tight)' }}>
              <div style={CARD}>
                <span style={LABEL}>Seanslar</span>
                <span style={VALUE}>{totals.sessions}</span>
              </div>
              <div style={CARD}>
                <span style={LABEL}>O‘ynalgan soat</span>
                <span style={VALUE}>{totals.hours}</span>
              </div>
              <div style={CARD}>
                <span style={LABEL}>O‘rtacha bandlik</span>
                <span style={VALUE}>{totals.occupancy}%</span>
              </div>
              <div style={CARD}>
                <span style={LABEL}>Xona soni</span>
                <span style={VALUE}>{rooms.length}</span>
              </div>
            </div>
          </Panel>

          <Panel title="Eng ko‘p sotilgan" notch>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {topProducts.map((row) => (
                <div key={row.product.id} style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                  <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10 }}>
                    <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-body)' }}>
                      {row.product.name}
                    </span>
                    <span style={{ font: 'var(--type-data)', color: 'var(--text-title)', whiteSpace: 'nowrap' }}>
                      {S(row.revenue)}
                    </span>
                  </div>
                  <ProgressMeter
                    percent={
                      topProducts[0] && topProducts[0].revenue > 0
                        ? (row.revenue / topProducts[0].revenue) * 100
                        : 0
                    }
                    tip={() => `${row.product.name} · ${S(row.revenue)}`}
                  />
                </div>
              ))}
            </div>
          </Panel>
        </div>

        <Panel title="Xarajat taqsimoti" notch brackets>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
            {catRows.map((row) => (
              <Breakdown
                key={row.cat}
                label={row.cat}
                amount={row.amount}
                total={totals.expenses}
                color="var(--red-100)"
              />
            ))}
          </div>

          <div style={{ marginTop: 'var(--gap-panel)' }}>
            <StatusLine
              tone={totals.profit > 0 ? 'ok' : 'danger'}
              icon={totals.profit > 0 ? 'trending_up' : 'trending_down'}
              parts={[
                `${config.label} foyda ${S(totals.profit)} so‘m`,
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
