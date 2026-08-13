import {
  Button,
  EntityTable,
  Icon,
  Panel,
  Select,
  StatusLine,
  Tabs,
  Tag,
  TextField,
} from '@playbron/ui';
import { useRef, useState, type CSSProperties, type ReactNode } from 'react';

import {
  CONSOLES,
  DEVICE_KIND,
  DEVICE_STATUS,
  ROOM_KINDS,
  consoleLabel,
  rateWith,
  type Device,
  type DeviceKind,
  type DeviceStatus,
  type Room,
  type Tariff,
} from '../../mock/club';
import { S } from '../../mock/data';
import { nextId, useClub } from '../../store/club';
import { FormGrid, Labeled, RowActions, hm, parseHm } from './parts';

const TABS = ['Umumiy', 'Tariflar', 'Xonalar', 'Qurilmalar'];

const FULL: CSSProperties = { width: '100%' };

/** Klub ma'lumoti — cover, manzil, tariflar, xonalar va qurilmalar CRUD. */
export function ClubInfoScreen(): ReactNode {
  const [tab, setTab] = useState(TABS[0] as string);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <div className="ds-scroll-x">
        <Tabs items={TABS} value={tab} onChange={setTab} />
      </div>

      {tab === 'Umumiy' ? <GeneralTab /> : null}
      {tab === 'Tariflar' ? <TariffsTab /> : null}
      {tab === 'Xonalar' ? <RoomsTab /> : null}
      {tab === 'Qurilmalar' ? <DevicesTab /> : null}
    </div>
  );
}

// ─────────────────────────── umumiy ───────────────────────────

const MAX_COVER = 1_500_000;

function GeneralTab(): ReactNode {
  const club = useClub((state) => state.club);
  const setClub = useClub((state) => state.setClub);
  const fileRef = useRef<HTMLInputElement>(null);

  const [opens, setOpens] = useState(hm(club.opensAt));
  const [closes, setCloses] = useState(hm(club.closesAt));
  const [error, setError] = useState<string | null>(null);

  const applyHours = (): void => {
    const from = parseHm(opens);
    const to = parseHm(closes);
    if (from === null || to === null) {
      setError('Vaqt HH:MM shaklida bo‘lishi kerak');
      return;
    }
    if (to <= from) {
      setError('Yopilish vaqti ochilishdan keyin bo‘lsin (tunda 26:00 gacha)');
      return;
    }
    setClub({ opensAt: from, closesAt: to });
    setError(null);
  };

  const pickCover = (file: File | undefined): void => {
    if (!file) return;
    if (file.size > MAX_COVER) {
      setError('Rasm 1.5 MB dan kichik bo‘lsin');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      setClub({ cover: String(reader.result) });
      setError(null);
    };
    reader.readAsDataURL(file);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <Panel title="Cover rasmi" notch brackets>
        <div
          style={{
            height: 180,
            background: club.cover
              ? `center/cover no-repeat url(${club.cover})`
              : 'var(--surface-inset)',
            border: '1px solid var(--line-1)',
            clipPath: 'var(--clip-tr)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: 'var(--gap-block)',
          }}
        >
          {club.cover ? null : (
            <span
              style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-dim)' }}
            >
              <Icon name="image" size={20} />
              <span style={{ font: 'var(--type-body-sm)' }}>Rasm tanlanmagan</span>
            </span>
          )}
        </div>

        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          hidden
          onChange={(event) => pickCover(event.target.files?.[0])}
        />

        <div style={{ display: 'flex', gap: 'var(--gap-tight)', flexWrap: 'wrap' }}>
          <Button variant="secondary" icon="upload" onClick={() => fileRef.current?.click()}>
            Rasm yuklash
          </Button>
          {club.cover ? (
            <Button variant="ghost" icon="delete" onClick={() => setClub({ cover: '' })}>
              O‘chirish
            </Button>
          ) : null}
        </div>
      </Panel>

      <Panel title="Asosiy ma’lumot" notch>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
          <FormGrid>
            <TextField
              label="Klub nomi"
              value={club.name}
              onChange={(value) => setClub({ name: value })}
              icon="storefront"
            />
            <TextField
              label="Telefon"
              value={club.phone}
              onChange={(value) => setClub({ phone: value })}
              icon="call"
              inputMode="tel"
            />
          </FormGrid>

          <TextField
            label="Manzil"
            value={club.address}
            onChange={(value) => setClub({ address: value })}
            icon="location_on"
          />

          <TextField
            label="Tavsif"
            value={club.about}
            onChange={(value) => setClub({ about: value })}
            icon="notes"
          />

          <FormGrid>
            <TextField label="Ochilish" value={opens} onChange={setOpens} icon="schedule" />
            <TextField
              label="Yopilish"
              value={closes}
              onChange={setCloses}
              icon="bedtime"
              onSubmitKey={applyHours}
            />
            <Button variant="secondary" icon="check" onClick={applyHours}>
              Vaqtni saqlash
            </Button>
          </FormGrid>

          {error ? <StatusLine tone="danger" icon="error" parts={error} /> : null}

          <StatusLine
            tone="neutral"
            icon="info"
            parts={[
              `Ish vaqti ${hm(club.opensAt)} – ${hm(club.closesAt)}`,
              'Yarim tundan keyingi vaqt 24:00 dan katta yoziladi',
            ]}
          />
        </div>
      </Panel>
    </div>
  );
}

// ─────────────────────────── tariflar ───────────────────────────

const EMPTY_TARIFF: Tariff = { id: '', label: '', from: 10 * 60, to: 18 * 60, factor: 1 };

function TariffsTab(): ReactNode {
  const tariffs = useClub((state) => state.tariffs);
  const saveTariff = useClub((state) => state.saveTariff);
  const removeTariff = useClub((state) => state.removeTariff);

  const [draft, setDraft] = useState<Tariff | null>(null);
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [factor, setFactor] = useState('1');
  const [error, setError] = useState<string | null>(null);

  const open = (tariff: Tariff): void => {
    setDraft(tariff);
    setFrom(hm(tariff.from));
    setTo(hm(tariff.to));
    setFactor(String(tariff.factor));
    setError(null);
  };

  const submit = (): void => {
    if (!draft) return;
    const start = parseHm(from);
    const end = parseHm(to);

    if (draft.label.trim().length < 2) {
      setError('Tarif nomini kiriting');
      return;
    }
    if (start === null || end === null || end <= start) {
      setError('Vaqt oynasi HH:MM va tugash boshlanishdan keyin bo‘lsin');
      return;
    }
    const value = Number(factor.replace(',', '.'));
    if (!Number.isFinite(value) || value <= 0 || value > 3) {
      setError('Koeffitsiyent 0 dan 3 gacha bo‘lsin');
      return;
    }

    saveTariff({
      ...draft,
      id: draft.id || nextId('t'),
      label: draft.label.trim(),
      from: start,
      to: end,
      factor: value,
    });
    setDraft(null);
    setError(null);
  };

  return (
    <Panel
      title={`Tariflar (${tariffs.length})`}
      notch
      brackets
      action={
        draft ? null : (
          <Button variant="primary" size="sm" icon="add" onClick={() => open(EMPTY_TARIFF)}>
            Tarif qo‘shish
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
              label="Nomi"
              value={draft.label}
              onChange={(value) => setDraft({ ...draft, label: value })}
              icon="sell"
            />
            <TextField label="Dan" value={from} onChange={setFrom} icon="schedule" />
            <TextField label="Gacha" value={to} onChange={setTo} icon="schedule" />
            <TextField
              label="Koeffitsiyent"
              value={factor}
              onChange={setFactor}
              icon="percent"
              inputMode="numeric"
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
        rows={tariffs}
        rowKey={(row) => row.id}
        empty="Tarif kiritilmagan"
        columns={[
          {
            key: 'label',
            header: 'Tarif',
            render: (row) => <span style={{ color: 'var(--text-title)' }}>{row.label}</span>,
          },
          {
            key: 'window',
            header: 'Vaqt oynasi',
            render: (row) => (
              <span style={{ font: 'var(--type-data)' }}>
                {hm(row.from)} – {hm(row.to)}
              </span>
            ),
          },
          {
            key: 'factor',
            header: 'Koeffitsiyent',
            align: 'right',
            render: (row) => (
              <span style={{ font: 'var(--type-data)', color: 'var(--purple-100)' }}>
                ×{row.factor}
              </span>
            ),
          },
          {
            key: 'actions',
            header: '',
            align: 'right',
            render: (row) => (
              <RowActions onEdit={() => open(row)} onRemove={() => removeTariff(row.id)} />
            ),
          },
        ]}
      />

      <div style={{ marginTop: 'var(--gap-block)' }}>
        <StatusLine
          tone="neutral"
          icon="calculate"
          parts={['Soatlik summa xonada belgilanadi', 'Tarif koeffitsiyenti shu summaga qo‘llanadi']}
        />
      </div>
    </Panel>
  );
}

// ─────────────────────────── xonalar ───────────────────────────

const EMPTY_ROOM: Room = {
  id: '',
  name: '',
  floor: 1,
  kind: ROOM_KINDS[0] as string,
  console: 'ps5',
  tv: 55,
  pads: 2,
  rate: 40000,
};

function RoomsTab(): ReactNode {
  const rooms = useClub((state) => state.rooms);
  const tariffs = useClub((state) => state.tariffs);
  const saveRoom = useClub((state) => state.saveRoom);
  const removeRoom = useClub((state) => state.removeRoom);

  const [draft, setDraft] = useState<Room | null>(null);
  const [error, setError] = useState<string | null>(null);

  const consoleItems = CONSOLES.map((item) => item.label);
  // Eng qimmat tarif — narx ustunida shu ko'rsatiladi
  const peak = tariffs.reduce<Tariff | null>(
    (best, row) => (best === null || row.factor > best.factor ? row : best),
    null,
  );

  const submit = (): void => {
    if (!draft) return;
    if (draft.name.trim().length < 1) {
      setError('Xona nomini kiriting');
      return;
    }
    if (rooms.some((room) => room.name === draft.name.trim() && room.id !== draft.id)) {
      setError('Bunday nomli xona bor');
      return;
    }
    if (draft.rate < 1000) {
      setError('Soatlik summa kamida 1 000 so‘m');
      return;
    }

    saveRoom({ ...draft, id: draft.id || nextId('r'), name: draft.name.trim() });
    setDraft(null);
    setError(null);
  };

  return (
    <Panel
      title={`Xonalar (${rooms.length})`}
      notch
      brackets
      action={
        draft ? null : (
          <Button variant="primary" size="sm" icon="add" onClick={() => setDraft(EMPTY_ROOM)}>
            Xona qo‘shish
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
              label="Nomi"
              value={draft.name}
              onChange={(value) => setDraft({ ...draft, name: value })}
              icon="meeting_room"
            />
            <TextField
              label="Qavat"
              value={String(draft.floor)}
              onChange={(value) => setDraft({ ...draft, floor: Math.max(1, Number(value) || 1) })}
              icon="stairs"
              inputMode="numeric"
            />
            <Labeled label="Turi">
              <Select
                value={draft.kind}
                items={ROOM_KINDS}
                onChange={(value) => setDraft({ ...draft, kind: value })}
                style={FULL}
              />
            </Labeled>
            <Labeled label="Konsol">
              <Select
                value={consoleLabel(draft.console)}
                items={consoleItems}
                onChange={(value) =>
                  setDraft({
                    ...draft,
                    console: CONSOLES.find((item) => item.label === value)?.id ?? draft.console,
                  })
                }
                style={FULL}
              />
            </Labeled>
            <TextField
              label="Ekran (dyuym)"
              value={String(draft.tv)}
              onChange={(value) => setDraft({ ...draft, tv: Number(value) || 0 })}
              icon="tv"
              inputMode="numeric"
            />
            <TextField
              label="Joystik"
              value={String(draft.pads)}
              onChange={(value) => setDraft({ ...draft, pads: Number(value) || 0 })}
              icon="sports_esports"
              inputMode="numeric"
            />
            <TextField
              label="Soatlik summa"
              value={String(draft.rate)}
              onChange={(value) => setDraft({ ...draft, rate: Number(value) || 0 })}
              icon="payments"
              inputMode="numeric"
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
        rows={rooms}
        rowKey={(row) => row.id}
        empty="Xona kiritilmagan"
        columns={[
          {
            key: 'name',
            header: 'Xona',
            render: (row) => (
              <span style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
                <span style={{ color: 'var(--text-title)' }}>{row.name}</span>
                <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                  {row.floor}-qavat · {row.kind}
                </span>
              </span>
            ),
          },
          {
            key: 'spec',
            header: 'Jihoz',
            render: (row) => (
              <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-muted)' }}>
                {consoleLabel(row.console)} · {row.tv}" · {row.pads} pad
              </span>
            ),
          },
          {
            key: 'rate',
            header: 'Soatlik',
            align: 'right',
            render: (row) => (
              <span
                style={{ font: 'var(--type-data)', color: 'var(--text-title)', whiteSpace: 'nowrap' }}
              >
                {S(row.rate)}
              </span>
            ),
          },
          {
            key: 'peak',
            header: peak ? `Peak · ${peak.label}` : 'Peak',
            align: 'right',
            render: (row) => (
              <span
                style={{ font: 'var(--type-data)', color: 'var(--purple-100)', whiteSpace: 'nowrap' }}
              >
                {peak ? S(rateWith(row, peak)) : '—'}
              </span>
            ),
          },
          {
            key: 'actions',
            header: '',
            align: 'right',
            render: (row) => (
              <RowActions onEdit={() => setDraft(row)} onRemove={() => removeRoom(row.id)} />
            ),
          },
        ]}
      />
    </Panel>
  );
}

// ─────────────────────────── qurilmalar ───────────────────────────

const KIND_ITEMS = Object.values(DEVICE_KIND);
const KIND_BY_LABEL = Object.fromEntries(
  Object.entries(DEVICE_KIND).map(([key, label]) => [label, key as DeviceKind]),
);
const DSTATUS_ITEMS = Object.values(DEVICE_STATUS).map((item) => item.label);
const DSTATUS_BY_LABEL = Object.fromEntries(
  Object.entries(DEVICE_STATUS).map(([key, value]) => [value.label, key as DeviceStatus]),
);

const EMPTY_DEVICE: Device = {
  id: '',
  kind: 'console',
  model: 'ps5',
  serial: '',
  roomId: '',
  status: 'OK',
};

const NO_ROOM = 'Biriktirilmagan';

function DevicesTab(): ReactNode {
  const devices = useClub((state) => state.devices);
  const rooms = useClub((state) => state.rooms);
  const saveDevice = useClub((state) => state.saveDevice);
  const removeDevice = useClub((state) => state.removeDevice);

  const [draft, setDraft] = useState<Device | null>(null);
  const [error, setError] = useState<string | null>(null);

  const roomItems = [NO_ROOM, ...rooms.map((room) => room.name)];
  const roomName = (id: string): string => rooms.find((room) => room.id === id)?.name ?? NO_ROOM;
  const modelText = (device: Device): string =>
    device.kind === 'console' ? consoleLabel(device.model) : device.model;

  const submit = (): void => {
    if (!draft) return;
    if (draft.serial.trim().length < 2) {
      setError('Seriya raqamini kiriting');
      return;
    }
    if (devices.some((row) => row.serial === draft.serial.trim() && row.id !== draft.id)) {
      setError('Bu seriya raqam allaqachon kiritilgan');
      return;
    }
    if (draft.kind !== 'console' && draft.model.trim().length < 2) {
      setError('Model nomini kiriting');
      return;
    }

    saveDevice({ ...draft, id: draft.id || nextId('d'), serial: draft.serial.trim() });
    setDraft(null);
    setError(null);
  };

  const broken = devices.filter((device) => device.status === 'REPAIR').length;

  return (
    <Panel
      title={`Qurilmalar (${devices.length})`}
      notch
      brackets
      action={
        draft ? null : (
          <Button variant="primary" size="sm" icon="add" onClick={() => setDraft(EMPTY_DEVICE)}>
            Qurilma qo‘shish
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
            <Labeled label="Turi">
              <Select
                value={DEVICE_KIND[draft.kind]}
                items={KIND_ITEMS}
                onChange={(value) => {
                  const kind = KIND_BY_LABEL[value] ?? 'console';
                  setDraft({ ...draft, kind, model: kind === 'console' ? 'ps5' : '' });
                }}
                style={FULL}
              />
            </Labeled>

            {draft.kind === 'console' ? (
              <Labeled label="Model">
                <Select
                  value={consoleLabel(draft.model)}
                  items={CONSOLES.map((item) => item.label)}
                  onChange={(value) =>
                    setDraft({
                      ...draft,
                      model: CONSOLES.find((item) => item.label === value)?.id ?? draft.model,
                    })
                  }
                  style={FULL}
                />
              </Labeled>
            ) : (
              <TextField
                label="Model"
                value={draft.model}
                onChange={(value) => setDraft({ ...draft, model: value })}
                icon="memory"
              />
            )}

            <TextField
              label="Seriya"
              value={draft.serial}
              onChange={(value) => setDraft({ ...draft, serial: value })}
              icon="tag"
            />
            <Labeled label="Xona">
              <Select
                value={roomName(draft.roomId)}
                items={roomItems}
                onChange={(value) =>
                  setDraft({ ...draft, roomId: rooms.find((room) => room.name === value)?.id ?? '' })
                }
                style={FULL}
              />
            </Labeled>
            <Labeled label="Holat">
              <Select
                value={DEVICE_STATUS[draft.status].label}
                items={DSTATUS_ITEMS}
                onChange={(value) => setDraft({ ...draft, status: DSTATUS_BY_LABEL[value] ?? 'OK' })}
                style={FULL}
              />
            </Labeled>
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
        rows={devices}
        rowKey={(row) => row.id}
        empty="Qurilma kiritilmagan"
        columns={[
          {
            key: 'model',
            header: 'Qurilma',
            render: (row) => (
              <span style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
                <span style={{ color: 'var(--text-title)' }}>{modelText(row)}</span>
                <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                  {DEVICE_KIND[row.kind]}
                </span>
              </span>
            ),
          },
          {
            key: 'serial',
            header: 'Seriya',
            render: (row) => (
              <span style={{ font: 'var(--type-data)', color: 'var(--purple-100)' }}>
                {row.serial}
              </span>
            ),
          },
          { key: 'room', header: 'Xona', render: (row) => roomName(row.roomId) },
          {
            key: 'status',
            header: 'Holat',
            render: (row) => (
              <Tag tone={row.status === 'OK' ? 'ok' : row.status === 'REPAIR' ? 'warn' : 'neutral'}>
                {DEVICE_STATUS[row.status].label}
              </Tag>
            ),
          },
          {
            key: 'actions',
            header: '',
            align: 'right',
            render: (row) => (
              <RowActions onEdit={() => setDraft(row)} onRemove={() => removeDevice(row.id)} />
            ),
          },
        ]}
      />

      {broken > 0 ? (
        <div style={{ marginTop: 'var(--gap-block)' }}>
          <StatusLine
            tone="warn"
            icon="build"
            parts={[`${broken} qurilma ta’mirda`, 'Xona jihozini tekshiring']}
          />
        </div>
      ) : null}
    </Panel>
  );
}
