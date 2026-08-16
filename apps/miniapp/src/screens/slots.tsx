import { Panel } from '@playbron/ui';
import { useEffect, type CSSProperties, type ReactNode } from 'react';

import { S, dayOptions, HM } from '../mock/data';
import {
  ANY,
  CONSOLE_LABEL,
  DURATIONS,
  consoleTypes,
  freeStations,
  isPast,
  isoDateOf,
  maxHours,
  nowMinutesOfDay,
  roomTypes,
  slotTimes,
  stationSpec,
  type SlotFilter,
} from '../lib/slots';
import { useApp } from '../store/app';
import { useBooking, useDayBookings } from '../store/booking';

/**
 * Slot tanlash — real stansiya + `GET /clubs/{id}/bookings/day` ustida.
 *
 * Mock versiyada kun tasmasi har bir kun uchun "N bo'sh" hisoblardi — bu
 * 14 kunni OLDINDAN so'rashni talab qilardi (14 so'rov). Soddalik uchun
 * shu bosqichda tasma faqat sana ko'rsatadi, bandlik faqat TANLANGAN kun
 * uchun yuklanadi — asosiy oqim (vaqt tanlash) o'zgarmaydi.
 */
export function SlotsScreen(): ReactNode {
  const state = useApp();
  const clubId = state.clubId;
  const club = useBooking((s) => s.clubs.find((item) => item.id === clubId) ?? null);
  const stations = useBooking((s) => s.stations);
  const loadStations = useBooking((s) => s.loadStations);
  const loadDay = useBooking((s) => s.loadDay);
  const dayLoading = useBooking((s) => s.dayLoading);

  const timezone = club?.timezone ?? 'Asia/Tashkent';
  const dateKey = isoDateOf(state.day, timezone);
  const dayBookings = useDayBookings(dateKey);
  const nowMin = nowMinutesOfDay(timezone);

  const openMin = club?.opensAtMin ?? 0;
  const closeMin = club?.closesAtMin ?? 0;

  useEffect(() => {
    if (clubId === null) return;
    if (stations.length === 0) void loadStations(clubId);
  }, [clubId, stations.length, loadStations]);

  useEffect(() => {
    if (clubId === null) return;
    void loadDay(clubId, dateKey);
  }, [clubId, dateKey, loadDay]);

  const filter: SlotFilter = { room: state.room, console: state.console };
  const days = dayOptions();
  const times = slotTimes(openMin, closeMin).filter((from) => !isPast(state.day, from, nowMin));
  const open = times.filter(
    (from) => freeStations(stations, dayBookings, from, 1, closeMin, filter, timezone).length > 0,
  );
  const limit = maxHours(stations, dayBookings, state.start, closeMin, filter, timezone);
  const freeNow = freeStations(
    stations,
    dayBookings,
    state.start,
    state.hours,
    closeMin,
    filter,
    timezone,
  );

  // Tanlangan xona konsolsiz bo'lsa (0023'dan keyingi) — mijoz o'zi tanlaydi
  const selectedStation = stations.find((item) => item.id === state.station);
  const needsConsole = selectedStation !== undefined && selectedStation.consoleType === null;

  const { day, start, hours, station, setDay, setStart, setHours, setStation } = state;

  // Filtr, kun yoki bandlik o'zgarganda tanlov yaroqsiz bo'lib qolmasin.
  useEffect(() => {
    if (stations.length === 0) return;
    const scope: SlotFilter = { room: state.room, console: state.console };
    const free = slotTimes(openMin, closeMin).filter(
      (from) =>
        !isPast(day, from, nowMin) &&
        freeStations(stations, dayBookings, from, 1, closeMin, scope, timezone).length > 0,
    );

    if (free.length === 0) {
      setStation(null);
      return;
    }

    if (!free.includes(start)) {
      setStart(free[0] as number);
      return;
    }

    const max = maxHours(stations, dayBookings, start, closeMin, scope, timezone);
    if (hours > max) {
      setHours(max);
      return;
    }

    const list = freeStations(stations, dayBookings, start, hours, closeMin, scope, timezone);
    if (list.length > 0 && !list.some((item) => item.id === station)) {
      setStation((list[0] as (typeof list)[number]).id);
    } else if (list.length === 0) {
      setStation(null);
    }
  }, [
    stations,
    dayBookings,
    day,
    start,
    hours,
    station,
    state.room,
    state.console,
    openMin,
    closeMin,
    nowMin,
    timezone,
    setStation,
    setStart,
    setHours,
  ]);

  if (clubId === null || !club) {
    return (
      <div style={{ font: 'var(--type-body-sm)', color: 'var(--text-muted)' }}>Klub tanlanmagan</div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <section style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <SectionLabel>Sana</SectionLabel>
        <div style={STRIP}>
          {days.map((option) => {
            const on = option.index === state.day;
            return (
              <button
                key={option.index}
                type="button"
                onClick={() => setDay(option.index)}
                aria-current={on ? 'date' : undefined}
                style={{
                  flex: 'none',
                  cursor: 'pointer',
                  width: 62,
                  padding: '7px 0',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 2,
                  background: on ? 'var(--surface-selected)' : 'var(--surface-card)',
                  border: `1px solid ${on ? 'var(--primary-100)' : 'var(--line-1)'}`,
                  clipPath: 'var(--clip-tr)',
                  transition: 'var(--t-control)',
                }}
              >
                <span style={{ font: 'var(--type-label)', color: 'var(--text-dim)' }}>
                  {option.dow}
                </span>
                <span
                  style={{
                    font: 'var(--type-data)',
                    color: on ? 'var(--text-title)' : 'var(--text-body)',
                  }}
                >
                  {option.day}
                </span>
              </button>
            );
          })}
        </div>
      </section>

      <section style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <SectionLabel>Xona turi</SectionLabel>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          <Pick on={state.room === ANY} onClick={() => state.setRoom(ANY)}>
            {ANY}
          </Pick>
          {roomTypes(stations).map((room) => (
            <Pick key={room} on={state.room === room} onClick={() => state.setRoom(room)}>
              {room}
            </Pick>
          ))}
        </div>
      </section>

      <section style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <SectionLabel>Konsol</SectionLabel>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          <Pick on={state.console === ANY} onClick={() => state.setConsole(ANY)}>
            {ANY}
          </Pick>
          {consoleTypes(stations).map((type) => (
            <Pick
              key={type.id}
              on={state.console === type.id}
              onClick={() => state.setConsole(type.id)}
            >
              {type.label}
            </Pick>
          ))}
        </div>
      </section>

      <section style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <SectionLabel hint={limit > 0 ? `Bu vaqtdan ${limit} soatgacha` : undefined}>
          Davomiylik
        </SectionLabel>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {DURATIONS.map((value) => (
            <Pick
              key={value}
              on={state.hours === value}
              off={value > limit}
              onClick={() => state.setHours(value)}
            >
              {value} soat
            </Pick>
          ))}
        </div>
      </section>

      <Panel title="Bo‘sh vaqt" notch>
        {dayLoading ? (
          <div style={{ font: 'var(--type-body-sm)', color: 'var(--text-muted)' }}>Yuklanmoqda…</div>
        ) : open.length === 0 ? (
          <div style={{ font: 'var(--type-body-sm)', color: 'var(--text-muted)' }}>
            Bu kunda tanlangan filtr bo‘yicha bo‘sh vaqt yo‘q. Boshqa sana yoki xona turini tanlang.
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6 }}>
            {times.map((from) => {
              const count = freeStations(
                stations,
                dayBookings,
                from,
                state.hours,
                closeMin,
                filter,
                timezone,
              ).length;
              const fits = count > 0 ? 0 : maxHours(stations, dayBookings, from, closeMin, filter, timezone);
              const on = from === state.start;
              const usable = count > 0 || fits > 0;

              return (
                <button
                  key={from}
                  type="button"
                  disabled={!usable}
                  onClick={() => state.setStart(from)}
                  aria-pressed={on}
                  style={{
                    cursor: usable ? 'pointer' : 'not-allowed',
                    minHeight: 42,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 1,
                    background: on ? 'var(--primary-100)' : 'var(--surface-inset)',
                    border: `1px solid ${on ? 'var(--primary-100)' : 'var(--line-1)'}`,
                    color: on ? 'var(--text-on-accent)' : usable ? 'var(--text-body)' : 'var(--text-dim)',
                    opacity: usable ? 1 : 0.45,
                    transition: 'var(--t-control)',
                  }}
                >
                  <span style={{ font: 'var(--type-data)' }}>{HM(from)}</span>
                  <span
                    style={{
                      font: 'var(--type-data-xs)',
                      color: on
                        ? 'var(--text-on-accent)'
                        : count > 0
                          ? 'var(--secondary-500)'
                          : fits > 0
                            ? 'var(--yellow-100)'
                            : 'var(--text-dim)',
                    }}
                  >
                    {count > 0 ? `${count} xona` : fits > 0 ? `${fits} soat` : 'band'}
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </Panel>

      <Panel
        title={`Bo‘sh xonalar · ${HM(state.start)} → ${HM(state.start + state.hours * 60)}`}
        notch
      >
        {freeNow.length === 0 ? (
          <div style={{ font: 'var(--type-body-sm)', color: 'var(--text-muted)' }}>
            {state.hours} soatga bo‘sh xona yo‘q — davomiylikni qisqartiring.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {freeNow.map((item) => {
              const on = item.id === state.station;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => state.setStation(item.id)}
                  aria-pressed={on}
                  style={{
                    cursor: 'pointer',
                    textAlign: 'left',
                    padding: 'var(--card-pad)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 4,
                    background: on ? 'var(--surface-selected)' : 'var(--surface-card)',
                    border: `1px solid ${on ? 'var(--primary-100)' : 'var(--line-1)'}`,
                    transition: 'var(--t-control)',
                  }}
                >
                  <span style={ROW}>
                    <span style={{ font: 'var(--type-section)', color: 'var(--text-title)' }}>
                      {item.code}
                    </span>
                    <span
                      style={{ font: 'var(--type-data)', color: 'var(--purple-100)', whiteSpace: 'nowrap' }}
                    >
                      {S(item.rate * state.hours)} so‘m
                    </span>
                  </span>
                  <span
                    style={{
                      font: 'var(--type-data-xs)',
                      color: 'var(--text-dim)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {`${item.roomLabel} · ${stationSpec(item)}`}
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </Panel>

      {/* Konsolsiz (0023'dan keyingi) xonada konsolni MIJOZ tanlaydi —
          server uni majburiy talab qiladi (`CONSOLE_TYPE_REQUIRED`).
          Bu bo'lim bo'lmaganda yangi klublarda bron UMUMAN yuborilmasdi
          (audit topilmasi, 2026-08-16). Xonada eski `consoleType` bo'lsa
          server o'shani ishlatadi va bu bo'lim ko'rsatilmaydi. */}
      {needsConsole ? (
        <section style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <SectionLabel hint={state.bookingConsole ? undefined : 'Tanlanishi shart'}>
            Konsol
          </SectionLabel>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {Object.entries(CONSOLE_LABEL).map(([id, label]) => (
              <Pick
                key={id}
                on={state.bookingConsole === id}
                onClick={() => state.setBookingConsole(id)}
              >
                {label}
              </Pick>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

const ROW: CSSProperties = {
  display: 'flex',
  alignItems: 'baseline',
  justifyContent: 'space-between',
  gap: 8,
};

const STRIP: CSSProperties = {
  display: 'flex',
  gap: 6,
  overflowX: 'auto',
  scrollbarWidth: 'none',
  margin: '0 calc(var(--gutter) * -1)',
  padding: '0 var(--gutter)',
};

function SectionLabel({ children, hint }: { children: ReactNode; hint?: string }): ReactNode {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 }}>
      <span
        style={{
          font: 'var(--type-label)',
          letterSpacing: 'var(--ls-label)',
          textTransform: 'uppercase',
          color: 'var(--text-dim)',
        }}
      >
        {children}
      </span>
      {hint ? (
        <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-muted)' }}>{hint}</span>
      ) : null}
    </div>
  );
}

function Pick({
  children,
  on,
  off,
  onClick,
}: {
  children: ReactNode;
  on: boolean;
  off?: boolean;
  onClick: () => void;
}): ReactNode {
  return (
    <button
      type="button"
      disabled={off}
      onClick={onClick}
      aria-pressed={on}
      style={{
        cursor: off ? 'not-allowed' : 'pointer',
        height: 'var(--control-h)',
        padding: '0 11px',
        display: 'inline-flex',
        alignItems: 'center',
        background: on ? 'var(--surface-selected)' : 'var(--surface-inset)',
        border: `1px solid ${on ? 'var(--primary-100)' : 'var(--line-1)'}`,
        color: on ? 'var(--text-title)' : 'var(--text-muted)',
        font: 'var(--type-body-sm)',
        opacity: off ? 0.4 : 1,
        transition: 'var(--t-control)',
      }}
    >
      {children}
    </button>
  );
}
