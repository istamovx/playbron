import { Button, Icon, Panel, StatusLine, Tabs, TextField, prepayAmount } from '@playbron/ui';
import type { ReactNode } from 'react';

import { BONUS, CLK, DUR, HM, MENU, S, STOCK, soldNow } from '../mock/data';
import { useBoard, useNow } from '../store/board';
import { liveStations } from './live-board';

const MENU_CATS = ['Ichimliklar', 'Snack', 'Ovqat'];

const CATALOG_NOTE =
  'Katalog, narx va kirim faqat admin tomonidan kiritiladi. Xodim sotadi va smena yakunida sanaydi.';

const CASH_NOTE = 'Naqd pul kassaga qabul qilinadi va smena yakunida sanaladi.';

/** Kassa — `PlayBron Xodim.dc.html` KASSA / POS bo'limi. */
export function PosScreen(): ReactNode {
  const now = useNow();
  const state = useBoard();
  const live = liveStations(state.nsMarked, state.closedRooms, state.extended);

  const posStation = live.find((station) => station.id === state.posSel) ?? live[0];
  if (!posStation) return null;

  /** Barcha savatlar — qoldiqni kamaytirish uchun. */
  const allCart: Record<string, number> = {};
  for (const cart of Object.values(state.carts)) {
    for (const [id, qty] of Object.entries(cart)) allCart[id] = (allCart[id] ?? 0) + qty;
  }

  const cart = state.carts[state.posSel] ?? {};

  /** Qoldiq avtomatik: admin kiritgan miqdor − yetkazilgan buyurtmalar. */
  const stockOf = (id: string): number | null => {
    const entry = STOCK.find((row) => row.id === id);
    if (!entry) return null;
    return entry.start - entry.soldBefore - soldNow(id, state.orders, {});
  };

  // Qidiruv bo'sh bo'lsa — joriy kategoriya; aks holda butun katalog bo'ylab
  const query = state.search.trim().toLocaleLowerCase('uz-UZ');
  const source = query
    ? MENU.filter((item) => item.name.toLocaleLowerCase('uz-UZ').includes(query))
    : MENU.filter((item) => item.cat === state.menuCat);

  const posItems = source.map((item) => {
    const base = stockOf(item.id);
    const left = base === null ? null : base - (allCart[item.id] ?? 0);
    const out = left !== null && left <= 0;
    return {
      id: item.id,
      name: item.name,
      price: S(item.price),
      cat: item.cat,
      stock: left === null ? '∞' : out ? 'Tugadi' : `${left} dona`,
      stockTone: out
        ? 'var(--red-100)'
        : left !== null && left <= 5
          ? 'var(--yellow-100)'
          : 'var(--text-dim)',
      nameTone: out ? 'var(--text-dim)' : 'var(--text-title)',
      out,
    };
  });

  const cartLines = Object.entries(cart).map(([id, qty]) => {
    const item = MENU.find((menu) => menu.id === id);
    return {
      id,
      name: item?.name ?? '',
      unit: S(item?.price ?? 0),
      qty,
      sum: S((item?.price ?? 0) * qty),
    };
  });

  const ordersAmount = cartLines.reduce(
    (sum, line) => sum + (MENU.find((item) => item.id === line.id)?.price ?? 0) * line.qty,
    0,
  );

  const posHours = (posStation.b - posStation.a) / 60;
  const posPlay = Math.round(posHours * posStation.rate);
  const prepaid = prepayAmount(posStation.rate);
  const loyalty = BONUS[posStation.id] ?? 0;
  const due = Math.max(0, posPlay + ordersAmount - prepaid - loyalty);

  const openBills = live
    .filter((station) => station.status === 'OCCUPIED')
    .map((station) => {
      const on = station.id === state.posSel;
      const stationCart = state.carts[station.id] ?? {};
      const bar = Object.entries(stationCart).reduce(
        (sum, [id, qty]) => sum + (MENU.find((item) => item.id === id)?.price ?? 0) * qty,
        0,
      );
      const hours = (station.b - station.a) / 60;
      const remaining = station.b * 60 - now;
      const play = Math.round(hours * station.rate);
      const dep = prepayAmount(station.rate);

      return {
        id: station.id,
        code: station.code,
        guest: station.guest ?? '',
        total: S(Math.max(0, play + bar - dep - (BONUS[station.id] ?? 0))),
        timer: DUR(remaining),
        timerTone:
          remaining < 0
            ? 'var(--red-100)'
            : remaining < 900
              ? 'var(--yellow-100)'
              : 'var(--text-muted)',
        on,
      };
    });

  const closed = state.closed;
  const notClosed = !closed && posStation.status === 'OCCUPIED';
  const noOpenBills = !closed && posStation.status !== 'OCCUPIED';
  const closable = state.pay === 'Naqd' || state.receipt === 'confirmed';

  return (
    <div className="ds-split" style={{ alignItems: 'start' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)', minWidth: 0 }}>
        <div className="ds-scroll-x">
          <Tabs items={MENU_CATS} value={state.menuCat} onChange={state.setMenuCat} />
        </div>

        <Panel title="Ochiq hisoblar" notch>
          <div
            style={{
              display: 'grid',
              minWidth: 0,
              // 16px shrift uchun kod + taymer bir qatorga sig'ishi kerak
              gridTemplateColumns: 'repeat(auto-fit, minmax(min(215px, 100%), 1fr))',
              gap: 'var(--gap-tight)',
            }}
          >
            {openBills.map((bill) => (
              <div
                key={bill.id}
                role="button"
                tabIndex={0}
                onClick={() => state.setPosSel(bill.id)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') state.setPosSel(bill.id);
                }}
                style={{
                  cursor: 'pointer',
                  padding: 'var(--card-pad)',
                  background: bill.on ? 'var(--surface-selected)' : 'var(--surface-card)',
                  border: `1px solid ${bill.on ? 'var(--primary-100)' : 'var(--line-1)'}`,
                  clipPath: 'var(--clip-tr)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 6,
                  minWidth: 0,
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'baseline',
                    justifyContent: 'space-between',
                    gap: 8,
                  }}
                >
                  <span style={{ font: 'var(--type-section)', color: 'var(--text-title)' }}>
                    {bill.code}
                  </span>
                  <span style={{ font: 'var(--type-data-xs)', color: bill.timerTone }}>
                    {bill.timer}
                  </span>
                </div>
                <span
                  style={{
                    font: 'var(--type-body-sm)',
                    color: 'var(--text-muted)',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {bill.guest}
                </span>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'baseline',
                    justifyContent: 'space-between',
                    gap: 8,
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
                    To‘lanadi
                  </span>
                  <span style={{ font: 'var(--type-data)', color: 'var(--purple-100)' }}>
                    {bill.total}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Panel>

        <div
          style={{
            display: 'flex',
            gap: 10,
            alignItems: 'flex-start',
            padding: 'var(--card-pad)',
            border: '1px dashed var(--line-2)',
          }}
        >
          <span style={{ flex: 'none', color: 'var(--text-dim)', display: 'flex' }}>
            <Icon name="lock" size={15} />
          </span>
          <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-muted)' }}>
            {CATALOG_NOTE}
          </span>
        </div>

        <Panel
          title="Tez sotuv"
          notch
          brackets
          action={
            <TextField
              value={state.search}
              onChange={state.setSearch}
              placeholder="Mahsulot qidirish"
              icon="search"
              // Sarlavha bilan bir qatorga sig'masa o'z qatoriga tushib to'liq kenglik oladi
              style={{ flex: '1 1 220px', minWidth: 0, maxWidth: 320 }}
            />
          }
        >
          <div
            style={{
              display: 'grid',
              minWidth: 0,
              gridTemplateColumns: 'repeat(auto-fit, minmax(min(200px, 100%), 1fr))',
              gap: 'var(--gap-panel)',
            }}
          >
            {posItems.map((item) => (
              <div
                key={item.id}
                role="button"
                tabIndex={item.out ? -1 : 0}
                onClick={() => {
                  if (!item.out) state.bump(item.id, 1);
                }}
                onKeyDown={(event) => {
                  if (!item.out && (event.key === 'Enter' || event.key === ' ')) state.bump(item.id, 1);
                }}
                style={{
                  cursor: item.out ? 'not-allowed' : 'pointer',
                  minWidth: 0,
                  padding: 'var(--card-pad)',
                  background: 'var(--surface-card)',
                  border: '1px solid var(--line-1)',
                  clipPath: 'var(--clip-tr)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 8,
                  minHeight: 82,
                  justifyContent: 'space-between',
                  transition: 'background 140ms cubic-bezier(.22,.61,.36,1)',
                }}
              >
                <span style={{ display: 'grid', gap: 2, minWidth: 0 }}>
                  <span
                    style={{
                      font: 'var(--type-section)',
                      color: item.nameTone,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {item.name}
                  </span>
                  {query ? (
                    <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                      {item.cat}
                    </span>
                  ) : null}
                </span>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'baseline',
                    justifyContent: 'space-between',
                    gap: 8,
                    flexWrap: 'wrap',
                  }}
                >
                  <span style={{ font: 'var(--type-data)', color: 'var(--purple-100)' }}>
                    {item.price}
                  </span>
                  <span style={{ font: 'var(--type-data-xs)', color: item.stockTone }}>
                    {item.stock}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)', minWidth: 0 }}>
        <Panel
          title={
            closed
              ? `Hisob yopildi · ${closed.code}`
              : posStation.status === 'OCCUPIED'
                ? `Hisob · ${posStation.code}`
                : 'Hisob'
          }
          notch
          brackets
          glow
        >
          {noOpenBills ? (
            <div
              style={{
                border: '1px dashed var(--line-2)',
                padding: 24,
                textAlign: 'center',
                font: 'var(--type-body-sm)',
                color: 'var(--text-dim)',
              }}
            >
              Ochiq hisob yo‘q
            </div>
          ) : null}

          {notClosed ? (
            <>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2, marginBottom: 12 }}>
                {[
                  { k: 'Xona', v: posStation.code },
                  { k: 'Mijoz', v: posStation.guest ?? '' },
                  { k: 'Seans', v: `${HM(posStation.a)} → ${HM(posStation.b)}` },
                  { k: 'O‘ynadi', v: `${posHours.toFixed(1).replace('.0', '')} soat` },
                  { k: 'Tarif', v: `${S(posStation.rate)} / soat` },
                ].map((field) => (
                  <FieldLine key={field.k} label={field.k} value={field.v} />
                ))}
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
                Buyurtmalar
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 12 }}>
                {cartLines.map((line) => (
                  <div
                    key={line.id}
                    style={{
                      // Nom qisqaradi, stepper va summa hech qachon pastga tushmaydi
                      display: 'grid',
                      gridTemplateColumns: 'minmax(0, 1fr) auto auto',
                      alignItems: 'center',
                      gap: 8,
                    }}
                  >
                    <span style={{ display: 'grid', gap: 2, minWidth: 0 }}>
                      <span
                        style={{
                          font: 'var(--type-body-sm)',
                          color: 'var(--text-body)',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                      >
                        {line.name}
                      </span>
                      <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                        {line.unit}
                      </span>
                    </span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <Stepper label="−" onClick={() => state.bump(line.id, -1)} />
                      <span
                        style={{
                          font: 'var(--type-data)',
                          color: 'var(--text-title)',
                          minWidth: 16,
                          textAlign: 'center',
                        }}
                      >
                        {line.qty}
                      </span>
                      <Stepper label="+" onClick={() => state.bump(line.id, 1)} />
                    </div>
                    <span
                      style={{
                        font: 'var(--type-data)',
                        color: 'var(--text-title)',
                        minWidth: 76,
                        textAlign: 'right',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {line.sum}
                    </span>
                  </div>
                ))}

                {cartLines.length === 0 ? (
                  <div
                    style={{
                      border: '1px dashed var(--line-2)',
                      padding: 14,
                      textAlign: 'center',
                      font: 'var(--type-body-sm)',
                      color: 'var(--text-dim)',
                    }}
                  >
                    Buyurtma qo‘shilmagan
                  </div>
                ) : null}
              </div>

              <div style={{ height: 1, background: 'var(--line-1)', marginBottom: 10 }} />

              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-tight)' }}>
                {[
                  {
                    k: `O‘yin (${posHours.toFixed(1).replace('.0', '')} soat)`,
                    v: S(posPlay),
                    tone: 'var(--text-body)',
                  },
                  { k: 'Bar', v: S(ordersAmount), tone: 'var(--text-body)' },
                  {
                    k: 'Bron to‘lovi hisobga olindi',
                    v: `− ${S(prepaid)}`,
                    tone: 'var(--secondary-500)',
                  },
                  { k: 'Bonus ball', v: `− ${S(loyalty)}`, tone: 'var(--secondary-500)' },
                  { k: 'Chegirma', v: '0', tone: 'var(--text-dim)' },
                ].map((line) => (
                  <div
                    key={line.k}
                    style={{
                      display: 'flex',
                      alignItems: 'baseline',
                      justifyContent: 'space-between',
                      gap: 12,
                    }}
                  >
                    <span style={{ font: 'var(--type-body-sm)', color: line.tone }}>{line.k}</span>
                    <span
                      style={{ font: 'var(--type-data)', color: line.tone, whiteSpace: 'nowrap' }}
                    >
                      {line.v}
                    </span>
                  </div>
                ))}
              </div>

              <div
                style={{
                  display: 'flex',
                  alignItems: 'baseline',
                  justifyContent: 'space-between',
                  gap: 12,
                  flexWrap: 'wrap',
                  marginTop: 12,
                  paddingTop: 12,
                  borderTop: '1px solid var(--line-2)',
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
                  To‘lanadi
                </span>
                <span
                  style={{
                    font: 'var(--fw-medium) var(--fs-metric-fluid)/1 var(--font-display)',
                    color: 'var(--text-title)',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {S(due)}
                </span>
              </div>

              <div
                style={{
                  font: 'var(--type-label)',
                  letterSpacing: 'var(--ls-label)',
                  textTransform: 'uppercase',
                  color: 'var(--text-label)',
                  margin: 'var(--gap-block) 0 8px',
                }}
              >
                To‘lov usuli
              </div>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(min(120px, 100%), 1fr))',
                  gap: 'var(--gap-tight)',
                }}
              >
                {(
                  [
                    { id: 'Naqd', label: 'Naqd', icon: 'payments' },
                    { id: 'O‘tkazma', label: 'O‘tkazma', icon: 'account_balance' },
                  ] as const
                ).map((option) => {
                  const on = state.pay === option.id;
                  return (
                    <div
                      key={option.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => state.setPay(option.id)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') state.setPay(option.id);
                      }}
                      style={{
                        cursor: 'pointer',
                        minHeight: 'var(--control-h-lg)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: 7,
                        background: on ? 'var(--surface-selected)' : 'var(--surface-field)',
                        border: `1px solid ${on ? 'var(--primary-100)' : 'var(--line-2)'}`,
                        font: 'var(--type-control)',
                        color: on ? 'var(--text-title)' : 'var(--text-body)',
                        transition: 'background 140ms cubic-bezier(.22,.61,.36,1)',
                      }}
                    >
                      <Icon name={option.icon} size={15} />
                      {option.label}
                    </div>
                  );
                })}
              </div>

              {state.pay === 'Naqd' ? (
                <div
                  style={{
                    marginTop: 'var(--gap-block)',
                    padding: 'var(--card-pad)',
                    border: '1px dashed var(--line-2)',
                    font: 'var(--type-body-sm)',
                    color: 'var(--text-muted)',
                  }}
                >
                  {CASH_NOTE}
                </div>
              ) : (
                <div
                  style={{
                    marginTop: 'var(--gap-block)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 'var(--gap-block)',
                  }}
                >
                  {state.receipt === 'waiting' ? (
                    <div
                      style={{
                        padding: 'var(--card-pad)',
                        border: '1px dashed var(--yellow-100)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 8,
                        alignItems: 'center',
                        textAlign: 'center',
                      }}
                    >
                      <StatusLine
                        tone="amber"
                        icon="hourglass_top"
                        align="center"
                        parts={['Chek kutilmoqda', 'Mijoz Mini App’dan yuklaydi']}
                      />
                      <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-dim)' }}>
                        Chek kelgach shu yerda ko‘rinadi va tasdiqlash tugmasi ochiladi.
                      </span>
                    </div>
                  ) : null}

                  {state.receipt === 'uploaded' ? (
                    <div
                      style={{
                        border: '1px solid var(--primary-100)',
                        background: 'var(--surface-card)',
                        clipPath: 'var(--clip-tr)',
                      }}
                    >
                      <div
                        style={{
                          height: 132,
                          background: 'var(--surface-inset)',
                          borderBottom: '1px solid var(--line-1)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: 8,
                          color: 'var(--text-dim)',
                        }}
                      >
                        <Icon name="receipt_long" size={18} />
                        <span
                          style={{
                            font: 'var(--type-label)',
                            letterSpacing: 'var(--ls-label)',
                            textTransform: 'uppercase',
                          }}
                        >
                          Chek rasmi
                        </span>
                      </div>
                      <div
                        style={{
                          padding: 'var(--card-pad)',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 'var(--gap-tight)',
                        }}
                      >
                        <span
                          style={{
                            font: 'var(--type-data-xs)',
                            color: 'var(--purple-100)',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}
                        >
                          chek_20260812_2014.jpg · 248 KB
                        </span>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                          <FieldLine label="Yuborildi" value="20:14:02" />
                          <FieldLine label="Summa" value={S(due)} tone="var(--text-title)" />
                          <FieldLine label="Mijoz" value={posStation.guest ?? ''} />
                        </div>
                        <div
                          style={{
                            display: 'grid',
                            gridTemplateColumns: 'repeat(auto-fit, minmax(min(120px, 100%), 1fr))',
                            gap: 'var(--gap-tight)',
                          }}
                        >
                          <Button
                            variant="primary"
                            block
                            icon="check"
                            onClick={() => state.setReceipt('confirmed')}
                          >
                            Tasdiqlash
                          </Button>
                          <Button
                            variant="danger"
                            block
                            icon="close"
                            onClick={() => state.setReceipt('rejected')}
                          >
                            Rad etish
                          </Button>
                        </div>
                      </div>
                    </div>
                  ) : null}

                  {state.receipt === 'confirmed' ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-tight)' }}>
                      <StatusLine
                        tone="success"
                        icon="check_circle"
                        parts={['Chek tasdiqlandi', 'Reestrga yozildi']}
                      />
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <FieldLine label="Usul" value="O‘tkazma" />
                        <FieldLine label="Summa" value={S(due)} tone="var(--text-title)" />
                        <FieldLine label="Tasdiqladi" value="Kamola R. · 20:14:38" />
                        <FieldLine
                          label="Reestr"
                          value="PAY-2041 yozildi"
                          tone="var(--secondary-500)"
                        />
                      </div>
                    </div>
                  ) : null}

                  {state.receipt === 'rejected' ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-tight)' }}>
                      <StatusLine
                        tone="danger"
                        icon="error"
                        parts={['Chek rad etildi', 'Mijozdan qayta so‘raldi']}
                      />
                      <Button
                        variant="secondary"
                        block
                        icon="refresh"
                        onClick={() => state.setReceipt('waiting')}
                      >
                        Chekni qayta so‘rash
                      </Button>
                    </div>
                  ) : null}
                </div>
              )}

              <div style={{ marginTop: 'var(--gap-block)' }}>
                <Button
                  variant="primary"
                  size="lg"
                  notch
                  block
                  icon="lock"
                  disabled={!closable}
                  onClick={() => state.closeBill(CLK(now))}
                >
                  {closable ? 'Hisobni yopish' : 'Chek tasdiqlanmagan'}
                </Button>
              </div>
            </>
          ) : null}

          {closed ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
              <StatusLine
                tone="success"
                icon="check_circle"
                parts={['Hisob yopildi', closed.code, 'Telegram’ga xabar yuborildi']}
              />

              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <FieldLine label="Xona" value={closed.room} />
                <FieldLine label="Mijoz" value={closed.guest} tone="var(--text-title)" />
                <FieldLine label="O‘ynagan vaqt" value={closed.hours} />
                <FieldLine label="O‘yin" value={closed.play} />
                <FieldLine label="Bar" value={closed.bar} />
                <FieldLine label="To‘landi" value={closed.total} tone="var(--text-title)" />
                <FieldLine label="Usul" value={closed.method} />
                <FieldLine label="Yopdi" value={`Kamola R. · ${closed.at}`} />
              </div>

              <div style={{ border: '1px solid var(--line-1)', background: 'var(--surface-card)' }}>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '10px var(--card-pad)',
                    borderBottom: '1px solid var(--line-1)',
                    color: 'var(--text-muted)',
                  }}
                >
                  <Icon name="send" size={15} />
                  <span
                    style={{
                      font: 'var(--type-label)',
                      letterSpacing: 'var(--ls-label)',
                      textTransform: 'uppercase',
                    }}
                  >
                    Mijozga Telegram xabari
                  </span>
                </div>
                <div
                  style={{
                    padding: 'var(--card-pad)',
                    font: 'var(--type-data-xs)',
                    color: 'var(--text-body)',
                    whiteSpace: 'pre-line',
                    lineHeight: 1.6,
                  }}
                >
                  {`Neon Arena · hisob yopildi\n${closed.room} · ${closed.hours}\nO‘yin ${closed.play} · Bar ${closed.bar}\nJami to‘landi: ${closed.total} so‘m\nBonus: +${closed.points} ball\nRahmat! Sharh qoldirasizmi?`}
                </div>
              </div>

              <Button variant="secondary" size="lg" block icon="add" onClick={state.newBill}>
                Yangi hisob
              </Button>
            </div>
          ) : null}
        </Panel>
      </div>
    </div>
  );
}

function FieldLine({
  label,
  value,
  tone = 'var(--text-title)',
}: {
  label: string;
  value: string;
  tone?: string;
}): ReactNode {
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
        {label}
      </span>
      <span style={{ font: 'var(--type-data)', color: tone, textAlign: 'right' }}>{value}</span>
    </div>
  );
}

function Stepper({ label, onClick }: { label: string; onClick: () => void }): ReactNode {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        cursor: 'pointer',
        width: 'var(--control-h)',
        height: 'var(--control-h)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        border: '1px solid var(--line-2)',
        background: 'transparent',
        color: 'var(--text-muted)',
        font: 'var(--type-control)',
      }}
    >
      {label}
    </button>
  );
}
