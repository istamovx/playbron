import { Panel } from '@playbron/ui';
import { useEffect, type CSSProperties, type ReactNode } from 'react';

import {
  ANY,
  DURATIONS,
  HM,
  S,
  SLOT_STEP,
  clubConsoles,
  clubRoomTypes,
  dayOptions,
  freeSlotCount,
  freeStations,
  isPast,
  maxHours,
  slotTimes,
  stationSpec,
  type SlotFilter,
} from '../mock/data';
import { useApp, useNow } from '../store/app';

/**
 * Slot tanlash — sana, xona turi/konsol filtri, davomiylik va vaqt.
 * Bo'sh vaqtlar `bookedRanges()` dan hisoblanadi: band slot tanlanmaydi,
 * davomiylik esa faqat sig'adigan qismigacha ochiq turadi.
 */
export function SlotsScreen(): ReactNode {
  const state = useApp();
  const nowMin = Math.floor(useNow() / 60);
  // Slot chegarasiga yaxlitlash — effekt har soniyada emas, har 30 daqiqada qayta ishlaydi
  const nowSlot = Math.floor(nowMin / SLOT_STEP) * SLOT_STEP;

  const filter: SlotFilter = { room: state.room, console: state.console };
  const days = dayOptions();
  // O'tib ketgan slotlar ko'rsatilmaydi — bugungi to'r qolgan vaqtdan boshlanadi
  const times = slotTimes().filter((from) => !isPast(state.day, from, nowSlot));
  const open = times.filter((from) => freeStations(state.day, from, 1, filter).length > 0);
  const limit = maxHours(state.day, state.start, filter);
  const stations = freeStations(state.day, state.start, state.hours, filter);

  const { day, start, hours, station, setDay, setStart, setHours, setStation } = state;

  // Filtr yoki kun o'zgarganda tanlov yaroqsiz bo'lib qolmasin
  useEffect(() => {
    const scope: SlotFilter = { room: state.room, console: state.console };
    const free = slotTimes().filter(
      (from) => !isPast(day, from, nowSlot) && freeStations(day, from, 1, scope).length > 0,
    );

    // Filtr joriy kunni bo'shatib qo'ysa — eng yaqin bo'sh kunga o'tamiz
    if (free.length === 0) {
      const nearest = dayOptions().find(
        (option) => freeSlotCount(option.index, 1, scope, nowSlot) > 0,
      );
      if (nearest && nearest.index !== day) setDay(nearest.index);
      return;
    }

    if (!free.includes(start)) {
      setStart(free[0] as number);
      return;
    }

    const max = maxHours(day, start, scope);
    if (hours > max) {
      setHours(max);
      return;
    }

    const list = freeStations(day, start, hours, scope);
    if (list.length > 0 && !list.some((item) => item.code === station)) {
      setStation((list[0] as (typeof list)[number]).code);
    }
  }, [
    day,
    start,
    hours,
    station,
    state.room,
    state.console,
    nowSlot,
    setDay,
    setStart,
    setHours,
    setStation,
  ]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <section style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <SectionLabel>Sana</SectionLabel>
        <div style={STRIP}>
          {days.map((option) => {
            const on = option.index === state.day;
            const free = freeSlotCount(option.index, state.hours, filter, nowSlot);
            // Tanlangan davomiylik sig'masa ham kun ochiq qoladi — qisqaroq seans bo'lishi mumkin
            const shorter = free > 0 ? free : freeSlotCount(option.index, 1, filter, nowSlot);
            return (
              <button
                key={option.index}
                type="button"
                onClick={() => state.setDay(option.index)}
                aria-current={on ? 'date' : undefined}
                disabled={shorter === 0}
                style={{
                  flex: 'none',
                  cursor: shorter === 0 ? 'not-allowed' : 'pointer',
                  width: 62,
                  padding: '7px 0',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 2,
                  background: on ? 'var(--surface-selected)' : 'var(--surface-card)',
                  border: `1px solid ${on ? 'var(--primary-100)' : 'var(--line-1)'}`,
                  clipPath: 'var(--clip-tr)',
                  opacity: shorter === 0 ? 0.4 : 1,
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
                <span
                  style={{
                    font: 'var(--type-data-xs)',
                    color:
                      free > 0
                        ? 'var(--secondary-500)'
                        : shorter > 0
                          ? 'var(--yellow-100)'
                          : 'var(--text-dim)',
                  }}
                >
                  {free > 0 ? free : shorter > 0 ? 'qisqa' : 'band'}
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
          {clubRoomTypes().map((room) => (
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
          {clubConsoles().map((type) => (
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
        {open.length === 0 ? (
          <div style={{ font: 'var(--type-body-sm)', color: 'var(--text-muted)' }}>
            Bu kunda tanlangan filtr bo‘yicha bo‘sh vaqt yo‘q. Boshqa sana yoki xona turini tanlang.
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6 }}>
            {times.map((from) => {
              const count = freeStations(state.day, from, state.hours, filter).length;
              // Tanlangan davomiylik sig'masa — shu vaqtdan qancha olish mumkinligi
              const fits = count > 0 ? 0 : maxHours(state.day, from, filter);
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
        {stations.length === 0 ? (
          <div style={{ font: 'var(--type-body-sm)', color: 'var(--text-muted)' }}>
            {state.hours} soatga bo‘sh xona yo‘q — davomiylikni qisqartiring.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {stations.map((item) => {
              const on = item.code === state.station;
              return (
                <button
                  key={item.code}
                  type="button"
                  onClick={() => state.setStation(item.code)}
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
                      style={{
                        font: 'var(--type-data)',
                        color: 'var(--purple-100)',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {S(item.rate * state.hours)} so‘m
                    </span>
                  </span>
                  {/* Soatlik narx klub sahifasida — bu yerda faqat spetsifikatsiya sig'adi */}
                  <span
                    style={{
                      font: 'var(--type-data-xs)',
                      color: 'var(--text-dim)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {stationSpec(item)}
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </Panel>
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

/** Tanlov tugmasi — `Chip` ning o'chiriladigan varianti. */
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
