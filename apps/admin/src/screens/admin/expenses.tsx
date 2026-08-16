import {
  Button,
  EntityTable,
  Panel,
  ProgressMeter,
  Select,
  StatTile,
  StatusLine,
  TextField,
} from '@playbron/ui';
import { useState, type CSSProperties, type ReactNode } from 'react';

import { EXPENSE_CATS, type Expense } from '../../mock/club';
import { S } from '../../mock/data';
import { nextId, useClub } from '../../store/club';
import { FormGrid, Labeled, RowActions, today } from './parts';

const EMPTY: Expense = { id: '', date: '', cat: EXPENSE_CATS[0] as string, amount: 0, note: '' };

const DATE_RE = /^(\d{2})-(\d{2})-(\d{4})$/;

const FULL: CSSProperties = { width: '100%' };

/** Xarajatlar — kommunal, ijara, maosh va boshqalar. */
export function ExpensesScreen(): ReactNode {
  const expenses = useClub((state) => state.expenses);
  const saveExpense = useClub((state) => state.saveExpense);
  const removeExpense = useClub((state) => state.removeExpense);

  const [draft, setDraft] = useState<Expense | null>(null);
  const [error, setError] = useState<string | null>(null);

  const total = expenses.reduce((sum, row) => sum + row.amount, 0);
  const byCat = expenses.reduce<Record<string, number>>((acc, row) => {
    acc[row.cat] = (acc[row.cat] ?? 0) + row.amount;
    return acc;
  }, {});
  const catRows = Object.entries(byCat).sort((a, b) => b[1] - a[1]);
  const biggest = catRows[0];
  const utilities = (byCat['Elektr'] ?? 0) + (byCat['Suv'] ?? 0) + (byCat['Internet'] ?? 0);

  // Yangi yozuv tepada — sanani teskari tartibda solishtiramiz
  const sorted = [...expenses].sort((a, b) => {
    const left = DATE_RE.exec(a.date);
    const right = DATE_RE.exec(b.date);
    if (!left || !right) return 0;
    return `${right[3]}${right[2]}${right[1]}`.localeCompare(`${left[3]}${left[2]}${left[1]}`);
  });

  const submit = (): void => {
    if (!draft) return;
    if (!DATE_RE.test(draft.date)) {
      setError('Sana DD-MM-YYYY shaklida bo‘lishi kerak');
      return;
    }
    if (draft.amount <= 0) {
      setError('Summa 0 dan katta bo‘lsin');
      return;
    }

    saveExpense({ ...draft, id: draft.id || nextId('e'), note: draft.note.trim() });
    setDraft(null);
    setError(null);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <div className="pb-tiles-4">
        <StatTile label="Jami xarajat" value={S(total)} unit="so‘m" icon="payments" />
        <StatTile label="Kommunal" value={S(utilities)} unit="so‘m" icon="bolt" />
        <StatTile
          label="Eng katta modda"
          value={biggest ? biggest[0] : '—'}
          unit={biggest ? `${S(biggest[1])} so‘m` : ''}
          icon="pie_chart"
        />
        <StatTile label="Yozuvlar" value={String(expenses.length)} unit="ta" icon="receipt_long" />
      </div>

      <div className="ds-split" style={{ alignItems: 'start' }}>
        <Panel
          title={`Xarajatlar (${expenses.length})`}
          notch
          brackets
          action={
            draft ? null : (
              <Button
                variant="primary"
                size="sm"
                icon="add"
                onClick={() => setDraft({ ...EMPTY, date: today() })}
              >
                Xarajat qo‘shish
              </Button>
            )
          }
        >
          {draft ? (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--gap-block)',
                marginBottom: 'var(--gap-panel)',
              }}
            >
              <FormGrid>
                <TextField
                  label="Sana"
                  value={draft.date}
                  onChange={(value) => setDraft({ ...draft, date: value })}
                  icon="event"
                />
                <Labeled label="Modda">
                  <Select
                    value={draft.cat}
                    items={EXPENSE_CATS}
                    onChange={(value) => setDraft({ ...draft, cat: value })}
                    style={FULL}
                  />
                </Labeled>
                <TextField
                  label="Summa"
                  value={String(draft.amount)}
                  onChange={(value) => setDraft({ ...draft, amount: Number(value) || 0 })}
                  icon="payments"
                  inputMode="numeric"
                />
                <TextField
                  label="Izoh"
                  value={draft.note}
                  onChange={(value) => setDraft({ ...draft, note: value })}
                  icon="notes"
                  onSubmitKey={submit}
                />
              </FormGrid>

              {error ? <StatusLine tone="danger" icon="error" parts={error} /> : null}

              <div style={{ display: 'flex', gap: 'var(--gap-tight)', flexWrap: 'wrap' }}>
                <Button variant="primary" notch icon="check" onClick={submit}>
                  Saqlash
                </Button>
                <Button variant="ghost" onClick={() => setDraft(null)}>
                  Bekor
                </Button>
              </div>
            </div>
          ) : null}

          <EntityTable
            rows={sorted}
            rowKey={(row) => row.id}
            empty="Xarajat kiritilmagan"
            columns={[
              {
                key: 'date',
                header: 'Sana',
                render: (row) => (
                  <span style={{ font: 'var(--type-data)', whiteSpace: 'nowrap' }}>{row.date}</span>
                ),
              },
              {
                key: 'cat',
                header: 'Modda',
                render: (row) => <span style={{ color: 'var(--text-title)' }}>{row.cat}</span>,
              },
              {
                key: 'note',
                header: 'Izoh',
                render: (row) => (
                  <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-muted)' }}>
                    {row.note || '—'}
                  </span>
                ),
              },
              {
                key: 'amount',
                header: 'Summa',
                align: 'right',
                render: (row) => (
                  <span
                    style={{ font: 'var(--type-data)', color: 'var(--red-100)', whiteSpace: 'nowrap' }}
                  >
                    {S(row.amount)}
                  </span>
                ),
              },
              {
                key: 'actions',
                header: '',
                align: 'right',
                render: (row) => (
                  <RowActions
                    onEdit={() => {
                      setDraft(row);
                      setError(null);
                    }}
                    onRemove={() => removeExpense(row.id)}
                  />
                ),
              },
            ]}
          />
        </Panel>

        <Panel title="Moddalar bo‘yicha" notch>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
            {catRows.map(([cat, amount]) => (
              <div key={cat} style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'baseline',
                    justifyContent: 'space-between',
                    gap: 10,
                  }}
                >
                  <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-body)' }}>
                    {cat}
                  </span>
                  <span
                    style={{
                      font: 'var(--type-data)',
                      color: 'var(--text-title)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {S(amount)}
                  </span>
                </div>
                <ProgressMeter
                  percent={total === 0 ? 0 : (amount / total) * 100}
                  color="var(--red-100)"
                  tip={() =>
                    `${cat} · ${S(amount)} so‘m (${total === 0 ? 0 : Math.round((amount / total) * 100)}%)`
                  }
                />
              </div>
            ))}
          </div>

          <div style={{ marginTop: 'var(--gap-panel)' }}>
            <StatusLine
              tone="neutral"
              icon="insights"
              parts={['Xarajatlar hisobotdagi foydadan ayiriladi', 'Oylik ro‘yxat asos qilinadi']}
            />
          </div>
        </Panel>
      </div>
    </div>
  );
}
