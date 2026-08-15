import {
  closeBill,
  errorText,
  getBill,
  listOpenBookings,
  type BillDto,
  type OpenBookingDto,
} from '@playbron/api-client';
import { Button, Icon, Panel, StatusLine, toast } from '@playbron/ui';
import { useCallback, useEffect, useState, type ReactNode } from 'react';

import { api } from '../lib/api';
import { S } from '../mock/data';
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
  const clubId = session?.clubs[0]?.id ?? null;

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

  const submit = async (): Promise<void> => {
    if (clubId === null || selected === null || bill === null) return;
    setClosing(true);
    setError(null);
    try {
      const result = await closeBill(api, clubId, selected.id, {
        paymentMethod: payment,
        paidAmount: bill.total,
      });
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

  return (
    <div className="ds-split" style={{ alignItems: 'start' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)', minWidth: 0 }}>
        <Panel title={`Ochiq hisoblar (${open.length})`} notch brackets>
          {open.length === 0 ? (
            <div
              style={{
                border: '1px dashed var(--line-2)',
                padding: 18,
                textAlign: 'center',
                font: 'var(--type-body-sm)',
                color: 'var(--text-dim)',
              }}
            >
              Ochiq hisob yo‘q
            </div>
          ) : (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(min(200px, 100%), 1fr))',
                gap: 'var(--gap-tight)',
              }}
            >
              {open.map((booking) => {
                const on = booking.id === selectedId;
                return (
                  <div
                    key={booking.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => setSelectedId(booking.id)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') setSelectedId(booking.id);
                    }}
                    style={{
                      cursor: 'pointer',
                      padding: 'var(--card-pad)',
                      background: on ? 'var(--surface-selected)' : 'var(--surface-card)',
                      border: `1px solid ${on ? 'var(--primary-100)' : 'var(--line-1)'}`,
                      clipPath: 'var(--clip-tr)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 6,
                      minWidth: 0,
                    }}
                  >
                    <span style={{ font: 'var(--type-section)', color: 'var(--text-title)' }}>
                      {booking.stationCode}
                    </span>
                    <span
                      style={{
                        font: 'var(--type-body-sm)',
                        color: 'var(--text-muted)',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {booking.guestLabel ?? 'Mijoz'}
                    </span>
                    <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                      {`${formatClock(booking.startsAt)} → ${formatClock(booking.endsAt)}`}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
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
                      tabIndex={0}
                      onClick={() => setPayment(option.id)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') setPayment(option.id);
                      }}
                      style={{
                        cursor: 'pointer',
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

              {error ? <StatusLine tone="danger" icon="error" parts={[error]} /> : null}

              <Button
                variant="primary"
                size="lg"
                notch
                block
                icon="lock"
                disabled={closing}
                onClick={() => void submit()}
              >
                {closing ? 'Yopilmoqda…' : 'Hisobni yopish'}
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
