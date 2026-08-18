import {
  ApiError,
  closeBill,
  errorText,
  getBill,
  getPaymentProofBlob,
  listOpenBookings,
  type BillDto,
  type OpenBookingDto,
  type OverpayReason,
  type ShortfallReason,
} from '@playbron/api-client';
import {
  Button,
  EntityTable,
  Icon,
  Panel,
  StatusLine,
  TextField,
  toast,
  type Column,
} from '@playbron/ui';
import { useCallback, useEffect, useState, type ReactNode } from 'react';

import { useT, type MsgKey } from '../i18n';
import { api } from '../lib/api';
import { S } from '../mock/data';
import { useBoard } from '../store/board';
import { useSession } from '../store/session';

function formatClock(iso: string): string {
  return new Date(iso).toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' });
}

/**
 * `«250 000»` → `250000`. Pul butun so'mda (`CLAUDE.md` §Pul) — kasr,
 * minus yoki harf bo'lsa `null`, ya'ni "yuborilmaydi".
 */
function parseSom(raw: string): number | null {
  // `\s` uzilmas probelni ham qamraydi — `S()` bilan formatlangan
  // qiymat maydonga qaytib tushsa ham o'qiladi.
  const cleaned = raw.replace(/\s/g, '');
  if (!/^\d+$/.test(cleaned)) return null;
  const value = Number(cleaned);
  return Number.isSafeInteger(value) ? value : null;
}

/**
 * `errorText()` ustidagi kassaga xos qatlam. Farq sababi UI'da MAJBURIY
 * qilingani uchun 422'lar odatda chiqmaydi — bu ikkinchi himoya qatori
 * (hisob boshqa terminalda o'zgargan holat uchun).
 */
function closeErrorText(cause: unknown, t: (key: MsgKey) => string): string {
  if (cause instanceof ApiError) {
    if (cause.code === 'SHIFT_REQUIRED') return t('posShiftRequired');
    if (cause.code === 'SHORTFALL_REASON_REQUIRED' || cause.code === 'OVERPAY_REASON_REQUIRED') {
      return t('posReasonRequired');
    }
  }
  return errorText(cause);
}

interface Choice<T extends string> {
  id: T;
  label: string;
  icon: string;
}

/**
 * Kassa — ochiq (yopilmagan) bronlarni yopish: o'yin summasi + buyurtmalar
 * yig'indisi = jami hisob. Prototipdagi chek yuklash/tasdiqlash, bonus ball
 * va bron to'lovi chegirmasi hozircha yo'q — to'lov Bosqich 2'da qo'shiladi
 * (`docs`), shu bosqichda faqat naqd/o'tkazma belgilanadi.
 */
export function PosScreen(): ReactNode {
  const t = useT();
  const session = useSession((state) => state.session);
  // Faol klub — header'dagi almashtirgichdan (`store/board.ts::activeClubId`);
  // hali sinxronlanmagan bo'lsa (App() darhol sozlaydi) birinchi a'zolikka tushadi.
  const activeClubId = useBoard((state) => state.activeClubId);
  const clubId = activeClubId ?? session?.clubs[0]?.id ?? null;

  const [open, setOpen] = useState<OpenBookingDto[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [bill, setBill] = useState<BillDto | null>(null);
  const [payment, setPayment] = useState<'CASH' | 'TRANSFER'>('CASH');
  const [closing, setClosing] = useState(false);
  const [closedSummary, setClosedSummary] = useState<{
    station: string;
    bill: BillDto;
    /** Kassaga HAQIQATAN tushgan summa — server javobida yo'q, shuning
     * uchun yuborilgan qiymat saqlanadi (frontend uni `total`dan qayta
     * HISOBLAMAYDI, `CLAUDE.md` §Pul). */
    paid: number;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Olingan summa — sukut bo'yicha hisobning o'zi. Xodim o'zgartirsa farq
  // sababi so'raladi (`close_bill()`: chegirma / qarz / choychaqa).
  const [paidInput, setPaidInput] = useState('');
  const [shortfallReason, setShortfallReason] = useState<ShortfallReason | null>(null);
  const [overpayReason, setOverpayReason] = useState<OverpayReason | null>(null);

  const reload = useCallback(async (): Promise<void> => {
    if (clubId === null) return;
    try {
      const rows = await listOpenBookings(api, clubId);
      setOpen(rows);
      if (selectedId === null && rows.length > 0) setSelectedId(rows[0]?.id ?? null);
    } catch (cause) {
      toast.error(errorText(cause));
    }
  }, [clubId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const selected = open.find((b) => b.id === selectedId) ?? null;

  useEffect(() => {
    if (clubId === null || selected === null) {
      setBill(null);
      return;
    }
    void getBill(api, clubId, selected.id)
      .then(setBill)
      .catch((cause: unknown) => toast.error(errorText(cause)));
  }, [clubId, selected]);

  // Mijoz chek yuborganini xodim kutmasdan bilsin (reja #37) — "javob
  // kutilmoqda" holatida holat har 5 soniyada avtomatik qayta tekshiriladi.
  useEffect(() => {
    if (clubId === null || selected === null || bill?.paymentProofStatus !== 'PENDING') return;
    const timer = setInterval(() => {
      void getBill(api, clubId, selected.id).then(setBill);
    }, 5000);
    return () => clearInterval(timer);
  }, [clubId, selected, bill?.paymentProofStatus]);

  // Boshqa hisob tanlansa yoki server `total`ni qayta hisoblasa maydon
  // yangi summaga qaytadi va sabab tozalanadi — eski qiymat qolib ketsa
  // xodim bilmagan holda chegirma yozib yuborardi.
  const billBookingId = bill?.bookingId ?? null;
  const billTotal = bill?.total ?? null;
  useEffect(() => {
    if (billTotal === null) return;
    setPaidInput(String(billTotal));
    setShortfallReason(null);
    setOverpayReason(null);
  }, [billBookingId, billTotal]);

  const paid = parseSom(paidInput);
  const amountInvalid = paid === null;
  const difference = paid === null || bill === null ? 0 : paid - bill.total;
  const shortfall = difference < 0 ? -difference : 0;
  const overpay = difference > 0 ? difference : 0;
  const reasonMissing =
    (shortfall > 0 && shortfallReason === null) || (overpay > 0 && overpayReason === null);

  const submit = async (): Promise<void> => {
    if (clubId === null || selected === null || bill === null) return;
    // Server 422'si IKKINCHI himoya qatori — so'rov sababsiz ketmaydi.
    if (paid === null) {
      setError(t('posAmountInvalid'));
      return;
    }
    if (reasonMissing) {
      setError(t('posReasonRequired'));
      return;
    }
    setClosing(true);
    setError(null);
    try {
      // Hisob EKRANGA olingandan keyin barga yangi buyurtma qo'shilgan
      // bo'lishi mumkin — server `total`ni QAYTA hisoblaydi. Shuning
      // uchun yopishdan oldin hisob yangilanadi.
      const fresh = await getBill(api, clubId, selected.id);
      setBill(fresh);

      // Yangilangan hisob boshqa chiqsa FARQ MA'NOSI o'zgaradi: xodim
      // "to'liq to'landi" deb bosgan tugma jimgina chegirmaga (yoki
      // qarzga) aylanib qolardi. Shuning uchun yopilmaydi — yuqoridagi
      // effekt maydonni yangi summaga qaytaradi, xodim qayta tasdiqlaydi.
      if (fresh.total !== bill.total) {
        setError(t('posBillChanged'));
        return;
      }

      const result = await closeBill(api, clubId, selected.id, {
        paymentMethod: payment,
        paidAmount: paid,
        shortfallReason: shortfall > 0 && shortfallReason !== null ? shortfallReason : undefined,
        overpayReason: overpay > 0 && overpayReason !== null ? overpayReason : undefined,
      });
      if (result.awaitingProof) {
        // O'tkazma + botga ulangan mijoz — hisob HALI OCHIQ, chek
        // kutilmoqda (reja #37). Kartochka ro'yxatidan ham chiqarilmaydi.
        setBill(result);
        toast.success('Mijozga chek so‘raldi — javob kutilmoqda');
        return;
      }
      setClosedSummary({ station: selected.stationCode, bill: result, paid });
      setSelectedId(null);
      setBill(null);
      toast.success('Hisob yopildi');
      await reload();
    } catch (cause) {
      const message = closeErrorText(cause, t);
      setError(message);
      toast.error(message);
    } finally {
      setClosing(false);
    }
  };

  const [proofUrl, setProofUrl] = useState<string | null>(null);
  const [proofLoading, setProofLoading] = useState(false);

  useEffect(() => {
    setProofUrl((current) => {
      if (current) URL.revokeObjectURL(current);
      return null;
    });
    if (clubId === null || selected === null || bill?.paymentProofStatus !== 'SUBMITTED') return;
    setProofLoading(true);
    void getPaymentProofBlob(api, clubId, selected.id)
      .then((blob) => setProofUrl(URL.createObjectURL(blob)))
      .catch((cause: unknown) => toast.error(errorText(cause)))
      .finally(() => setProofLoading(false));
  }, [clubId, selected, bill?.paymentProofStatus]);

  // Card grid o'rniga jadval (loyiha egasining topilmasi, 2026-08-16):
  // hisoblar soni o'zgarganda auto-fit grid layout buzilardi.
  const openColumns: Column<OpenBookingDto>[] = [
    {
      key: 'station',
      header: 'Xona',
      render: (booking) => (
        <button
          type="button"
          onClick={() => setSelectedId(booking.id)}
          style={{
            background: 'none',
            border: 'none',
            padding: 0,
            cursor: 'pointer',
            font: 'var(--type-control)',
            color: booking.id === selectedId ? 'var(--text-accent)' : 'var(--text-title)',
          }}
        >
          {booking.stationCode}
        </button>
      ),
    },
    {
      key: 'guest',
      header: 'Mijoz',
      render: (booking) => booking.guestLabel ?? 'Mijoz',
    },
    {
      key: 'time',
      header: 'Vaqt',
      render: (booking) => `${formatClock(booking.startsAt)} → ${formatClock(booking.endsAt)}`,
    },
    {
      key: 'select',
      header: '',
      align: 'right',
      render: (booking) => (
        <Button
          variant={booking.id === selectedId ? 'primary' : 'ghost'}
          size="sm"
          onClick={() => setSelectedId(booking.id)}
        >
          {booking.id === selectedId ? 'Tanlangan' : 'Tanlash'}
        </Button>
      ),
    },
  ];

  return (
    <div className="ds-split" style={{ alignItems: 'start' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)', minWidth: 0 }}>
        <Panel title={`Ochiq hisoblar (${open.length})`} notch brackets>
          <EntityTable<OpenBookingDto>
            columns={openColumns}
            rows={open}
            rowKey={(booking) => String(booking.id)}
            empty="Ochiq hisob yo‘q"
          />
        </Panel>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)', minWidth: 0 }}>
        <Panel
          title={selected ? `Hisob · ${selected.stationCode}` : 'Hisob'}
          notch
          brackets
          glow
        >
          {selected && bill ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <FieldLine label="Xona" value={selected.stationCode} />
                <FieldLine label="Mijoz" value={selected.guestLabel ?? '—'} />
                <FieldLine label="Soat" value={`${selected.hours} soat`} />
              </div>

              <div style={{ height: 1, background: 'var(--line-1)' }} />

              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-tight)' }}>
                <Row label={`O‘yin (${selected.hours} soat)`} value={S(bill.playAmount)} />
                <Row label="Bar" value={S(bill.ordersAmount)} />
              </div>

              <div
                style={{
                  display: 'flex',
                  alignItems: 'baseline',
                  justifyContent: 'space-between',
                  gap: 12,
                  paddingTop: 12,
                  borderTop: '1px solid var(--line-2)',
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
                  Jami
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

              <TextField
                label={t('posReceivedLabel')}
                value={paidInput}
                onChange={setPaidInput}
                icon="payments"
                inputMode="numeric"
                disabled={bill.paymentProofStatus === 'PENDING'}
                error={amountInvalid ? t('posAmountInvalid') : undefined}
              />

              {amountInvalid ? (
                <StatusLine tone="danger" icon="error" parts={[t('posAmountInvalid')]} />
              ) : null}

              {shortfall > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-tight)' }}>
                  <Row label={t('posShortfallLabel')} value={S(shortfall)} />
                  <SectionLabel>{t('posShortfallReason')}</SectionLabel>
                  <ChoiceTiles<ShortfallReason>
                    options={[
                      { id: 'DISCOUNT', label: t('posReasonDiscount'), icon: 'sell' },
                      { id: 'DEBT', label: t('posReasonDebt'), icon: 'schedule' },
                    ]}
                    value={shortfallReason}
                    onChange={setShortfallReason}
                  />
                </div>
              ) : null}

              {overpay > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-tight)' }}>
                  <Row label={t('posOverpayLabel')} value={S(overpay)} />
                  <SectionLabel>{t('posOverpayReason')}</SectionLabel>
                  <ChoiceTiles<OverpayReason>
                    options={[{ id: 'TIP', label: t('posReasonTip'), icon: 'volunteer_activism' }]}
                    value={overpayReason}
                    onChange={setOverpayReason}
                  />
                </div>
              ) : null}

              {reasonMissing ? (
                <StatusLine tone="warn" icon="help" parts={[t('posReasonRequired')]} />
              ) : null}

              <SectionLabel>{t('payMethodLabel')}</SectionLabel>
              <ChoiceTiles<'CASH' | 'TRANSFER'>
                options={[
                  { id: 'CASH', label: t('payMethodCash'), icon: 'payments' },
                  { id: 'TRANSFER', label: t('payMethodTransfer'), icon: 'account_balance' },
                ]}
                value={payment}
                onChange={setPayment}
                locked={bill.paymentProofStatus !== null}
              />

              {bill.paymentProofStatus === 'PENDING' ? (
                <StatusLine
                  tone="warn"
                  icon="hourglass_top"
                  parts={['Mijozga chek so‘raldi — javob kutilmoqda']}
                />
              ) : null}

              {bill.paymentProofStatus === 'SUBMITTED' ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-tight)' }}>
                  <StatusLine tone="ok" icon="mark_email_read" parts={['Chek keldi — tekshiring']} />
                  {proofLoading ? (
                    <StatusLine tone="neutral" icon="hourglass_empty" parts={['Yuklanmoqda…']} />
                  ) : proofUrl ? (
                    <img
                      src={proofUrl}
                      alt="To‘lov cheki"
                      style={{
                        width: '100%',
                        maxHeight: 320,
                        objectFit: 'contain',
                        border: '1px solid var(--line-2)',
                        background: 'var(--surface-field)',
                      }}
                    />
                  ) : null}
                </div>
              ) : null}

              {error ? <StatusLine tone="danger" icon="error" parts={[error]} /> : null}

              <Button
                variant="primary"
                size="lg"
                notch
                block
                icon={bill.paymentProofStatus === 'SUBMITTED' ? 'check_circle' : 'lock'}
                disabled={
                  closing ||
                  bill.paymentProofStatus === 'PENDING' ||
                  amountInvalid ||
                  reasonMissing
                }
                onClick={() => void submit()}
              >
                {closing
                  ? 'Yopilmoqda…'
                  : bill.paymentProofStatus === 'SUBMITTED'
                    ? 'Tasdiqlash va yopish'
                    : bill.paymentProofStatus === 'PENDING'
                      ? 'Javob kutilmoqda…'
                      : 'Hisobni yopish'}
              </Button>
            </div>
          ) : closedSummary ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
              <StatusLine
                tone="ok"
                icon="check_circle"
                parts={['Hisob yopildi', closedSummary.station]}
              />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <FieldLine label="O‘yin" value={S(closedSummary.bill.playAmount)} />
                <FieldLine label="Bar" value={S(closedSummary.bill.ordersAmount)} />
                <FieldLine label={t('posBillTotal')} value={S(closedSummary.bill.total)} />
                <FieldLine label={t('posPaidLabel')} value={S(closedSummary.paid)} />
                {/* Farq qatorlari SERVER qaytargan summalardan — frontend
                    ularni `total` va `paid`dan qayta hisoblamaydi. */}
                {closedSummary.bill.discountAmount > 0 ? (
                  <FieldLine
                    label={t('posReasonDiscount')}
                    value={S(closedSummary.bill.discountAmount)}
                  />
                ) : null}
                {closedSummary.bill.debtAmount > 0 ? (
                  <FieldLine label={t('posReasonDebt')} value={S(closedSummary.bill.debtAmount)} />
                ) : null}
                {closedSummary.bill.tipAmount > 0 ? (
                  <FieldLine label={t('posReasonTip')} value={S(closedSummary.bill.tipAmount)} />
                ) : null}
              </div>
              <Button variant="secondary" size="lg" block icon="add" onClick={() => setClosedSummary(null)}>
                Yopish
              </Button>
            </div>
          ) : (
            <div
              style={{
                border: '1px dashed var(--line-2)',
                padding: 24,
                textAlign: 'center',
                font: 'var(--type-body-sm)',
                color: 'var(--text-dim)',
              }}
            >
              Ochiq hisob yo‘q
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}

/** Blok ustidagi ALL CAPS yorliq — to'lov usuli va farq sababi bir xil
 * ko'rinishda turishi uchun. */
function SectionLabel({ children }: { children: ReactNode }): ReactNode {
  return (
    <div
      style={{
        font: 'var(--type-label)',
        letterSpacing: 'var(--ls-label)',
        textTransform: 'uppercase',
        color: 'var(--text-label)',
      }}
    >
      {children}
    </div>
  );
}

/**
 * Yonma-yon tanlov plitkalari. To'lov usuli va farq sababi (chegirma /
 * qarz / choychaqa) uchun bir xil boshqaruv — ilgari to'lov usuli JSX'da
 * inline yozilgan edi.
 *
 * `locked` — chek kutilayotgan hisobda tanlov qotib qoladi: tanlangani
 * ko'rinadi, boshqasi so'nadi.
 */
function ChoiceTiles<T extends string>({
  options,
  value,
  onChange,
  locked = false,
}: {
  options: readonly Choice<T>[];
  value: T | null;
  onChange: (id: T) => void;
  locked?: boolean;
}): ReactNode {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${options.length}, 1fr)`,
        gap: 'var(--gap-tight)',
      }}
    >
      {options.map((option) => {
        const on = value === option.id;
        return (
          <div
            key={option.id}
            role="button"
            tabIndex={locked ? -1 : 0}
            onClick={() => {
              if (!locked) onChange(option.id);
            }}
            onKeyDown={(event) => {
              if (!locked && (event.key === 'Enter' || event.key === ' ')) onChange(option.id);
            }}
            style={{
              cursor: locked ? 'default' : 'pointer',
              opacity: locked && !on ? 0.5 : 1,
              minHeight: 'var(--control-h-lg)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 7,
              background: on ? 'var(--surface-selected)' : 'var(--surface-field)',
              border: `1px solid ${on ? 'var(--primary-100)' : 'var(--line-2)'}`,
              font: 'var(--type-control)',
              color: on ? 'var(--text-title)' : 'var(--text-body)',
            }}
          >
            <Icon name={option.icon} size={15} />
            {option.label}
          </div>
        );
      })}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }): ReactNode {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 }}>
      <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-body)' }}>{label}</span>
      <span style={{ font: 'var(--type-data)', color: 'var(--text-body)', whiteSpace: 'nowrap' }}>
        {value}
      </span>
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
