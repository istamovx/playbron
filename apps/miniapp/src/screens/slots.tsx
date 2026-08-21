import { CyberLoader, EmptyState, Panel } from '@playbron/ui';
import { useEffect, useMemo, type CSSProperties, type ReactNode } from 'react';

import { useLocale, useT } from '../i18n';
import { hhmm, money } from '../lib/format';
import {
  ANY,
  CONSOLE_LABEL,
  consoleTypes,
  dayOptions,
  freeStations,
  isPast,
  durationOptions,
  isoDateOf,
  maxHours,
  nowMinutesOfDay,
  roomTypes,
  slotTimes,
  stationSpec,
  type BookingLimits,
  type SlotFilter,
} from '../lib/slots';
import { useApp } from '../store/app';
import { useBooking, useDayBookings } from '../store/booking';

/**
 * Slot tanlash — real stansiya + `GET /clubs/{id}/bookings/day` ustida.
 *
 * Kun tasmasi faqat sana ko'rsatadi (bandlik faqat TANLANGAN kun uchun
 * yuklanadi) — 14 kunni oldindan so'rash 14 ta so'rov degani edi.
 */
export function SlotsScreen(): ReactNode {
  const t = useT();
  const locale = useLocale();
  const state = useApp();
  const clubId = state.clubId;
  const club = useBooking((s) => s.clubs.find((item) => item.id === clubId) ?? null);
  const stations = useBooking((s) => s.stations);
  const stationsLoading = useBooking((s) => s.stationsLoading);
  const loadStations = useBooking((s) => s.loadStations);
  const loadDay = useBooking((s) => s.loadDay);
  const dayLoading = useBooking((s) => s.dayLoading);

  const timezone = club?.timezone ?? 'Asia/Tashkent';
  const dateKey = isoDateOf(state.day, timezone);
  const dayBookings = useDayBookings(dateKey);
  const nowMin = nowMinutesOfDay(timezone);

  const openMin = club?.opensAtMin ?? 0;
  const closeMin = club?.closesAtMin ?? 0;

  // Klub hali yuklanmagan bo'lsa ham hook'lar chaqirilishi kerak — pastdagi
  // erta `return` shartsiz hook tartibini buzardi. Klubsiz holda `openMin`
  // ham `closeMin` ham 0, ya'ni `slotTimes()` baribir bo'sh ro'yxat beradi.
  const limits: BookingLimits = useMemo(
    () => ({
      minBookingHours: club?.minBookingHours ?? 1,
      maxBookingHours: club?.maxBookingHours ?? 1,
      maxAdvanceDays: club?.maxAdvanceDays ?? 1,
      slotStepMin: club?.slotStepMin ?? 30,
    }),
    [club?.minBookingHours, club?.maxBookingHours, club?.maxAdvanceDays, club?.slotStepMin],
  );
  const durations = useMemo(() => durationOptions(limits), [limits]);

  useEffect(() => {
    if (clubId === null) return;
    if (stations.length === 0) void loadStations(clubId);
  }, [clubId, stations.length, loadStations]);

  useEffect(() => {
    if (clubId === null) return;
    void loadDay(clubId, dateKey);
  }, [clubId, dateKey, loadDay]);

  const filter: SlotFilter = useMemo(
    () => ({ room: state.room, console: state.console }),
    [state.room, state.console],
  );
  const days = useMemo(
    () =>
      dayOptions(timezone, locale, { today: t('today'), tomorrow: t('tomorrow') }, limits.maxAdvanceDays),
    [timezone, locale, t, limits.maxAdvanceDays],
  );

  // Butun bandlik to'ri memolangan. Ekran soat tiki tufayli SEKUNDIGA
  // qayta render bo'ladi, `freeStations()` esa har slot uchun stansiya ×
  // bron bo'yicha yuguradi — memosiz bu sekundiga o'n minglab
  // `Intl.formatToParts` chaqiruvi edi. `nowMin` daqiqa aniqligida,
  // shuning uchun haqiqiy qayta hisob daqiqada bir marta bo'ladi.
  const times = useMemo(
    () => slotTimes(openMin, closeMin, limits).filter((from) => !isPast(state.day, from, nowMin)),
    [openMin, closeMin, limits, state.day, nowMin],
  );
  const open = useMemo(
    () =>
      times.filter(
        (from) =>
          freeStations(stations, dayBookings, from, 1, closeMin, filter, timezone).length > 0,
      ),
    [times, stations, dayBookings, closeMin, filter, timezone],
  );
  const limit = useMemo(
    () => maxHours(stations, dayBookings, state.start, closeMin, filter, timezone, limits),
    [stations, dayBookings, state.start, closeMin, filter, timezone, limits],
  );
  const freeNow = useMemo(
    () =>
      freeStations(stations, dayBookings, state.start, state.hours, closeMin, filter, timezone),
    [stations, dayBookings, state.start, state.hours, closeMin, filter, timezone],
  );

  // Tanlangan xona konsolsiz bo'lsa (0023'dan keyingi) — mijoz o'zi tanlaydi
  const selectedStation = stations.find((item) => item.id === state.station);
  const needsConsole = selectedStation !== undefined && selectedStation.consoleType === null;

  const { start, hours, station, setDay, setStart, setHours, setStation } = state;

  // Filtr, kun yoki bandlik o'zgarganda tanlov yaroqsiz bo'lib qolmasin.
  useEffect(() => {
    if (stations.length === 0) return;
    // `open` render'da allaqachon hisoblangan — bu yerda ikkinchi nusxasi
    // turardi, ya'ni butun to'r har render'da IKKI marta yugurar va ikki
    // nusxa bir-biridan ajralib ketishi mumkin edi.
    const free = open;
    const scope = filter;

    if (free.length === 0) {
      setStation(null);
      return;
    }

    if (!free.includes(start)) {
      setStart(free[0] as number);
      return;
    }

    const max = maxHours(stations, dayBookings, start, closeMin, scope, timezone, limits);
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
    open,
    filter,
    limits,
    start,
    hours,
    station,
    closeMin,
    timezone,
    setStation,
    setStart,
    setHours,
  ]);

  if (clubId === null || !club) {
    return <EmptyState icon="storefront">{t('clubNotSelected')}</EmptyState>;
  }

  if (stationsLoading && stations.length === 0) {
    return (
      <div style={{ display: 'flex', flex: 1, justifyContent: 'center', alignItems: 'center' }}>
        <CyberLoader label={t('loading')} />
      </div>
    );
  }

  if (stations.length === 0) {
    return (
      <EmptyState icon="meeting_room" title={t('roomsEmptyTitle')}>
        {t('roomsEmptyHint')}
      </EmptyState>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <section style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <SectionLabel>{t('labelDate')}</SectionLabel>
        <div style={STRIP}>
          {days.map((option) => {
            const on = option.index === state.day;
            return (
              <button
                key={option.index}
                type="button"
                onClick={() => setDay(option.index)}
                aria-current={on ? 'date' : undefined}
                aria-label={option.label}
                title={option.label}
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
                  {option.weekday}
                </span>
                <span
                  style={{
                    font: 'var(--type-data)',
                    color: on ? 'var(--text-title)' : 'var(--text-body)',
                  }}
                >
                  {option.dayNumber}
                </span>
              </button>
            );
          })}
        </div>
      </section>

      <section style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <SectionLabel>{t('labelRoomType')}</SectionLabel>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          <Pick on={state.room === ANY} onClick={() => state.setRoom(ANY)}>
            {t('filterAny')}
          </Pick>
          {roomTypes(stations).map((room) => (
            <Pick key={room} on={state.room === room} onClick={() => state.setRoom(room)}>
              {room}
            </Pick>
          ))}
        </div>
      </section>

      <section style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <SectionLabel>{t('labelConsole')}</SectionLabel>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          <Pick on={state.console === ANY} onClick={() => state.setConsole(ANY)}>
            {t('filterAny')}
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
        <SectionLabel hint={limit > 0 ? t('durationLimit', { hours: limit }) : undefined}>
          {t('labelDuration')}
        </SectionLabel>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {durations.map((value) => (
            <Pick
              key={value}
              on={state.hours === value}
              off={value > limit}
              onClick={() => state.setHours(value)}
            >
              {t('hoursUnit', { hours: value })}
            </Pick>
          ))}
        </div>
      </section>

      <Panel title={t('freeTimeTitle')} notch>
        {dayLoading && dayBookings.length === 0 ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '12px 0' }}>
            <CyberLoader label={t('loading')} />
          </div>
        ) : open.length === 0 ? (
          <EmptyState icon="event_busy" title={t('freeTimeEmptyTitle')}>
            {t('freeTimeEmptyHint')}
          </EmptyState>
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
              const fits =
                count > 0
                  ? 0
                  : maxHours(stations, dayBookings, from, closeMin, filter, timezone, limits);
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
                    color: on
                      ? 'var(--text-on-accent)'
                      : usable
                        ? 'var(--text-body)'
                        : 'var(--text-dim)',
                    opacity: usable ? 1 : 0.45,
                    transition: 'var(--t-control)',
                  }}
                >
                  <span style={{ font: 'var(--type-data)' }}>{hhmm(from)}</span>
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
                    {count > 0
                      ? t('slotRooms', { count })
                      : fits > 0
                        ? t('slotFits', { hours: fits })
                        : t('slotBusy')}
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </Panel>

      <Panel
        title={t('freeRoomsTitle', {
          from: hhmm(state.start),
          to: hhmm(state.start + state.hours * 60),
        })}
        notch
      >
        {freeNow.length === 0 ? (
          <EmptyState icon="meeting_room" title={t('freeRoomsEmptyTitle')}>
            {t('freeRoomsEmptyHint', { hours: state.hours })}
          </EmptyState>
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
                    {/* Soatlik tarif — server qiymati. Umumiy summa bu yerda
                        KO'PAYTIRILMAYDI: tarif oyna ichida o'zgarishi mumkin
                        (`CLAUDE.md` §Pul). */}
                    <span
                      style={{
                        font: 'var(--type-data)',
                        color: 'var(--purple-100)',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {t('perHour', { sum: money(item.rate) })}
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
                    {[item.roomLabel, stationSpec(item)].filter(Boolean).join(' · ')}
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
          <SectionLabel hint={state.bookingConsole ? undefined : t('consoleRequired')}>
            {t('labelConsole')}
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
    <div
      style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 }}
    >
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
