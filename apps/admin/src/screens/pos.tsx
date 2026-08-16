import {
  closeBill,
  errorText,
  getBill,
  getPaymentProofBlob,
  listOpenBookings,
  type BillDto,
  type OpenBookingDto,
} from '@playbron/api-client';
import { Button, EntityTable, Icon, Panel, StatusLine, toast, type Column } from '@playbron/ui';
import { useCallback, useEffect, useState, type ReactNode } from 'react';

import { api } from '../lib/api';
import { S } from '../mock/data';
import { useBoard } from '../store/board';
import { useSession } from '../store/session';

function formatClock(iso: string): string {
  return new Date(iso).toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' });
}

/**
 * Kassa — ochiq (yopilmagan) bronlarni yopish: o'yin summasi + buyurtmalar
 * yig'indisi = jami hisob. Prototipdagi chek yuklash/tasdiqlash, bonus ball
 * va bron to'lovi chegirmasi hozircha yo'q — to'lov Bosqich 2'da qo'shiladi
 * (`docs`), shu bosqichda faqat naqd/o'tkazma belgilanadi.
 */
export function PosScreen(): ReactNode {
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
  const [closedSummary, setClosedSummary] = useState<{ station: string; bill: BillDto } | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  const submit = async (): Promise<void> => {
    if (clubId === null || selected === null || bill === null) return;
    setClosing(true);
    setError(null);
    try {
      const result = await closeBill(api, clubId, selected.id, {
        paymentMethod: payment,
        paidAmount: bill.total,
      });
      if (result.awaitingProof) {
        // O'tkazma + botga ulangan mijoz — hisob HALI OCHIQ, chek
        // kutilmoqda (reja #37). Kartochka ro'yxatidan ham chiqarilmaydi.
        setBill(result);
        toast.success('Mijozga chek so‘raldi — javob kutilmoqda');
        return;
      }
      setClosedSummary({ station: selected.stationCode, bill: result });
      setSelectedId(null);
      setBill(null);
      toast.success('Hisob yopildi');
      await reload();
    } catch (cause) {
      const message = errorText(cause);
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

              <div
                style={{
                  font: 'var(--type-label)',
                  letterSpacing: 'var(--ls-label)',
                  textTransform: 'uppercase',
                  color: 'var(--text-label)',
                }}
              >
                To‘lov usuli
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 'var(--gap-tight)' }}>
                {(
                  [
                    { id: 'CASH', label: 'Naqd', icon: 'payments' },
                    { id: 'TRANSFER', label: 'O‘tkazma', icon: 'account_balance' },
                  ] as const
                ).map((option) => {
                  const on = payment === option.id;
                  return (
                    <div
                      key={option.id}
                      role="button"
                      tabIndex={bill.paymentProofStatus ? -1 : 0}
                      onClick={() => {
                        if (!bill.paymentProofStatus) setPayment(option.id);
                      }}
                      onKeyDown={(event) => {
                        if (
                          !bill.paymentProofStatus &&
                          (event.key === 'Enter' || event.key === ' ')
                        ) {
                          setPayment(option.id);
                        }
                      }}
                      style={{
                        cursor: bill.paymentProofStatus ? 'default' : 'pointer',
                        opacity: bill.paymentProofStatus && !on ? 0.5 : 1,
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
                disabled={closing || bill.paymentProofStatus === 'PENDING'}
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
                <FieldLine label="Jami to‘landi" value={S(closedSummary.bill.total)} />
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
