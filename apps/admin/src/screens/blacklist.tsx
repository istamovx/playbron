import { Button, EntityTable, NO_SHOW_MIN, Panel, StatusLine, Tag } from '@playbron/ui';
import type { ReactNode } from 'react';

import { useBoard } from '../store/board';

/** Qora ro'yxat — `PlayBron Xodim.dc.html` QORA RO'YXAT bo'limi. */
const BLOCKED = [
  { name: 'Rustam Xolmatov', phone: '+998 90 411-70-25', n: 3, reason: 'Ketma-ket 3 marta kelmadi', at: '2026-07-22' },
  { name: 'Sanjar Umarov', phone: '+998 93 118-40-19', n: 4, reason: 'VIP xona bron qilib kelmadi', at: '2026-06-30' },
  { name: 'Islom Tosheov', phone: '+998 88 902-16-33', n: 3, reason: 'Xodim bilan janjal · no-show', at: '2026-06-11' },
];

const WATCH = [
  { name: 'Kamron Halilov', phone: '+998 95 220-14-08', n: 2 },
  { name: 'Doston Ravshanov', phone: '+998 99 350-88-04', n: 2 },
  { name: 'Mansur Ergashev', phone: '+998 91 604-22-77', n: 1 },
  { name: 'Ozod Sattorov', phone: '+998 94 771-30-52', n: 1 },
];

const RULES = [
  { n: '1', text: `Bron boshlanganidan ${NO_SHOW_MIN} daqiqa o‘tsa xona "Kelmadi?" holatiga o‘tadi va xodim qo‘lda tasdiqlaydi.` },
  { n: '2', text: 'No-show belgilangach bron to‘lovi (1 soatlik summa) jarima sifatida klubda qoladi, xona darhol bo‘shaydi.' },
  { n: '3', text: 'Ikkinchi no-show’dan keyin mijoz kuzatuvga tushadi — keyingi bronda to‘liq summa oldindan olinadi.' },
  { n: '4', text: 'Uchinchi no-show avtomatik blok: mijoz Mini App’dan bron qila olmaydi, faqat joyida navbat bilan o‘ynaydi.' },
  { n: '5', text: 'Blokni faqat klub egasi olib tashlaydi, har bir amal audit log’ga yoziladi.' },
];

const NS_STATS = [
  { k: 'No-show', v: '9', tone: 'var(--red-100)' },
  { k: 'Yo‘qolgan soat', v: '17.5', tone: 'var(--text-title)' },
  { k: 'Ushlab qolingan to‘lov', v: '214 000', tone: 'var(--secondary-500)' },
  { k: 'Yangi blok', v: '1', tone: 'var(--yellow-100)' },
];

export function BlacklistScreen(): ReactNode {
  const nsMarked = useBoard((state) => state.nsMarked);

  const watchList = nsMarked ? WATCH.filter((item) => item.name !== 'Kamron Halilov') : WATCH;
  const blocked = [
    ...(nsMarked
      ? [
          {
            name: 'Kamron Halilov',
            phone: '+998 95 220-14-08',
            n: 3,
            reason: '3-no-show · 6-xona 19:50',
            at: '2026-08-12',
            fresh: true,
          },
        ]
      : []),
    ...BLOCKED,
  ];

  return (
    <div className="pb-split-wide" style={{ alignItems: 'start' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)', minWidth: 0 }}>
        {nsMarked ? (
          <StatusLine
            tone="danger"
            icon="person_off"
            parts={[
              'Kamron Halilov qora ro‘yxatga qo‘shildi',
              '3-no-show',
              'Bron to‘lovi 25 000 klubda qoldi',
              '6-xona bo‘shatildi',
            ]}
          />
        ) : null}

        <Panel title={`Qora ro‘yxat (${blocked.length})`} notch brackets>
          {/* `EntityTable` telefonda o'zi kartaga aylanadi — alohida tartib kerak emas */}
          <EntityTable
            rows={blocked}
            rowKey={(row) => row.name}
            empty="Qora ro‘yxat bo‘sh"
            columns={[
              {
                key: 'name',
                header: 'Mijoz',
                render: (row) => (
                  <span style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
                    <span style={{ color: 'var(--text-title)' }}>{row.name}</span>
                    <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                      {row.phone}
                    </span>
                  </span>
                ),
              },
              {
                key: 'n',
                header: 'No-show',
                align: 'right',
                render: (row) => (
                  <span style={{ font: 'var(--type-data)', color: 'var(--red-100)' }}>{row.n}</span>
                ),
              },
              {
                key: 'reason',
                header: 'Sabab',
                render: (row) => (
                  <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-muted)' }}>
                    {row.reason}
                  </span>
                ),
              },
              {
                key: 'at',
                header: 'Bloklandi',
                align: 'right',
                render: (row) => (
                  <span
                    style={{
                      font: 'var(--type-data-xs)',
                      color: 'var(--text-dim)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {row.at}
                  </span>
                ),
              },
              {
                key: 'actions',
                header: '',
                align: 'right',
                render: () => (
                  <Button variant="ghost" size="sm" icon="lock_open">
                    Blokdan olish
                  </Button>
                ),
              },
            ]}
          />
        </Panel>

        <Panel title={`Kuzatuvda (${watchList.length})`} notch>
          <div
            style={{
              display: 'grid',
              minWidth: 0,
              gridTemplateColumns: 'repeat(auto-fit, minmax(min(230px, 100%), 1fr))',
              gap: 'var(--gap-panel)',
            }}
          >
            {watchList.map((item) => (
              <div
                key={item.name}
                style={{
                  padding: 'var(--card-pad)',
                  background: 'var(--surface-card)',
                  border: '1px solid var(--line-1)',
                  clipPath: 'var(--clip-tr)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 'var(--gap-tight)',
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
                  <Tag tone={item.n === 2 ? 'danger' : 'amber'}>{`${item.n} / 3`}</Tag>
                </div>
                <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                  {item.phone}
                </span>
                <span
                  style={{
                    font: 'var(--type-body-sm)',
                    color: item.n === 2 ? 'var(--red-100)' : 'var(--yellow-100)',
                  }}
                >
                  {item.n === 2 ? 'Keyingi no-show — avtomatik blok' : 'To‘liq summa oldindan olinadi'}
                </span>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)', minWidth: 0 }}>
        <Panel title="Qoida" notch brackets>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
            {RULES.map((rule) => (
              <div key={rule.n} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                <span
                  style={{
                    flex: 'none',
                    width: 22,
                    height: 22,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    border: '1px solid var(--line-2)',
                    font: 'var(--type-data-xs)',
                    color: 'var(--text-muted)',
                  }}
                >
                  {rule.n}
                </span>
                <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-body)' }}>
                  {rule.text}
                </span>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Bu oyda" notch>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {NS_STATS.map((stat) => (
              <div
                key={stat.k}
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
                  {stat.k}
                </span>
                <span style={{ font: 'var(--type-data)', color: stat.tone }}>{stat.v}</span>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}
