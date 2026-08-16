import {
  errorText,
  listLiveStations,
  listTimeline,
  type LiveStationDto,
  type TimelineBookingDto,
} from '@playbron/api-client';
import { Modal, Panel, SegmentedControl, StatusLine, useNarrow } from '@playbron/ui';
import { useCallback, useEffect, useState, type ReactNode } from 'react';

import { api } from '../lib/api';
import { DAY_END, DAY_ITEMS, DAY_START, HM, consoleLabel, type DayId } from '../mock/data';
import { useBoard, useNow } from '../store/board';
import { useSession } from '../store/session';
import { BookingDetailPanel } from './live-board';

/**
 * Kunlik gantt — `PlayBron Xodim.dc.html` TIMELINE bo'limi.
 *
 * Reja #33 (2026-08-16, loyiha egasi): to'liq mock (`ST`, `YESTERDAY`,
 * `TOMORROW` — soxta mijoz, soxta bron) edi, HAQIQIY `GET /clubs/{id}/
 * bookings/timeline`ga (`bookings/service.py::list_timeline`) ko'chirildi
 * — stansiya ro'yxati (`listLiveStations`, allaqachon real) + shu kunning
 * haqiqiy bronlari.
 *
 * "Kelmadi" (no-show) rangi OLIB TASHLANDI: bunday kuzatuv hali qurilmagan
 * (reja #32, `blacklist.tsx`). "Overtime" esa HAQIQIY hisoblanadi (bugungi
 * hisob yopilmagan bo'lsa va vaqti o'tgan bo'lsa) — bu real ma'lumotdan
 * kelib chiqadi, soxta emas.
 */

const LEGEND = [
  { k: 'Band', c: 'var(--primary-100)' },
  { k: 'Kutilmoqda', c: 'var(--yellow-100)' },
  { k: 'Tugagan', c: 'var(--fg-4)' },
  { k: 'Overtime', c: 'var(--red-100)' },
  { k: 'Hozir', c: 'var(--red-100)' },
];

const SPAN = DAY_END - DAY_START;

/** Ko'rinadigan oynaga (10:00–02:00) qisib qo'yiladi — chetdan chiqqan band kesiladi. */
const clamp = (minutes: number): number => Math.max(DAY_START, Math.min(DAY_END, minutes));

const pos = (minutes: number): string =>
  `${(((clamp(minutes) - DAY_START) / SPAN) * 100).toFixed(2)}%`;

const wide = (from: number, to: number): string =>
  `${(((clamp(to) - clamp(from)) / SPAN) * 100).toFixed(2)}%`;

/** Oyna bilan kesishmaydigan band umuman chizilmaydi. */
const visible = (from: number, to: number): boolean => to > DAY_START && from < DAY_END;

interface Bar {
  id: number;
  status: string;
  left: string;
  width: string;
  bg: string;
  line: string;
  name: string;
  time: string;
}

function offsetOf(iso: string, dayStart: number): number {
  return (new Date(iso).getTime() - dayStart) / 60000;
}

function barsForStation(
  bookings: TimelineBookingDto[],
  stationId: number,
  dayStartMs: number,
  nowMin: number,
  isToday: boolean,
): Bar[] {
  const bars: Bar[] = [];
  for (const b of bookings) {
    if (b.stationId !== stationId) continue;
    const from = offsetOf(b.startsAt, dayStartMs);
    const to = offsetOf(b.endsAt, dayStartMs);
    if (!visible(from, to)) continue;

    const overtime = isToday && !b.closed && b.status === 'CONFIRMED' && to < nowMin;
    const pending = b.status === 'PENDING';
    const label = (b.guestLabel ?? 'Mijoz').split(' ')[0] ?? 'Mijoz';

    bars.push({
      id: b.id,
      status: b.status,
      left: pos(from),
      width: wide(from, to),
      bg: overtime
        ? 'rgba(255,80,93,.10)'
        : b.closed
          ? 'rgba(255,255,255,.05)'
          : pending
            ? 'rgba(237,176,126,.14)'
            : 'rgba(87,0,255,.20)',
      line: overtime
        ? 'var(--red-100)'
        : b.closed
          ? 'var(--line-2)'
          : pending
            ? 'var(--yellow-100)'
            : 'var(--primary-100)',
      name: overtime ? `${label} · Overtime` : label,
      time: `${HM(Math.max(0, from))}–${HM(Math.max(0, to))}`,
    });
  }
  return bars;
}

/** Tanlangan kun ("Kecha"/"Bugun"/"Ertaga") — `YYYY-MM-DD` (brauzer mahalliy vaqti). */
function dateFor(day: DayId): { iso: string; startMs: number } {
  const base = new Date();
  base.setHours(0, 0, 0, 0);
  const offset = day === 'Kecha' ? -1 : day === 'Ertaga' ? 1 : 0;
  base.setDate(base.getDate() + offset);
  const pad = (n: number) => String(n).padStart(2, '0');
  return {
    iso: `${base.getFullYear()}-${pad(base.getMonth() + 1)}-${pad(base.getDate())}`,
    startMs: base.getTime(),
  };
}

export function TimelineScreen(): ReactNode {
  const session = useSession((state) => state.session);
  // Faol klub — header'dagi almashtirgichdan (`store/board.ts::activeClubId`);
  // hali sinxronlanmagan bo'lsa (App() darhol sozlaydi) birinchi a'zolikka tushadi.
  const activeClubId = useBoard((state) => state.activeClubId);
  const clubId = activeClubId ?? session?.clubs[0]?.id ?? null;
  const now = useNow();
  const nowMin = now / 60;
  const narrow = useNarrow();

  const [day, setDay] = useState<DayId>('Bugun');
  const [stations, setStations] = useState<LiveStationDto[]>([]);
  const [bookings, setBookings] = useState<TimelineBookingDto[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  // Bar tanlansa — hisob tafsiloti/bekor qilish (`live-board.tsx` bilan
  // bir xil panel, loyiha egasining so'rovi, 2026-08-16).
  const [detailBookingId, setDetailBookingId] = useState<number | null>(null);

  const reload = useCallback(async (): Promise<void> => {
    if (clubId === null) return;
    setLoading(true);
    setLoadError(null);
    try {
      const { iso } = dateFor(day);
      const [liveStations, timeline] = await Promise.all([
        listLiveStations(api, clubId),
        listTimeline(api, clubId, iso),
      ]);
      setStations(liveStations);
      setBookings(timeline);
    } catch (cause) {
      setLoadError(errorText(cause));
    } finally {
      setLoading(false);
    }
  }, [clubId, day]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const { startMs: dayStartMs } = dateFor(day);
  const ticks = Array.from({ length: 17 }, (_, hour) => `${((hour * 60) / SPAN * 100).toFixed(2)}%`);
  const hourCols = Array.from({ length: 16 }, (_, hour) => String((10 + hour) % 24).padStart(2, '0'));
  const nowInWindow = nowMin >= DAY_START && nowMin <= DAY_END;
  const nowOvernight = nowMin + 24 * 60 <= DAY_END;
  const nowVisible = nowInWindow || nowOvernight;
  const nowLeft = `${((((nowOvernight ? nowMin + 24 * 60 : nowMin) - DAY_START) / SPAN) * 100).toFixed(2)}%`;

  if (loading && stations.length === 0) {
    return <StatusLine tone="neutral" icon="hourglass_empty" parts="Yuklanmoqda…" />;
  }
  if (loadError && stations.length === 0) {
    return <StatusLine tone="danger" icon="error" parts={[loadError]} />;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <Modal
        open={detailBookingId !== null}
        onClose={() => setDetailBookingId(null)}
        title="Hisob tafsiloti"
        variant="drawer"
      >
        {clubId !== null && detailBookingId !== null ? (
          <BookingDetailPanel
            clubId={clubId}
            bookingId={detailBookingId}
            onChanged={() => void reload()}
            onClose={() => setDetailBookingId(null)}
          />
        ) : null}
      </Modal>

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 'var(--gap-block)',
          flexWrap: 'wrap',
        }}
      >
        <SegmentedControl brackets items={[...DAY_ITEMS]} value={day} onChange={(v) => setDay(v as DayId)} />

        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--gap-block)', flexWrap: 'wrap' }}>
          {LEGEND.map((item) => (
            <span
              key={item.k}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                font: 'var(--type-label)',
                letterSpacing: 'var(--ls-label)',
                textTransform: 'uppercase',
                color: 'var(--text-muted)',
              }}
            >
              <span style={{ width: 8, height: 8, background: item.c }} />
              {item.k}
            </span>
          ))}
        </div>
      </div>

      <Panel title="Kunlik jadval" notch brackets>
        {stations.length === 0 ? (
          <StatusLine tone="neutral" icon="meeting_room" parts="Xona qo‘shilmagan" />
        ) : (
          <div className="ds-scroll-x">
            <div style={{ minWidth: 820 }}>
              <div
                style={{
                  display: 'flex',
                  paddingLeft: 78,
                  borderBottom: '1px solid var(--line-1)',
                  paddingBottom: 6,
                  marginBottom: 8,
                }}
              >
                {hourCols.map((hour) => (
                  <span
                    key={hour}
                    style={{
                      flex: 1,
                      font: 'var(--type-data-xs)',
                      color: 'var(--text-dim)',
                      textAlign: 'left',
                    }}
                  >
                    {hour}
                  </span>
                ))}
              </div>

              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 12,
                  // 10 qatordan keyin ichki scroll (loyiha egasining
                  // topilmasi, 2026-08-16) — qator balandligi kontentga
                  // qarab o'zgaruvchan (`minHeight`) bo'lgani uchun aniq
                  // piksel emas, taxminiy o'rtacha bilan hisoblangan.
                  maxHeight: 'calc(10 * (var(--control-h-lg) + 12px))',
                  overflowY: 'auto',
                }}
              >
                {stations.map((station) => (
                  <div
                    key={station.id}
                    style={{ display: 'flex', alignItems: 'center', minHeight: 'var(--control-h-lg)' }}
                  >
                    <div
                      style={{
                        width: 78,
                        flex: 'none',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 2,
                      }}
                    >
                      <span style={{ font: 'var(--type-control)', color: 'var(--text-title)' }}>
                        {station.code}
                      </span>
                      {station.consoleType ? (
                        <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                          {consoleLabel(station.consoleType)}
                        </span>
                      ) : null}
                    </div>

                    <div
                      style={{
                        flex: 1,
                        position: 'relative',
                        height: '100%',
                        background: 'var(--chart-plot)',
                        border: '1px solid var(--line-1)',
                      }}
                    >
                      {ticks.map((tick) => (
                        <div
                          key={tick}
                          style={{
                            position: 'absolute',
                            top: 0,
                            bottom: 0,
                            width: 1,
                            background: 'var(--grid-line)',
                            left: tick,
                          }}
                        />
                      ))}

                      {barsForStation(bookings, station.id, dayStartMs, nowMin, day === 'Bugun').map(
                        (bar) => (
                          <div
                            key={bar.id}
                            role="button"
                            tabIndex={0}
                            title={`${bar.name} · ${bar.time}`}
                            onClick={() => setDetailBookingId(bar.id)}
                            onKeyDown={(event) => {
                              if (event.key === 'Enter' || event.key === ' ') setDetailBookingId(bar.id);
                            }}
                            style={{
                              position: 'absolute',
                              top: 4,
                              bottom: 4,
                              left: bar.left,
                              width: bar.width,
                              background: bar.bg,
                              border: `1px solid ${bar.line}`,
                              display: 'flex',
                              alignItems: 'center',
                              padding: '0 7px',
                              gap: 6,
                              overflow: 'hidden',
                              cursor: 'pointer',
                              clipPath: 'var(--clip-tr)',
                            }}
                          >
                            <span
                              style={{
                                font: 'var(--type-control)',
                                color: 'var(--text-title)',
                                whiteSpace: 'nowrap',
                              }}
                            >
                              {bar.name}
                            </span>
                            {narrow ? null : (
                              <span
                                style={{
                                  font: 'var(--type-data-xs)',
                                  color: 'var(--text-muted)',
                                  whiteSpace: 'nowrap',
                                }}
                              >
                                {bar.time}
                              </span>
                            )}
                          </div>
                        ),
                      )}

                      {nowVisible && day === 'Bugun' ? (
                        <div
                          style={{
                            position: 'absolute',
                            top: -3,
                            bottom: -3,
                            width: 1,
                            background: 'var(--red-100)',
                            left: nowLeft,
                          }}
                        />
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </Panel>
    </div>
  );
}
