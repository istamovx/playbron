import {
  addShiftMovement,
  closeShift,
  errorText,
  getCurrentShift,
  openShift,
  type ShiftDto,
} from '@playbron/api-client';
import { Button, Modal, Panel, StatTile, StatusLine, TextField, toast } from '@playbron/ui';
import { useCallback, useEffect, useState, type ReactNode } from 'react';

import { api } from '../lib/api';
import { S } from '../mock/data';
import { useBoard } from '../store/board';
import { useSession } from '../store/session';

/**
 * Smena — `PlayBron Xodim.dc.html` SMENA bo'limi.
 *
 * Reja #26 (2026-08-16, jonli sinovda topilgan): ekran to'liq dekorativ
 * edi — "Kirim"/"Chiqim"/"Smenani yopish" tugmalarida `onClick` UMUMAN
 * yo'q edi. Endi to'liq real backend (`api/src/playbron/modules/finance/
 * shifts.py`, `0021_shifts.py`): smena ochish/yopish, qo'lda kirim/
 * chiqim, "kutilayotgan naqd" esa qo'lda kiritilganlar + shu smenada
 * NAQD yopilgan bronlar yig'indisi (`bookings.paid_amount`, `0013_pos.py`
 * — takrorlanmaydi, faqat o'qiladi).
 *
 * Tovar reestri xodimda ko'rsatilmaydi: qoldiq buyurtma yetkazilganda avtomatik
 * kamayadi, sanash va inventarizatsiya superadmin yuzasiga o'tkazildi.
 */

type MovementKind = 'IN' | 'OUT';

export function ShiftScreen(): ReactNode {
  const session = useSession((state) => state.session);
  // Faol klub — header'dagi almashtirgichdan (`store/board.ts::activeClubId`);
  // hali sinxronlanmagan bo'lsa (App() darhol sozlaydi) birinchi a'zolikka tushadi.
  const activeClubId = useBoard((state) => state.activeClubId);
  const clubId = activeClubId ?? session?.clubs[0]?.id ?? null;

  const [shift, setShift] = useState<ShiftDto | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [openDraft, setOpenDraft] = useState<{ opening: string } | null>(null);
  const [movementDraft, setMovementDraft] = useState<{ kind: MovementKind; amount: string; reason: string } | null>(
    null,
  );
  const [closeDraft, setCloseDraft] = useState<{ counted: string } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const reload = useCallback(async (): Promise<void> => {
    if (clubId === null) return;
    setLoading(true);
    setLoadError(null);
    try {
      setShift(await getCurrentShift(api, clubId));
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

  const submitOpen = async (): Promise<void> => {
    if (!openDraft || clubId === null) return;
    const opening = Number(openDraft.opening);
    if (!Number.isFinite(opening) || opening < 0) {
      setFormError('Summani tekshiring');
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      await openShift(api, clubId, Math.round(opening));
      toast.success('Smena ochildi');
      setOpenDraft(null);
      await reload();
    } catch (cause) {
      const message = errorText(cause);
      setFormError(message);
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  const submitMovement = async (): Promise<void> => {
    if (!movementDraft || clubId === null || shift === null) return;
    const amount = Number(movementDraft.amount);
    if (!Number.isFinite(amount) || amount <= 0) {
      setFormError('Summa 0 dan katta bo‘lsin');
      return;
    }
    if (movementDraft.reason.trim().length < 1) {
      setFormError('Sababni kiriting');
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      await addShiftMovement(api, clubId, shift.id, {
        kind: movementDraft.kind,
        amount: Math.round(amount),
        reason: movementDraft.reason.trim(),
      });
      toast.success(movementDraft.kind === 'IN' ? 'Kirim qo‘shildi' : 'Chiqim qo‘shildi');
      setMovementDraft(null);
      await reload();
    } catch (cause) {
      const message = errorText(cause);
      setFormError(message);
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  const submitClose = async (): Promise<void> => {
    if (!closeDraft || clubId === null || shift === null) return;
    const counted = Number(closeDraft.counted);
    if (!Number.isFinite(counted) || counted < 0) {
      setFormError('Summani tekshiring');
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      const closed = await closeShift(api, clubId, shift.id, Math.round(counted));
      toast.success(
        closed.variance === 0
          ? 'Smena yopildi — kassa mos keldi'
          : `Smena yopildi — farq ${S(closed.variance ?? 0)} so‘m`,
      );
      setCloseDraft(null);
      await reload();
    } catch (cause) {
      const message = errorText(cause);
      setFormError(message);
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  if (loadError && !shift) {
    return <StatusLine tone="danger" icon="error" parts={[loadError]} />;
  }

  if (!loading && shift === null) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
        <Panel title="Smena" notch brackets>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)', alignItems: 'flex-start' }}>
            <StatusLine
              tone="neutral"
              icon="lock_clock"
              parts={['Ochiq smena yo‘q', 'Boshlash uchun boshlang‘ich kassani kiriting']}
            />
            <Button
              variant="primary"
              size="lg"
              notch
              icon="play_circle"
              onClick={() => {
                setFormError(null);
                setOpenDraft({ opening: '0' });
              }}
            >
              Smena ochish
            </Button>
          </div>
        </Panel>

        <Modal
          open={openDraft !== null}
          onClose={() => {
            setOpenDraft(null);
            setFormError(null);
          }}
          title="Smena ochish"
          variant="center"
        >
          {openDraft ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
              <TextField
                label="Boshlang‘ich kassa"
                value={openDraft.opening}
                onChange={(value) => setOpenDraft({ opening: value })}
                icon="payments"
                inputMode="numeric"
                placeholder="200000"
              />
              {formError ? <StatusLine tone="danger" icon="error" parts={formError} /> : null}
              <div style={{ display: 'flex', gap: 'var(--gap-tight)', flexWrap: 'wrap' }}>
                <Button variant="primary" notch icon="check" disabled={submitting} onClick={() => void submitOpen()}>
                  {submitting ? 'Ochilmoqda…' : 'Ochish'}
                </Button>
                <Button variant="ghost" disabled={submitting} onClick={() => setOpenDraft(null)}>
                  Bekor
                </Button>
              </div>
            </div>
          ) : null}
        </Modal>
      </div>
    );
  }

  if (shift === null) {
    return <StatusLine tone="neutral" icon="hourglass_empty" parts="Yuklanmoqda…" />;
  }

  const inTotal = shift.movements.filter((m) => m.kind === 'IN').reduce((sum, m) => sum + m.amount, 0);
  const outTotal = shift.movements.filter((m) => m.kind === 'OUT').reduce((sum, m) => sum + m.amount, 0);

  return (
    <div className="ds-split" style={{ alignItems: 'start' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)', minWidth: 0 }}>
        <div className="pb-tiles-4">
          <StatTile label="Boshlang‘ich kassa" value={S(shift.openingCash)} unit="so‘m" icon="payments" />
          <StatTile label="Kutilayotgan naqd" value={S(shift.expectedCash)} unit="so‘m" icon="account_balance_wallet" />
          <StatTile label="Kirim" value={S(inTotal)} unit="so‘m" icon="add_circle" />
          <StatTile label="Chiqim" value={S(outTotal)} unit="so‘m" icon="remove_circle" />
        </div>

        <Panel title="Kassa harakatlari" notch brackets>
          {shift.movements.length === 0 ? (
            <StatusLine tone="neutral" icon="receipt_long" parts="Hali harakat yo‘q" />
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
                {shift.movements.map((row) => (
                  <div
                    key={row.id}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'minmax(96px, auto) minmax(0, 1fr) minmax(72px, auto) minmax(96px, auto)',
                      gap: 10,
                      padding: '0 10px',
                      minHeight: 40,
                      alignItems: 'center',
                      borderBottom: '1px solid var(--line-1)',
                    }}
                  >
                    <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                      {new Date(row.createdAt).toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </span>
                    <span
                      style={{
                        font: 'var(--type-body-sm)',
                        color: 'var(--text-body)',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {row.reason}
                      {row.createdByName ? ` · ${row.createdByName}` : ''}
                    </span>
                    <span
                      style={{
                        font: 'var(--type-label)',
                        letterSpacing: 'var(--ls-label)',
                        textTransform: 'uppercase',
                        color: row.kind === 'IN' ? 'var(--secondary-500)' : 'var(--red-100)',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {row.kind === 'IN' ? 'Kirim' : 'Chiqim'}
                    </span>
                    <span
                      style={{
                        font: 'var(--type-data)',
                        color: row.kind === 'IN' ? 'var(--secondary-500)' : 'var(--red-100)',
                        textAlign: 'right',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {row.kind === 'IN' ? '' : '− '}
                      {S(row.amount)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Panel>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)', minWidth: 0 }}>
        <Panel title="Joriy smena" notch brackets>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {[
              { k: 'Ochilgan', v: new Date(shift.openedAt).toLocaleString('uz-UZ') },
              { k: 'Boshlang‘ich kassa', v: `${S(shift.openingCash)} so‘m` },
              { k: 'Kutilayotgan naqd', v: `${S(shift.expectedCash)} so‘m` },
            ].map((field) => (
              <div
                key={field.k}
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
                  {field.k}
                </span>
                <span style={{ font: 'var(--type-data)', color: 'var(--text-title)', textAlign: 'right', whiteSpace: 'nowrap' }}>
                  {field.v}
                </span>
              </div>
            ))}
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(min(130px, 100%), 1fr))',
              gap: 'var(--gap-tight)',
              marginTop: 14,
            }}
          >
            <Button
              variant="secondary"
              icon="add"
              block
              onClick={() => {
                setFormError(null);
                setMovementDraft({ kind: 'IN', amount: '', reason: '' });
              }}
            >
              Kirim
            </Button>
            <Button
              variant="secondary"
              icon="remove"
              block
              onClick={() => {
                setFormError(null);
                setMovementDraft({ kind: 'OUT', amount: '', reason: '' });
              }}
            >
              Chiqim
            </Button>
          </div>

          <div style={{ marginTop: 'var(--gap-block)' }}>
            <Button
              variant="primary"
              size="lg"
              notch
              block
              icon="lock_clock"
              onClick={() => {
                setFormError(null);
                setCloseDraft({ counted: String(shift.expectedCash) });
              }}
            >
              Smenani yopish
            </Button>
          </div>
        </Panel>
      </div>

      <Modal
        open={movementDraft !== null}
        onClose={() => {
          setMovementDraft(null);
          setFormError(null);
        }}
        title={movementDraft?.kind === 'IN' ? 'Kirim qo‘shish' : 'Chiqim qo‘shish'}
        variant="center"
      >
        {movementDraft ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
            <TextField
              label="Summa"
              value={movementDraft.amount}
              onChange={(value) => setMovementDraft({ ...movementDraft, amount: value })}
              icon="payments"
              inputMode="numeric"
              placeholder="35000"
            />
            <TextField
              label="Sabab"
              value={movementDraft.reason}
              onChange={(value) => setMovementDraft({ ...movementDraft, reason: value })}
              icon="notes"
              placeholder={movementDraft.kind === 'IN' ? 'Masalan: naqd hisob' : 'Masalan: kuryer to‘lovi'}
              onSubmitKey={() => void submitMovement()}
            />
            {formError ? <StatusLine tone="danger" icon="error" parts={formError} /> : null}
            <div style={{ display: 'flex', gap: 'var(--gap-tight)', flexWrap: 'wrap' }}>
              <Button variant="primary" notch icon="check" disabled={submitting} onClick={() => void submitMovement()}>
                {submitting ? 'Saqlanmoqda…' : 'Saqlash'}
              </Button>
              <Button variant="ghost" disabled={submitting} onClick={() => setMovementDraft(null)}>
                Bekor
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>

      <Modal
        open={closeDraft !== null}
        onClose={() => {
          setCloseDraft(null);
          setFormError(null);
        }}
        title="Smenani yopish"
        variant="center"
      >
        {closeDraft ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
            <StatusLine
              tone="neutral"
              icon="account_balance_wallet"
              parts={[`Kutilayotgan naqd: ${S(shift.expectedCash)} so‘m`, 'Naqdni sanab, natijani kiriting']}
            />
            <TextField
              label="Sanalgan naqd"
              value={closeDraft.counted}
              onChange={(value) => setCloseDraft({ counted: value })}
              icon="payments"
              inputMode="numeric"
              onSubmitKey={() => void submitClose()}
            />
            {formError ? <StatusLine tone="danger" icon="error" parts={formError} /> : null}
            <div style={{ display: 'flex', gap: 'var(--gap-tight)', flexWrap: 'wrap' }}>
              <Button variant="primary" notch icon="lock_clock" disabled={submitting} onClick={() => void submitClose()}>
                {submitting ? 'Yopilmoqda…' : 'Yopish'}
              </Button>
              <Button variant="ghost" disabled={submitting} onClick={() => setCloseDraft(null)}>
                Bekor
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}
