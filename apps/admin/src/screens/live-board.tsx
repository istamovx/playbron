import {
  ActivityBars,
  Button,
  FieldLadder,
  Grid,
  MetricCell,
  NO_SHOW_MIN,
  Panel,
  SegmentedControl,
  StatusLine,
  prepayAmount,
  type ButtonVariant,
} from '@playbron/ui';
import type { ReactNode } from 'react';

import {
  DAY_END,
  DAY_START,
  DUR,
  EXT_ITEMS,
  EXT_MIN,
  HM,
  LABEL,
  S,
  ST,
  TONE,
  consoleLabel,
  type MockStation,
} from '../mock/data';
import { useBoard, useNow } from '../store/board';

/** Keyingi bron — uzaytirish chegarasi shu yerdan chiqadi (prototipdagi NEXT). */
const NEXT: Record<number, number> = { 1: 22 * 60, 8: 21 * 60 + 30, 9: 22 * 60 + 30 };

/**
 * Joriy lahza gistogrammaning nechanchi ustuniga tushadi (10:00 – 02:00 oynasi).
 * Oyna tashqarisida urg'u ko'rsatilmaydi.
 */
function nowBar(bars: number, now: number): number | undefined {
  const minutes = now / 60;
  const offset = minutes >= DAY_START ? minutes - DAY_START : minutes + 24 * 60 - DAY_START;
  const span = DAY_END - DAY_START;
  if (offset < 0 || offset >= span) return undefined;
  return Math.min(bars - 1, Math.floor((offset / span) * bars));
}

interface Field {
  k: string;
  v: string;
  tone: string;
}

interface Action {
  label: string;
  variant: ButtonVariant;
  icon: string;
  onClick: () => void;
}

export function LiveBoardScreen(): ReactNode {
  const now = useNow();
  const state = useBoard();

  const live = liveStations(state.nsMarked, state.closedRooms, state.extended);
  const selected = live.find((station) => station.id === state.sel) ?? (live[0] as MockStation);
  const extendTarget = state.extendFor
    ? (live.find((station) => station.id === state.extendFor) ?? null)
    : null;

  const counters = {
    occupied: live.filter((station) => station.status === 'OCCUPIED').length,
    free: live.filter((station) => station.status === 'FREE').length,
    reserved: live.filter((station) => station.status === 'RESERVED').length,
    maintenance: live.filter((station) => station.status === 'MAINTENANCE').length,
    overtime: live.filter((station) => station.status === 'OCCUPIED' && station.b * 60 - now < 0)
      .length,
  };

  const limit =
    extendTarget && NEXT[extendTarget.id] !== undefined
      ? (NEXT[extendTarget.id] as number) - extendTarget.b
      : null;
  const extendBlocked = Boolean(extendTarget && limit !== null && state.extendMin > limit);
  const limitText = extendTarget
    ? limit === null
      ? 'Keyingi bron yo‘q — cheklovsiz uzaytirish mumkin'
      : `Keyingi bron ${HM(NEXT[extendTarget.id] as number)} da · maksimum ${limit} daqiqa`
    : '';

  return (
    <div className="ds-split" style={{ alignItems: 'start' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)', minWidth: 0 }}>
        <div className="pb-tiles-5">
          <MetricCell label="Band" value={`${counters.occupied} / 10`} />
          <MetricCell label="Bo‘sh" value={String(counters.free)} />
          <MetricCell label="Rezerv" value={String(counters.reserved)} tone="med" />
          <MetricCell label="Ta’mirda" value={String(counters.maintenance)} />
          <MetricCell label="Overtime" value={String(counters.overtime)} tone="high" />
        </div>

        <Panel title="Xonalar" notch brackets>
          <Grid min={235}>
            {live.map((station) => (
              <StationCard
                key={station.id}
                station={station}
                now={now}
                selected={state.sel === station.id}
                onSelect={() => state.select(station.id)}
              />
            ))}
          </Grid>
        </Panel>

        <Panel title="Bugungi bandlik" notch>
          <div className="ds-chart">
            <ActivityBars
              bars={44}
              height={74}
              seed={7}
              active={nowBar(44, now)}
              labels={['10:00', '14:00', '18:00', '22:00', '02:00']}
              tip={(value, index) =>
                `${HM(DAY_START + Math.round((index / 44) * (DAY_END - DAY_START)))} · ${Math.round(Math.min(1, value) * 10)} / 10 xona`
              }
            />
          </div>
        </Panel>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)', minWidth: 0 }}>
        {extendTarget ? (
          <Panel title={`Uzaytirish · ${extendTarget.code}`} notch brackets glow>
            <div
              style={{
                padding: 'var(--card-pad)',
                border: '1px dashed var(--line-3)',
                display: 'flex',
                gap: 10,
                alignItems: 'flex-start',
                marginBottom: 'var(--gap-block)',
              }}
            >
              <span style={{ flex: 'none', color: 'var(--purple-100)', display: 'flex' }}>
                <span
                  className="material-symbols-rounded"
                  style={{ fontFamily: 'var(--font-icon)', fontSize: 16, lineHeight: 1 }}
                >
                  record_voice_over
                </span>
              </span>
              <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-body)' }}>
                Mijozdan so‘rang: hali o‘ynaysizmi yoki hisobni yopamizmi? O‘ynaydi desa taxminiy
                vaqtni aniqlang.
              </span>
            </div>

            <div
              style={{
                font: 'var(--type-label)',
                letterSpacing: 'var(--ls-label)',
                textTransform: 'uppercase',
                color: 'var(--text-label)',
                marginBottom: 8,
              }}
            >
              Qancha vaqtga
            </div>
            <div className="ds-scroll-x">
              <SegmentedControl
                brackets
                items={EXT_ITEMS}
                value={EXT_ITEMS[EXT_MIN.indexOf(state.extendMin)] ?? (EXT_ITEMS[1] as string)}
                onChange={(label) => {
                  const index = EXT_ITEMS.indexOf(label);
                  if (index >= 0) state.setExtendMin(EXT_MIN[index] as number);
                }}
              />
            </div>

            <div style={{ marginTop: 'var(--gap-block)' }}>
              <FieldLadder>
                {extendFields(extendTarget, state.extendMin).map((field) => (
                  <Row key={field.k} field={field} />
                ))}
              </FieldLadder>
            </div>

            <div style={{ marginTop: 'var(--gap-block)' }}>
              <StatusLine
                tone={extendBlocked ? 'danger' : 'neutral'}
                icon={extendBlocked ? 'event_busy' : 'event_available'}
                parts={limitText}
              />
            </div>

            <div
              style={{
                marginTop: 'var(--gap-block)',
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--gap-tight)',
              }}
            >
              <Button
                variant="primary"
                size="lg"
                notch
                block
                icon="more_time"
                disabled={extendBlocked}
                onClick={state.confirmExtend}
              >
                {`+${state.extendMin} daqiqa`}
              </Button>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(min(120px, 100%), 1fr))',
                  gap: 'var(--gap-tight)',
                }}
              >
                <Button variant="secondary" block icon="lock" onClick={() => state.setScreen('pos')}>
                  Yopamiz
                </Button>
                <Button variant="ghost" block onClick={state.closeExtend}>
                  Bekor
                </Button>
              </div>
            </div>
          </Panel>
        ) : null}

        <Panel title={`${selected.code} · ${selected.room}`} notch brackets>
          <FieldLadder>
            {detailFields(selected, now).map((field) => (
              <Row key={field.k} field={field} />
            ))}
          </FieldLadder>

          <div
            style={{
              marginTop: 'var(--gap-block)',
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--gap-tight)',
            }}
          >
            {detailActions(selected, now, {
              extend: () => state.openExtend(selected.id),
              pos: () => state.setScreen('pos'),
              noShow: () => {
                state.markNoShow();
                state.setScreen('blacklist');
              },
            }).map((action, index) => (
              <Button
                key={action.label}
                variant={action.variant}
                size={index === 0 ? 'lg' : 'md'}
                notch={index === 0}
                block
                icon={action.icon}
                onClick={action.onClick}
              >
                {action.label}
              </Button>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}

function Row({ field }: { field: Field }): ReactNode {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 12,
        minHeight: 'var(--field-h)',
        padding: '4px 10px',
        background: 'var(--surface-field)',
        border: '1px solid var(--line-1)',
      }}
    >
      <span
        style={{
          font: 'var(--type-label)',
          letterSpacing: 'var(--ls-label)',
          textTransform: 'uppercase',
          color: 'var(--text-label)',
        }}
      >
        {field.k}
      </span>
      <span style={{ font: 'var(--type-data)', color: field.tone }}>{field.v}</span>
    </div>
  );
}

function StationCard({
  station,
  now,
  selected,
  onSelect,
}: {
  station: MockStation;
  now: number;
  selected: boolean;
  onSelect: () => void;
}): ReactNode {
  const view = cardView(station, now);

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') onSelect();
      }}
      style={{
        cursor: 'pointer',
        minWidth: 0,
        padding: 'var(--card-pad)',
        background: 'var(--surface-panel)',
        border: `1px solid ${selected ? 'var(--primary-100)' : 'var(--line-1)'}`,
        boxShadow: `inset 3px 0 0 ${view.acc}`,
        clipPath: 'var(--clip-tr)',
        display: 'flex',
        flexDirection: 'column',
        gap: 9,
        transition:
          'background 140ms cubic-bezier(.22,.61,.36,1),border-color 140ms cubic-bezier(.22,.61,.36,1)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 }}>
        <span
          style={{
            font: 'var(--fw-regular) var(--fs-panel-fluid)/var(--lh-snug) var(--font-display)',
            color: 'var(--text-title)',
            letterSpacing: '.02em',
          }}
        >
          {station.code}
        </span>
        <span
          style={{
            font: 'var(--type-label)',
            letterSpacing: 'var(--ls-label)',
            textTransform: 'uppercase',
            color: view.acc,
            whiteSpace: 'nowrap',
          }}
        >
          {view.statusLabel}
        </span>
      </div>

      <div
        style={{
          font: 'var(--type-data-xs)',
          color: 'var(--text-dim)',
          letterSpacing: '.02em',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {`${consoleLabel(station.cons)} · ${station.tv}" · ${station.pads} pad`}
      </div>

      <div style={{ height: 1, background: 'var(--line-1)' }} />

      <div
        style={{
          font: 'var(--type-body-sm)',
          color: view.guestColor,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {view.guest}
      </div>

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
          flexWrap: 'wrap',
        }}
      >
        <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-muted)' }}>{view.window}</span>
        <span style={{ font: 'var(--type-data)', color: view.timerColor, letterSpacing: '.03em' }}>
          {view.timer}
        </span>
      </div>

      <div style={{ height: 3, background: 'var(--chart-track)', position: 'relative', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', inset: '0 auto 0 0', width: view.pct, background: view.acc }} />
      </div>
    </div>
  );
}

/** Prototipdagi LIVE hisobi: no-show, yopilgan xona va uzaytirish qo'llanadi. */
export function liveStations(
  nsMarked: boolean,
  closedRooms: Record<number, { from: number; to: number }>,
  extended: Record<number, number>,
): MockStation[] {
  return ST.map((station) => {
    if (nsMarked && station.id === 6) {
      return { ...station, status: 'FREE' as const, guest: undefined, a: 0, b: 0 };
    }

    const shut = closedRooms[station.id];
    if (shut) {
      return {
        ...station,
        status: 'FREE' as const,
        guest: undefined,
        a: 0,
        b: 0,
        hist: [...station.hist, [shut.from, shut.to, (station.guest ?? '').split(' ')[0] ?? '']] as [
          number,
          number,
          string,
        ][],
      };
    }
    if (extended[station.id]) {
      return { ...station, b: station.b + (extended[station.id] as number) };
    }
    return station;
  });
}

function cardView(
  station: MockStation,
  now: number,
): {
  acc: string;
  statusLabel: string;
  guest: string;
  guestColor: string;
  window: string;
  timer: string;
  timerColor: string;
  pct: string;
} {
  let timer = '—';
  let timerColor = 'var(--text-dim)';
  let pct = '0%';
  let window = '—';
  let guest = 'Bo‘sh';
  let guestColor = 'var(--text-dim)';
  let over = false;
  let overdue = false;

  if (station.status === 'OCCUPIED') {
    const remaining = station.b * 60 - now;
    over = remaining < 0;
    timer = DUR(remaining);
    timerColor = over
      ? 'var(--red-100)'
      : remaining < 900
        ? 'var(--yellow-100)'
        : 'var(--text-title)';
    pct = `${Math.max(0, Math.min(100, ((now - station.a * 60) / ((station.b - station.a) * 60)) * 100)).toFixed(1)}%`;
    window = `${HM(station.a)} → ${HM(station.b)}`;
    guest = station.guest ?? '';
    guestColor = 'var(--text-title)';
  } else if (station.status === 'RESERVED') {
    const late = now - station.a * 60;
    overdue = late > NO_SHOW_MIN * 60;
    timer = DUR(station.a * 60 - now);
    timerColor = overdue ? 'var(--red-100)' : 'var(--yellow-100)';
    window = `${HM(station.a)} dan`;
    guest = station.guest ?? '';
    guestColor = 'var(--text-body)';
  } else if (station.status === 'MAINTENANCE') {
    guest = station.note ?? '';
    guestColor = 'var(--text-dim)';
    window = 'Bloklangan';
  } else {
    window = 'Darhol';
  }

  return {
    acc: over || overdue ? 'var(--red-100)' : TONE[station.status],
    statusLabel: over ? 'Overtime' : overdue ? 'Kelmadi?' : LABEL[station.status],
    guest,
    guestColor,
    window,
    timer,
    timerColor,
    pct,
  };
}

function detailFields(station: MockStation, now: number): Field[] {
  const overdue = station.status === 'RESERVED' && now - station.a * 60 > NO_SHOW_MIN * 60;
  const hours =
    station.status === 'FREE' || station.status === 'MAINTENANCE' ? 0 : (station.b - station.a) / 60;
  const play = Math.round(hours * station.rate);

  const fields: Field[] =
    station.status === 'FREE'
      ? [
          { k: 'Turi', v: `${station.room} xona`, tone: 'var(--text-body)' },
          { k: 'Konsol', v: consoleLabel(station.cons), tone: 'var(--text-body)' },
          { k: 'Ekran', v: `${station.tv}"`, tone: 'var(--text-body)' },
          { k: 'Joystik', v: `${station.pads} ta`, tone: 'var(--text-body)' },
          { k: 'Tarif', v: `${S(station.rate)} / soat`, tone: 'var(--text-title)' },
          { k: 'Holat', v: 'Bo‘sh', tone: 'var(--slot-free)' },
        ]
      : station.status === 'MAINTENANCE'
        ? [
            { k: 'Turi', v: `${station.room} xona`, tone: 'var(--text-body)' },
            { k: 'Konsol', v: consoleLabel(station.cons), tone: 'var(--text-body)' },
            { k: 'Sabab', v: station.note ?? '', tone: 'var(--yellow-100)' },
            { k: 'Holat', v: 'Bloklangan', tone: 'var(--fg-4)' },
          ]
        : [
            { k: 'Mijoz', v: station.guest ?? '', tone: 'var(--text-title)' },
            { k: 'Telefon', v: station.phone ?? '', tone: 'var(--text-body)' },
            { k: 'Kod', v: station.code6 ?? '', tone: 'var(--purple-100)' },
            { k: 'Turi', v: `${station.room} xona`, tone: 'var(--text-body)' },
            { k: 'Konsol', v: `${consoleLabel(station.cons)} · ${station.tv}"`, tone: 'var(--text-body)' },
            { k: 'Vaqt', v: `${HM(station.a)} → ${HM(station.b)}`, tone: 'var(--text-body)' },
            { k: 'Tarif', v: `${S(station.rate)} / soat`, tone: 'var(--text-body)' },
            { k: 'O‘yin summasi', v: S(play), tone: 'var(--text-title)' },
            { k: 'Bar', v: S(station.bar), tone: 'var(--text-title)' },
            {
              k: 'Bron to‘lovi',
              v: S(prepayAmount(station.rate)),
              tone: 'var(--secondary-500)',
            },
          ];

  if (station.priorNoShow) {
    fields.push({
      k: 'Oldingi no-show',
      v: `${station.priorNoShow} marta`,
      tone: 'var(--red-100)',
    });
  }
  if (overdue) {
    fields.push({ k: 'Kechikish', v: DUR(now - station.a * 60), tone: 'var(--red-100)' });
  }

  return fields;
}

function detailActions(
  station: MockStation,
  now: number,
  handlers: { extend: () => void; pos: () => void; noShow: () => void },
): Action[] {
  const overdue = station.status === 'RESERVED' && now - station.a * 60 > NO_SHOW_MIN * 60;
  const noop = (): void => undefined;

  if (station.status === 'FREE') {
    return [
      { label: 'Seans boshlash', variant: 'primary', icon: 'play_arrow', onClick: noop },
      { label: 'Bron', variant: 'secondary', icon: 'event', onClick: noop },
      { label: 'Bloklash', variant: 'ghost', icon: 'build', onClick: noop },
    ];
  }
  if (station.status === 'RESERVED' && overdue) {
    return [
      { label: 'Check-in', variant: 'primary', icon: 'how_to_reg', onClick: noop },
      { label: 'Yana 10 daqiqa', variant: 'secondary', icon: 'more_time', onClick: noop },
      {
        label: 'Kelmadi deb belgilash',
        variant: 'danger',
        icon: 'person_off',
        onClick: handlers.noShow,
      },
    ];
  }
  if (station.status === 'RESERVED') {
    return [
      { label: 'Check-in', variant: 'primary', icon: 'how_to_reg', onClick: noop },
      { label: 'Bekor', variant: 'danger', icon: 'close', onClick: noop },
    ];
  }
  if (station.status === 'MAINTENANCE') {
    return [{ label: 'Ishga qaytarish', variant: 'primary', icon: 'restart_alt', onClick: noop }];
  }

  return [
    { label: 'Uzaytirish', variant: 'primary', icon: 'more_time', onClick: handlers.extend },
    { label: 'Buyurtma', variant: 'secondary', icon: 'add_shopping_cart', onClick: handlers.pos },
    { label: 'Hisobni yopish', variant: 'secondary', icon: 'lock', onClick: handlers.pos },
  ];
}

function extendFields(station: MockStation, minutes: number): Field[] {
  return [
    { k: 'Joriy tugash', v: HM(station.b), tone: 'var(--text-body)' },
    { k: 'Yangi tugash', v: HM(station.b + minutes), tone: 'var(--text-title)' },
    {
      k: 'Qo‘shimcha',
      v: `${(minutes / 60).toFixed(1).replace('.0', '')} soat`,
      tone: 'var(--text-body)',
    },
    { k: 'Tarif', v: `${S(station.rate)} / soat`, tone: 'var(--text-body)' },
    {
      k: 'Qo‘shimcha summa',
      v: S(Math.round((minutes / 60) * station.rate)),
      tone: 'var(--text-title)',
    },
  ];
}
