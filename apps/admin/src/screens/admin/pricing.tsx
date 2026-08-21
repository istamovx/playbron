import {
  TARIFF_ALL_DAYS,
  createRoom,
  createTariff,
  errorText,
  listRooms,
  listTariffs,
  updateRoom,
  updateTariff,
  type RoomDto,
  type TariffDto,
} from '@playbron/api-client';
import {
  Button,
  Chip,
  EntityTable,
  Modal,
  Panel,
  Select,
  StatTile,
  StatusLine,
  Tag,
  TextField,
  formatSum,
  toast,
} from '@playbron/ui';
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';

import { useT, type MsgKey } from '../../i18n';
import { api } from '../../lib/api';
import { CONSOLES, consoleLabel } from '../../mock/data';
import { useBoard } from '../../store/board';
import { useSession } from '../../store/session';
import { FormGrid, Labeled } from './parts';

/**
 * Narxlar — xonalar (`rooms`) va soatlik tariflar (`tariffs`).
 *
 * `0037_rooms_tariffs.py` jadvallarni va `pricing.py` narx hisobini bergan
 * edi, lekin boshqaruv yo'li yo'q edi: tarifni faqat xom SQL bilan
 * kiritish mumkin edi (`CLAUDE.md`, «Ma'lum texnik qarz»). Bu ekran o'sha
 * bo'shliqni yopadi.
 *
 * Hisob mantig'i BU YERDA TAKRORLANMAYDI (`CLAUDE.md`, §Frontend): ekran
 * faqat tarif qatorlarini tahrirlaydi, bron narxini esa doim server
 * beradi (`bookings.play_amount`).
 *
 * O'chirish yo'q — arxivlanadi: yopilgan bronlarning narxi shu qatorlar
 * orqali hisoblangan.
 */

const MINUTES_PER_DAY = 24 * 60;
/** `tariffs_window_ck` (`0033`) — yarim tundan o'tuvchi oyna uchun. */
const MAX_TO_MIN = 2 * MINUTES_PER_DAY;

const DAY_KEYS: readonly MsgKey[] = [
  'dayMon',
  'dayTue',
  'dayWed',
  'dayThu',
  'dayFri',
  'daySat',
  'daySun',
];

/** Dushanba — 0-bit (backenddagi `datetime.weekday()` bilan bir xil). */
const WORKDAYS_MASK = 0b000_1111 | 0b001_0000;
const WEEKEND_MASK = 0b110_0000;

/** Daqiqa → `HH:MM`. 24:00 dan oshsa ham shu ko'rinishda (26:00). */
const hm = (minutes: number): string =>
  `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;

/** `26:00` → 1560. Format buzilsa `null`. */
function parseHm(value: string): number | null {
  const match = /^(\d{1,2}):(\d{2})$/.exec(value.trim());
  const rawHours = match?.[1];
  const rawMinutes = match?.[2];
  if (rawHours === undefined || rawMinutes === undefined) return null;
  const hours = Number(rawHours);
  const minutes = Number(rawMinutes);
  if (minutes > 59) return null;
  const total = hours * 60 + minutes;
  return total > MAX_TO_MIN ? null : total;
}

/** `'12'` → 12; bo'sh, kasr yoki manfiy bo'lsa `null`. */
function parseWhole(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed.length === 0) return null;
  const parsed = Number(trimmed);
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : null;
}

interface RoomDraft {
  id: number | null;
  name: string;
  kind: string;
  sort: string;
  isActive: boolean;
}

interface TariffDraft {
  id: number | null;
  name: string;
  daysMask: number;
  from: string;
  to: string;
  price: string;
  priority: string;
  /** Bo'sh qator — «har qanday» (`null` bo'lib ketadi). */
  consoleType: string;
  roomKind: string;
  isActive: boolean;
}

const EMPTY_ROOM: RoomDraft = { id: null, name: '', kind: 'Standart', sort: '0', isActive: true };

const EMPTY_TARIFF: TariffDraft = {
  id: null,
  name: '',
  daysMask: TARIFF_ALL_DAYS,
  from: '10:00',
  to: '22:00',
  price: '',
  priority: '0',
  consoleType: '',
  roomKind: '',
  isActive: true,
};

export function PricingScreen(): ReactNode {
  const t = useT();
  const session = useSession((state) => state.session);
  const activeClubId = useBoard((state) => state.activeClubId);
  const clubId = activeClubId ?? session?.clubs[0]?.id ?? null;

  const [rooms, setRooms] = useState<RoomDto[]>([]);
  const [tariffs, setTariffs] = useState<TariffDto[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [roomDraft, setRoomDraft] = useState<RoomDraft | null>(null);
  const [tariffDraft, setTariffDraft] = useState<TariffDraft | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Qaysi klub uchun so'ralganini eslab qolamiz. Klub almashtirilganda
  // eski (sekinroq) javob yangisining ustiga yozilib, ekranda A klubning
  // narxlari turgani holda B klubga PATCH ketardi.
  const latest = useRef(0);

  const reload = useCallback(async (): Promise<void> => {
    if (clubId === null) return;
    const ticket = latest.current + 1;
    latest.current = ticket;
    setLoading(true);
    setLoadError(null);
    try {
      const [nextRooms, nextTariffs] = await Promise.all([
        listRooms(api, clubId),
        listTariffs(api, clubId),
      ]);
      if (latest.current !== ticket) return;
      setRooms(nextRooms);
      setTariffs(nextTariffs);
    } catch (cause) {
      if (latest.current !== ticket) return;
      const message = errorText(cause);
      setLoadError(message);
      toast.error(message);
    } finally {
      if (latest.current === ticket) setLoading(false);
    }
  }, [clubId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const anyLabel = t('scopeAny');
  // Tarif `rooms.kind` ga qarab yo'naltiriladi, shuning uchun ro'yxat
  // xonalarning O'ZIDAN quriladi — qo'lda yozilgan tur hech qachon
  // mos kelmasdi.
  const roomKinds = [...new Set(rooms.map((room) => room.kind))].sort();

  const closeForms = (): void => {
    setRoomDraft(null);
    setTariffDraft(null);
    setError(null);
  };

  const submitRoom = async (draft: RoomDraft): Promise<void> => {
    if (clubId === null) return;
    const name = draft.name.trim();
    if (name.length < 1) {
      setError(t('errNameRequired'));
      return;
    }
    const sort = parseWhole(draft.sort);
    if (sort === null) {
      setError(t('errWholeNumber'));
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const body = { name, kind: draft.kind.trim() || 'Standart', sort };
      if (draft.id === null) {
        await createRoom(api, clubId, body);
      } else {
        await updateRoom(api, clubId, draft.id, { ...body, isActive: draft.isActive });
      }
      toast.success(t('roomSaved'));
      closeForms();
      await reload();
    } catch (cause) {
      const message = errorText(cause);
      setError(message);
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  const submitTariff = async (draft: TariffDraft): Promise<void> => {
    if (clubId === null) return;
    const name = draft.name.trim();
    if (name.length < 1) {
      setError(t('errNameRequired'));
      return;
    }
    if (draft.daysMask < 1) {
      setError(t('errDaysRequired'));
      return;
    }
    const fromMin = parseHm(draft.from);
    const toMin = parseHm(draft.to);
    if (fromMin === null || toMin === null) {
      setError(t('errTimeFormat'));
      return;
    }
    if (fromMin >= MINUTES_PER_DAY) {
      setError(t('errStartWithinDay'));
      return;
    }
    if (toMin <= fromMin) {
      setError(t('errWindowOrder'));
      return;
    }
    const price = parseWhole(draft.price);
    if (price === null || price <= 0) {
      setError(t('errPricePositive'));
      return;
    }
    const priority = parseWhole(draft.priority);
    if (priority === null) {
      setError(t('errWholeNumber'));
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const body = {
        name,
        daysMask: draft.daysMask,
        fromMin,
        toMin,
        pricePerHour: price,
        priority,
        consoleType: draft.consoleType || null,
        roomKind: draft.roomKind || null,
      };
      if (draft.id === null) {
        await createTariff(api, clubId, body);
      } else {
        await updateTariff(api, clubId, draft.id, { ...body, isActive: draft.isActive });
      }
      toast.success(t('tariffSaved'));
      closeForms();
      await reload();
    } catch (cause) {
      const message = errorText(cause);
      setError(message);
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  const toggleRoom = async (room: RoomDto): Promise<void> => {
    if (clubId === null) return;
    try {
      await updateRoom(api, clubId, room.id, {
        name: room.name,
        kind: room.kind,
        sort: room.sort,
        isActive: !room.isActive,
      });
      toast.success(room.isActive ? t('rowArchived') : t('rowRestored'));
      await reload();
    } catch (cause) {
      toast.error(errorText(cause));
    }
  };

  const toggleTariff = async (tariff: TariffDto): Promise<void> => {
    if (clubId === null) return;
    try {
      await updateTariff(api, clubId, tariff.id, {
        name: tariff.name,
        daysMask: tariff.daysMask,
        fromMin: tariff.fromMin,
        toMin: tariff.toMin,
        pricePerHour: tariff.pricePerHour,
        priority: tariff.priority,
        consoleType: tariff.consoleType,
        roomKind: tariff.roomKind,
        isActive: !tariff.isActive,
      });
      toast.success(tariff.isActive ? t('rowArchived') : t('rowRestored'));
      await reload();
    } catch (cause) {
      toast.error(errorText(cause));
    }
  };

  const daysLabel = (mask: number): string => {
    if (mask === TARIFF_ALL_DAYS) return t('daysEvery');
    if (mask === WORKDAYS_MASK) return t('daysWorkdays');
    if (mask === WEEKEND_MASK) return t('daysWeekend');
    return DAY_KEYS.filter((_, index) => (mask & (1 << index)) !== 0)
      .map((key) => t(key))
      .join(' ');
  };

  const scopeLabel = (tariff: TariffDto): string =>
    [
      tariff.consoleType === null ? anyLabel : consoleLabel(tariff.consoleType),
      tariff.roomKind ?? anyLabel,
    ].join(' · ');

  if (clubId === null) {
    return <StatusLine tone="warn" icon="info" parts={[t('pricingNoClub')]} />;
  }

  const emptyRooms = loading ? t('pricingLoading') : t('roomsEmpty');
  const emptyTariffs = loading ? t('pricingLoading') : t('tariffsEmpty');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <div className="pb-tiles-2">
        <StatTile
          label={t('roomsPanel')}
          value={String(rooms.length)}
          unit={t('unitPieces')}
          icon="meeting_room"
        />
        <StatTile
          label={t('tariffsPanel')}
          value={String(tariffs.filter((row) => row.isActive).length)}
          unit={t('unitPieces')}
          icon="schedule"
        />
      </div>

      {loadError ? <StatusLine tone="danger" icon="error" parts={[loadError]} /> : null}

      <Modal
        open={roomDraft !== null}
        onClose={closeForms}
        title={roomDraft?.id === null ? t('roomFormNew') : t('roomFormEdit')}
        variant="drawer"
      >
        {roomDraft ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
            <FormGrid>
              <TextField
                label={t('fieldName')}
                value={roomDraft.name}
                onChange={(value) => setRoomDraft({ ...roomDraft, name: value })}
                icon="meeting_room"
              />
              <TextField
                label={t('fieldKind')}
                value={roomDraft.kind}
                onChange={(value) => setRoomDraft({ ...roomDraft, kind: value })}
                icon="category"
              />
              <TextField
                label={t('fieldOrder')}
                value={roomDraft.sort}
                onChange={(value) => setRoomDraft({ ...roomDraft, sort: value })}
                icon="sort"
                inputMode="numeric"
              />
            </FormGrid>
            <FormActions
              busy={submitting}
              error={error}
              saveLabel={t('saveButton')}
              savingLabel={t('actionSaving')}
              cancelLabel={t('actionCancel')}
              onSave={() => void submitRoom(roomDraft)}
              onCancel={closeForms}
            />
          </div>
        ) : null}
      </Modal>

      <Modal
        open={tariffDraft !== null}
        onClose={closeForms}
        title={tariffDraft?.id === null ? t('tariffFormNew') : t('tariffFormEdit')}
        variant="drawer"
      >
        {tariffDraft ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
            <FormGrid>
              <TextField
                label={t('fieldName')}
                value={tariffDraft.name}
                onChange={(value) => setTariffDraft({ ...tariffDraft, name: value })}
                icon="sell"
              />
              <Labeled label={t('fieldDays')}>
                <DaysPicker
                  value={tariffDraft.daysMask}
                  onChange={(daysMask) => setTariffDraft({ ...tariffDraft, daysMask })}
                />
              </Labeled>
              <TextField
                label={t('fieldFrom')}
                value={tariffDraft.from}
                onChange={(value) => setTariffDraft({ ...tariffDraft, from: value })}
                icon="schedule"
                placeholder="18:00"
              />
              <TextField
                label={t('fieldTo')}
                value={tariffDraft.to}
                onChange={(value) => setTariffDraft({ ...tariffDraft, to: value })}
                icon="schedule"
                placeholder="26:00"
              />
              <StatusLine tone="neutral" icon="info" parts={[t('overnightNote')]} />
              <TextField
                label={t('fieldPerHour')}
                value={tariffDraft.price}
                onChange={(value) => setTariffDraft({ ...tariffDraft, price: value })}
                icon="payments"
                inputMode="numeric"
                placeholder="50000"
              />
              <TextField
                label={t('fieldPriority')}
                value={tariffDraft.priority}
                onChange={(value) => setTariffDraft({ ...tariffDraft, priority: value })}
                icon="low_priority"
                inputMode="numeric"
              />
              <Labeled label={t('fieldConsole')}>
                <Select
                  value={
                    tariffDraft.consoleType ? consoleLabel(tariffDraft.consoleType) : anyLabel
                  }
                  items={[anyLabel, ...CONSOLES.map((item) => item.label)]}
                  onChange={(label) =>
                    setTariffDraft({
                      ...tariffDraft,
                      consoleType: CONSOLES.find((item) => item.label === label)?.id ?? '',
                    })
                  }
                  style={{ width: '100%' }}
                />
              </Labeled>
              <Labeled label={t('fieldRoomKind')}>
                <Select
                  value={tariffDraft.roomKind || anyLabel}
                  items={[
                    anyLabel,
                    ...new Set(
                      tariffDraft.roomKind ? [tariffDraft.roomKind, ...roomKinds] : roomKinds,
                    ),
                  ]}
                  onChange={(kind) =>
                    setTariffDraft({ ...tariffDraft, roomKind: kind === anyLabel ? '' : kind })
                  }
                  style={{ width: '100%' }}
                />
              </Labeled>
            </FormGrid>
            <FormActions
              busy={submitting}
              error={error}
              saveLabel={t('saveButton')}
              savingLabel={t('actionSaving')}
              cancelLabel={t('actionCancel')}
              onSave={() => void submitTariff(tariffDraft)}
              onCancel={closeForms}
            />
          </div>
        ) : null}
      </Modal>

      <Panel
        title={`${t('roomsPanel')} (${rooms.length})`}
        notch
        brackets
        action={
          <Button
            variant="primary"
            size="sm"
            icon="add"
            onClick={() => {
              setError(null);
              setRoomDraft(EMPTY_ROOM);
            }}
          >
            {t('roomAdd')}
          </Button>
        }
      >
        <EntityTable
          rows={rooms}
          rowKey={(row) => String(row.id)}
          empty={emptyRooms}
          columns={[
            { key: 'name', header: t('colRoom'), render: (row) => row.name },
            {
              key: 'kind',
              header: t('colKind'),
              render: (row) => <Tag tone="violet">{row.kind}</Tag>,
            },
            { key: 'sort', header: t('colOrder'), align: 'right', render: (row) => row.sort },
            {
              key: 'state',
              header: t('colState'),
              render: (row) => (
                <Tag tone={row.isActive ? 'success' : 'neutral'}>
                  {row.isActive ? t('stateActive') : t('stateArchived')}
                </Tag>
              ),
            },
            {
              key: 'actions',
              header: '',
              align: 'right',
              render: (row) => (
                <RowButtons
                  archived={!row.isActive}
                  archiveTitle={row.isActive ? t('actionArchive') : t('actionRestore')}
                  onEdit={() => {
                    setError(null);
                    setRoomDraft({
                      id: row.id,
                      name: row.name,
                      kind: row.kind,
                      sort: String(row.sort),
                      isActive: row.isActive,
                    });
                  }}
                  onToggle={() => void toggleRoom(row)}
                />
              ),
            },
          ]}
        />
      </Panel>

      <Panel
        title={`${t('tariffsPanel')} (${tariffs.length})`}
        notch
        brackets
        action={
          <Button
            variant="primary"
            size="sm"
            icon="add"
            onClick={() => {
              setError(null);
              setTariffDraft(EMPTY_TARIFF);
            }}
          >
            {t('tariffAdd')}
          </Button>
        }
      >
        <StatusLine tone="neutral" icon="info" parts={[t('tariffsHint')]} />

        <EntityTable
          rows={tariffs}
          rowKey={(row) => String(row.id)}
          empty={emptyTariffs}
          columns={[
            { key: 'name', header: t('colTariff'), render: (row) => row.name },
            { key: 'days', header: t('colDays'), render: (row) => daysLabel(row.daysMask) },
            {
              key: 'window',
              header: t('colWindow'),
              render: (row) => (
                <span style={{ font: 'var(--type-data)', whiteSpace: 'nowrap' }}>
                  {hm(row.fromMin)}–{hm(row.toMin)}
                </span>
              ),
            },
            {
              key: 'price',
              header: t('colPerHour'),
              align: 'right',
              render: (row) => (
                <span
                  style={{
                    font: 'var(--type-data)',
                    color: 'var(--text-title)',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {formatSum(BigInt(row.pricePerHour))}
                </span>
              ),
            },
            {
              key: 'priority',
              header: t('colPriority'),
              align: 'right',
              render: (row) => row.priority,
            },
            { key: 'scope', header: t('colScope'), render: (row) => scopeLabel(row) },
            {
              key: 'state',
              header: t('colState'),
              render: (row) => (
                <Tag tone={row.isActive ? 'success' : 'neutral'}>
                  {row.isActive ? t('stateActive') : t('stateArchived')}
                </Tag>
              ),
            },
            {
              key: 'actions',
              header: '',
              align: 'right',
              render: (row) => (
                <RowButtons
                  archived={!row.isActive}
                  archiveTitle={row.isActive ? t('actionArchive') : t('actionRestore')}
                  onEdit={() => {
                    setError(null);
                    setTariffDraft({
                      id: row.id,
                      name: row.name,
                      daysMask: row.daysMask,
                      from: hm(row.fromMin),
                      to: hm(row.toMin),
                      price: String(row.pricePerHour),
                      priority: String(row.priority),
                      consoleType: row.consoleType ?? '',
                      roomKind: row.roomKind ?? '',
                      isActive: row.isActive,
                    });
                  }}
                  onToggle={() => void toggleTariff(row)}
                />
              ),
            },
          ]}
        />
      </Panel>
    </div>
  );
}

/**
 * Hafta kunlari — xom bitmaska o'rniga bosiladigan yetti chip.
 * Bit tartibi backend bilan bir xil: dushanba — 0-bit.
 */
function DaysPicker({
  value,
  onChange,
}: {
  value: number;
  onChange: (value: number) => void;
}): ReactNode {
  const t = useT();
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-tight)' }}>
      <div style={{ display: 'flex', gap: 'var(--sp-3)', flexWrap: 'wrap' }}>
        {DAY_KEYS.map((key, index) => (
          <Chip
            key={key}
            selected={(value & (1 << index)) !== 0}
            onClick={() => onChange(value ^ (1 << index))}
          >
            {t(key)}
          </Chip>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 'var(--sp-3)', flexWrap: 'wrap' }}>
        <Button variant="ghost" size="sm" onClick={() => onChange(TARIFF_ALL_DAYS)}>
          {t('daysEvery')}
        </Button>
        <Button variant="ghost" size="sm" onClick={() => onChange(WORKDAYS_MASK)}>
          {t('daysWorkdays')}
        </Button>
        <Button variant="ghost" size="sm" onClick={() => onChange(WEEKEND_MASK)}>
          {t('daysWeekend')}
        </Button>
      </div>
    </div>
  );
}

function FormActions({
  busy,
  error,
  saveLabel,
  savingLabel,
  cancelLabel,
  onSave,
  onCancel,
}: {
  busy: boolean;
  error: string | null;
  saveLabel: string;
  savingLabel: string;
  cancelLabel: string;
  onSave: () => void;
  onCancel: () => void;
}): ReactNode {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
      {error ? <StatusLine tone="danger" icon="error" parts={[error]} /> : null}
      <div style={{ display: 'flex', gap: 'var(--gap-tight)', flexWrap: 'wrap' }}>
        <Button variant="primary" notch icon="check" disabled={busy} onClick={onSave}>
          {busy ? savingLabel : saveLabel}
        </Button>
        <Button variant="ghost" disabled={busy} onClick={onCancel}>
          {cancelLabel}
        </Button>
      </div>
    </div>
  );
}

/** Jadval qatoridagi tahrirlash va arxivlash — o'chirish YO'Q. */
function RowButtons({
  archived,
  archiveTitle,
  onEdit,
  onToggle,
}: {
  archived: boolean;
  archiveTitle: string;
  onEdit: () => void;
  onToggle: () => void;
}): ReactNode {
  return (
    <div style={{ display: 'flex', gap: 'var(--sp-3)', justifyContent: 'flex-end' }}>
      <Button variant="ghost" size="sm" icon="edit" onClick={onEdit} />
      <Button
        variant="ghost"
        size="sm"
        icon={archived ? 'unarchive' : 'archive'}
        title={archiveTitle}
        onClick={onToggle}
      />
    </div>
  );
}
