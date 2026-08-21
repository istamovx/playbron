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
import { Button, DatePicker, Modal, Panel, Select, StatusLine, TextField, TimeSelect, toast } from '@playbron/ui';
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';

import { api } from '../lib/api';
import { useBoard } from '../store/board';
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

interface StartValue {
  date: string;
  time: string;
}

function toStartValue(d: Date): StartValue {
  const pad = (n: number) => String(n).padStart(2, '0');
  return {
    date: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`,
    time: `${pad(d.getHours())}:${pad(d.getMinutes())}`,
  };
}

/** Sukut boshlanish — telefon orqali OLDINDAN bron uchun (2 soat keyinga,
 * 30 daqiqaga yaxlitlangan). Kalendar/vaqt tanlagich — brauzer mahalliy
 * vaqti, klub vaqt zonasi hisobsiz (`native input[type=date]` ba'zi
 * WebView/brauzerlarda tanlagich umuman ochmasdi — loyiha egasining
 * ikki marta xabar bergan topilmasi, 2026-08-16, `packages/ui`dagi
 * `DatePicker`/`TimeSelect` bilan almashtirildi). */
function defaultStart(): StartValue {
  const in2h = new Date(Date.now() + 2 * 60 * 60 * 1000);
  in2h.setMinutes(Math.ceil(in2h.getMinutes() / 30) * 30, 0, 0);
  return toStartValue(in2h);
}

/** Mijoz hozir kelgan — hisob shu zahotiyoq boshlanadi (loyiha egasining
 * so'rovi, 2026-08-16): sukut `defaultStart()` telefon orqali OLDINDAN
 * bron uchun (2 soat keyinga), joyida kelgan mijoz uchun esa "Hozir" tez
 * tugmasi hozirgi daqiqani qo'yadi. */
function nowStart(): StartValue {
  return toStartValue(new Date());
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
 * Xona tanlash — faqat kod. `roomLabel` (odatda sukut "Standart") va
 * konsol turi bu ro'yxatda KO'RSATILMAYDI (loyiha egasi, 2026-08-21):
 * "1-xona · Standart · PS4 Pro" xodimni chalg'itardi, konsol allaqachon
 * pastdagi alohida "Konsol" tanlagichida so'raladi.
 */
function stationLabelOf(s: StationDto): string {
  return s.code;
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
  // Faol klub — header'dagi almashtirgichdan (`store/board.ts::activeClubId`);
  // hali sinxronlanmagan bo'lsa (App() darhol sozlaydi) birinchi a'zolikka tushadi.
  const activeClubId = useBoard((state) => state.activeClubId);
  const clubId = activeClubId ?? session?.clubs[0]?.id ?? null;

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

/**
 * Qo'lda bron formasi — `bookings.tsx`dan (kutilayotgan navbat ekrani) va
 * `live-board.tsx`dan (bo'sh/band xonaga to'g'ridan hisob ochish) bir xil
 * shaklda ishlatiladi.
 *
 * `initialStation` berilsa (Live Board'dan kelgan chaqiruv):
 *   - xona OLDINDAN tanlangan, boshlanish "hozir" (`nowStart()`).
 *   - shu xona ro'yxatda HAR DOIM bor — hatto tizim uni "band"/nofaol deb
 *     bilsa ham (loyiha egasining so'rovi, 2026-08-16: "qaysi xona
 *     bo'shligini xodim tizimdan ko'proq biladi, erkinlik unga
 *     topshirilsin"). Haqiqiy to'qnashuv baribir backend'dagi
 *     `bookings_no_overlap` orqali tekshiriladi — frontend faqat oldindan
 *     TAKLIF qiladi, TAQIQLAMAYDI.
 */
export function ManualBookingPanel({
  clubId,
  stations,
  initialStation,
  onCreated,
}: {
  clubId: number | null;
  stations: StationDto[];
  initialStation?: StationDto;
  onCreated: () => void;
}): ReactNode {
  const activeStations = useMemo(() => {
    const active = stations.filter((s) => s.status === 'active');
    if (initialStation && !active.some((s) => s.id === initialStation.id)) {
      return [initialStation, ...active];
    }
    return active;
  }, [stations, initialStation]);

  const [stationLabel, setStationLabel] = useState(() =>
    initialStation ? stationLabelOf(initialStation) : '',
  );
  const [start, setStart] = useState<StartValue>(() => (initialStation ? nowStart() : defaultStart()));
  const [hours, setHours] = useState('1');
  const [guestName, setGuestName] = useState('');
  const [guestPhone, setGuestPhone] = useState(PHONE_PREFIX);
  // Yangi (konsolsiz) xonada MAJBURIY — reja #38, loyiha egasi, 2026-08-16:
  // "xonaga konsol biriktirmaslik kerak, xodim bron/hisob ochganda tanlasin".
  const [consoleType, setConsoleType] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!stationLabel && activeStations.length > 0) {
      setStationLabel(stationLabelOf(activeStations[0] as StationDto));
    }
  }, [activeStations, stationLabel]);

  const selectedStation = activeStations.find((s) => stationLabelOf(s) === stationLabel);
  // Xona o'zida konsol saqlagan (eski, 0023'dan oldingi) bo'lsa ham DOIM
  // qo'lda tanlanadi — loyiha egasining topilmasi (2026-08-16): "xonaga
  // konsol biriktirilgan turibdi, olib tashla, qo'lda tanlasin". Xonaning
  // eski `consoleType`si endi faqat BOSHLANG'ICH taklif (pastda), majburiy
  // fallback sifatida ISHLATILMAYDI.
  const needsConsoleType = selectedStation !== undefined;

  // Xona almashtirilganda eski tanlov qolib ketmasin. Xonada eski
  // `consoleType` bo'lsa u BOSHLANG'ICH qiymat sifatida qo'yiladi — xodim
  // baribir uni Select'da ko'radi va o'zgartira oladi (majburiy emas).
  useEffect(() => {
    setConsoleType(selectedStation?.consoleType ?? '');
  }, [stationLabel, selectedStation?.consoleType]);

  const hoursNum = Number(hours);
  const ready =
    clubId !== null &&
    selectedStation !== undefined &&
    (!needsConsoleType || consoleType.length > 0) &&
    start.date.length > 0 &&
    start.time.length > 0 &&
    hoursNum >= 1 &&
    hoursNum <= 6 &&
    guestName.trim().length > 0 &&
    guestPhone.replace(/\D/g, '').length >= 12 &&
    !submitting;

  const submit = async (): Promise<void> => {
    if (!ready || clubId === null || !selectedStation) return;

    setSubmitting(true);
    setError(null);
    setDone(false);
    // Bosilgan tugma bo'yicha BIR marta — ichki 401-yangilash qayta
    // urinishi shu kalitni takrorlaydi, yangi bosish esa yangisini oladi
    // (`packages/api-client/src/client.ts::send()`).
    const idempotencyKey = crypto.randomUUID();
    try {
      await createStaffBooking(
        api,
        clubId,
        {
          stationId: selectedStation.id,
          // `DatePicker`/`TimeSelect` — mahalliy vaqt, `Z` yo'q; `Date` shuni
          // brauzer zonasida talqin qiladi, ISO'ga aylantirilganda UTC'ga
          // to'g'ri o'giradi.
          startsAt: new Date(`${start.date}T${start.time}`).toISOString(),
          hours: hoursNum,
          guestName: guestName.trim(),
          guestPhone,
          consoleType: consoleType || undefined,
        },
        idempotencyKey,
      );
      setGuestName('');
      setGuestPhone(PHONE_PREFIX);
      setStart(defaultStart());
      setConsoleType('');
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
            items={activeStations.map(stationLabelOf)}
            onChange={setStationLabel}
            size="lg"
            notch
          />
        </label>
      )}

      {needsConsoleType ? (
        <label style={{ display: 'grid', gap: 6 }}>
          <span
            style={{
              font: 'var(--type-label)',
              letterSpacing: 'var(--ls-label)',
              textTransform: 'uppercase',
              color: 'var(--text-label)',
            }}
          >
            Konsol
          </span>
          <Select
            value={CONSOLE_LABEL[consoleType] ?? ''}
            items={Object.values(CONSOLE_LABEL)}
            onChange={(label) => {
              const id = Object.keys(CONSOLE_LABEL).find((c) => CONSOLE_LABEL[c] === label);
              if (id) setConsoleType(id);
            }}
            size="lg"
            notch
          />
        </label>
      ) : null}

      <DatePicker label="Sana" value={start.date} onChange={(date) => setStart({ ...start, date })} />

      <label style={{ display: 'grid', gap: 6 }}>
        <span
          style={{
            font: 'var(--type-label)',
            letterSpacing: 'var(--ls-label)',
            textTransform: 'uppercase',
            color: 'var(--text-label)',
          }}
        >
          Vaqt
        </span>
        <TimeSelect value={start.time} onChange={(time) => setStart({ ...start, time })} style={{ width: '100%' }} />
      </label>

      <Button variant="ghost" icon="bolt" onClick={() => setStart(nowStart())} block>
        Hozir boshlash
      </Button>

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
