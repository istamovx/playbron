import { Button, Chip, GRACE_MIN, Icon, NOTIFY_BEFORE_MIN, Panel } from '@playbron/ui';
import { useEffect, type ReactNode } from 'react';

import {
  CLK,
  DUR,
  HM,
  MENU,
  ORDER_FLOW,
  ORDER_LABEL,
  ORDER_TONE,
  S,
  SESSION_ROOM,
  SESSION_START,
  orderStatusAt,
} from '../mock/data';
import { cartCount, cartTotal } from '../lib/bill';
import { haptic } from '../lib/telegram';
import { useApp, useNow, useProfile, useSessionEnd } from '../store/app';

const CATS = ['Ichimliklar', 'Snack', 'Ovqat'];

/**
 * Aktiv seans — `PlayBron Mijoz.dc.html` SEANS ekrani.
 * Qolgan vaqt real hisoblanadi: 30 va 15 daqiqa qolganda bildirishnoma chiqadi,
 * vaqt tugagach `GRACE_MIN` daqiqa kutiladi va shundan keyin hisob yopiladi.
 */
export function SessionScreen(): ReactNode {
  const now = useNow();
  const state = useApp();
  const sessionEnd = useSessionEnd();
  const remain = sessionEnd - now;
  const notified = state.notified;
  const markNotified = state.markNotified;
  const notify = useProfile((current) => current.notify);
  const haptics = useProfile((current) => current.haptics);

  const grace = GRACE_MIN * 60;
  const phase = remain > 0 ? 'active' : remain > -grace ? 'grace' : 'over';

  // Bildirishnomalar bir martadan ko'p yubormaydi; profilda o'chirsa — umuman yubormaydi
  useEffect(() => {
    if (!notify) return;
    for (const at of NOTIFY_BEFORE_MIN) {
      const key = `before-${at}`;
      if (remain > 0 && remain <= at * 60 && !notified.includes(key)) {
        markNotified(key);
        if (haptics) haptic('tap');
        return;
      }
    }
    if (remain <= 0 && !notified.includes('ended')) {
      markNotified('ended');
      if (haptics) haptic('error');
    }
  }, [notify, haptics, remain, notified, markNotified]);

  const pct = `${Math.max(0, Math.min(100, ((now - SESSION_START) / (sessionEnd - SESSION_START)) * 100)).toFixed(1)}%`;
  const tone =
    remain < 0
      ? 'var(--red-100)'
      : remain < 15 * 60
        ? 'var(--red-100)'
        : remain < 30 * 60
          ? 'var(--yellow-100)'
          : 'var(--text-title)';

  const menu = MENU.filter((item) => item.cat === state.cat);
  const count = cartCount(state.cart);
  const pending = cartTotal(state.cart);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <Notice phase={phase} remain={remain} />

      <Panel notch brackets glow>
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 8,
            padding: '6px 0',
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
            Qolgan vaqt · {SESSION_ROOM}
          </span>
          <span
            style={{
              font: 'var(--fw-medium) var(--fs-metric-fluid)/1 var(--font-mono)',
              color: tone,
              letterSpacing: '.04em',
            }}
          >
            {DUR(remain)}
          </span>
          <div
            style={{
              width: '100%',
              height: 4,
              background: 'var(--chart-track)',
              position: 'relative',
              marginTop: 4,
            }}
          >
            <div
              className="pb-fill"
              style={{
                position: 'absolute',
                inset: '0 auto 0 0',
                width: pct,
                background: remain < 0 ? 'var(--red-100)' : 'var(--primary-100)',
                boxShadow: remain < 0 ? 'var(--glow-risk)' : 'var(--glow-violet-sm)',
              }}
            />
          </div>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              width: '100%',
              font: 'var(--type-data-xs)',
              color: 'var(--text-dim)',
            }}
          >
            <span>{HM(SESSION_START / 60)}</span>
            <span>{HM(sessionEnd / 60)}</span>
          </div>
        </div>
      </Panel>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--gap-tight)' }}>
        <Button variant="secondary" size="lg" block icon="more_time" onClick={state.extend}>
          Uzaytirish
        </Button>
        <Button
          variant="secondary"
          size="lg"
          block
          icon="receipt_long"
          onClick={() => state.go('bill')}
        >
          Hisob
        </Button>
      </div>

      {state.orders.length > 0 ? (
        <Panel title={`Buyurtmalarim (${state.orders.length})`} notch>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[...state.orders].reverse().map((order) => {
              const status = orderStatusAt(now - order.at);
              const step = ORDER_FLOW.indexOf(status);
              const tone = ORDER_TONE[status];

              return (
                <div
                  key={order.code}
                  style={{
                    padding: 'var(--card-pad)',
                    background: 'var(--surface-card)',
                    border: '1px solid var(--line-1)',
                    boxShadow: `inset 3px 0 0 ${tone}`,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 8,
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
                      #{order.code}
                    </span>
                    <span
                      style={{
                        font: 'var(--type-label)',
                        letterSpacing: 'var(--ls-label)',
                        textTransform: 'uppercase',
                        color: tone,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {ORDER_LABEL[status]}
                    </span>
                  </div>

                  {/* Bosqichlar — kassadagi holat bilan bir xil ketma-ketlik */}
                  <div style={{ display: 'flex', gap: 3 }}>
                    {ORDER_FLOW.map((stage, index) => (
                      <span
                        key={stage}
                        style={{
                          flex: 1,
                          height: 3,
                          background: index <= step ? tone : 'var(--chart-track)',
                          boxShadow: index === step ? 'var(--glow-violet-sm)' : undefined,
                          transition: 'background 320ms cubic-bezier(.22,.61,.36,1)',
                        }}
                      />
                    ))}
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                    {order.lines.map((line) => {
                      const item = MENU.find((menu) => menu.id === line.id);
                      if (!item) return null;
                      return (
                        <div
                          key={line.id}
                          style={{
                            display: 'flex',
                            alignItems: 'baseline',
                            justifyContent: 'space-between',
                            gap: 8,
                          }}
                        >
                          <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-body)' }}>
                            {item.name} × {line.qty}
                          </span>
                          <span
                            style={{
                              font: 'var(--type-data-xs)',
                              color: 'var(--text-muted)',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {S(item.price * line.qty)}
                          </span>
                        </div>
                      );
                    })}
                  </div>

                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'baseline',
                      justifyContent: 'space-between',
                      gap: 8,
                      paddingTop: 6,
                      borderTop: '1px solid var(--line-1)',
                    }}
                  >
                    <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                      {CLK(order.at)}
                    </span>
                    <span
                      style={{
                        font: 'var(--type-data)',
                        color: 'var(--purple-100)',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {S(order.amount)} so‘m
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </Panel>
      ) : null}

      <Panel title="Bar menyusi" notch>
        <div style={{ display: 'flex', gap: 6, overflow: 'auto', marginBottom: 10, paddingBottom: 2 }}>
          {CATS.map((cat) => (
            <Chip key={cat} selected={state.cat === cat} onClick={() => state.setCat(cat)}>
              {cat}
            </Chip>
          ))}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {menu.map((item) => {
            const qty = state.cart[item.id] ?? 0;
            return (
              <div
                key={item.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: 'var(--gap-tight) var(--card-pad)',
                  background: 'var(--surface-card)',
                  border: '1px solid var(--line-1)',
                }}
              >
                <div
                  style={{
                    flex: 1,
                    minWidth: 0,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 3,
                  }}
                >
                  <span
                    style={{
                      font: 'var(--type-section)',
                      color: 'var(--text-title)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {item.name}
                  </span>
                  <span style={{ font: 'var(--type-data-xs)', color: 'var(--purple-100)' }}>
                    {S(item.price)} so‘m
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 'none' }}>
                  <Step label="−" onClick={() => state.bump(item.id, -1)} />
                  <span
                    style={{
                      font: 'var(--type-data)',
                      color: 'var(--text-title)',
                      minWidth: 16,
                      textAlign: 'center',
                    }}
                  >
                    {qty}
                  </span>
                  <Step label="+" onClick={() => state.bump(item.id, 1)} />
                </div>
              </div>
            );
          })}
        </div>

        {count > 0 ? (
          <div
            style={{
              marginTop: 'var(--gap-block)',
              paddingTop: 'var(--gap-tight)',
              borderTop: '1px solid var(--line-2)',
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
                color: 'var(--text-label)',
              }}
            >
              Savat · {count} dona
            </span>
            <span style={{ font: 'var(--type-data)', color: 'var(--text-title)' }}>
              {S(pending)} so‘m
            </span>
          </div>
        ) : null}
      </Panel>
    </div>
  );
}

/** Vaqt holatiga qarab ogohlantirish — bildirishnoma matni bilan bir xil. */
function Notice({ phase, remain }: { phase: string; remain: number }): ReactNode {
  const minutes = Math.ceil(Math.abs(remain) / 60);

  const notice =
    phase === 'over'
      ? {
          icon: 'lock_clock',
          tone: 'var(--red-100)',
          text: `Seans yakunlandi va xona bo‘shatildi. Hisob kassada yopiladi.`,
        }
      : phase === 'grace'
        ? {
            icon: 'timer_off',
            tone: 'var(--red-100)',
            text: `Vaqt tugadi. Xona ${GRACE_MIN} daqiqa saqlanadi — uzaytiring yoki hisobni yoping.`,
          }
        : remain <= 15 * 60
          ? {
              icon: 'notifications_active',
              tone: 'var(--red-100)',
              text: `Seans tugashiga ${minutes} daqiqa qoldi.`,
            }
          : remain <= 30 * 60
            ? {
                icon: 'notifications',
                tone: 'var(--yellow-100)',
                text: `Seans tugashiga ${minutes} daqiqa qoldi. Uzaytirish kerak bo‘lsa oldindan bosing.`,
              }
            : null;

  if (!notice) return null;

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: 'var(--card-pad)',
        background: 'var(--surface-inset)',
        border: `1px solid ${notice.tone}`,
        clipPath: 'var(--clip-tr)',
        color: notice.tone,
      }}
    >
      <Icon name={notice.icon} size={18} />
      <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-body)' }}>{notice.text}</span>
    </div>
  );
}

function Step({ label, onClick }: { label: string; onClick: () => void }): ReactNode {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label === '+' ? 'Qo‘shish' : 'Kamaytirish'}
      style={{
        cursor: 'pointer',
        width: 'var(--control-h)',
        height: 'var(--control-h)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'transparent',
        border: '1px solid var(--line-2)',
        color: 'var(--text-muted)',
        font: 'var(--type-control)',
      }}
    >
      {label}
    </button>
  );
}
