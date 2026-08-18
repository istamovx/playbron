import { quoteBooking, errorText } from '@playbron/api-client';
import { EmptyState, Panel, StatusLine } from '@playbron/ui';
import { useEffect, useMemo, useState, type ReactNode } from 'react';

import { useLocale, useT } from '../i18n';
import { api } from '../lib/api';
import { hhmm, money } from '../lib/format';
import { consoleForRequest, dayOptions, startInstantIso, stationSpec } from '../lib/slots';
import { useApp } from '../store/app';
import { useBooking } from '../store/booking';

/**
 * Bron tasdiqlash — to'lovsiz oqim (Bosqich 1). Yuborish tugmasi pastdagi
 * umumiy footer'da (`app.tsx::mainButton`), bu ekran faqat xulosa ko'rsatadi.
 *
 * UMUMIY SUMMA KLIENTDA HISOBLANMAYDI. Avval `rate × soat` ko'rsatilardi —
 * tarif oyna ichida o'zgarsa (`tariffs.from_min/to_min`) bu son server
 * hisoblagan `bookings.play_amount` dan farq qilardi va mijoz boshqa summa
 * kutgan holda kelardi.
 *
 * O'rniga `POST /clubs/{id}/bookings/quote` so'raladi: bron QILINMAYDI,
 * faqat narx qaytadi va u yaratishdagi bilan bir xil validatsiyadan
 * o'tadi. So'rov faqat tanlov o'zgarganda ketadi (ekran soat tiki bilan
 * qayta render bo'lsa ham).
 */
export function ConfirmScreen(): ReactNode {
  const t = useT();
  const locale = useLocale();
  const state = useApp();
  const club = useBooking((s) => s.clubs.find((item) => item.id === state.clubId) ?? null);
  const stations = useBooking((s) => s.stations);
  const submitError = useBooking((s) => s.submitError);
  const station = stations.find((item) => item.id === state.station) ?? null;

  const timezone = club?.timezone ?? null;
  const [quote, setQuote] = useState<{ playAmount: number; rateSnapshot: number } | null>(
    null,
  );
  const [quoteError, setQuoteError] = useState<string | null>(null);

  // Tanlov o'zgarganda — sekundiga emas. `state.tick` bog'liqlikda YO'Q.
  useEffect(() => {
    if (!timezone || !club || !station) return;
    let alive = true;
    setQuote(null);
    setQuoteError(null);
    void quoteBooking(api, club.id, {
      stationId: station.id,
      startsAt: startInstantIso(state.day, state.start, timezone),
      hours: state.hours,
      consoleType: consoleForRequest(station, state.bookingConsole),
    })
      .then((row) => {
        if (alive) setQuote({ playAmount: row.playAmount, rateSnapshot: row.rateSnapshot });
      })
      .catch((cause: unknown) => {
        if (alive) setQuoteError(errorText(cause));
      });
    return () => {
      alive = false;
    };
  }, [
    club?.id,
    station?.id,
    state.day,
    state.start,
    state.hours,
    state.bookingConsole,
    timezone,
  ]);

  const day = useMemo(
    () =>
      timezone
        ? dayOptions(
            timezone,
            locale,
            { today: t('today'), tomorrow: t('tomorrow') },
            club?.maxAdvanceDays ?? 1,
          ).find((option) => option.index === state.day)
        : undefined,
    [timezone, locale, state.day, t, club?.maxAdvanceDays],
  );

  if (!club || !station) {
    return <EmptyState icon="meeting_room">{t('roomNotSelected')}</EmptyState>;
  }

  const spec = stationSpec(station);
  const consoleLabel = spec || state.bookingConsole.toUpperCase();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <Panel title={t('confirmTitle')} notch>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <Row label={t('fieldClub')} value={club.name} />
          <Row
            label={t('fieldRoom')}
            value={[station.code, station.roomLabel, consoleLabel].filter(Boolean).join(' · ')}
          />
          <Row label={t('fieldDate')} value={day ? day.label : ''} />
          <Row
            label={t('fieldTime')}
            value={`${hhmm(state.start)} → ${hhmm(state.start + state.hours * 60)} · ${t('hoursUnit', { hours: state.hours })}`}
          />
          <div style={{ height: 1, background: 'var(--line-1)' }} />
          {/* Soatlik narx ham SERVERDAN. `station.rate` — tarifsiz
              klublar uchun zaxira ustun; tarif bor klubda u boshqa son
              bo'lib, bitta panelda ikkita ziddiyatli narx chiqardi. */}
          <Row
            label={t('fieldRate')}
            value={quote ? t('perHour', { sum: money(quote.rateSnapshot) }) : '—'}
          />
          <Row
            label={t('fieldTotal')}
            value={quote ? money(quote.playAmount) : quoteError ? '—' : t('quoteLoading')}
            bold
          />
        </div>
      </Panel>

      {quoteError ? (
        <StatusLine tone="danger" icon="calculate" parts={[quoteError]} />
      ) : (
        <StatusLine tone="neutral" icon="calculate" parts={[t('finalAmountNote')]} />
      )}

      <StatusLine tone="neutral" icon="storefront" parts={[t('payAtClub'), t('payAtClubHint')]} />

      <StatusLine tone="warn" icon="pending" parts={[t('staffConfirms'), t('botNotice')]} />

      {submitError ? <StatusLine tone="danger" icon="error" parts={[submitError]} /> : null}
    </div>
  );
}

function Row({ label, value, bold }: { label: string; value: string; bold?: boolean }): ReactNode {
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
