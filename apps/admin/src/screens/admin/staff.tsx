import { Button, EntityTable, Panel, Select, StatTile, StatusLine, Tag, TextField } from '@playbron/ui';
import { useState, type ReactNode } from 'react';

import { SHIFTS, STAFF_STATUS, type StaffMember, type StaffStatus } from '../../mock/club';
import { S } from '../../mock/data';
import { nextId, useClub } from '../../store/club';
import { FormGrid, Labeled, RowActions } from './parts';

const STATUS_ITEMS = Object.values(STAFF_STATUS).map((value) => value.label);
const STATUS_BY_LABEL = Object.fromEntries(
  Object.entries(STAFF_STATUS).map(([key, value]) => [value.label, key as StaffStatus]),
);

const FULL: React.CSSProperties = { width: '100%' };

const EMPTY: StaffMember = {
  id: '',
  name: '',
  phone: '+998',
  login: '',
  shift: SHIFTS[0] as string,
  status: 'ACTIVE',
  bills: 0,
  revenue: 0,
};

/** Xodimlar — ro'yxat, smenalar va kirish loginlari. */
export function StaffScreen(): ReactNode {
  const staff = useClub((state) => state.staff);
  const saveStaff = useClub((state) => state.saveStaff);
  const removeStaff = useClub((state) => state.removeStaff);

  const [draft, setDraft] = useState<StaffMember | null>(null);
  const [error, setError] = useState<string | null>(null);

  const totalRevenue = staff.reduce((sum, member) => sum + member.revenue, 0);
  const totalBills = staff.reduce((sum, member) => sum + member.bills, 0);
  const active = staff.filter((member) => member.status === 'ACTIVE').length;

  const submit = (): void => {
    if (!draft) return;
    if (draft.name.trim().length < 3) {
      setError('Ism-familiyani to‘liq kiriting');
      return;
    }
    if (!/^\+998\d{9}$/.test(draft.phone.replace(/[\s()-]/g, ''))) {
      setError('Telefon +998XXXXXXXXX shaklida bo‘lishi kerak');
      return;
    }
    if (draft.login.trim().length < 3) {
      setError('Login kamida 3 belgi bo‘lishi kerak');
      return;
    }
    if (
      staff.some(
        (member) => member.login === draft.login.trim().toLowerCase() && member.id !== draft.id,
      )
    ) {
      setError('Bu login band');
      return;
    }

    saveStaff({
      ...draft,
      id: draft.id || nextId('s'),
      name: draft.name.trim(),
      phone: draft.phone.replace(/[\s()-]/g, ''),
      login: draft.login.trim().toLowerCase(),
    });
    setDraft(null);
    setError(null);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <div className="pb-tiles-4">
        <StatTile label="Xodimlar" value={String(staff.length)} unit="ta" icon="group" />
        <StatTile label="Smenada" value={String(active)} unit="ta" icon="badge" />
        <StatTile label="Yopilgan hisob" value={String(totalBills)} unit="ta" icon="receipt_long" />
        <StatTile label="Kassa (oy)" value={S(totalRevenue)} unit="so‘m" icon="payments" />
      </div>

      <Panel
        title={`Xodimlar (${staff.length})`}
        notch
        brackets
        action={
          draft ? null : (
            <Button variant="primary" size="sm" icon="person_add" onClick={() => setDraft(EMPTY)}>
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
                label="Ism-familiya"
                value={draft.name}
                onChange={(value) => setDraft({ ...draft, name: value })}
                icon="person"
              />
              <TextField
                label="Telefon"
                value={draft.phone}
                onChange={(value) => setDraft({ ...draft, phone: value })}
                icon="call"
                inputMode="tel"
              />
              <TextField
                label="Login"
                value={draft.login}
                onChange={(value) => setDraft({ ...draft, login: value })}
                icon="key"
              />
              <Labeled label="Smena">
                <Select
                  value={draft.shift}
                  items={SHIFTS}
                  onChange={(value) => setDraft({ ...draft, shift: value })}
                  style={FULL}
                />
              </Labeled>
              <Labeled label="Holat">
                <Select
                  value={STAFF_STATUS[draft.status].label}
                  items={STATUS_ITEMS}
                  onChange={(value) =>
                    setDraft({ ...draft, status: STATUS_BY_LABEL[value] ?? 'ACTIVE' })
                  }
                  style={FULL}
                />
              </Labeled>
            </FormGrid>

            {error ? <StatusLine tone="danger" icon="error" parts={error} /> : null}

            <div style={{ display: 'flex', gap: 'var(--gap-tight)', flexWrap: 'wrap' }}>
              <Button variant="primary" notch icon="check" onClick={submit}>
                Saqlash
              </Button>
              <Button
                variant="ghost"
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

        <EntityTable
          rows={staff}
          rowKey={(row) => row.id}
          empty="Xodim qo‘shilmagan"
          columns={[
            {
              key: 'name',
              header: 'Xodim',
              render: (row) => (
                <span style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
                  <span style={{ color: 'var(--text-title)' }}>{row.name}</span>
                  <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                    {row.phone}
                  </span>
                </span>
              ),
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
            { key: 'shift', header: 'Smena', render: (row) => row.shift },
            {
              key: 'status',
              header: 'Holat',
              render: (row) => (
                <Tag
                  tone={
                    row.status === 'ACTIVE' ? 'ok' : row.status === 'BLOCKED' ? 'danger' : 'neutral'
                  }
                >
                  {STAFF_STATUS[row.status].label}
                </Tag>
              ),
            },
            {
              key: 'bills',
              header: 'Hisob',
              align: 'right',
              render: (row) => <span style={{ font: 'var(--type-data)' }}>{row.bills}</span>,
            },
            {
              key: 'revenue',
              header: 'Kassa',
              align: 'right',
              render: (row) => (
                <span
                  style={{ font: 'var(--type-data)', color: 'var(--text-title)', whiteSpace: 'nowrap' }}
                >
                  {S(row.revenue)}
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
                  onRemove={() => removeStaff(row.id)}
                />
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
          'Sessiya 24 soatda tugaydi',
        ]}
      />
    </div>
  );
}
