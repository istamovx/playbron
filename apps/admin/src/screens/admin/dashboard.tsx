import { ActivityBars, Grid, Panel, ProgressMeter, StatTile, StatusLine } from '@playbron/ui';
import type { ReactNode } from 'react';

import { EXPENSE_SHARE, consoleLabel, seriesFor, stockRow, totalsFor } from '../../mock/club';
import { S } from '../../mock/data';
import { useClub } from '../../store/club';
import { CARD, LABEL, VALUE, hourSlot } from './parts';

/** Boshqaruv paneli — klub admini ochganda ko'radigan birinchi ekran. */
export function DashboardScreen(): ReactNode {
  const club = useClub((state) => state.club);
  const rooms = useClub((state) => state.rooms);
  const products = useClub((state) => state.products);
  const expenses = useClub((state) => state.expenses);
  const staff = useClub((state) => state.staff);

  const monthExpenses = expenses.reduce((sum, row) => sum + row.amount, 0);
  const totals = totalsFor('day', Math.round(monthExpenses * EXPENSE_SHARE.day));
  const series = seriesFor('day', 16);
  // 10:00 dan boshlanadigan 16 soatlik oynada joriy soat qaysi ustunga tushadi
  const activeBar = hourSlot(series.length);
  const seriesSum = series.reduce((sum, value) => sum + value, 0);

  const stock = products.map(stockRow);
  const lowStock = stock.filter((row) => row.low);
  const barRevenue = stock.reduce((sum, row) => sum + row.revenue, 0);
  const barProfit = stock.reduce((sum, row) => sum + row.profit, 0);

  const onShift = staff.filter((member) => member.status === 'ACTIVE');
  const busy = Math.round((totals.occupancy / 100) * rooms.length);

  const byFloor = [...new Set(rooms.map((room) => room.floor))].sort((a, b) => a - b);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <div className="pb-tiles-4">
        <StatTile label="Bugungi tushum" value={S(totals.revenue)} unit="so‘m" icon="payments" />
        <StatTile label="Sof foyda" value={S(totals.profit)} unit="so‘m" icon="trending_up" />
        <StatTile label="Seanslar" value={String(totals.sessions)} unit="ta" icon="sports_esports" />
        <StatTile label="Bandlik" value={String(totals.occupancy)} unit="%" icon="donut_large" />
      </div>

      <div className="ds-split" style={{ alignItems: 'start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)', minWidth: 0 }}>
          <Panel title="Bugungi bandlik" notch brackets>
            <div className="ds-chart">
              <ActivityBars
                bars={series.length}
                values={series}
                active={activeBar}
                height={92}
                labels={['10:00', '14:00', '18:00', '22:00', '02:00']}
                tip={(value, index) =>
                  `${String((10 + index) % 24).padStart(2, '0')}:00 · ${Math.round(value * 100)}% · ${S(Math.round(totals.revenue * (value / seriesSum)))} so‘m`
                }
              />
            </div>
            <StatusLine
              tone="neutral"
              icon="schedule"
              parts={[
                `Ish vaqti ${Math.floor(club.opensAt / 60)}:00 – ${Math.floor(club.closesAt / 60) % 24}:00`,
                `${busy} / ${rooms.length} xona band`,
              ]}
            />
          </Panel>

          <Panel title="Xonalar qavat bo‘yicha" notch>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
              {byFloor.map((floor) => {
                const list = rooms.filter((room) => room.floor === floor);
                const kinds = [...new Set(list.map((room) => room.kind))];
                const consoles = [...new Set(list.map((room) => room.console))];
                const share = (list.length / rooms.length) * 100;

                return (
                  <div key={floor} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10 }}>
                      <span style={{ font: 'var(--type-section)', color: 'var(--text-title)' }}>
                        {floor}-qavat
                      </span>
                      <span style={{ font: 'var(--type-data)', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                        {list.length} xona
                      </span>
                    </div>
                    <ProgressMeter percent={share} />
                    <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                      {kinds.join(' · ')} — {consoles.map(consoleLabel).join(', ')}
                    </span>
                  </div>
                );
              })}
            </div>
          </Panel>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)', minWidth: 0 }}>
          <Panel title="Bar savdosi" notch brackets>
            <Grid min={150}>
              <div style={CARD}>
                <span style={LABEL}>Tushum</span>
                <span style={VALUE}>{S(barRevenue)}</span>
              </div>
              <div style={CARD}>
                <span style={LABEL}>Foyda</span>
                <span style={{ ...VALUE, color: 'var(--secondary-500)' }}>{S(barProfit)}</span>
              </div>
            </Grid>

            {lowStock.length > 0 ? (
              <div style={{ marginTop: 'var(--gap-block)', display: 'flex', flexDirection: 'column', gap: 6 }}>
                <StatusLine
                  tone="warn"
                  icon="inventory"
                  parts={[`${lowStock.length} pozitsiya tugayapti`, 'Kirim qilish kerak']}
                />
                {lowStock.slice(0, 4).map((row) => (
                  <div
                    key={row.product.id}
                    style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10 }}
                  >
                    <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-body)' }}>
                      {row.product.name}
                    </span>
                    <span style={{ font: 'var(--type-data)', color: 'var(--yellow-100)', whiteSpace: 'nowrap' }}>
                      {row.left} dona
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ marginTop: 'var(--gap-block)' }}>
                <StatusLine tone="ok" icon="check_circle" parts="Qoldiqlar yetarli" />
              </div>
            )}
          </Panel>

          <Panel title="Smenadagi xodimlar" notch>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {onShift.map((member) => (
                <div
                  key={member.id}
                  style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10 }}
                >
                  <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-title)' }}>
                    {member.name}
                  </span>
                  <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)', whiteSpace: 'nowrap' }}>
                    {member.shift}
                  </span>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Bugungi xarajat" notch>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10 }}>
              <span style={LABEL}>Oylikdan ulush</span>
              <span style={{ ...VALUE, color: 'var(--red-100)' }}>{S(totals.expenses)}</span>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
