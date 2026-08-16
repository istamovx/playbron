import {
  errorText,
  getClubDashboard,
  listOpenShifts,
  type ClubDashboardDto,
  type OpenShiftSummaryDto,
} from '@playbron/api-client';
import { ActivityBars, Panel, StatTile, StatusLine, Tag, toast } from '@playbron/ui';
import { useCallback, useEffect, useState, type ReactNode } from 'react';

import { api } from '../../lib/api';
import { S } from '../../mock/data';
import { useBoard } from '../../store/board';
import { useSession } from '../../store/session';

/**
 * Boshqaruv paneli — klub admini ochganda ko'radigan birinchi ekran.
 *
 * Reja #27 (2026-08-16, loyiha egasi): "hech qayerda seed qolmasin, hamma
 * rol 0 dan boshlansin" — ekran to'liq `useClub()` mock do'konidan REAL
 * agregatsiyaga (`GET /clubs/{id}/dashboard`, `finance/reports.py`)
 * ko'chirildi. "Smenadagi xodimlar" — real ochiq smenalar (reja #26).
 *
 * "Xonalar qavat bo'yicha" panel OLIB TASHLANDI: `stations.floor` ustuni
 * hali yo'q (reja #19) — soxta guruhlash o'rniga tekis stansiya holati
 * ko'rsatiladi. "Bar savdosi"dagi FOYDA ham yo'q: tannarx ustuni yo'q
 * (reja #21) — faqat haqiqiy TUSHUM ko'rsatiladi.
 */

function hourLabel(hour: number): string {
  return `${String(hour % 24).padStart(2, '0')}:00`;
}

/** Klub ish vaqti oralig'idagi soatlar (kechayarim oshib ketishi mumkin). */
function hoursInWindow(opensAtMin: number, closesAtMin: number): number[] {
  const opensHour = Math.floor(opensAtMin / 60);
  let closesHour = Math.floor(closesAtMin / 60);
  if (closesHour <= opensHour) closesHour += 24;
  const hours: number[] = [];
  for (let h = opensHour; h <= closesHour; h += 1) hours.push(h % 24);
  return hours;
}

export function DashboardScreen(): ReactNode {
  const session = useSession((state) => state.session);
  // Faol klub — header'dagi almashtirgichdan (`store/board.ts::activeClubId`);
  // hali sinxronlanmagan bo'lsa (App() darhol sozlaydi) birinchi a'zolikka tushadi.
  const activeClubId = useBoard((state) => state.activeClubId);
  const clubId = activeClubId ?? session?.clubs[0]?.id ?? null;

  const [data, setData] = useState<ClubDashboardDto | null>(null);
  const [onShift, setOnShift] = useState<OpenShiftSummaryDto[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const reload = useCallback(async (): Promise<void> => {
    if (clubId === null) return;
    setLoading(true);
    setLoadError(null);
    try {
      const [dashboard, shifts] = await Promise.all([
        getClubDashboard(api, clubId),
        listOpenShifts(api, clubId),
      ]);
      setData(dashboard);
      setOnShift(shifts);
    } catch (cause) {
      const message = errorText(cause);
      setLoadError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }, [clubId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  if (loading && data === null) {
    return <StatusLine tone="neutral" icon="hourglass_empty" parts="Yuklanmoqda…" />;
  }

  if (loadError && data === null) {
    return <StatusLine tone="danger" icon="error" parts={[loadError]} />;
  }

  if (data === null) {
    return null;
  }

  const hours = hoursInWindow(data.opensAtMin, data.closesAtMin);
  const counts = hours.map((h) => data.hourly[String(h)] ?? 0);
  const peak = Math.max(1, ...counts);
  const series = counts.map((n) => Math.min(1, n / peak));
  const nowHour = new Date().getHours();
  const activeBar = Math.max(0, hours.indexOf(nowHour));
  const busy = data.stations.filter((s) => s.occupied).length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <div className="pb-tiles-4">
        <StatTile label="Bugungi tushum" value={S(data.revenueToday)} unit="so‘m" icon="payments" />
        <StatTile label="Sof foyda" value={S(data.profitToday)} unit="so‘m" icon="trending_up" />
        <StatTile label="Seanslar" value={String(data.sessionsToday)} unit="ta" icon="sports_esports" />
        <StatTile label="Bandlik" value={String(data.occupancyToday)} unit="%" icon="donut_large" />
      </div>

      <div className="ds-split" style={{ alignItems: 'start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)', minWidth: 0 }}>
          <Panel title="Bugungi bandlik" notch brackets>
            <div className="ds-chart">
              <ActivityBars
                bars={hours.length}
                values={series}
                active={activeBar}
                height={92}
                labels={hours.filter((_, i) => i % Math.max(1, Math.floor(hours.length / 5)) === 0).map(hourLabel)}
                tip={(_value, index) => `${hourLabel(hours[index] ?? 0)} · ${counts[index] ?? 0} ta seans`}
              />
            </div>
            <StatusLine
              tone="neutral"
              icon="schedule"
              parts={[
                `Ish vaqti ${Math.floor(data.opensAtMin / 60)}:00 – ${Math.floor(data.closesAtMin / 60) % 24}:00`,
                `${busy} / ${data.stations.length} xona band`,
              ]}
            />
          </Panel>

          <Panel title="Xonalar" notch>
            {data.stations.length === 0 ? (
              <StatusLine tone="neutral" icon="meeting_room" parts="Xona qo‘shilmagan" />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {data.stations.map((station) => (
                  <div
                    key={station.id}
                    style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}
                  >
                    <span style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
                      <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-title)' }}>
                        {station.code} · {station.roomLabel}
                      </span>
                      <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                        {station.consoleType.toUpperCase()}
                      </span>
                    </span>
                    <Tag tone={station.occupied ? 'amber' : 'success'}>{station.occupied ? 'Band' : 'Bo‘sh'}</Tag>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)', minWidth: 0 }}>
          <Panel title="Bar savdosi" notch brackets>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10 }}>
              <span
                style={{
                  font: 'var(--type-label)',
                  letterSpacing: 'var(--ls-label)',
                  textTransform: 'uppercase',
                  color: 'var(--text-label)',
                }}
              >
                Tushum
              </span>
              <span style={{ font: 'var(--type-data)', color: 'var(--text-title)' }}>
                {S(data.barRevenueToday)}
              </span>
            </div>
          </Panel>

          <Panel title="Smenadagi xodimlar" notch>
            {onShift.length === 0 ? (
              <StatusLine tone="neutral" icon="person_off" parts="Hozir ochiq smena yo‘q" />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {onShift.map((member) => (
                  <div
                    key={member.id}
                    style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10 }}
                  >
                    <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-title)' }}>
                      {member.staffName}
                    </span>
                    <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)', whiteSpace: 'nowrap' }}>
                      {new Date(member.openedAt).toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' })}dan
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <Panel title="Bugungi xarajat" notch>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10 }}>
              <span
                style={{
                  font: 'var(--type-label)',
                  letterSpacing: 'var(--ls-label)',
                  textTransform: 'uppercase',
                  color: 'var(--text-label)',
                }}
              >
                Jami
              </span>
              <span style={{ font: 'var(--type-data)', color: 'var(--red-100)' }}>{S(data.expensesToday)}</span>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
