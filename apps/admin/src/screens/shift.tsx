import { Button, Panel, StatTile } from '@playbron/ui';
import type { ReactNode } from 'react';

import { DUR } from '../mock/data';
import { useNow } from '../store/board';

/**
 * Smena — `PlayBron Xodim.dc.html` SMENA bo'limi.
 *
 * Tovar reestri xodimda ko'rsatilmaydi: qoldiq buyurtma yetkazilganda avtomatik
 * kamayadi, sanash va inventarizatsiya superadmin yuzasiga o'tkazildi.
 */
const CASH_HEAD = ['Vaqt', 'Sabab', 'Turi', 'Summa'];

const CASH_ROWS = [
  { time: '18:04:12', reason: 'Smena boshlang‘ich kassa', kind: 'Kirim', amount: '200 000', tone: 'var(--secondary-500)' },
  { time: '19:12:40', reason: '5-xona hisob · naqd', kind: 'Kirim', amount: '168 000', tone: 'var(--secondary-500)' },
  { time: '19:48:03', reason: 'Bar mahsulot yetkazib berish', kind: 'Chiqim', amount: '− 120 000', tone: 'var(--red-100)' },
  { time: '20:01:55', reason: 'VIP-1 hisob · naqd', kind: 'Kirim', amount: '216 000', tone: 'var(--secondary-500)' },
  { time: '20:09:21', reason: 'Kuryer to‘lovi', kind: 'Chiqim', amount: '− 35 000', tone: 'var(--red-100)' },
  { time: '20:13:44', reason: '8-xona hisob · naqd', kind: 'Kirim', amount: '96 000', tone: 'var(--secondary-500)' },
];

const CASH_COLS = 'minmax(96px, auto) minmax(0, 1fr) minmax(72px, auto) minmax(96px, auto)';

export function ShiftScreen(): ReactNode {
  const now = useNow();

  const shiftFields = [
    { k: 'Xodim', v: 'Kamola Rasulova', tone: 'var(--text-title)' },
    { k: 'Ochilgan', v: '2026-08-12 18:00:04', tone: 'var(--text-body)' },
    { k: 'Davomiylik', v: DUR(now - 18 * 3600), tone: 'var(--text-body)' },
    { k: 'Boshlang‘ich kassa', v: '200 000', tone: 'var(--text-body)' },
    { k: 'Kutilayotgan naqd', v: '1 180 000', tone: 'var(--text-title)' },
    { k: 'Sanaldi', v: '1 140 000', tone: 'var(--text-title)' },
    { k: 'Farq', v: '− 40 000', tone: 'var(--red-100)' },
  ];

  return (
    <div className="ds-split" style={{ alignItems: 'start' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)', minWidth: 0 }}>
        <div className="pb-tiles-4">
          <StatTile label="Naqd tushum" value="980 000" unit="so‘m" icon="payments" />
          <StatTile label="O‘tkazma" value="640 000" unit="so‘m" icon="account_balance" />
          <StatTile label="Onlayn bron to‘lovi" value="280 000" unit="so‘m" icon="cloud_done" />
          <StatTile label="Yopilgan hisob" value="14" unit="ta" icon="receipt_long" />
        </div>

        <Panel title="Kassa harakatlari" notch brackets>
          <div style={{ overflowX: 'auto' }}>
            <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: CASH_COLS,
                  gap: 10,
                  padding: '0 10px 8px',
                  borderBottom: '1px solid var(--line-1)',
                }}
              >
                {CASH_HEAD.map((head) => (
                  <span
                    key={head}
                    style={{
                      font: 'var(--type-label)',
                      letterSpacing: 'var(--ls-label)',
                      textTransform: 'uppercase',
                      color: 'var(--text-label)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {head}
                  </span>
                ))}
              </div>

              {CASH_ROWS.map((row) => (
                <div
                  key={row.time}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: CASH_COLS,
                    gap: 10,
                    padding: '0 10px',
                    minHeight: 40,
                    alignItems: 'center',
                    borderBottom: '1px solid var(--line-1)',
                  }}
                >
                  <span
                    style={{
                      font: 'var(--type-data-xs)',
                      color: 'var(--text-muted)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {row.time}
                  </span>
                  <span
                    style={{
                      font: 'var(--type-body-sm)',
                      color: 'var(--text-body)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {row.reason}
                  </span>
                  <span
                    style={{
                      font: 'var(--type-label)',
                      letterSpacing: 'var(--ls-label)',
                      textTransform: 'uppercase',
                      color: row.tone,
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {row.kind}
                  </span>
                  <span
                    style={{
                      font: 'var(--type-data)',
                      color: row.tone,
                      textAlign: 'right',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {row.amount}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </Panel>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)', minWidth: 0 }}>
        <Panel title="Joriy smena" notch brackets>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {shiftFields.map((field) => (
              <div
                key={field.k}
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
                <span
                  style={{
                    font: 'var(--type-data)',
                    color: field.tone,
                    textAlign: 'right',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {field.v}
                </span>
              </div>
            ))}
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(min(130px, 100%), 1fr))',
              gap: 'var(--gap-tight)',
              marginTop: 14,
            }}
          >
            <Button variant="secondary" icon="add" block>
              Kirim
            </Button>
            <Button variant="secondary" icon="remove" block>
              Chiqim
            </Button>
          </div>

          <div style={{ marginTop: 'var(--gap-block)' }}>
            <Button variant="primary" size="lg" notch block icon="lock_clock">
              Smenani yopish
            </Button>
          </div>
        </Panel>
      </div>
    </div>
  );
}
