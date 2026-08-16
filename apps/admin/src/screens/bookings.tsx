import {
  confirmBooking,
  createStaffBooking,
  errorText,
  listPendingBookings,
  listStations,
  rejectBooking,
  type PendingBookingDto,
  type StationDto,
} from '@playbron/api-client';
import { Button, Modal, Panel, Select, StatusLine, TextField, toast } from '@playbron/ui';
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';

import { api } from '../lib/api';
import { useSession } from '../store/session';

/** `stations.console_type` — CHECK ro'yxati bilan bir xil (`0009_bookings.py`). */
const CONSOLE_LABEL: Record<string, string> = {
  ps3: 'PS3',
  ps4: 'PS4',
  ps4pro: 'PS4 Pro',
  ps5: 'PS5',
  ps5pro: 'PS5 Pro',
};

const PHONE_PREFIX = '+998';
const PHONE_DIGITS = 9;

/** `login.tsx::formatPhone` bilan bir xil — bu yerda mehmon raqami uchun. */
function formatPhone(raw: string): string {
  let digits = raw.replace(/\D/g, '');
  if (digits.startsWith('998')) digits = digits.slice(3);
  digits = digits.slice(0, PHONE_DIGITS);

  let out = PHONE_PREFIX;
  if (digits.length > 0) out += ' ' + digits.slice(0, 2);
  if (digits.length > 2) out += ' ' + digits.slice(2, 5);
  if (digits.length > 5) out += ' ' + digits.slice(5, 7);
  if (digits.length > 7) out += ' ' + digits.slice(7, 9);
  return out;
}

/** `datetime-local` input qiymati — klub vaqt zonasi hisobsiz, brauzer mahalliy vaqti. */
function defaultStart(): string {
  const in2h = new Date(Date.now() + 2 * 60 * 60 * 1000);
  in2h.setMinutes(Math.ceil(in2h.getMinutes() / 30) * 30, 0, 0);
  return toLocalInput(in2h);
}

function toLocalInput(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Mijoz hozir kelgan — hisob shu zahotiyoq boshlanadi (loyiha egasining
 * so'rovi, 2026-08-16): sukut `defaultStart()` telefon orqali OLDINDAN
 * bron uchun (2 soat keyinga), joyida kelgan mijoz uchun esa "Hozir" tez
 * tugmasi hozirgi daqiqani qo'yadi. */
function nowStart(): string {
  return toLocalInput(new Date());
}

function formatClock(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString('uz-UZ', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Xodim uchun bron boshqaruvi — ikki qism:
 *   1. Mijoz yuborgan `PENDING` navbat — tasdiq/rad
 *   2. Qo'lda bron — telefon/kelib bron qiluvchi mijoz uchun, hisobsiz
 *      (`docs`dagi so'rov: "xodim qog'ozbozlikdan qutiladi")
 */
export function BookingsScreen(): ReactNode {
  const session = useSession((state) => state.session);
  // Ko'p klublik almashtirgich hali yo'q (`store/board.ts::activeClubId`
  // birinchi klubga `App()`da sinxronlanadi) — birinchi a'zolik yetarli.
  const clubId = session?.clubs[0]?.id ?? null;

  const [pending, setPending] = useState<PendingBookingDto[]>([]);
  const [stations, setStations] = useState<StationDto[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [acting, setActing] = useState<number | null>(null);
  const [manualOpen, setManualOpen] = useState(false);

  const reload = useCallback(async (): Promise<void> => {
    if (clubId === null) return;
    setLoading(true);
    setLoadError(null);
    try {
      const [p, s] = await Promise.all([
        listPendingBookings(api, clubId),
        listStations(api, clubId),
      ]);
      setPending(p);
      setStations(s);
    } catch (cause) {
      const message = errorText(cause);
      setLoadError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }, [clubId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const act = async (id: number, kind: 'confirm' | 'reject'): Promise<void> => {
    if (clubId === null) return;
    setActing(id);
    try {
      if (kind === 'confirm') await confirmBooking(api, clubId, id);
      else await rejectBooking(api, clubId, id);
      toast.success(kind === 'confirm' ? 'Bron tasdiqlandi' : 'Bron rad etildi');
      await reload();
    } catch (cause) {
      const message = errorText(cause);
      setLoadError(message);
      toast.error(message);
    } finally {
      setActing(null);
    }
  };

  return (
    <>
      <Modal
        open={manualOpen}
        onClose={() => setManualOpen(false)}
        title="Qo‘lda bron"
        variant="drawer"
      >
        <ManualBookingPanel
          clubId={clubId}
          stations={stations}
          onCreated={() => {
            void reload();
            setManualOpen(false);
          }}
        />
      </Modal>

      <Panel
        title={`Kutilayotgan bronlar (${pending.length})`}
        notch
        brackets
        action={
          <Button variant="primary" size="sm" icon="add" onClick={() => setManualOpen(true)}>
            Qo‘lda bron
          </Button>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-tight)' }}>
          {loadError ? <StatusLine tone="danger" icon="error" parts={[loadError]} /> : null}

          {!loading && pending.length === 0 && !loadError ? (
            <div
              style={{
                border: '1px dashed var(--line-2)',
                padding: 18,
                textAlign: 'center',
                font: 'var(--type-body-sm)',
                color: 'var(--text-dim)',
              }}
            >
              Kutilayotgan bron yo‘q
            </div>
          ) : null}

          {pending.map((booking) => (
            <PendingCard
              key={booking.id}
              booking={booking}
              busy={acting === booking.id}
              onConfirm={() => void act(booking.id, 'confirm')}
              onReject={() => void act(booking.id, 'reject')}
            />
          ))}
        </div>
      </Panel>
    </>
  );
}

function PendingCard({
  booking,
  busy,
  onConfirm,
  onReject,
}: {
  booking: PendingBookingDto;
  busy: boolean;
  onConfirm: () => void;
  onReject: () => void;
}): ReactNode {
  return (
    <div
      style={{
        padding: 'var(--card-pad)',
        background: 'var(--surface-card)',
        border: '1px solid var(--yellow-100)',
        clipPath: 'var(--clip-tr)',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        minWidth: 0,
      }}
    >
      <div
        style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 }}
      >
        <span style={{ font: 'var(--type-control)', color: 'var(--text-title)' }}>
          {booking.stationCode}
        </span>
        <span style={{ font: 'var(--type-data)', color: 'var(--text-muted)' }}>
          {formatClock(booking.startsAt)} · {booking.hours} soat
        </span>
      </div>

      <div style={{ font: 'var(--type-body-sm)', color: 'var(--text-body)' }}>
        {booking.customerName ?? 'Mijoz'}
        {booking.customerPhone ? ` · ${booking.customerPhone}` : ''}
      </div>

      <div style={{ display: 'flex', gap: 'var(--gap-tight)', flexWrap: 'wrap' }}>
        <Button variant="primary" size="sm" icon="check" disabled={busy} onClick={onConfirm}>
          Tasdiqlash
        </Button>
        <Button variant="ghost" size="sm" icon="close" disabled={busy} onClick={onReject}>
          Rad etish
        </Button>
      </div>
    </div>
  );
}

function ManualBookingPanel({
  clubId,
  stations,
  onCreated,
}: {
  clubId: number | null;
  stations: StationDto[];
  onCreated: () => void;
}): ReactNode {
  const activeStations = useMemo(() => stations.filter((s) => s.status === 'active'), [stations]);
  const labelOf = (s: StationDto): string =>
    `${s.code} · ${s.roomLabel} · ${CONSOLE_LABEL[s.consoleType] ?? s.consoleType}`;

  const [stationLabel, setStationLabel] = useState('');
  const [starts, setStarts] = useState(defaultStart());
  const [hours, setHours] = useState('1');
  const [guestName, setGuestName] = useState('');
  const [guestPhone, setGuestPhone] = useState(PHONE_PREFIX);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!stationLabel && activeStations.length > 0) {
      setStationLabel(labelOf(activeStations[0] as StationDto));
    }
  }, [activeStations, stationLabel]);

  const hoursNum = Number(hours);
  const ready =
    clubId !== null &&
    activeStations.some((s) => labelOf(s) === stationLabel) &&
    starts.length > 0 &&
    hoursNum >= 1 &&
    hoursNum <= 6 &&
    guestName.trim().length > 0 &&
    guestPhone.replace(/\D/g, '').length >= 12 &&
    !submitting;

  const submit = async (): Promise<void> => {
    if (!ready || clubId === null) return;
    const station = activeStations.find((s) => labelOf(s) === stationLabel);
    if (!station) return;

    setSubmitting(true);
    setError(null);
    setDone(false);
    try {
      await createStaffBooking(api, clubId, {
        stationId: station.id,
        // `datetime-local` — mahalliy vaqt, `Z` yo'q; `Date` shuni
        // brauzer zonasida talqin qiladi, ISO'ga aylantirilganda UTC'ga
        // to'g'ri o'giradi.
        startsAt: new Date(starts).toISOString(),
        hours: hoursNum,
        guestName: guestName.trim(),
        guestPhone,
      });
      setGuestName('');
      setGuestPhone(PHONE_PREFIX);
      setStarts(defaultStart());
      setDone(true);
      toast.success('Bron ochildi');
      onCreated();
    } catch (cause) {
      const message = errorText(cause);
      setError(message);
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
      <StatusLine
        tone="neutral"
        icon="call"
        parts={['Telefon yoki kelib bron qilgan mijoz uchun', 'Darhol tasdiqlangan holda ochiladi']}
      />

      {activeStations.length === 0 ? (
        <StatusLine tone="warn" icon="warning" parts={['Faol xona topilmadi']} />
      ) : (
        <label style={{ display: 'grid', gap: 6 }}>
          <span
            style={{
              font: 'var(--type-label)',
              letterSpacing: 'var(--ls-label)',
              textTransform: 'uppercase',
              color: 'var(--text-label)',
            }}
          >
            Xona
          </span>
          <Select
            value={stationLabel}
            items={activeStations.map(labelOf)}
            onChange={setStationLabel}
            size="lg"
            notch
          />
        </label>
      )}

      <label style={{ display: 'grid', gap: 6 }}>
        <span
          style={{
            font: 'var(--type-label)',
            letterSpacing: 'var(--ls-label)',
            textTransform: 'uppercase',
            color: 'var(--text-label)',
          }}
        >
          Boshlanish vaqti
        </span>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            type="datetime-local"
            value={starts}
            onChange={(event) => setStarts(event.target.value)}
            style={{
              flex: 1,
              minWidth: 0,
              height: 'var(--control-h-lg)',
              padding: '0 10px',
              background: 'var(--surface-field)',
              border: '1px solid var(--line-2)',
              borderRadius: 'var(--r-1)',
              clipPath: 'var(--clip-tr)',
              font: 'var(--type-data)',
              color: 'var(--fg-1)',
            }}
          />
          <Button variant="ghost" icon="bolt" onClick={() => setStarts(nowStart())}>
            Hozir
          </Button>
        </div>
      </label>

      <TextField
        label="Necha soat"
        value={hours}
        onChange={setHours}
        type="number"
        inputMode="numeric"
        icon="schedule"
      />

      <TextField
        label="Mijoz ismi"
        value={guestName}
        onChange={setGuestName}
        placeholder="Ism"
        icon="person"
      />

      <TextField
        label="Mijoz telefoni"
        value={guestPhone}
        onChange={(next) => setGuestPhone(formatPhone(next))}
        placeholder={`${PHONE_PREFIX} 90 123 45 67`}
        icon="call"
        inputMode="tel"
      />

      <Button
        variant="primary"
        size="lg"
        block
        notch
        icon="event_available"
        disabled={!ready}
        onClick={() => void submit()}
      >
        {submitting ? 'Yuborilmoqda…' : 'Bron ochish'}
      </Button>

      {done ? <StatusLine tone="ok" icon="check_circle" parts={['Bron ochildi']} /> : null}
      {error ? <StatusLine tone="danger" icon="error" parts={[error]} /> : null}
    </div>
  );
}
