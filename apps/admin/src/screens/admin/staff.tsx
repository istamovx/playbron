import {
  createStaffMember,
  errorText,
  listStaffMembers,
  type StaffMemberDto,
} from '@playbron/api-client';
import { Button, EntityTable, Panel, Select, StatTile, StatusLine, Tag, TextField } from '@playbron/ui';
import { useCallback, useEffect, useState, type ReactNode } from 'react';

import { api } from '../../lib/api';
import { useSession } from '../../store/session';
import { FormGrid, Labeled } from './parts';

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

/** Xodimlar — hisob ochish va rol berish (`POST /clubs/{id}/staff`). */
export function StaffScreen(): ReactNode {
  const session = useSession((state) => state.session);
  const clubId = session?.clubs[0]?.id ?? null;
  // Faol klubdagi CHAQIRUVCHI roli — ADMIN o'ziga teng (ADMIN) rol bera
  // olmaydi, server ham shuni majburlaydi (`ROLE_NOT_ALLOWED`)
  const callerRole = session?.clubs.find((c) => c.id === clubId)?.role ?? 'STAFF';
  const roleOptions: Array<'ADMIN' | 'STAFF'> = callerRole === 'OWNER' ? ['ADMIN', 'STAFF'] : ['STAFF'];

  const [staff, setStaff] = useState<StaffMemberDto[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [draft, setDraft] = useState<Draft | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [created, setCreated] = useState<{ login: string; password: string } | null>(null);

  const reload = useCallback(async (): Promise<void> => {
    if (clubId === null) return;
    setLoading(true);
    setLoadError(null);
    try {
      setStaff(await listStaffMembers(api, clubId));
    } catch (cause) {
      setLoadError(errorText(cause));
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
      await reload();
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setSubmitting(false);
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

      <Panel
        title={`Xodimlar (${staff.length})`}
        notch
        brackets
        action={
          draft ? null : (
            <Button
              variant="primary"
              size="sm"
              icon="person_add"
              onClick={() => {
                setCreated(null);
                setDraft({ ...EMPTY_DRAFT, password: randomPassword() });
              }}
            >
              Qo‘shish
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
                label="Ism"
                value={draft.firstName}
                onChange={(value) => setDraft({ ...draft, firstName: value })}
                icon="person"
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
            </FormGrid>

            {error ? <StatusLine tone="danger" icon="error" parts={error} /> : null}

            <div style={{ display: 'flex', gap: 'var(--gap-tight)', flexWrap: 'wrap' }}>
              <Button variant="primary" notch icon="check" disabled={submitting} onClick={() => void submit()}>
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
