import { EntityTable, NO_SHOW_MIN, Panel, StatusLine } from '@playbron/ui';
import type { ReactNode } from 'react';

/**
 * Qora ro'yxat — `PlayBron Xodim.dc.html` QORA RO'YXAT bo'limi.
 *
 * Reja #32 (2026-08-16, loyiha egasi): "hech qayerda seed qolmasin" —
 * ekran to'liq soxta mijoz ro'yxati (3 ta bloklangan, 4 ta kuzatuvda,
 * oylik statistika) bilan edi, HECH QANDAY real backend yo'q edi (no-show
 * kuzatuvi, bloklash — hali qurilmagan funksiya, `docs`da rejalashtirilgan
 * xolos). Soxta ma'lumot ko'rsatishdan ko'ra — bo'sh, halol holat.
 *
 * `useBoard().nsMarked` orqali ishlaydigan "jonli demo" ham olib
 * tashlandi: hech qanday ekranda uni `true` qiladigan amal yo'q edi
 * (o'lik ulanish).
 */

interface BlockedRow {
  name: string;
  phone: string;
  n: number;
  reason: string;
  at: string;
}

const RULES = [
  { n: '1', text: `Bron boshlanganidan ${NO_SHOW_MIN} daqiqa o‘tsa xona "Kelmadi?" holatiga o‘tadi va xodim qo‘lda tasdiqlaydi.` },
  { n: '2', text: 'No-show belgilangach bron to‘lovi (1 soatlik summa) jarima sifatida klubda qoladi, xona darhol bo‘shaydi.' },
  { n: '3', text: 'Ikkinchi no-show’dan keyin mijoz kuzatuvga tushadi — keyingi bronda to‘liq summa oldindan olinadi.' },
  { n: '4', text: 'Uchinchi no-show avtomatik blok: mijoz Mini App’dan bron qila olmaydi, faqat joyida navbat bilan o‘ynaydi.' },
  { n: '5', text: 'Blokni faqat klub egasi olib tashlaydi, har bir amal audit log’ga yoziladi.' },
];

export function BlacklistScreen(): ReactNode {
  const blocked: BlockedRow[] = [];

  return (
    <div className="pb-split-wide" style={{ alignItems: 'start' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)', minWidth: 0 }}>
        <StatusLine
          tone="neutral"
          icon="hourglass_empty"
          parts={['No-show kuzatuvi hali ishga tushirilmagan', 'Tez orada qo‘shiladi']}
        />

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
            ]}
          />
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
      </div>
    </div>
  );
}
