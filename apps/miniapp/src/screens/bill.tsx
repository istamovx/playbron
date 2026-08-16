import { Icon, Panel, StatusLine } from '@playbron/ui';
import type { CSSProperties, ReactNode } from 'react';

import {
  BONUS_POINTS,
  CASH_NOTE,
  SESSION_ROOM,
  SESSION_START,
  STATIONS,
  S,
  TRANSFER_NOTE,
} from '../mock/data';
import { billOf, cartCount, orderTotal } from '../lib/bill';
import { useApp, useSessionEnd } from '../store/app';

const PAY_OPTIONS = [
  { id: 'Naqd', label: 'Naqd', icon: 'payments' },
  { id: 'O‘tkazma', label: 'O‘tkazma', icon: 'account_balance' },
];

/** Hisob — `PlayBron Mijoz.dc.html` HISOB ekrani. */
export function BillScreen(): ReactNode {
  const state = useApp();
  const sessionEnd = useSessionEnd();

  const station = STATIONS.find((item) => item.code === SESSION_ROOM) ?? (STATIONS[0] as (typeof STATIONS)[number]);
  const hours = (sessionEnd - SESSION_START) / 3600;
  const bar = orderTotal(state.orders);
  const bill = billOf(hours, station.rate, bar);
  const unsent = cartCount(state.cart);

  const lines = [
    { k: `O‘yin (${hours % 1 === 0 ? hours : hours.toFixed(1)} soat)`, v: S(bill.play), tone: 'var(--text-body)' },
    { k: 'Bar', v: S(bill.bar), tone: 'var(--text-body)' },
    { k: 'Bron to‘lovi hisobga olindi', v: `− ${S(bill.prepaid)}`, tone: 'var(--secondary-500)' },
    { k: `Bonus ball (${BONUS_POINTS})`, v: `− ${S(bill.bonus)}`, tone: 'var(--secondary-500)' },
  ];

  const transfer = state.payFinal === 'O‘tkazma';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      {unsent > 0 ? (
        <StatusLine
          tone="warn"
          icon="shopping_basket"
          parts={[`Savatda ${unsent} dona yuborilmagan`, 'Hisobga kirmaydi']}
        />
      ) : null}

      <Panel title="Joriy hisob" notch brackets>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {lines.map((line) => (
            <div key={line.k} style={ROW}>
              <span style={{ font: 'var(--type-body-sm)', color: line.tone }}>{line.k}</span>
              <span style={{ font: 'var(--type-data)', color: line.tone, whiteSpace: 'nowrap' }}>
                {line.v}
              </span>
            </div>
          ))}

          <div style={{ height: 1, background: 'var(--line-2)', margin: '4px 0' }} />

          <div style={ROW}>
            <span
              style={{
                font: 'var(--type-label)',
                letterSpacing: 'var(--ls-label)',
                textTransform: 'uppercase',
                color: 'var(--text-label)',
              }}
            >
              Klubda to‘lanadi
            </span>
            <span
              style={{
                font: 'var(--fw-medium) var(--fs-metric-fluid)/1 var(--font-display)',
                color: 'var(--text-title)',
              }}
            >
              {S(bill.total)}
            </span>
          </div>
        </div>
      </Panel>

      <Panel title="To‘lov usuli" notch>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--gap-tight)' }}>
          {PAY_OPTIONS.map((option) => {
            const on = state.payFinal === option.id;
            return (
              <button
                key={option.id}
                type="button"
                aria-pressed={on}
                onClick={() => {
                  state.setPayFinal(option.id);
                  state.setReceipt('none');
                }}
                style={{
                  cursor: 'pointer',
                  minHeight: 44,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 7,
                  background: on ? 'var(--surface-selected)' : 'var(--surface-field)',
                  border: `1px solid ${on ? 'var(--primary-100)' : 'var(--line-2)'}`,
                  font: 'var(--type-control)',
                  color: on ? 'var(--text-title)' : 'var(--text-body)',
                  transition: 'var(--t-control)',
                }}
              >
                <Icon name={option.icon} size={15} />
                {option.label}
              </button>
            );
          })}
        </div>

        {transfer ? (
          <div
            style={{
              marginTop: 'var(--gap-block)',
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--gap-block)',
            }}
          >
            {/* Klubning HAQIQIY to'lov rekvizitlari uchun `clubs` jadvalida
                ustun hali yo'q. Avval bu yerda o'ylab topilgan karta raqami
                turardi va u HAR QANDAY klubda ko'rsatilardi — mijoz begona
                (mavjud bo'lmagan) hisobga pul o'tkazishi mumkin edi. */}
            <StatusLine
              tone="warn"
              icon="info"
              parts={['To‘lov rekvizitlari hali sozlanmagan', 'Xodimdan so‘rang']}
            />

            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {[{ k: 'Summa', v: S(bill.total), tone: 'var(--text-title)' }].map(
                (field) => (
                  <div
                    key={field.k}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 12,
                      minHeight: 'var(--field-h)',
                      padding: '5px 10px',
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
                    <span
                      style={{ font: 'var(--type-data)', color: field.tone, textAlign: 'right' }}
                    >
                      {field.v}
                    </span>
                  </div>
                ),
              )}
            </div>

            {state.receipt === 'none' ? (
              <button
                type="button"
                onClick={() => state.setReceipt('sent')}
                style={{
                  cursor: 'pointer',
                  padding: '20px var(--card-pad)',
                  background: 'transparent',
                  border: '1px dashed var(--line-3)',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 8,
                  textAlign: 'center',
                }}
              >
                <span style={{ color: 'var(--purple-100)', display: 'flex' }}>
                  <Icon name="upload_file" size={22} />
                </span>
                <span style={{ font: 'var(--type-section)', color: 'var(--text-title)' }}>
                  Chek rasmini yuklang
                </span>
                <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-dim)' }}>
                  {TRANSFER_NOTE}
                </span>
              </button>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-tight)' }}>
                <StatusLine
                  tone="warn"
                  icon="hourglass_top"
                  parts={['Chek yuborildi', 'Xodim tasdiqlashini kutmoqda']}
                />
                <div
                  style={{
                    border: '1px solid var(--line-1)',
                    background: 'var(--surface-card)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    padding: 'var(--card-pad)',
                  }}
                >
                  <span style={{ flex: 'none', color: 'var(--text-muted)', display: 'flex' }}>
                    <Icon name="receipt_long" size={18} />
                  </span>
                  <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
                    <span
                      style={{
                        font: 'var(--type-data-xs)',
                        color: 'var(--purple-100)',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      chek_20260813_2014.jpg
                    </span>
                    <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                      248 KB · 20:14:02
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        ) : (
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
        )}
      </Panel>
    </div>
  );
}

const ROW: CSSProperties = {
  display: 'flex',
  alignItems: 'baseline',
  justifyContent: 'space-between',
  gap: 10,
};
