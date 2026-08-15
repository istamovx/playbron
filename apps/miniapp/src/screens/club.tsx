import { Panel, Tag } from '@playbron/ui';
import type { ReactNode } from 'react';
import { useEffect, useMemo } from 'react';

import { HM, S } from '../mock/data';
import { CONSOLE_LABEL, isoDateOf, nowMinutesOfDay } from '../lib/slots';
import { useApp } from '../store/app';
import { useBooking, useDayBookings } from '../store/booking';

/**
 * Klub sahifasi — real xonalar (`stations`) va bugungi bandlik.
 *
 * Sharhlar paneli mock'da 3 ta o'ylab topilgan ism/matn edi — backend'da
 * sharh tizimi yo'q, shuning uchun ATAYLAB olib tashlangan (soxta fikr
 * ko'rsatishdan ko'ra ko'rsatmaslik ma'qul).
 */
export function ClubScreen(): ReactNode {
  const clubId = useApp((state) => state.clubId);
  const club = useBooking((state) => state.clubs.find((item) => item.id === clubId) ?? null);
  const stations = useBooking((state) => state.stations);
  const stationsLoading = useBooking((state) => state.stationsLoading);
  const stationsError = useBooking((state) => state.stationsError);
  const loadStations = useBooking((state) => state.loadStations);
  const loadDay = useBooking((state) => state.loadDay);

  const today = isoDateOf(0);
  const todayBookings = useDayBookings(today);
  const nowMin = nowMinutesOfDay();

  useEffect(() => {
    if (clubId === null) return;
    void loadStations(clubId);
    void loadDay(clubId, today);
  }, [clubId, loadStations, loadDay, today]);

  const rooms = useMemo(() => {
    const byRoom = new Map<string, typeof stations>();
    for (const station of stations) {
      const list = byRoom.get(station.roomLabel) ?? [];
      list.push(station);
      byRoom.set(station.roomLabel, list);
    }

    return [...byRoom.entries()].map(([name, group]) => {
      const rates = [...new Set(group.map((s) => s.rate))].sort((a, b) => a - b);
      const consoles = [...new Set(group.map((s) => CONSOLE_LABEL[s.consoleType] ?? s.consoleType))];
      const busy = group.filter((s) =>
        todayBookings.some((b) => {
          if (b.stationId !== s.id) return false;
          const from = new Date(b.startsAt).getHours() * 60 + new Date(b.startsAt).getMinutes();
          const to = new Date(b.endsAt).getHours() * 60 + new Date(b.endsAt).getMinutes();
          return nowMin >= from && nowMin < (to > from ? to : 24 * 60);
        }),
      ).length;
      const free = group.length - busy;

      return {
        name,
        price:
          rates.length === 1
            ? `${S(rates[0] as number)} / soat`
            : `${S(rates[0] as number)}–${S(rates[rates.length - 1] as number)} / soat`,
        spec: `${consoles.join(' · ')} · ${group.length} xona`,
        pct: Math.round((busy / group.length) * 100),
        free,
      };
    });
  }, [stations, todayBookings, nowMin]);

  if (clubId === null || !club) {
    return (
      <div style={{ font: 'var(--type-body-sm)', color: 'var(--text-muted)' }}>Klub tanlanmagan</div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <div
        style={{
          height: 150,
          background: 'var(--surface-inset)',
          border: '1px solid var(--line-1)',
          clipPath: 'var(--clip-tr)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <span
          style={{
            font: 'var(--type-label)',
            letterSpacing: 'var(--ls-label)',
            textTransform: 'uppercase',
            color: 'var(--text-dim)',
          }}
        >
          Klub galereyasi
        </span>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        <Tag tone="neutral">{`${stations.length} xona`}</Tag>
        <Tag tone="neutral">{`${HM(club.opensAtMin)} – ${HM(club.closesAtMin)}`}</Tag>
        {club.address ? <Tag tone="neutral">{club.address}</Tag> : null}
      </div>

      {club.about ? (
        <div style={{ font: 'var(--type-body)', color: 'var(--text-body)' }}>{club.about}</div>
      ) : null}

      <Panel title="Xonalar va narxlar" notch>
        {stationsError ? (
          <div style={{ font: 'var(--type-body-sm)', color: 'var(--red-100)' }}>{stationsError}</div>
        ) : !stationsLoading && rooms.length === 0 ? (
          <div style={{ font: 'var(--type-body-sm)', color: 'var(--text-muted)' }}>
            Bu klubda hali xona qo‘shilmagan.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {rooms.map((room) => (
              <div
                key={room.name}
                style={{
                  padding: 'var(--card-pad)',
                  background: 'var(--surface-card)',
                  border: '1px solid var(--line-1)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 6,
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'baseline',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: '2px 8px',
                  }}
                >
                  <span
                    style={{
                      font: 'var(--type-section)',
                      color: 'var(--text-title)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {room.name}
                  </span>
                  <span
                    style={{
                      font: 'var(--type-data)',
                      color: 'var(--purple-100)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {room.price}
                  </span>
                </div>

                <div style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                  {room.spec}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div
                    style={{ flex: 1, height: 3, background: 'var(--chart-track)', position: 'relative' }}
                  >
                    <div
                      className="pb-fill"
                      style={{
                        position: 'absolute',
                        inset: '0 auto 0 0',
                        width: `${room.pct}%`,
                        background:
                          room.pct >= 100
                            ? 'var(--red-100)'
                            : room.pct >= 70
                              ? 'var(--yellow-100)'
                              : 'var(--secondary-500)',
                      }}
                    />
                  </div>
                  <span
                    style={{ font: 'var(--type-data-xs)', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}
                  >
                    {room.free === 0 ? 'Band' : `${room.free} bo‘sh`}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
