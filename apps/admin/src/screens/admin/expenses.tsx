import {
  ApiError,
  createExpense,
  errorText,
  listExpenses,
  listOpenShifts,
  updateExpense,
  type ExpenseDto,
  type OpenShiftSummaryDto,
} from '@playbron/api-client';
import {
  Button,
  EntityTable,
  Modal,
  Panel,
  ProgressMeter,
  Select,
  StatTile,
  StatusLine,
  Tag,
  TextField,
  toast,
} from '@playbron/ui';
import { useCallback, useEffect, useState, type ReactNode } from 'react';

import { useT, type MsgKey } from '../../i18n';
import { api } from '../../lib/api';
import { EXPENSE_CATS, EXPENSES_INIT, type Expense as LegacyExpense } from '../../mock/club';
import { S } from '../../mock/data';
import { useBoard } from '../../store/board';
import { useSession } from '../../store/session';
import { useClub } from '../../store/club';
import { FormGrid, Labeled } from './parts';

/**
 * Xarajatlar — kommunal, ijara, maosh va boshqalar.
 *
 * Reja #18 (2026-08-16): ekran to'liq `useClub()` mock do'konidan
 * (`playbron.club` localStorage) real backendga o'tkazildi
 * (`api/src/playbron/modules/finance/*`, `0020_expenses.py`). Dashboard
 * va Hisobot hali eski mock `expenses`dan foydalanadi — ular reja #22da
 * navbatda (`docs/00-audit.md`dagi bosqichma-bosqich ko'chirish naqshi,
 * `dashboard.tsx`dagi klub ish vaqti bilan bir xil).
 */

const MIGRATION_DONE_IDS_KEY = 'playbron.expenses.migrated.ids';

/**
 * Modul darajasidagi qulf — komponent instansiyasiga EMAS, JS moduliga
 * bog'liq, shuning uchun React StrictMode'ning dev rejimidagi sinxron
 * mount→cleanup→qayta-mount tsiklida HAM saqlanib qoladi (`useRef` esa
 * ikkala chaqiruvda ham "yangi" bo'lib ko'rinadi — aynan shu sabab jonli
 * sinovda ikki baravar yozuv topildi, 2026-08-16). `clubId` bo'yicha —
 * foydalanuvchi sahifani qayta yuklamay boshqa klubga o'tsa ham ishlashi
 * uchun. `localStorage`dagi progres esa haqiqiy sahifa qayta
 * yuklanishlari orasida qo'riqlaydi.
 */
const migrationClaimedThisLoad = new Set<number>();

function readMigratedIds(): Set<string> {
  try {
    const raw = localStorage.getItem(MIGRATION_DONE_IDS_KEY);
    return new Set(raw ? (JSON.parse(raw) as string[]) : []);
  } catch {
    return new Set();
  }
}

function markMigrated(id: string): void {
  const ids = readMigratedIds();
  ids.add(id);
  localStorage.setItem(MIGRATION_DONE_IDS_KEY, JSON.stringify([...ids]));
}

/** `''` — kassaga tegmaydigan yozuv (backendda `method = null`). */
type DraftMethod = '' | 'CASH' | 'TRANSFER';

interface Draft {
  id: number | null;
  spentOn: string;
  category: string;
  amount: string;
  note: string;
  status: 'active' | 'archived';
  /** Faqat YARATISHDA yuboriladi — `updateExpense()` `method`ni qabul
   * qilmaydi (yopilgan smena hisobini keyin o'zgartirib bo'lmaydi,
   * `CLAUDE.md` §Pul). */
  method: DraftMethod;
  /** Naqd xarajat qaysi ochiq smenadan chiqadi. */
  shiftId: number | null;
}

function todayIso(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}

const EMPTY_DRAFT: Draft = {
  id: null,
  spentOn: todayIso(),
  category: EXPENSE_CATS[0] as string,
  amount: '',
  note: '',
  status: 'active',
  method: '',
  shiftId: null,
};

/** Naqd xarajat uchun ochiq smena kerak — server xatosi foydalanuvchi
 * tilida ko'rsatiladi (`finance/service.py::create_expense()`). */
function expenseErrorText(cause: unknown, t: (key: MsgKey) => string): string {
  if (cause instanceof ApiError && cause.code === 'SHIFT_REQUIRED') {
    return t('expenseNoOpenShift');
  }
  return errorText(cause);
}

/**
 * Smena tanlagichning yorliqlari — xodim ismi, o'ziniki alohida
 * belgilanadi. `Select` qiymat sifatida MATNni beradi, shuning uchun
 * yorliqlar takrorlanmasligi shart: bir xil ismli ikki xodim bo'lsa
 * smena ID'si qo'shiladi.
 *
 * Ochilish vaqti ATAYLAB ko'rsatilmaydi: konsolda `clubs.timezone` yo'q,
 * brauzer zonasiga tayanish esa taqiqlangan (`CLAUDE.md` §Vaqt).
 */
function shiftOptions(
  shifts: readonly OpenShiftSummaryDto[],
  myStaffId: number | null,
  mineWord: string,
): { id: number; label: string }[] {
  const used = new Set<string>();
  return shifts.map((shift) => {
    const base = shift.staffId === myStaffId ? `${shift.staffName} (${mineWord})` : shift.staffName;
    const label = used.has(base) ? `${base} #${shift.id}` : base;
    used.add(label);
    return { id: shift.id, label };
  });
}

/** Eski `DD-MM-YYYY`dan ISO (`YYYY-MM-DD`)ga — noto'g'ri shakl bo'lsa `null`. */
function ddmmyyyyToIso(raw: string): string | null {
  const m = /^(\d{2})-(\d{2})-(\d{4})$/.exec(raw);
  if (!m) return null;
  return `${m[3]}-${m[2]}-${m[1]}`;
}

/** Foydalanuvchi HECH QACHON tegmagan asl seed qatormi (`EXPENSES_INIT`dan
 * bittasi bilan aynan bir xil) — bunday qatorlar KO'CHIRILMAYDI, aks holda
 * har bir yangi klubga soxta "Avgust ijarasi" kabi yozuvlar tushib qolardi. */
function isUntouchedSeed(row: LegacyExpense): boolean {
  const original = EXPENSES_INIT.find((seed) => seed.id === row.id);
  if (!original) return false;
  return (
    original.date === row.date &&
    original.cat === row.cat &&
    original.amount === row.amount &&
    original.note === row.note
  );
}

export function ExpensesScreen(): ReactNode {
  const t = useT();
  const session = useSession((state) => state.session);
  // Faol klub — header'dagi almashtirgichdan (`store/board.ts::activeClubId`);
  // hali sinxronlanmagan bo'lsa (App() darhol sozlaydi) birinchi a'zolikka tushadi.
  const activeClubId = useBoard((state) => state.activeClubId);
  const clubId = activeClubId ?? session?.clubs[0]?.id ?? null;

  const [expenses, setExpenses] = useState<ExpenseDto[]>([]);
  const [openShifts, setOpenShifts] = useState<OpenShiftSummaryDto[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [draft, setDraft] = useState<Draft | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const reload = useCallback(async (): Promise<void> => {
    if (clubId === null) return;
    setLoading(true);
    setLoadError(null);
    // Ikkala so'rov MUSTAQIL — ketma-ket kutish ekran ochilish vaqtini
    // ikki round-trip'ga cho'zardi. Ochiq smenalar xatosi baribir
    // yutiladi: u naqd xarajat uchungina kerak va xarajatlar jadvalini
    // bo'shatib qo'ymasligi shart (bo'sh ro'yxatda formada «ochiq smena
    // yo'q» ogohlantirishi chiqadi).
    const [rows, shifts] = await Promise.all([
      listExpenses(api, clubId).catch((cause: unknown) => {
        const message = errorText(cause);
        setLoadError(message);
        toast.error(message);
        return null;
      }),
      listOpenShifts(api, clubId).catch(() => []),
    ]);
    if (rows !== null) setExpenses(rows);
    setOpenShifts(shifts);
    setLoading(false);
  }, [clubId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  // LocalStorage'dan bazaga ko'chirish — "hech qachon qo'shilgan ma'lumot
  // yo'qolmasligi kerak" talabi (loyiha egasi, 2026-08-16). Faqat
  // FOYDALANUVCHI qo'shgan/tahrirlagan qatorlar (`isUntouchedSeed` orqali
  // soxta seed'dan ajratiladi). Har bir qator ID'si ALOHIDA "ko'chirildi"
  // deb belgilanadi (bitta umumiy bayroq EMAS) — sahifa ko'chirish
  // yarim yo'lda uzilib qolsa (foydalanuvchi yopib yuborsa), keyingi
  // ochilishda faqat QOLGAN qatorlar qayta urinadi, na takrorlanadi
  // (allaqachon ko'chirilganlar o'tkazib yuboriladi), na yo'qoladi.
  useEffect(() => {
    if (clubId === null || migrationClaimedThisLoad.has(clubId)) return;
    migrationClaimedThisLoad.add(clubId);

    const done = readMigratedIds();
    const legacy = useClub
      .getState()
      .expenses.filter((row) => !isUntouchedSeed(row) && !done.has(row.id));
    if (legacy.length === 0) return;

    // Effekt tozalovchisi (unmount) orqali BEKOR QILINMAYDI — StrictMode
    // dev rejimida React effektni sinxron mount→cleanup→qayta-mount
    // qiladi, bu YOLG'ON "bekor qilish" signalini berardi va tsiklni
    // yarim yo'lda to'xtatib, qolgan qatorlarni HECH QACHON ko'chirmay
    // qoldirardi (jonli sinovda TOPILGAN ikkinchi xato, 2026-08-16).
    // `migrationClaimedThisLoad` yuqorida allaqachon takroriy ishga
    // tushishning oldini oladi — shu yetarli, alohida bekor qilish shart
    // emas: bu bir martalik fon ko'chirish, komponent holatiga bog'liq
    // emas.
    void (async () => {
      let migrated = 0;
      let failed = 0;
      for (const row of legacy) {
        const spentOn = ddmmyyyyToIso(row.date);
        if (spentOn === null) {
          failed += 1;
          continue;
        }
        try {
          await createExpense(
            api,
            clubId,
            {
              spentOn,
              category: row.cat,
              amount: row.amount,
              note: row.note.trim() || null,
            },
            crypto.randomUUID(),
          );
          markMigrated(row.id);
          migrated += 1;
        } catch {
          failed += 1;
        }
      }
      if (migrated > 0) {
        toast.success(`${migrated} ta eski xarajat ko‘chirildi`);
        await reload();
      }
      if (failed > 0) {
        toast.error(`${failed} ta eski xarajatni ko‘chirib bo‘lmadi — qo‘lda tekshiring`);
      }
    })();
  }, [clubId, reload]);

  const activeExpenses = expenses.filter((row) => row.status === 'active');
  const total = activeExpenses.reduce((sum, row) => sum + row.amount, 0);
  const byCat = activeExpenses.reduce<Record<string, number>>((acc, row) => {
    acc[row.category] = (acc[row.category] ?? 0) + row.amount;
    return acc;
  }, {});
  const catRows = Object.entries(byCat).sort((a, b) => b[1] - a[1]);
  const biggest = catRows[0];
  const utilities = (byCat['Elektr'] ?? 0) + (byCat['Suv'] ?? 0) + (byCat['Internet'] ?? 0);

  const myStaffId = session?.userId ?? null;
  const myOpenShift = openShifts.find((shift) => shift.staffId === myStaffId) ?? null;
  const shiftChoices = shiftOptions(openShifts, myStaffId, t('expenseShiftMine'));

  const methodChoices: { key: DraftMethod; label: string }[] = [
    { key: '', label: t('payMethodNone') },
    { key: 'CASH', label: t('payMethodCash') },
    { key: 'TRANSFER', label: t('payMethodTransfer') },
  ];
  const methodLabel = (method: DraftMethod): string =>
    methodChoices.find((choice) => choice.key === method)?.label ?? t('payMethodNone');

  const submit = async (): Promise<void> => {
    if (!draft || clubId === null) return;
    const amount = Number(draft.amount);
    if (!draft.spentOn) {
      setError('Sanani tanlang');
      return;
    }
    if (!Number.isFinite(amount) || amount <= 0) {
      setError('Summa 0 dan katta bo‘lsin');
      return;
    }
    // Naqd pul kassadan chiqadi — server ochiq smenasiz qabul qilmaydi
    // (`409 SHIFT_REQUIRED`). So'rov sababsiz yuborilmaydi.
    if (draft.id === null && draft.method === 'CASH' && draft.shiftId === null) {
      setError(openShifts.length === 0 ? t('expenseNoOpenShift') : t('expenseShiftPick'));
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      if (draft.id === null) {
        await createExpense(
          api,
          clubId,
          {
            spentOn: draft.spentOn,
            category: draft.category,
            amount,
            note: draft.note.trim() || null,
            method: draft.method || null,
            shiftId: draft.method === 'CASH' ? draft.shiftId : null,
          },
          crypto.randomUUID(),
        );
        toast.success('Xarajat qo‘shildi');
      } else {
        await updateExpense(api, clubId, draft.id, {
          spentOn: draft.spentOn,
          category: draft.category,
          amount,
          note: draft.note.trim() || null,
          status: draft.status,
        });
        toast.success('Xarajat yangilandi');
      }
      setDraft(null);
      await reload();
    } catch (cause) {
      const message = expenseErrorText(cause, t);
      setError(message);
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  const toggleArchive = async (row: ExpenseDto): Promise<void> => {
    if (clubId === null) return;
    try {
      await updateExpense(api, clubId, row.id, {
        spentOn: row.spentOn,
        category: row.category,
        amount: row.amount,
        note: row.note,
        status: row.status === 'active' ? 'archived' : 'active',
      });
      toast.success(row.status === 'active' ? 'Arxivlandi' : 'Qayta tiklandi');
      await reload();
    } catch (cause) {
      toast.error(errorText(cause));
    }
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
        <StatTile label="Yozuvlar" value={String(activeExpenses.length)} unit="ta" icon="receipt_long" />
      </div>

      <Modal
        open={draft !== null}
        onClose={() => {
          setDraft(null);
          setError(null);
        }}
        title={draft?.id === null ? 'Xarajat qo‘shish' : 'Xarajatni tahrirlash'}
        variant="drawer"
      >
        {draft ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
            <FormGrid>
              <TextField
                label="Sana"
                type="date"
                value={draft.spentOn}
                onChange={(value) => setDraft({ ...draft, spentOn: value })}
                icon="event"
              />
              <Labeled label="Modda">
                <Select
                  value={draft.category}
                  items={[...new Set([draft.category, ...EXPENSE_CATS])]}
                  onChange={(value) => setDraft({ ...draft, category: value })}
                  style={{ width: '100%' }}
                />
              </Labeled>
              <TextField
                label="Summa"
                value={draft.amount}
                onChange={(value) => setDraft({ ...draft, amount: value })}
                icon="payments"
                inputMode="numeric"
                placeholder="250 000"
              />
              <TextField
                label="Izoh"
                value={draft.note}
                onChange={(value) => setDraft({ ...draft, note: value })}
                icon="notes"
                placeholder="Ixtiyoriy izoh"
                onSubmitKey={() => void submit()}
              />

              {draft.id === null ? (
                <Labeled label={t('payMethodLabel')}>
                  <Select
                    value={methodLabel(draft.method)}
                    items={methodChoices.map((choice) => choice.label)}
                    onChange={(label) => {
                      const picked =
                        methodChoices.find((choice) => choice.label === label)?.key ?? '';
                      setDraft({
                        ...draft,
                        method: picked,
                        // Sukut bo'yicha yozayotganning O'Z ochiq smenasi;
                        // admin ro'yxatdan boshqasini tanlashi mumkin.
                        shiftId:
                          picked === 'CASH' ? (draft.shiftId ?? myOpenShift?.id ?? null) : null,
                      });
                    }}
                    style={{ width: '100%' }}
                  />
                </Labeled>
              ) : (
                <Labeled label={t('payMethodLabel')}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 'var(--gap-tight)' }}>
                    <Tag tone={draft.method === 'CASH' ? 'amber' : 'neutral'}>
                      {methodLabel(draft.method)}
                    </Tag>
                    <span style={{ font: 'var(--type-body-sm)', color: 'var(--text-muted)' }}>
                      {t('expenseMethodLocked')}
                    </span>
                  </span>
                </Labeled>
              )}

              {draft.id === null && draft.method === 'CASH' ? (
                shiftChoices.length === 0 ? (
                  <StatusLine tone="warn" icon="warning" parts={[t('expenseNoOpenShift')]} />
                ) : (
                  <Labeled label={t('expenseShiftLabel')}>
                    <Select
                      value={
                        shiftChoices.find((choice) => choice.id === draft.shiftId)?.label ??
                        t('expenseShiftUnset')
                      }
                      items={shiftChoices.map((choice) => choice.label)}
                      onChange={(label) => {
                        const picked = shiftChoices.find((choice) => choice.label === label);
                        setDraft({ ...draft, shiftId: picked?.id ?? null });
                      }}
                      style={{ width: '100%' }}
                    />
                  </Labeled>
                )
              ) : null}
            </FormGrid>

            {draft.id === null && draft.method === 'CASH' ? (
              <StatusLine tone="neutral" icon="savings" parts={[t('expenseCashNote')]} />
            ) : null}

            {error ? <StatusLine tone="danger" icon="error" parts={error} /> : null}

            <div style={{ display: 'flex', gap: 'var(--gap-tight)', flexWrap: 'wrap' }}>
              <Button
                variant="primary"
                notch
                icon="check"
                disabled={submitting}
                onClick={() => void submit()}
              >
                {submitting ? 'Saqlanmoqda…' : 'Saqlash'}
              </Button>
              <Button
                variant="ghost"
                disabled={submitting}
                onClick={() => {
                  setDraft(null);
                  setError(null);
                }}
              >
                Bekor
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>

      <div className="ds-split" style={{ alignItems: 'start' }}>
        <Panel
          title={`Xarajatlar (${expenses.length})`}
          notch
          brackets
          action={
            <Button
              variant="primary"
              size="sm"
              icon="add"
              onClick={() => {
                setError(null);
                setDraft(EMPTY_DRAFT);
              }}
            >
              Xarajat qo‘shish
            </Button>
          }
        >
          {loadError ? <StatusLine tone="danger" icon="error" parts={[loadError]} /> : null}

          <EntityTable
            rows={expenses}
            rowKey={(row) => String(row.id)}
            empty={loading ? 'Yuklanmoqda…' : 'Xarajat kiritilmagan'}
            columns={[
              {
                key: 'date',
                header: 'Sana',
                render: (row) => (
                  <span style={{ font: 'var(--type-data)', whiteSpace: 'nowrap' }}>
                    {row.spentOn}
                  </span>
                ),
              },
              {
                key: 'cat',
                header: 'Modda',
                render: (row) => <span style={{ color: 'var(--text-title)' }}>{row.category}</span>,
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
                key: 'method',
                header: t('payMethodLabel'),
                render: (row) => (
                  <Tag
                    tone={row.method === 'CASH' ? 'amber' : 'neutral'}
                    icon={
                      row.method === 'CASH'
                        ? 'payments'
                        : row.method === 'TRANSFER'
                          ? 'account_balance'
                          : 'remove'
                    }
                  >
                    {methodLabel(row.method ?? '')}
                  </Tag>
                ),
              },
              {
                key: 'status',
                header: 'Holat',
                render: (row) => (
                  <Tag tone={row.status === 'active' ? 'success' : 'neutral'}>
                    {row.status === 'active' ? 'Faol' : 'Arxiv'}
                  </Tag>
                ),
              },
              {
                key: 'actions',
                header: '',
                align: 'right',
                render: (row) => (
                  <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                    <Button
                      variant="ghost"
                      size="sm"
                      icon="edit"
                      onClick={() => {
                        setError(null);
                        setDraft({
                          id: row.id,
                          spentOn: row.spentOn,
                          category: row.category,
                          amount: String(row.amount),
                          note: row.note ?? '',
                          status: row.status,
                          method: row.method ?? '',
                          shiftId: null,
                        });
                      }}
                    />
                    <Button
                      variant="ghost"
                      size="sm"
                      icon={row.status === 'active' ? 'archive' : 'unarchive'}
                      onClick={() => void toggleArchive(row)}
                    />
                  </div>
                ),
              },
            ]}
          />
        </Panel>

        <Panel title="Moddalar bo‘yicha" notch>
          {catRows.length === 0 ? (
            <StatusLine
              tone="neutral"
              icon="pie_chart"
              parts={[loading ? 'Yuklanmoqda…' : 'Xarajat kiritilmagan']}
            />
          ) : (
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
          )}

          <div style={{ marginTop: 'var(--gap-panel)' }}>
            <StatusLine
              tone="neutral"
              icon="insights"
              parts={['Xarajatlar hisobotdagi foydadan ayiriladi', 'Faqat faol yozuvlar hisoblanadi']}
            />
          </div>
        </Panel>
      </div>
    </div>
  );
}
