import { CyberLoader, EmptyState, Icon, Panel, StatusLine } from '@playbron/ui';
import type { ReactNode } from 'react';
import { useEffect, useMemo } from 'react';

import { MapButton } from '../components/map-button';
import { useT } from '../i18n';
import { hhmm, money } from '../lib/format';
import { CONSOLE_LABEL, isoDateOf, minutesOfDayInZone, nowMinutesOfDay } from '../lib/slots';
import { useApp } from '../store/app';
import { useBooking, useDayBookings } from '../store/booking';

/**
 * Klub sahifasi — real xonalar (`stations`) va bugungi bandlik.
 *
 * RASM/GALEREYA YO'Q: bu yerda ham 150px balandlikdagi "Klub galereyasi"
 * plasholderi turardi (backendda rasm yo'q, `cover_url` doim `null`).
 * O'rnida klub NOMI, MANZILI, ISH VAQTI va xarita tugmasi — mijozga
 * haqiqatan kerak bo'lgani (loyiha egasi, 2026-08-17).
 *
 * Sharhlar paneli ham mock edi (3 ta o'ylab topilgan ism/matn) — sharh
 * tizimi backendda yo'q, shuning uchun olib tashlangan.
 */
export function ClubScreen(): ReactNode {
  const t = useT();
  const clubId = useApp((state) => state.clubId);
  const club = useBooking((state) => state.clubs.find((item) => item.id === clubId) ?? null);
  const stations = useBooking((state) => state.stations);
  const stationsLoading = useBooking((state) => state.stationsLoading);
  const stationsError = useBooking((state) => state.stationsError);
  const loadStations = useBooking((state) => state.loadStations);
  const loadDay = useBooking((state) => state.loadDay);

  const timezone = club?.timezone ?? 'Asia/Tashkent';
  const today = isoDateOf(0, timezone);
  const todayBookings = useDayBookings(today);
  const nowMin = nowMinutesOfDay(timezone);

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
      const consoles = [
        ...new Set(
          group
            .map((s) => (s.consoleType ? (CONSOLE_LABEL[s.consoleType] ?? s.consoleType) : null))
            .filter((label): label is string => label !== null),
        ),
      ];
      const busy = group.filter((s) =>
        todayBookings.some((b) => {
          if (b.stationId !== s.id) return false;
          const from = minutesOfDayInZone(b.startsAt, timezone);
          const to = minutesOfDayInZone(b.endsAt, timezone);
          return nowMin >= from && nowMin < (to > from ? to : 24 * 60);
        }),
      ).length;

      return {
        name,
        // Stansiyaning soatlik tarifi — SERVER qiymati. Umumiy summa bu
        // yerda hisoblanmaydi (`CLAUDE.md` §Pul).
        rate:
          rates.length === 1
            ? money(rates[0] as number)
            : `${money(rates[0] as number)}–${money(rates[rates.length - 1] as number)}`,
        consoles,
        count: group.length,
        pct: Math.round((busy / group.length) * 100),
        free: group.length - busy,
      };
    });
  }, [stations, todayBookings, nowMin, timezone]);

  if (clubId === null || !club) {
    return <EmptyState icon="storefront">{t('clubNotSelected')}</EmptyState>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <section
        style={{
          padding: 'var(--card-pad)',
          background: 'var(--surface-panel)',
          border: '1px solid var(--line-1)',
          clipPath: 'var(--clip-tr)',
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--gap-tight)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
          <span
            style={{
              flex: 1,
              minWidth: 0,
              font: 'var(--fw-medium) var(--fs-xl)/1.2 var(--font-display)',
              color: 'var(--text-title)',
            }}
          >
            {club.name}
          </span>
          <MapButton club={club} />
        </div>

        <Line icon="location_on" text={club.address || t('addressMissing')} />
        <Line icon="schedule" text={`${hhmm(club.opensAtMin)} – ${hhmm(club.closesAtMin)}`} />
        {club.phone ? <Line icon="call" text={club.phone} /> : null}
      </section>

      {club.about ? (
        <div style={{ font: 'var(--type-body)', color: 'var(--text-body)' }}>{club.about}</div>
      ) : null}

      <Panel title={t('roomsTitle')} notch>
        {stationsError ? (
          <StatusLine tone="danger" icon="error" parts={[stationsError]} />
        ) : stationsLoading && rooms.length === 0 ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '12px 0' }}>
            <CyberLoader label={t('loading')} />
          </div>
        ) : rooms.length === 0 ? (
          <EmptyState icon="meeting_room" title={t('roomsEmptyTitle')}>
            {t('roomsEmptyHint')}
          </EmptyState>
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
                    {t('perHour', { sum: room.rate })}
                  </span>
                </div>

                <div style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                  {[...room.consoles, t('roomsCount', { count: room.count })].join(' · ')}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div
                    style={{
                      flex: 1,
                      height: 3,
                      background: 'var(--chart-track)',
                      position: 'relative',
                    }}
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
                    style={{
                      font: 'var(--type-data-xs)',
                      color: 'var(--text-muted)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {room.free === 0 ? t('allBusy') : t('freeCount', { count: room.free })}
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

function Line({ icon, text }: { icon: string; text: string }): ReactNode {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7, minWidth: 0 }}>
      <Icon name={icon} size={15} color="var(--text-dim)" />
      <span style={{ minWidth: 0, font: 'var(--type-body-sm)', color: 'var(--text-muted)' }}>
        {text}
      </span>
    </div>
  );
}
