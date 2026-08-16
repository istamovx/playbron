import {
  cancelBooking,
  errorText,
  extendBooking,
  getBookingDetail,
  listLiveStations,
  type BookingDetailDto,
  type LiveStationDto,
} from '@playbron/api-client';
import { Button, Grid, MetricCell, Modal, Panel, StatusLine, TextField, toast } from '@playbron/ui';
import { useCallback, useEffect, useState, type ReactNode } from 'react';

import { api } from '../lib/api';
import { S } from '../mock/data';
import { useBoard, useNow } from '../store/board';
import { useSession } from '../store/session';
import { ManualBookingPanel } from './bookings';

const CONSOLE_LABEL: Record<string, string> = {
  ps3: 'PS3',
  ps4: 'PS4',
  ps4pro: 'PS4 Pro',
  ps5: 'PS5',
  ps5pro: 'PS5 Pro',
};

function formatClock(iso: string): string {
  return new Date(iso).toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' });
}

/**
 * Live board — real bandlik: CONFIRMED bron `period`i shu lahzani o'z ichiga
 * olsa xona band. Prototipdagi kelmadi/uzaytirish/rezerv oqimlari hozircha
 * yo'q — backend'da mos amal yo'q (`stations.status='maintenance'` bundan
 * mustasno). 20 soniyada avtomatik yangilanadi.
 */
export function LiveBoardScreen(): ReactNode {
  const session = useSession((state) => state.session);
  // Faol klub — header'dagi almashtirgichdan (`store/board.ts::activeClubId`);
  // hali sinxronlanmagan bo'lsa (App() darhol sozlaydi) birinchi a'zolikka tushadi.
  const activeClubId = useBoard((state) => state.activeClubId);
  const clubId = activeClubId ?? session?.clubs[0]?.id ?? null;

  const [stations, setStations] = useState<LiveStationDto[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Live Board'dan to'g'ridan hisob ochish (loyiha egasining so'rovi,
  // 2026-08-16): "xona qaysi bo'shligini xodim tizimdan ko'proq biladi,
  // erkinlik unga topshirilsin" — tugma HAR BIR kartada, statusidan
  // qat'i nazar; haqiqiy to'qnashuvni backend tekshiradi.
  const [openStation, setOpenStation] = useState<LiveStationDto | null>(null);
  // Band karta tanlansa — buyurtma/vaqt detali (reja #36, 2026-08-16).
  const [detailBookingId, setDetailBookingId] = useState<number | null>(null);

  const reload = useCallback(async (): Promise<void> => {
    if (clubId === null) return;
    try {
      setStations(await listLiveStations(api, clubId));
      setError(null);
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setLoading(false);
    }
  }, [clubId]);

  useEffect(() => {
    setLoading(true);
    void reload();
    const timer = setInterval(() => void reload(), 20_000);
    return () => clearInterval(timer);
  }, [reload]);

  const occupied = stations.filter((s) => s.bookingId !== null).length;
  const free = stations.filter((s) => s.bookingId === null && s.status === 'active').length;
  const maintenance = stations.filter((s) => s.status === 'maintenance').length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <Modal
        open={openStation !== null}
        onClose={() => setOpenStation(null)}
        title={openStation ? `Hisob ochish — ${openStation.code}` : 'Hisob ochish'}
        variant="drawer"
      >
        {openStation ? (
          <ManualBookingPanel
            clubId={clubId}
            stations={stations}
            initialStation={openStation}
            onCreated={() => {
              void reload();
              setOpenStation(null);
            }}
          />
        ) : null}
      </Modal>

      <Modal
        open={detailBookingId !== null}
        onClose={() => setDetailBookingId(null)}
        title="Hisob tafsiloti"
        variant="drawer"
      >
        {clubId !== null && detailBookingId !== null ? (
          <BookingDetailPanel
            clubId={clubId}
            bookingId={detailBookingId}
            onChanged={() => void reload()}
            onClose={() => setDetailBookingId(null)}
          />
        ) : null}
      </Modal>

      <div className="pb-tiles-3">
        <MetricCell label="Band" value={`${occupied} / ${stations.length}`} />
        <MetricCell label="Bo‘sh" value={String(free)} />
        <MetricCell label="Ta’mirda" value={String(maintenance)} />
      </div>

      {error ? <StatusLine tone="danger" icon="error" parts={[error]} /> : null}

      <Panel title="Xonalar" notch brackets>
        {!loading && stations.length === 0 && !error ? (
          <div
            style={{
              border: '1px dashed var(--line-2)',
              padding: 18,
              textAlign: 'center',
              font: 'var(--type-body-sm)',
              color: 'var(--text-dim)',
            }}
          >
            Xona qo‘shilmagan
          </div>
        ) : (
          <Grid min={235}>
            {stations.map((station) => (
              <StationCard
                key={station.id}
                station={station}
                onOpenAccount={() => setOpenStation(station)}
                onViewDetail={() => setDetailBookingId(station.bookingId)}
              />
            ))}
          </Grid>
        )}
      </Panel>
    </div>
  );
}

function StationCard({
  station,
  onOpenAccount,
  onViewDetail,
}: {
  station: LiveStationDto;
  onOpenAccount: () => void;
  onViewDetail: () => void;
}): ReactNode {
  const occupied = station.bookingId !== null;
  const tone =
    station.status === 'maintenance'
      ? 'var(--fg-4)'
      : occupied
        ? 'var(--yellow-100)'
        : 'var(--slot-free)';
  const label =
    station.status === 'maintenance' ? 'Ta’mirda' : occupied ? 'Band' : 'Bo‘sh';

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={occupied ? onViewDetail : onOpenAccount}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') (occupied ? onViewDetail : onOpenAccount)();
      }}
      style={{
        minWidth: 0,
        padding: 'var(--card-pad)',
        background: 'var(--surface-panel)',
        border: '1px solid var(--line-1)',
        boxShadow: `inset 3px 0 0 ${tone}`,
        clipPath: 'var(--clip-tr)',
        display: 'flex',
        flexDirection: 'column',
        gap: 9,
        cursor: 'pointer',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 }}>
        <span
          style={{
            font: 'var(--fw-regular) var(--fs-panel-fluid)/var(--lh-snug) var(--font-display)',
            color: 'var(--text-title)',
          }}
        >
          {station.code}
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
          {label}
        </span>
      </div>

      <div style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
        {[
          station.roomLabel,
          station.consoleType ? (CONSOLE_LABEL[station.consoleType] ?? station.consoleType) : null,
          `${S(station.rate)} / soat`,
        ]
          .filter(Boolean)
          .join(' · ')}
      </div>

      <div style={{ height: 1, background: 'var(--line-1)' }} />

      {occupied ? (
        <div style={{ font: 'var(--type-body-sm)', color: 'var(--text-title)' }}>
          {station.guestLabel ?? 'Mijoz'}
          {station.endsAt ? (
            <span style={{ color: 'var(--text-dim)' }}>{` · ${formatClock(station.endsAt)} gacha`}</span>
          ) : null}
        </div>
      ) : (
        <div style={{ font: 'var(--type-body-sm)', color: 'var(--text-dim)' }}>—</div>
      )}

      {occupied ? (
        <StatusLine tone="neutral" icon="visibility" parts={['Tafsilotni ko‘rish uchun bosing']} />
      ) : (
        <Button variant="ghost" size="sm" icon="add_circle" onClick={onOpenAccount} block>
          Hisob ochish
        </Button>
      )}
    </div>
  );
}

const EXTEND_OPTIONS = [1, 2, 3] as const;

/** Karta tanlanganda — buyurtma, ochilgan vaqt, countdown, uzaytirish/bekor
 * qilish (loyiha egasining so'rovi, 2026-08-16). `timeline.tsx`da ham bar
 * bosilganda qayta ishlatiladi — bekor qilish ikkala ekranda ham kerak. */
export function BookingDetailPanel({
  clubId,
  bookingId,
  onChanged,
  onClose,
}: {
  clubId: number;
  bookingId: number;
  onChanged: () => void;
  onClose: () => void;
}): ReactNode {
  const [detail, setDetail] = useState<BookingDetailDto | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [cancelReason, setCancelReason] = useState('');
  useNow(); // har soniyada qayta render — countdown yangilanib tursin

  const load = useCallback(async (): Promise<void> => {
    setLoading(true);
    try {
      setDetail(await getBookingDetail(api, clubId, bookingId));
      setError(null);
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setLoading(false);
    }
  }, [clubId, bookingId]);

  useEffect(() => {
    void load();
  }, [load]);

  const extend = async (hours: number): Promise<void> => {
    setBusy(true);
    try {
      await extendBooking(api, clubId, bookingId, hours);
      toast.success(`${hours} soatga uzaytirildi`);
      await load();
      onChanged();
    } catch (cause) {
      toast.error(errorText(cause));
    } finally {
      setBusy(false);
    }
  };

  const cancel = async (): Promise<void> => {
    setBusy(true);
    try {
      await cancelBooking(api, clubId, bookingId, cancelReason.trim() || undefined);
      toast.success('Bron bekor qilindi');
      onChanged();
      onClose();
    } catch (cause) {
      toast.error(errorText(cause));
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return <StatusLine tone="neutral" icon="hourglass_empty" parts={['Yuklanmoqda…']} />;
  }
  if (error || detail === null) {
    return <StatusLine tone="danger" icon="error" parts={[error ?? 'Topilmadi']} />;
  }

  const endsMs = new Date(detail.endsAt).getTime();
  const remainingMs = endsMs - Date.now();
  const overtime = remainingMs < 0;
  const absMin = Math.floor(Math.abs(remainingMs) / 60000);
  const countdown = `${String(Math.floor(absMin / 60)).padStart(2, '0')}:${String(absMin % 60).padStart(2, '0')}`;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
      <StatusLine
        tone={detail.status === 'CONFIRMED' ? (overtime ? 'danger' : 'ok') : 'neutral'}
        icon={detail.status === 'CONFIRMED' ? 'schedule' : 'info'}
        parts={[
          detail.stationCode,
          detail.guestLabel ?? 'Mijoz',
          detail.status === 'CONFIRMED'
            ? overtime
              ? `Overtime +${countdown}`
              : `Qoldi ${countdown}`
            : detail.status,
        ]}
      />

      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <FieldLine label="Ochilgan" value={formatClock(detail.startsAt)} />
        <FieldLine label="Tugash" value={formatClock(detail.endsAt)} />
        <FieldLine label="Soat" value={`${detail.hours} soat`} />
        <FieldLine label="O‘yin" value={S(detail.playAmount)} />
        <FieldLine label="Bar" value={S(detail.ordersAmount)} />
        <FieldLine label="Jami" value={S(detail.total)} />
      </div>

      <div
        style={{
          font: 'var(--type-label)',
          letterSpacing: 'var(--ls-label)',
          textTransform: 'uppercase',
          color: 'var(--text-label)',
        }}
      >
        Buyurtmalar
      </div>
      {detail.items.length === 0 ? (
        <StatusLine tone="neutral" parts={['Buyurtma yo‘q']} />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {detail.items.map((item, index) => (
            <div
              key={index}
              style={{ display: 'flex', justifyContent: 'space-between', gap: 8, font: 'var(--type-data)' }}
            >
              <span style={{ color: 'var(--text-body)' }}>{`${item.productName} × ${item.qty}`}</span>
              <span style={{ color: 'var(--text-title)', whiteSpace: 'nowrap' }}>
                {S(item.priceSnapshot * item.qty)}
              </span>
            </div>
          ))}
        </div>
      )}

      {detail.status === 'CONFIRMED' && !detail.closed ? (
        <>
          <div style={{ height: 1, background: 'var(--line-1)' }} />

          <div
            style={{
              font: 'var(--type-label)',
              letterSpacing: 'var(--ls-label)',
              textTransform: 'uppercase',
              color: 'var(--text-label)',
            }}
          >
            Vaqtni uzaytirish
          </div>
          <div style={{ display: 'flex', gap: 'var(--gap-tight)', flexWrap: 'wrap' }}>
            {EXTEND_OPTIONS.map((hours) => (
              <Button
                key={hours}
                variant="secondary"
                size="sm"
                icon="add_alarm"
                disabled={busy}
                onClick={() => void extend(hours)}
              >
                {`+${hours} soat`}
              </Button>
            ))}
          </div>

          {confirmCancel ? (
            <>
              <TextField
                label="Sabab (ixtiyoriy)"
                value={cancelReason}
                onChange={setCancelReason}
                placeholder="Mijoz kelmadi"
              />
              <div style={{ display: 'flex', gap: 'var(--gap-tight)', flexWrap: 'wrap' }}>
                <Button variant="danger" icon="cancel" disabled={busy} onClick={() => void cancel()}>
                  {busy ? 'Bekor qilinmoqda…' : 'Ha, bekor qilish'}
                </Button>
                <Button variant="ghost" onClick={() => setConfirmCancel(false)}>
                  Ortga
                </Button>
              </div>
            </>
          ) : (
            <Button variant="ghost" icon="cancel" onClick={() => setConfirmCancel(true)}>
              Mijoz kelmadi — bekor qilish
            </Button>
          )}
        </>
      ) : null}
    </div>
  );
}

function FieldLine({ label, value }: { label: string; value: string }): ReactNode {
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
      <span style={{ font: 'var(--type-data)', color: 'var(--text-title)', textAlign: 'right' }}>
        {value}
      </span>
    </div>
  );
}
