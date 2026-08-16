import {
  createStaffMember,
  deactivateStaffMember,
  errorText,
  listStaffMembers,
  updateStaffMember,
  type StaffMemberDto,
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

import { api } from '../../lib/api';
import { useSession } from '../../store/session';
import { Labeled } from './parts';

const ROLE_LABEL: Record<string, string> = { OWNER: 'Egasi', ADMIN: 'Admin', STAFF: 'Xodim' };

/**
 * 12+ belgili tasodifiy boshlang'ich parol — server MIN_LENGTH (12) bilan mos.
 * `Math.random()` emas — `crypto.getRandomValues()` (loyihada `Math.random`
 * cheklangan, deterministik bo'lmagan qiymat sinovlarni buzadi).
 */
function randomPassword(): string {
  const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789';
  const bytes = new Uint32Array(14);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (n) => alphabet[n % alphabet.length]).join('');
}

interface Draft {
  firstName: string;
  login: string;
  password: string;
  role: 'ADMIN' | 'STAFF';
}

const EMPTY_DRAFT: Draft = { firstName: '', login: '', password: randomPassword(), role: 'STAFF' };

interface EditDraft {
  userId: number;
  firstName: string;
  role: 'ADMIN' | 'STAFF';
}

/** Xodimlar — hisob ochish va rol berish (`POST /clubs/{id}/staff`). */
export function StaffScreen(): ReactNode {
  const session = useSession((state) => state.session);
  const clubId = session?.clubs[0]?.id ?? null;
  // Faol klubdagi CHAQIRUVCHI roli — ADMIN o'ziga teng (ADMIN) rol bera
  // olmaydi, server ham shuni majburlaydi (`ROLE_NOT_ALLOWED`)
  const callerRole = session?.clubs.find((c) => c.id === clubId)?.role ?? 'STAFF';
  const roleOptions: Array<'ADMIN' | 'STAFF'> =
    callerRole === 'OWNER' ? ['ADMIN', 'STAFF'] : ['STAFF'];

  const [staff, setStaff] = useState<StaffMemberDto[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [draft, setDraft] = useState<Draft | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [created, setCreated] = useState<{ login: string; password: string } | null>(null);

  const [editDraft, setEditDraft] = useState<EditDraft | null>(null);
  const [editError, setEditError] = useState<string | null>(null);
  const [editSubmitting, setEditSubmitting] = useState(false);

  // Ikki bosqichli tasdiq — bitta bosishda chiqarib yubormaslik uchun
  // (`settings.tsx::AccountTab`dagi "boshlang'ich holatga qaytarish" bilan
  // bir xil naqsh).
  const [confirmRemoveId, setConfirmRemoveId] = useState<number | null>(null);
  const [removingId, setRemovingId] = useState<number | null>(null);

  const reload = useCallback(async (): Promise<void> => {
    if (clubId === null) return;
    setLoading(true);
    setLoadError(null);
    try {
      setStaff(await listStaffMembers(api, clubId));
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

  const submit = async (): Promise<void> => {
    if (!draft || clubId === null) return;
    if (draft.firstName.trim().length < 2) {
      setError('Ismni to‘liq kiriting');
      return;
    }
    if (!/^[a-z0-9._-]{3,32}$/.test(draft.login.trim())) {
      setError('Login faqat kichik lotin harf, raqam, nuqta, pastki chiziq (3–32 belgi)');
      return;
    }
    if (draft.password.length < 12) {
      setError('Parol kamida 12 belgi bo‘lsin');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const result = await createStaffMember(api, clubId, {
        firstName: draft.firstName.trim(),
        login: draft.login.trim().toLowerCase(),
        password: draft.password,
        role: draft.role,
      });
      setCreated({ login: result.login, password: draft.password });
      setDraft(null);
      toast.success(`Xodim yaratildi — ${result.login}`);
      await reload();
    } catch (cause) {
      const message = errorText(cause);
      setError(message);
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  // Server rol shiftini `auth_update_staff()` ICHIDA majburlaydi
  // (`0019_staff_update.py`) — bu yerdagi tekshiruv faqat "Tahrirlash"
  // tugmasini noto'g'ri qatorda umuman ko'rsatmaslik uchun, HAKAM emas.
  const canEdit = (row: StaffMemberDto): boolean => {
    if (row.role === 'OWNER') return false;
    if (callerRole === 'ADMIN' && row.role !== 'STAFF') return false;
    return true;
  };

  const submitEdit = async (): Promise<void> => {
    if (!editDraft || clubId === null) return;
    if (editDraft.firstName.trim().length < 2) {
      setEditError('Ismni to‘liq kiriting');
      return;
    }

    setEditSubmitting(true);
    setEditError(null);
    try {
      await updateStaffMember(api, clubId, editDraft.userId, {
        firstName: editDraft.firstName.trim(),
        role: editDraft.role,
      });
      setEditDraft(null);
      toast.success('Xodim yangilandi');
      await reload();
    } catch (cause) {
      const message = errorText(cause);
      setEditError(message);
      toast.error(message);
    } finally {
      setEditSubmitting(false);
    }
  };

  // RLS'ning o'zi (`memberships_write_owner`/`_admin`, `0007`) shu ceilingni
  // majburlaydi — bu yerdagi tekshiruv ham faqat tugmani yashirish uchun.
  // O'z-o'zini chiqarib yuborish alohida server tekshiruvi bilan bloklangan
  // (`SELF_DEACTIVATE_FORBIDDEN`), shu yerda ham oldindan yashiriladi.
  const canRemove = (row: StaffMemberDto): boolean => {
    if (row.userId === session?.userId) return false;
    return canEdit(row);
  };

  const remove = async (userId: number): Promise<void> => {
    if (clubId === null) return;
    setRemovingId(userId);
    try {
      await deactivateStaffMember(api, clubId, userId);
      setConfirmRemoveId(null);
      toast.success('Xodim chiqarildi');
      await reload();
    } catch (cause) {
      toast.error(errorText(cause));
    } finally {
      setRemovingId(null);
    }
  };

  const activeCount = staff.filter((s) => s.status === 'active').length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <div className="pb-tiles-4">
        <StatTile label="Xodimlar" value={String(staff.length)} unit="ta" icon="group" />
        <StatTile label="Faol" value={String(activeCount)} unit="ta" icon="badge" />
      </div>

      {created ? (
        <Panel title="Hisob yaratildi" notch glow>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
            <StatusLine
              tone="warn"
              icon="key"
              parts={['Bu parol faqat SHU YERDA ko‘rinadi', 'Xodimga hozir bering']}
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
        open={draft !== null}
        onClose={() => {
          setDraft(null);
          setError(null);
        }}
        title="Xodim qo‘shish"
        variant="drawer"
      >
        {draft ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
            <TextField
              label="Ism"
              value={draft.firstName}
              onChange={(value) => setDraft({ ...draft, firstName: value })}
              icon="person"
              placeholder="Aziz Karimov"
            />
            <TextField
              label="Login"
              value={draft.login}
              onChange={(value) => setDraft({ ...draft, login: value })}
              icon="key"
              placeholder="aziz.kassa"
            />
            <TextField
              label="Boshlang‘ich parol"
              value={draft.password}
              onChange={(value) => setDraft({ ...draft, password: value })}
              icon="lock"
            />
            <Labeled label="Rol">
              <Select
                value={ROLE_LABEL[draft.role] ?? draft.role}
                items={roleOptions.map((r) => ROLE_LABEL[r] as string)}
                onChange={(label) => {
                  const role = roleOptions.find((r) => ROLE_LABEL[r] === label);
                  if (role) setDraft({ ...draft, role });
                }}
                style={{ width: '100%' }}
              />
            </Labeled>

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

      <Modal
        open={editDraft !== null}
        onClose={() => {
          setEditDraft(null);
          setEditError(null);
        }}
        title="Xodimni tahrirlash"
        variant="drawer"
      >
        {editDraft ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
            <TextField
              label="Ism"
              value={editDraft.firstName}
              onChange={(value) => setEditDraft({ ...editDraft, firstName: value })}
              icon="person"
              placeholder="Aziz Karimov"
            />
            <Labeled label="Rol">
              <Select
                value={ROLE_LABEL[editDraft.role] ?? editDraft.role}
                items={roleOptions.map((r) => ROLE_LABEL[r] as string)}
                onChange={(label) => {
                  const role = roleOptions.find((r) => ROLE_LABEL[r] === label);
                  if (role) setEditDraft({ ...editDraft, role });
                }}
                style={{ width: '100%' }}
              />
            </Labeled>

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
        title={`Xodimlar (${staff.length})`}
        notch
        brackets
        action={
          <Button
            variant="primary"
            size="sm"
            icon="person_add"
            onClick={() => {
              setCreated(null);
              setError(null);
              setDraft({ ...EMPTY_DRAFT, password: randomPassword() });
            }}
          >
            Qo‘shish
          </Button>
        }
      >
        {loadError ? <StatusLine tone="danger" icon="error" parts={[loadError]} /> : null}

        <EntityTable
          rows={staff}
          rowKey={(row) => String(row.userId)}
          empty={loading ? 'Yuklanmoqda…' : 'Xodim qo‘shilmagan'}
          columns={[
            {
              key: 'name',
              header: 'Xodim',
              render: (row) => <span style={{ color: 'var(--text-title)' }}>{row.firstName}</span>,
            },
            {
              key: 'login',
              header: 'Login',
              render: (row) => (
                <span style={{ font: 'var(--type-data)', color: 'var(--purple-100)' }}>
                  {row.login}
                </span>
              ),
            },
            {
              key: 'role',
              header: 'Rol',
              render: (row) => (
                <Tag tone={row.role === 'OWNER' ? 'violet' : 'neutral'}>
                  {ROLE_LABEL[row.role] ?? row.role}
                </Tag>
              ),
            },
            {
              key: 'actions',
              header: '',
              align: 'right',
              render: (row) => {
                if (confirmRemoveId === row.userId) {
                  return (
                    <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                      <Button
                        variant="danger"
                        size="sm"
                        disabled={removingId === row.userId}
                        onClick={() => void remove(row.userId)}
                      >
                        {removingId === row.userId ? 'Chiqarilmoqda…' : 'Tasdiqlash'}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={removingId === row.userId}
                        onClick={() => setConfirmRemoveId(null)}
                      >
                        Bekor
                      </Button>
                    </div>
                  );
                }
                return (
                  <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                    {canEdit(row) ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        icon="edit"
                        onClick={() => {
                          setEditError(null);
                          setEditDraft({
                            userId: row.userId,
                            firstName: row.firstName,
                            role: row.role === 'ADMIN' ? 'ADMIN' : 'STAFF',
                          });
                        }}
                      />
                    ) : null}
                    {canRemove(row) ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        icon="person_remove"
                        onClick={() => setConfirmRemoveId(row.userId)}
                      />
                    ) : null}
                  </div>
                );
              },
            },
          ]}
        />
      </Panel>

      <StatusLine
        tone="neutral"
        icon="info"
        parts={[
          'Login yaratilgach xodim konsolga o‘z hisobi bilan kiradi',
          'Birinchi kirishda parolni almashtirishi shart',
        ]}
      />
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
