import {
  createStation,
  errorText,
  listStationsForManagement,
  updateClub,
  updateStation,
  type StationDto,
} from '@playbron/api-client';
import {
  Button,
  EntityTable,
  Modal,
  Panel,
  Select,
  StatusLine,
  Tabs,
  Tag,
  TextField,
  toast,
} from '@playbron/ui';
import { useCallback, useEffect, useState, type CSSProperties, type ReactNode } from 'react';

import { api } from '../../lib/api';
import { S } from '../../mock/data';
import { useSession } from '../../store/session';
import { FormGrid, Labeled, parseHm } from './parts';

const TABS = ['Umumiy', 'Xonalar'];
const FULL: CSSProperties = { width: '100%' };

const CONSOLE_LABEL: Record<string, string> = {
  ps3: 'PS3',
  ps4: 'PS4',
  ps4pro: 'PS4 Pro',
  ps5: 'PS5',
  ps5pro: 'PS5 Pro',
};
const CONSOLE_TYPES = Object.keys(CONSOLE_LABEL);

/**
 * Klub ma'lumoti — umumiy sozlamalar va xonalar.
 *
 * Prototipda yana "Tariflar" (vaqt bo'yicha narx koeffitsiyenti) va
 * "Qurilmalar" (inventar) bo'limlari bor edi — backend'da bu ikkisi UCHUN
 * hech qanday jadval yo'q (stansiyada faqat bitta soatlik narx bor,
 * inventar kuzatuvi umuman boshqa loyiha). Soxta CRUD ko'rsatishdan ko'ra
 * olib tashlangan — real narx/inventar qo'shilganda qaytariladi.
 */
export function ClubInfoScreen(): ReactNode {
  const [tab, setTab] = useState(TABS[0] as string);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <div className="ds-scroll-x">
        <Tabs items={TABS} value={tab} onChange={setTab} />
      </div>

      {tab === 'Umumiy' ? <GeneralTab /> : null}
      {tab === 'Xonalar' ? <StationsTab /> : null}
    </div>
  );
}

// ─────────────────────────── umumiy ───────────────────────────

/**
 * `parts.tsx::hm()` daqiqani 24 soatga o'raydi (smena vaqti uchun to'g'ri) —
 * klub yopilish vaqti 26:00 gacha bo'lishi mumkin (`parseHm` shuni qabul
 * qiladi), o'ralsa "02:00" bo'lib ko'rinib, ochilish-yopilish teskari
 * ko'rinardi. Shu yerda o'ramaydigan variant kerak.
 */
function hm(minutes: number): string {
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
}

function GeneralTab(): ReactNode {
  const session = useSession((state) => state.session);
  const clubId = session?.clubs[0]?.id ?? null;
  const clubName = session?.clubs[0]?.name ?? '';

  const [name, setName] = useState(clubName);
  const [address, setAddress] = useState('');
  const [phone, setPhone] = useState('');
  const [about, setAbout] = useState('');
  const [opens, setOpens] = useState('10:00');
  const [closes, setCloses] = useState('24:00');
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (clubId === null) return;
    // Klub ma'lumoti hozircha faqat ochiq katalogdan o'qiladi — alohida
    // "bitta klubni olish" endpointi yo'q, lekin GET /clubs allaqachon bor.
    void (async () => {
      try {
        const clubs = await api.get<
          Array<{
            id: number;
            name: string;
            address: string;
            phone: string | null;
            about: string;
            opens_at_min: number;
            closes_at_min: number;
          }>
        >('/clubs');
        const club = clubs.find((c) => c.id === clubId);
        if (club) {
          setName(club.name);
          setAddress(club.address);
          setPhone(club.phone ?? '');
          setAbout(club.about);
          setOpens(hm(club.opens_at_min));
          setCloses(hm(club.closes_at_min));
        }
      } finally {
        setLoaded(true);
      }
    })();
  }, [clubId]);

  const submit = async (): Promise<void> => {
    if (clubId === null) return;
    const opensMin = parseHm(opens);
    const closesMin = parseHm(closes);
    if (opensMin === null || closesMin === null) {
      setError('Vaqt HH:MM shaklida bo‘lishi kerak');
      return;
    }
    if (closesMin <= opensMin) {
      setError('Yopilish vaqti ochilishdan keyin bo‘lsin (tunda 26:00 gacha yoziladi)');
      return;
    }
    if (name.trim().length === 0) {
      setError('Klub nomini kiriting');
      return;
    }

    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await updateClub(api, clubId, {
        name: name.trim(),
        address,
        phone: phone.trim() || null,
        about,
        opensAtMin: opensMin,
        closesAtMin: closesMin,
      });
      setSaved(true);
      toast.success('Klub ma’lumoti saqlandi');
    } catch (cause) {
      const message = errorText(cause);
      setError(message);
      toast.error(message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Panel title="Asosiy ma’lumot" notch brackets>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
        <FormGrid>
          <TextField
            label="Klub nomi"
            value={name}
            onChange={setName}
            icon="storefront"
            disabled={!loaded}
          />
          <TextField
            label="Telefon"
            value={phone}
            onChange={setPhone}
            icon="call"
            inputMode="tel"
            disabled={!loaded}
          />
        </FormGrid>

        <TextField
          label="Manzil"
          value={address}
          onChange={setAddress}
          icon="location_on"
          disabled={!loaded}
        />
        <TextField
          label="Tavsif"
          value={about}
          onChange={setAbout}
          icon="notes"
          disabled={!loaded}
        />

        <FormGrid>
          <TextField
            label="Ochilish"
            value={opens}
            onChange={setOpens}
            icon="schedule"
            disabled={!loaded}
          />
          <TextField
            label="Yopilish"
            value={closes}
            onChange={setCloses}
            icon="bedtime"
            disabled={!loaded}
          />
          <Button
            variant="primary"
            icon="check"
            disabled={!loaded || saving}
            onClick={() => void submit()}
          >
            {saving ? 'Saqlanmoqda…' : 'Saqlash'}
          </Button>
        </FormGrid>

        {error ? <StatusLine tone="danger" icon="error" parts={error} /> : null}
        {saved ? <StatusLine tone="ok" icon="check_circle" parts={['Saqlandi']} /> : null}
      </div>
    </Panel>
  );
}

// ─────────────────────────── xonalar ───────────────────────────

interface Draft {
  id: number | null;
  code: string;
  roomLabel: string;
  consoleType: string;
  rate: string;
  status: 'active' | 'maintenance';
}

const EMPTY_DRAFT: Draft = {
  id: null,
  code: '',
  roomLabel: 'Standart',
  consoleType: 'ps5',
  rate: '40000',
  status: 'active',
};

function StationsTab(): ReactNode {
  const session = useSession((state) => state.session);
  const clubId = session?.clubs[0]?.id ?? null;

  const [stations, setStations] = useState<StationDto[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const reload = useCallback(async (): Promise<void> => {
    if (clubId === null) return;
    setLoading(true);
    setLoadError(null);
    try {
      setStations(await listStationsForManagement(api, clubId));
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
    const rate = Number(draft.rate);
    if (draft.id === null && draft.code.trim().length === 0) {
      setError('Xona kodini kiriting');
      return;
    }
    if (!Number.isFinite(rate) || rate <= 0) {
      setError('Soatlik summa musbat bo‘lsin');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      if (draft.id === null) {
        await createStation(api, clubId, {
          code: draft.code.trim(),
          roomLabel: draft.roomLabel.trim() || 'Standart',
          consoleType: draft.consoleType,
          rate,
        });
        toast.success(`Xona qo‘shildi — ${draft.code.trim()}`);
      } else {
        await updateStation(api, clubId, draft.id, {
          roomLabel: draft.roomLabel.trim() || 'Standart',
          consoleType: draft.consoleType,
          rate,
          status: draft.status,
        });
        toast.success('Xona yangilandi');
      }
      setDraft(null);
      await reload();
    } catch (cause) {
      const message = errorText(cause);
      setError(message);
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  const toggleMaintenance = async (station: StationDto): Promise<void> => {
    if (clubId === null) return;
    try {
      await updateStation(api, clubId, station.id, {
        roomLabel: station.roomLabel,
        consoleType: station.consoleType,
        rate: station.rate,
        status: station.status === 'active' ? 'maintenance' : 'active',
      });
      toast.success(
        station.status === 'active' ? 'Xona ta’mirga chiqarildi' : 'Xona faollashtirildi',
      );
      await reload();
    } catch (cause) {
      toast.error(errorText(cause));
    }
  };

  return (
    <>
      <Modal
        open={draft !== null}
        onClose={() => {
          setDraft(null);
          setError(null);
        }}
        title={draft?.id === null ? 'Xona qo‘shish' : 'Xonani tahrirlash'}
        variant="center"
      >
        {draft ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
            <FormGrid>
              {draft.id === null ? (
                <TextField
                  label="Kod"
                  value={draft.code}
                  onChange={(value) => setDraft({ ...draft, code: value })}
                  icon="tag"
                  placeholder="A1"
                />
              ) : null}
              <TextField
                label="Xona turi"
                value={draft.roomLabel}
                onChange={(value) => setDraft({ ...draft, roomLabel: value })}
                icon="meeting_room"
                placeholder="Standart"
              />
              <Labeled label="Konsol">
                <Select
                  value={CONSOLE_LABEL[draft.consoleType] ?? draft.consoleType}
                  items={CONSOLE_TYPES.map((id) => CONSOLE_LABEL[id] as string)}
                  onChange={(label) => {
                    const id = CONSOLE_TYPES.find((c) => CONSOLE_LABEL[c] === label);
                    if (id) setDraft({ ...draft, consoleType: id });
                  }}
                  style={FULL}
                />
              </Labeled>
              <TextField
                label="Soatlik summa"
                value={draft.rate}
                onChange={(value) => setDraft({ ...draft, rate: value })}
                icon="payments"
                inputMode="numeric"
              />
            </FormGrid>

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

      <Panel
        title={`Xonalar (${stations.length})`}
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
            Xona qo‘shish
          </Button>
        }
      >
        {loadError ? <StatusLine tone="danger" icon="error" parts={[loadError]} /> : null}

        <EntityTable
          rows={stations}
          rowKey={(row) => String(row.id)}
          empty={loading ? 'Yuklanmoqda…' : 'Xona qo‘shilmagan'}
          columns={[
            {
              key: 'code',
              header: 'Xona',
              render: (row) => (
                <span style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
                  <span style={{ color: 'var(--text-title)' }}>{row.code}</span>
                  <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                    {row.roomLabel}
                  </span>
                </span>
              ),
            },
            {
              key: 'console',
              header: 'Konsol',
              render: (row) => CONSOLE_LABEL[row.consoleType] ?? row.consoleType,
            },
            {
              key: 'rate',
              header: 'Soatlik',
              align: 'right',
              render: (row) => (
                <span
                  style={{
                    font: 'var(--type-data)',
                    color: 'var(--text-title)',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {S(row.rate)}
                </span>
              ),
            },
            {
              key: 'status',
              header: 'Holat',
              render: (row) => (
                <Tag tone={row.status === 'active' ? 'success' : 'amber'}>
                  {row.status === 'active' ? 'Faol' : 'Ta’mirda'}
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
                        code: row.code,
                        roomLabel: row.roomLabel,
                        consoleType: row.consoleType,
                        rate: String(row.rate),
                        status: row.status === 'active' ? 'active' : 'maintenance',
                      });
                    }}
                  />
                  <Button
                    variant="ghost"
                    size="sm"
                    icon="build"
                    onClick={() => void toggleMaintenance(row)}
                  />
                </div>
              ),
            },
          ]}
        />
      </Panel>
    </>
  );
}
