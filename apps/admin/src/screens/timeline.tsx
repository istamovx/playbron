import { NO_SHOW_MIN, Panel, SegmentedControl, useNarrow } from '@playbron/ui';
import type { ReactNode } from 'react';

import {
  DAY_END,
  DAY_ITEMS,
  DAY_START,
  HM,
  TOMORROW,
  YESTERDAY,
  consoleLabel,
  type DayId,
  type MockStation,
} from '../mock/data';
import { useBoard, useNow } from '../store/board';
import { liveStations } from './live-board';

const LEGEND = [
  { k: 'Band', c: 'var(--primary-100)' },
  { k: 'Rezerv', c: 'var(--yellow-100)' },
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
  left: string;
  width: string;
  bg: string;
  line: string;
  name: string;
  time: string;
}

/** Kunlik gantt — `PlayBron Xodim.dc.html` TIMELINE bo'limi. */
export function TimelineScreen(): ReactNode {
  const now = useNow();
  const nowMin = now / 60;
  const narrow = useNarrow();
  const state = useBoard();
  const live = liveStations(state.nsMarked, state.closedRooms, state.extended);

  const ticks = Array.from({ length: 17 }, (_, hour) => `${((hour * 60) / SPAN * 100).toFixed(2)}%`);
  const hourCols = Array.from({ length: 16 }, (_, hour) => String((10 + hour) % 24).padStart(2, '0'));
  // Kechasi 02:00 dan keyin va 10:00 gacha joriy vaqt shkaladan tashqarida
  const nowInWindow = nowMin >= DAY_START && nowMin <= DAY_END;
  const nowOvernight = nowMin + 24 * 60 <= DAY_END;
  const nowVisible = nowInWindow || nowOvernight;
  const nowLeft = `${((((nowOvernight ? nowMin + 24 * 60 : nowMin) - DAY_START) / SPAN) * 100).toFixed(2)}%`;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 'var(--gap-block)',
          flexWrap: 'wrap',
        }}
      >
        <SegmentedControl brackets items={[...DAY_ITEMS]} value={state.day} onChange={state.setDay} />

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

            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {live.map((station) => (
                <div key={station.id} style={{ display: 'flex', alignItems: 'center', height: 34 }}>
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
                    <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                      {consoleLabel(station.cons)}
                    </span>
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

                    {(state.day === 'Bugun'
                      ? barsFor(station, now, nowMin)
                      : barsForDay(station.id, state.day as DayId)
                    ).map((bar, index) => (
                      <div
                        key={`${bar.name}-${index}`}
                        title={`${bar.name} · ${bar.time}`}
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
                        {/* Telefonda bandga faqat ism sig'adi — vaqt tooltipda qoladi */}
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
                    ))}

                    {nowVisible && state.day === 'Bugun' ? (
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
      </Panel>
    </div>
  );
}

/** Kecha va ertaga — o'z bronlari, joriy vaqt chizig'isiz. */
function barsForDay(stationId: number, day: DayId): Bar[] {
  const source = day === 'Kecha' ? YESTERDAY : TOMORROW;

  return source
    .filter((entry) => entry.station === stationId && visible(entry.from, entry.to))
    .map((entry) => ({
      left: pos(entry.from),
      width: wide(entry.from, entry.to),
      bg:
        entry.kind === 'noshow'
          ? 'rgba(255,80,93,.10)'
          : entry.kind === 'booked'
            ? 'rgba(87,0,255,.20)'
            : 'rgba(255,255,255,.05)',
      line:
        entry.kind === 'noshow'
          ? 'var(--red-100)'
          : entry.kind === 'booked'
            ? 'var(--primary-100)'
            : 'var(--line-2)',
      name: entry.kind === 'noshow' ? 'Kelmadi' : entry.guest,
      time: `${HM(entry.from)}–${HM(entry.to)}`,
    }));
}

function barsFor(station: MockStation, now: number, nowMin: number): Bar[] {
  const bars: Bar[] = [];

  for (const [from, to, name] of station.hist) {
    if (!visible(from, to)) continue;
    bars.push({
      left: pos(from),
      width: wide(from, to),
      bg: 'rgba(255,255,255,.05)',
      line: 'var(--line-2)',
      name,
      time: `${HM(from)}–${HM(to)}`,
    });
  }

  if (station.status === 'MAINTENANCE') {
    bars.push({
      left: '0%',
      width: '100%',
      bg: 'rgba(255,80,93,.06)',
      line: 'var(--line-1)',
      name: 'Ta’mirda',
      time: station.note ?? '',
    });
  }

  if (
    (station.status === 'OCCUPIED' || station.status === 'RESERVED') &&
    visible(station.a, station.b)
  ) {
    const late = station.status === 'RESERVED' && now - station.a * 60 > NO_SHOW_MIN * 60;
    bars.push({
      left: pos(station.a),
      width: wide(station.a, station.b),
      bg: late
        ? 'rgba(255,80,93,.10)'
        : station.status === 'RESERVED'
          ? 'rgba(237,176,126,.14)'
          : 'rgba(87,0,255,.20)',
      line: late
        ? 'var(--red-100)'
        : station.status === 'RESERVED'
          ? 'var(--yellow-100)'
          : 'var(--primary-100)',
      name: late ? 'Kelmadi?' : ((station.guest ?? '').split(' ')[0] ?? ''),
      time: `${HM(station.a)}–${HM(station.b)}`,
    });

    if (station.status === 'OCCUPIED' && nowMin > station.b) {
      bars.push({
        left: pos(station.b),
        width: wide(station.b, nowMin),
        bg: 'rgba(255,80,93,.18)',
        line: 'var(--red-100)',
        name: 'Overtime',
        time: `+${Math.round(nowMin - station.b)} daq`,
      });
    }
  }

  return bars;
}
