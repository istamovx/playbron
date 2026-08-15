import { Panel, StatusLine } from '@playbron/ui';
import type { ReactNode } from 'react';

import { HM, S, dayOptions } from '../mock/data';
import { stationSpec } from '../lib/slots';
import { useApp } from '../store/app';
import { useBooking } from '../store/booking';

/**
 * Bron tasdiqlash — to'lovsiz oqim (Bosqich 1). Yuborish tugmasi pastdagi
 * umumiy footer'da (`app.tsx::mainButton`), bu ekran faqat xulosa ko'rsatadi.
 */
export function ConfirmScreen(): ReactNode {
  const state = useApp();
  const club = useBooking((s) => s.clubs.find((item) => item.id === state.clubId) ?? null);
  const stations = useBooking((s) => s.stations);
  const submitError = useBooking((s) => s.submitError);
  const station = stations.find((item) => item.id === state.station) ?? null;

  if (!club || !station) {
    return (
      <div style={{ font: 'var(--type-body-sm)', color: 'var(--text-muted)' }}>
        Xona tanlanmagan — orqaga qaytib tanlang.
      </div>
    );
  }

  const day = dayOptions().find((option) => option.index === state.day);
  const price = station.rate * state.hours;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <Panel title="Bron xulosasi" notch>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <Row label="Klub" value={club.name} />
          <Row label="Xona" value={`${station.code} · ${station.roomLabel} · ${stationSpec(station)}`} />
          <Row label="Sana" value={day ? day.label : ''} />
          <Row
            label="Vaqt"
            value={`${HM(state.start)} → ${HM(state.start + state.hours * 60)} · ${state.hours} soat`}
          />
          <div style={{ height: 1, background: 'var(--line-1)' }} />
          <Row label="Narx" value={`${S(price)} so‘m`} bold />
        </div>
      </Panel>

      <StatusLine
        tone="neutral"
        icon="storefront"
        parts={['To‘lov klubda, kelganingizda', 'Bron hozircha to‘lovsiz yuboriladi']}
      />

      <StatusLine
        tone="warn"
        icon="pending"
        parts={['Yuborilgach xodim tasdiqlaydi', 'Tasdiqlangach botda xabar keladi']}
      />

      {submitError ? <StatusLine tone="danger" icon="error" parts={[submitError]} /> : null}
    </div>
  );
}

function Row({ label, value, bold }: { label: string; value: string; bold?: boolean }): ReactNode {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 }}>
      <span style={{ font: 'var(--type-label)', letterSpacing: 'var(--ls-label)', textTransform: 'uppercase', color: 'var(--text-dim)' }}>
        {label}
      </span>
      <span
        style={{
          font: bold ? 'var(--type-section)' : 'var(--type-data)',
          color: bold ? 'var(--purple-100)' : 'var(--text-title)',
          textAlign: 'right',
        }}
      >
        {value}
      </span>
    </div>
  );
}
