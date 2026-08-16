import {
  createPlatformOrg,
  errorText,
  listPlatformOrgs,
  recordPlatformPayment,
  updatePlatformOrg,
  type PlatformOrgDto,
  type PlatformOrgStatus,
} from '@playbron/api-client';
import {
  Button,
  EntityTable,
  Modal,
  Panel,
  Select,
  StatTile,
  StatusLine,
  Tag,
  TextField,
  toast,
} from '@playbron/ui';
import { useCallback, useEffect, useState, type ReactNode } from 'react';

import { api } from '../lib/api';
import { S } from '../mock/data';
import { FormGrid, Labeled } from './admin/parts';

/**
 * 16+ belgili tasodifiy boshlang'ich parol — server MIN_LENGTH (14) dan
 * yuqori zaxira bilan. `Math.random()` emas — `crypto.getRandomValues()`
 * (loyihada `Math.random` cheklangan, deterministik bo'lmagan qiymat
 * sinovlarni buzadi).
 */
function randomPassword(): string {
  const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789';
  const bytes = new Uint32Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (n) => alphabet[n % alphabet.length]).join('');
}

const PLAN_LABELS: string[] = ['Yo‘q', 'Gold', 'Platinium', 'Infinite'];
const PLAN_CODES: Array<string | null> = [null, 'gold', 'platinium', 'infinite'];
const PLAN_DISPLAY: Record<string, string> = {
  gold: 'Gold',
  platinium: 'Platinium',
  infinite: 'Infinite',
};

function planSelectLabel(code: string | null): string {
  const idx = PLAN_CODES.indexOf(code);
  return (idx >= 0 ? PLAN_LABELS[idx] : undefined) ?? PLAN_LABELS[0] ?? 'Yo‘q';
}

/** `bookings.tsx::formatClock` bilan bir xil naqsh — kichik yordamchi, alohida modul emas. */
function formatExpiry(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('uz-UZ', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

interface CreateDraft {
  firstName: string;
  clubName: string;
  phone: string;
  address: string;
  login: string;
  password: string;
}

const EMPTY_CREATE_DRAFT: CreateDraft = {
  firstName: '',
  clubName: '',
  phone: '',
  address: '',
  login: '',
  password: '',
};

interface PaymentDraft {
  amount: string;
  planCode: string | null;
  periodMonths: string;
  note: string;
}

const EMPTY_PAYMENT_DRAFT: PaymentDraft = { amount: '', planCode: null, periodMonths: '', note: '' };

interface EditDraft {
  orgId: number;
  name: string;
  status: PlatformOrgStatus;
}

const ORG_STATUS_LABELS: Record<PlatformOrgStatus, string> = {
  pending: 'Kutilmoqda',
  active: 'Faol',
  suspended: 'To‘xtatilgan',
};
const ORG_STATUS_OPTIONS: PlatformOrgStatus[] = ['pending', 'active', 'suspended'];

function orgStatusTone(status: string): 'success' | 'amber' | 'danger' | 'neutral' {
  if (status === 'active') return 'success';
  if (status === 'pending') return 'amber';
  if (status === 'suspended') return 'danger';
  return 'neutral';
}

/**
 * Platforma — Klublar: super admin uchun cross-tenant tashkilotlar ro'yxati.
 * Qo'lda klub+ega hisobi ochish (to'lov oqimi ishlamay qolganda yoki
 * avtomatik oqimdan tashqarida tarif sotib olinganda) va mavjud tashkilotga
 * qo'lda to'lov yozish (hali haqiqiy to'lov shlyuzi yo'q — bu daftar).
 * Manba: `0016_platform_org_admin.py`.
 */
export function PlatformClubsScreen(): ReactNode {
  const [orgs, setOrgs] = useState<PlatformOrgDto[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [createDraft, setCreateDraft] = useState<CreateDraft | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<{ login: string; password: string } | null>(null);

  const [selectedOrgId, setSelectedOrgId] = useState<number | null>(null);
  const [paymentDraft, setPaymentDraft] = useState<PaymentDraft>(EMPTY_PAYMENT_DRAFT);
  const [paymentError, setPaymentError] = useState<string | null>(null);
  const [payingSubmitting, setPayingSubmitting] = useState(false);

  const [editDraft, setEditDraft] = useState<EditDraft | null>(null);
  const [editError, setEditError] = useState<string | null>(null);
  const [editSubmitting, setEditSubmitting] = useState(false);

  const reload = useCallback(async (): Promise<void> => {
    setLoading(true);
    setLoadError(null);
    try {
      setOrgs(await listPlatformOrgs(api));
    } catch (cause) {
      const message = errorText(cause);
      setLoadError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const submitCreate = async (): Promise<void> => {
    if (!createDraft) return;
    if (createDraft.firstName.trim().length < 2) {
      setCreateError('Ismni to‘liq kiriting');
      return;
    }
    if (createDraft.clubName.trim().length < 2) {
      setCreateError('Klub nomini to‘liq kiriting');
      return;
    }
    if (!/^\+998\d{9}$/.test(createDraft.phone.trim())) {
      setCreateError('Telefon +998XXXXXXXXX shaklida bo‘lsin');
      return;
    }
    if (createDraft.address.trim().length < 3) {
      setCreateError('Manzilni kiriting');
      return;
    }
    if (!/^[a-z0-9._-]{3,32}$/.test(createDraft.login.trim())) {
      setCreateError('Login faqat kichik lotin harf, raqam, nuqta, pastki chiziq (3–32 belgi)');
      return;
    }
    if (createDraft.password.length < 14) {
      setCreateError('Parol kamida 14 belgi bo‘lsin');
      return;
    }

    setCreating(true);
    setCreateError(null);
    try {
      const result = await createPlatformOrg(api, {
        firstName: createDraft.firstName.trim(),
        clubName: createDraft.clubName.trim(),
        phone: createDraft.phone.trim(),
        address: createDraft.address.trim(),
        login: createDraft.login.trim().toLowerCase(),
        password: createDraft.password,
      });
      setCreated({ login: result.login, password: createDraft.password });
      setCreateDraft(null);
      toast.success(`Klub yaratildi — ${result.login}`);
      await reload();
    } catch (cause) {
      const message = errorText(cause);
      setCreateError(message);
      toast.error(message);
    } finally {
      setCreating(false);
    }
  };

  const submitPayment = async (): Promise<void> => {
    if (selectedOrgId === null) return;

    const amount = Number(paymentDraft.amount.trim());
    if (!Number.isInteger(amount) || amount <= 0) {
      setPaymentError('Summani butun va musbat son sifatida kiriting');
      return;
    }

    let periodMonths: number | null = null;
    if (paymentDraft.periodMonths.trim().length > 0) {
      const parsed = Number(paymentDraft.periodMonths.trim());
      if (!Number.isInteger(parsed) || parsed <= 0) {
        setPaymentError('Oy sonini butun va musbat son sifatida kiriting');
        return;
      }
      periodMonths = parsed;
    }

    setPayingSubmitting(true);
    setPaymentError(null);
    try {
      await recordPlatformPayment(api, selectedOrgId, {
        amount,
        planCode: paymentDraft.planCode,
        periodMonths,
        note: paymentDraft.note.trim().length > 0 ? paymentDraft.note.trim() : null,
      });
      toast.success('To‘lov qo‘shildi');
      setSelectedOrgId(null);
      await reload();
    } catch (cause) {
      const message = errorText(cause);
      setPaymentError(message);
      toast.error(message);
    } finally {
      setPayingSubmitting(false);
    }
  };

  const submitEdit = async (): Promise<void> => {
    if (!editDraft) return;
    if (editDraft.name.trim().length < 2) {
      setEditError('Nomni to‘liq kiriting');
      return;
    }

    setEditSubmitting(true);
    setEditError(null);
    try {
      await updatePlatformOrg(api, editDraft.orgId, {
        name: editDraft.name.trim(),
        status: editDraft.status,
      });
      toast.success('Tashkilot yangilandi');
      setEditDraft(null);
      await reload();
    } catch (cause) {
      const message = errorText(cause);
      setEditError(message);
      toast.error(message);
    } finally {
      setEditSubmitting(false);
    }
  };

  // Bir tashkilotning bir nechta klubi bo'lishi mumkin (`LEFT JOIN clubs`) —
  // `orgs` massivi klub QATORLARI, tashkilotlar EMAS. Sanashda `orgId`
  // bo'yicha noyoblashtiriladi, aks holda 2 klubli 1 tashkilot "2 ta" bo'lib
  // ko'rinardi.
  const uniqueOrgs = new Map(orgs.map((org) => [org.orgId, org]));
  const totalOrgs = uniqueOrgs.size;
  const activeOrgs = [...uniqueOrgs.values()].filter((org) => org.orgStatus === 'active').length;

  const parsedAmount = Number(paymentDraft.amount.trim());
  const amountValid =
    paymentDraft.amount.trim().length > 0 && Number.isInteger(parsedAmount) && parsedAmount > 0;
  const selectedOrg = orgs.find((org) => org.orgId === selectedOrgId) ?? null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <div className="pb-tiles-4">
        <StatTile label="Jami tashkilotlar" value={String(totalOrgs)} icon="corporate_fare" />
        <StatTile label="Faol tashkilotlar" value={String(activeOrgs)} icon="storefront" />
      </div>

      {created ? (
        <Panel title="Hisob yaratildi" notch glow>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
            <StatusLine
              tone="warn"
              icon="key"
              parts={['Bu parol faqat SHU YERDA ko‘rinadi', 'Klub egasiga hozir bering']}
            />
            <div style={{ display: 'flex', gap: 'var(--gap-tight)', flexWrap: 'wrap' }}>
              <FieldChip label="Login" value={created.login} />
              <FieldChip label="Parol" value={created.password} />
            </div>
            <Button variant="ghost" size="sm" onClick={() => setCreated(null)}>
              Yopish
            </Button>
          </div>
        </Panel>
      ) : null}

      <Modal
        open={createDraft !== null}
        onClose={() => {
          setCreateDraft(null);
          setCreateError(null);
        }}
        title="Klub qo‘shish"
        variant="drawer"
      >
        {createDraft ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
            <FormGrid>
              <TextField
                label="Ega ismi"
                value={createDraft.firstName}
                onChange={(value) => setCreateDraft({ ...createDraft, firstName: value })}
                icon="person"
              />
              <TextField
                label="Klub nomi"
                value={createDraft.clubName}
                onChange={(value) => setCreateDraft({ ...createDraft, clubName: value })}
                icon="storefront"
              />
              <TextField
                label="Telefon"
                value={createDraft.phone}
                onChange={(value) => setCreateDraft({ ...createDraft, phone: value })}
                icon="call"
                inputMode="tel"
                placeholder="+998901234567"
              />
              <TextField
                label="Manzil"
                value={createDraft.address}
                onChange={(value) => setCreateDraft({ ...createDraft, address: value })}
                icon="location_on"
              />
              <TextField
                label="Login"
                value={createDraft.login}
                onChange={(value) => setCreateDraft({ ...createDraft, login: value })}
                icon="key"
                placeholder="aziz.klub"
              />
              <TextField
                label="Boshlang‘ich parol"
                value={createDraft.password}
                onChange={(value) => setCreateDraft({ ...createDraft, password: value })}
                icon="lock"
                type="text"
              />
            </FormGrid>

            {createError ? <StatusLine tone="danger" icon="error" parts={createError} /> : null}

            <div style={{ display: 'flex', gap: 'var(--gap-tight)', flexWrap: 'wrap' }}>
              <Button
                variant="primary"
                notch
                icon="check"
                disabled={creating}
                onClick={() => void submitCreate()}
              >
                {creating ? 'Saqlanmoqda…' : 'Saqlash'}
              </Button>
              <Button
                variant="ghost"
                disabled={creating}
                onClick={() => {
                  setCreateDraft(null);
                  setCreateError(null);
                }}
              >
                Bekor
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>

      <Modal
        open={selectedOrgId !== null}
        onClose={() => {
          setSelectedOrgId(null);
          setPaymentError(null);
        }}
        title="To‘lov qo‘shish"
        variant="center"
      >
        {selectedOrgId !== null ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
            {selectedOrg ? (
              <StatusLine
                tone="neutral"
                icon="corporate_fare"
                parts={[selectedOrg.orgName, selectedOrg.clubName ?? '—']}
              />
            ) : null}

            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
                <TextField
                  label="Summa (so‘m)"
                  value={paymentDraft.amount}
                  onChange={(value) => setPaymentDraft({ ...paymentDraft, amount: value })}
                  icon="payments"
                  inputMode="numeric"
                  placeholder="1 250 000"
                />
                {/* Har doim joy band qilinadi (bo'sh bo'lsa ham) — aks holda
                    matn paydo bo'lganda qator balandligi o'zgarib, keyingi
                    maydon (Tarif) `FormGrid`ning `align-items: end`i bilan
                    pastga siljib, ustma-ust chiqib qolardi. */}
                <span
                  style={{
                    font: 'var(--type-data-xs)',
                    color: 'var(--text-dim)',
                    visibility: amountValid ? 'visible' : 'hidden',
                  }}
                >
                  {amountValid ? `${S(parsedAmount)} so‘m` : '—'}
                </span>
              </div>

              <FormGrid gap="var(--gap-panel)">
                <Labeled label="Tarif">
                  <Select
                    value={planSelectLabel(paymentDraft.planCode)}
                    items={PLAN_LABELS}
                    onChange={(label) => {
                      const idx = PLAN_LABELS.findIndex((item) => item === label);
                      if (idx >= 0) {
                        setPaymentDraft({ ...paymentDraft, planCode: PLAN_CODES[idx] ?? null });
                      }
                    }}
                    style={{ width: '100%' }}
                  />
                </Labeled>
                <TextField
                  label="Necha oy"
                  value={paymentDraft.periodMonths}
                  onChange={(value) => setPaymentDraft({ ...paymentDraft, periodMonths: value })}
                  icon="calendar_month"
                  inputMode="numeric"
                  placeholder="1"
                />
              </FormGrid>

              <TextField
                label="Izoh"
                value={paymentDraft.note}
                onChange={(value) => setPaymentDraft({ ...paymentDraft, note: value })}
                icon="edit_note"
                placeholder="Ixtiyoriy izoh"
              />
            </div>

            {paymentError ? <StatusLine tone="danger" icon="error" parts={paymentError} /> : null}

            <div style={{ display: 'flex', gap: 'var(--gap-tight)', flexWrap: 'wrap' }}>
              <Button
                variant="primary"
                notch
                icon="check"
                disabled={payingSubmitting}
                onClick={() => void submitPayment()}
              >
                {payingSubmitting ? 'Saqlanmoqda…' : 'Saqlash'}
              </Button>
              <Button
                variant="ghost"
                disabled={payingSubmitting}
                onClick={() => {
                  setSelectedOrgId(null);
                  setPaymentError(null);
                }}
              >
                Bekor
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>

      <Modal
        open={editDraft !== null}
        onClose={() => {
          setEditDraft(null);
          setEditError(null);
        }}
        title="Tashkilotni tahrirlash"
        variant="drawer"
      >
        {editDraft ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
            <TextField
              label="Tashkilot nomi"
              value={editDraft.name}
              onChange={(value) => setEditDraft({ ...editDraft, name: value })}
              icon="corporate_fare"
            />
            <Labeled label="Holat">
              <Select
                value={ORG_STATUS_LABELS[editDraft.status]}
                items={ORG_STATUS_OPTIONS.map((s) => ORG_STATUS_LABELS[s])}
                onChange={(label) => {
                  const status = ORG_STATUS_OPTIONS.find((s) => ORG_STATUS_LABELS[s] === label);
                  if (status) setEditDraft({ ...editDraft, status });
                }}
                style={{ width: '100%' }}
              />
            </Labeled>
            {editDraft.status === 'suspended' ? (
              <StatusLine
                tone="warn"
                icon="block"
                parts={['Hozircha faqat ko‘rsatish maqsadida', 'Kirish/bron avtomatik bloklanmaydi']}
              />
            ) : null}

            {editError ? <StatusLine tone="danger" icon="error" parts={editError} /> : null}

            <div style={{ display: 'flex', gap: 'var(--gap-tight)', flexWrap: 'wrap' }}>
              <Button
                variant="primary"
                notch
                icon="check"
                disabled={editSubmitting}
                onClick={() => void submitEdit()}
              >
                {editSubmitting ? 'Saqlanmoqda…' : 'Saqlash'}
              </Button>
              <Button
                variant="ghost"
                disabled={editSubmitting}
                onClick={() => {
                  setEditDraft(null);
                  setEditError(null);
                }}
              >
                Bekor
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>

      <Panel
        title={`Klublar (${orgs.length})`}
        notch
        brackets
        action={
          <Button
            variant="primary"
            size="sm"
            icon="add_business"
            onClick={() => {
              setCreated(null);
              setCreateError(null);
              setCreateDraft({ ...EMPTY_CREATE_DRAFT, password: randomPassword() });
            }}
          >
            Klub qo‘shish
          </Button>
        }
      >
        {loadError ? <StatusLine tone="danger" icon="error" parts={[loadError]} /> : null}

        <EntityTable
          rows={orgs}
          rowKey={(row) => String(row.orgId)}
          empty={loading ? 'Yuklanmoqda…' : 'Tashkilot topilmadi'}
          columns={[
            {
              key: 'club',
              header: 'Klub',
              render: (row) => (
                <span style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
                  <span style={{ color: 'var(--text-title)' }}>{row.clubName ?? '—'}</span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
                    <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                      {row.orgName}
                    </span>
                    <Tag tone={orgStatusTone(row.orgStatus)}>
                      {ORG_STATUS_LABELS[row.orgStatus as PlatformOrgStatus] ?? row.orgStatus}
                    </Tag>
                  </span>
                </span>
              ),
            },
            {
              key: 'owner',
              header: 'Ega',
              render: (row) => (
                <span style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
                  <span style={{ color: 'var(--text-title)' }}>{row.ownerName}</span>
                  <span style={{ font: 'var(--type-data)', color: 'var(--text-dim)' }}>
                    {row.ownerLogin ?? '—'}
                  </span>
                </span>
              ),
            },
            {
              key: 'status',
              header: 'Holat',
              render: (row) => (
                <Tag
                  tone={
                    row.clubStatus === 'active'
                      ? 'success'
                      : row.clubStatus === 'draft'
                        ? 'amber'
                        : 'neutral'
                  }
                >
                  {row.clubStatus === 'active'
                    ? 'Faol'
                    : row.clubStatus === 'draft'
                      ? 'Qoralama'
                      : '—'}
                </Tag>
              ),
            },
            {
              key: 'plan',
              header: 'Tarif',
              render: (row) => (
                <span style={{ font: 'var(--type-data)', color: 'var(--text-title)' }}>
                  {row.planCode ? (PLAN_DISPLAY[row.planCode] ?? row.planCode) : '—'}
                </span>
              ),
            },
            {
              key: 'expires',
              header: 'Amal qilish muddati',
              render: (row) => {
                if (!row.planExpiresAt) {
                  return <span style={{ color: 'var(--text-dim)' }}>—</span>;
                }
                const expired = new Date(row.planExpiresAt).getTime() < Date.now();
                return (
                  <Tag tone={expired ? 'danger' : 'neutral'}>
                    {expired ? 'Tugagan · ' : ''}
                    {formatExpiry(row.planExpiresAt)}
                  </Tag>
                );
              },
            },
            {
              key: 'stations',
              header: 'Stansiya',
              align: 'right',
              render: (row) => (
                <span style={{ font: 'var(--type-data)', color: 'var(--text-title)' }}>
                  {row.stationsCount}
                </span>
              ),
            },
            {
              key: 'bookings30d',
              header: '30 kun bron',
              align: 'right',
              render: (row) => (
                <span style={{ font: 'var(--type-data)', color: 'var(--text-title)' }}>
                  {row.bookings30d}
                </span>
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
                      setEditError(null);
                      setEditDraft({
                        orgId: row.orgId,
                        name: row.orgName,
                        status: (ORG_STATUS_OPTIONS as string[]).includes(row.orgStatus)
                          ? (row.orgStatus as PlatformOrgStatus)
                          : 'pending',
                      });
                    }}
                  />
                  <Button
                    variant="ghost"
                    size="sm"
                    icon="payments"
                    onClick={() => {
                      setSelectedOrgId(row.orgId);
                      setPaymentDraft(EMPTY_PAYMENT_DRAFT);
                      setPaymentError(null);
                    }}
                  >
                    To‘lov
                  </Button>
                </div>
              ),
            },
          ]}
        />
      </Panel>
    </div>
  );
}

function FieldChip({ label, value }: { label: string; value: string }): ReactNode {
  return (
    <div
      style={{
        padding: '6px 10px',
        background: 'var(--surface-inset)',
        border: '1px solid var(--line-1)',
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
      }}
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
      <span style={{ font: 'var(--type-data)', color: 'var(--text-title)' }}>{value}</span>
    </div>
  );
}
