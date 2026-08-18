import {
  createStation,
  errorText,
  getClub,
  getMe,
  listClubLogs,
  listStationsForManagement,
  pollTelegramLink,
  publishClub,
  startTelegramLink,
  updateClub,
  updateStation,
  type ActivityLogDto,
  type StationDto,
  type TelegramLinkStatus,
} from '@playbron/api-client';
import {
  Button,
  EntityTable,
  FieldLadder,
  FieldRow,
  Modal,
  Panel,
  StatusLine,
  Tabs,
  Tag,
  TextField,
  toast,
} from '@playbron/ui';
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';

import { api } from '../../lib/api';
import { S } from '../../mock/data';
import { useBoard } from '../../store/board';
import { ROLE_LABEL, remainingText, useSession } from '../../store/session';
import { FormGrid, parseHm } from './parts';

const TABS = ['Hisob', 'Klub ma’lumoti', 'Xonalar', 'Jurnal'];

/**
 * Sozlamalar — klub adminining shaxsiy hisobi + klub ma'lumoti + xonalar
 * + faoliyat jurnali.
 *
 * Avval "Klub ma'lumoti" alohida nav bo'limi edi (`club-info.tsx`) — loyiha
 * egasining so'rovi bilan shu yerga ko'chirildi (2026-08-16). "Jurnal" —
 * shu kuni qo'shilgan yana bir so'rov: "klub egasiga o'zi va xodimlar
 * logini ko'rsin".
 */
export function SettingsScreen(): ReactNode {
  const [tab, setTab] = useState(TABS[0] as string);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
      <div className="ds-scroll-x">
        <Tabs items={TABS} value={tab} onChange={setTab} />
      </div>

      {tab === 'Hisob' ? <AccountTab /> : null}
      {tab === 'Klub ma’lumoti' ? <ClubGeneralTab /> : null}
      {tab === 'Xonalar' ? <StationsTab /> : null}
      {tab === 'Jurnal' ? <LogTab /> : null}
    </div>
  );
}

// ─────────────────────────── hisob ───────────────────────────

/**
 * Hisob — ma'lumot, parol almashtirish va Telegram bog'lash.
 *
 * Avvalgi izoh ("kirish faqat Telegram orqali, DCR-001") ESKIRGAN edi va
 * ekranda YOLG'ON ma'lumot ko'rsatilardi: "Kirish — Telegram", "Parol
 * saqlanmaydi, o'g'irlanadigan sir yo'q" (audit topilmasi, 2026-08-16).
 * Aslida xodim dunyosiga kirish LOGIN + PAROL bilan
 * (`auth/staff.py::staff_login()`), parol esa Argon2id xeshi ko'rinishida
 * `staff_credentials` jadvalida saqlanadi. Klub egasi bu matnga qarab
 * "parolim yo'q, himoya kerak emas" degan xulosaga kelishi mumkin edi.
 */
function AccountTab(): ReactNode {
  const session = useSession((state) => state.session);
  const signOut = useSession((state) => state.signOut);
  const changePassword = useSession((state) => state.changePassword);

  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [repeat, setRepeat] = useState('');
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwSubmitting, setPwSubmitting] = useState(false);

  if (!session) return null;

  const submitPassword = async (): Promise<void> => {
    if (current.length < 1) {
      setPwError('Joriy parolni kiriting');
      return;
    }
    if (next.length < 8) {
      setPwError('Yangi parol kamida 8 belgi bo‘lsin');
      return;
    }
    if (next !== repeat) {
      setPwError('Yangi parol takrori mos kelmadi');
      return;
    }

    setPwSubmitting(true);
    setPwError(null);
    try {
      await changePassword(current, next);
      setCurrent('');
      setNext('');
      setRepeat('');
      toast.success('Parol almashtirildi');
    } catch (cause) {
      const message = errorText(cause);
      setPwError(message);
      toast.error(message);
    } finally {
      setPwSubmitting(false);
    }
  };

  return (
    <div className="ds-split" style={{ alignItems: 'start' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)', minWidth: 0 }}>
        <Panel title="Hisob" notch brackets>
          <FieldLadder>
            <FieldRow label="Ism" value={session.name} />
            <FieldRow label="Login" value={session.login ?? '—'} />
            <FieldRow label="Rol" value={ROLE_LABEL[session.role]} />
            <FieldRow label="Klublar" value={String(session.clubs.length)} />
            <FieldRow label="Sessiya tugashiga" value={remainingText(session.expiresAt)} />
          </FieldLadder>

          <div style={{ marginTop: 'var(--gap-block)' }}>
            <Button variant="secondary" icon="logout" onClick={signOut}>
              Chiqish
            </Button>
          </div>
        </Panel>

        <Panel title="Parolni almashtirish" notch>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
            <TextField
              label="Joriy parol"
              value={current}
              onChange={setCurrent}
              icon="lock"
              type="password"
            />
            <TextField
              label="Yangi parol"
              value={next}
              onChange={setNext}
              icon="lock_reset"
              type="password"
            />
            <TextField
              label="Yangi parol (takror)"
              value={repeat}
              onChange={setRepeat}
              icon="lock_reset"
              type="password"
            />

            {pwError ? <StatusLine tone="danger" icon="error" parts={pwError} /> : null}

            <Button
              variant="primary"
              notch
              icon="check"
              disabled={pwSubmitting}
              onClick={() => void submitPassword()}
            >
              {pwSubmitting ? 'Saqlanmoqda…' : 'Almashtirish'}
            </Button>
          </div>
        </Panel>

        <TelegramLinkPanel />
      </div>

      <Panel title="Xavfsizlik" notch>
        <StatusLine
          tone="neutral"
          icon="verified_user"
          parts={[
            'Kirish login va parol bilan',
            'Parol xesh ko‘rinishida saqlanadi (Argon2id)',
            'Birov bergan parol birinchi kirishda almashtiriladi',
          ]}
        />
      </Panel>
    </div>
  );
}

type LinkState = 'idle' | 'waiting' | 'ready' | 'expired' | 'error';

/**
 * Bron bildirishnomasi uchun xodimning o'z Telegram'ini ulashi.
 *
 * Naqsh — deep-link + poll (`botlogin.py`dagi bilan bir xil): nonce olinadi,
 * bot yangi bo'shliqda ochiladi (`t.me/...?start=<nonce>`), foydalanuvchi
 * botda **Start** bosgach konsol pollab natijani biladi. OAuth oynasi yo'q.
 *
 * Holat SERVERDAN o'qiladi (`GET /me` → `telegram_linked`, `staff_telegram`
 * jadvalidan) — loyiha egasining topilmasi (2026-08-16): "Telegram
 * ulanganda 'ulandi' ko'rsatadi, log out qilib qayta kirganda status
 * yo'q". Avval holat FAQAT shu komponentning lokal state'ida yashardi,
 * shuning uchun sahifa yangilansa yoki qayta kirilsa yo'qolardi. Bot
 * BIR MARTA ulanadi va shu holda qoladi; qayta bosish ham xavfsiz —
 * bog'lash `ON CONFLICT (user_id) DO UPDATE`.
 */
/** `app.tsx`da ham (header'dan) qayta ishlatiladi — xodim (`NAV_STAFF`)
 * menyusida "Sozlamalar" bandi UMUMAN yo'q (loyiha egasining topilmasi,
 * 2026-08-16: "xodim o'z accountini botga qanday ulaydi? Shu qism qolib
 * ketipti"), shuning uchun bog'lash HAR BIR rol ko'radigan headerga
 * ko'chirildi; bu yerdagi nusxa klub admin/egasi uchun saqlanib qoladi. */
export function TelegramLinkPanel(): ReactNode {
  const [state, setState] = useState<LinkState>('idle');
  // Serverdagi haqiqiy holat (`GET /me`). `null` — hali yuklanmoqda.
  const [linked, setLinked] = useState<boolean | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = (): void => {
    if (timer.current !== null) {
      clearInterval(timer.current);
      timer.current = null;
    }
  };

  useEffect(() => stopPolling, []);

  useEffect(() => {
    let cancelled = false;
    void getMe(api)
      .then((me) => {
        if (!cancelled) setLinked(me.telegram_linked);
      })
      .catch(() => {
        // Tarmoq xatosi — holat noma'lum qoladi, tugma baribir ishlaydi
        if (!cancelled) setLinked(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const POLL_INTERVAL_MS = 2000;

  const start = async (): Promise<void> => {
    stopPolling();
    setState('waiting');
    try {
      // `botUsername` server'dan — token'ni frontend BILMAYDI (`router.py::
      // start_telegram_link()`). Avval BU YERDA hardcode qilingan edi
      // (`@playbronappbot`, sinov manzili) — token/bot boshqacha bo'lsa
      // tugma DOIM o'lik havolaga olib borardi (loyiha egasi: "botlarni
      // ishlata olmadim"). `null` — token noto'g'ri/o'chirilgan (Telegram
      // `getMe` rad etgan), bu holda havola OCHILMAYDI.
      const { nonce, botUsername } = await startTelegramLink(api);
      if (!botUsername) {
        stopPolling();
        setState('error');
        return;
      }
      window.open(`https://t.me/${botUsername}?start=${nonce}`, '_blank', 'noopener');

      timer.current = setInterval(() => {
        void pollTelegramLink(api, nonce)
          .then((status: TelegramLinkStatus) => {
            if (status === 'pending') return;
            stopPolling();
            setState(status);
            if (status === 'ready') setLinked(true);
          })
          .catch(() => {
            stopPolling();
            setState('error');
          });
      }, POLL_INTERVAL_MS);
    } catch {
      setState('error');
    }
  };

  return (
    <Panel title="Bildirishnoma" notch>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
        <StatusLine
          tone="neutral"
          icon="notifications_active"
          parts={['Yangi bron kelganda Telegram botda xabar beriladi']}
        />

        {state === 'expired' ? (
          <StatusLine tone="warn" icon="schedule" parts={['Havola eskirdi — qaytadan urining']} />
        ) : state === 'error' ? (
          <StatusLine tone="danger" icon="error" parts={['Ulanmadi — qaytadan urining']} />
        ) : linked ? (
          <StatusLine tone="ok" icon="check_circle" parts={['Ulangan']} />
        ) : linked === false ? (
          <StatusLine tone="neutral" icon="link_off" parts={['Hali ulanmagan']} />
        ) : null}

        <Button
          variant="secondary"
          icon="link"
          disabled={state === 'waiting'}
          onClick={() => void start()}
        >
          {state === 'waiting'
            ? 'Botda Start bosing…'
            : linked
              ? 'Boshqa hisobga ulash'
              : 'Telegram botga ulash'}
        </Button>
      </div>
    </Panel>
  );
}

// ─────────────────────────── klub ma'lumoti ───────────────────────────

/**
 * `parts.tsx::hm()` daqiqani 24 soatga o'raydi (smena vaqti uchun to'g'ri) —
 * klub yopilish vaqti 26:00 gacha bo'lishi mumkin (`parseHm` shuni qabul
 * qiladi), o'ralsa "02:00" bo'lib ko'rinib, ochilish-yopilish teskari
 * ko'rinardi. Shu yerda o'ramaydigan variant kerak.
 */
function hm(minutes: number): string {
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
}

interface ClubDraft {
  name: string;
  address: string;
  phone: string;
  about: string;
  opens: string;
  closes: string;
  minHours: string;
  maxHours: string;
  advanceDays: string;
  extendMax: string;
  slotStep: string;
  googleMapsUrl: string;
  yandexMapsUrl: string;
}

/**
 * Klub ma'lumoti — o'qish uchun ko'rinish + "Tahrirlash" tugmasi bilan
 * ochiladigan forma. Avval bu yer to'g'ridan-to'g'ri, HAR DOIM tahrirlanadigan
 * forma edi — kirganda darhol editable holatda turishi chalkash va xato edi
 * (loyiha egasining topilmasi, 2026-08-16). Endi boshqa CRUD ekranlar bilan
 * bir xil naqsh: jadval/ko'rinish + tahrirlash tugmasi + markazdan modal.
 */
/** Butun son yoki `null` — chegaradan tashqarisi ham `null`. */
function num(raw: string, min: number, max: number): number | null {
  const value = Number(raw.trim());
  if (!Number.isInteger(value) || value < min || value > max) return null;
  return value;
}

function ClubGeneralTab(): ReactNode {
  const session = useSession((state) => state.session);
  // Faol klub — header'dagi almashtirgichdan (`store/board.ts::activeClubId`);
  // hali sinxronlanmagan bo'lsa (App() darhol sozlaydi) birinchi a'zolikka tushadi.
  const activeClubId = useBoard((state) => state.activeClubId);
  const clubId = activeClubId ?? session?.clubs[0]?.id ?? null;

  const [view, setView] = useState<ClubDraft | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [publishing, setPublishing] = useState(false);

  const [draft, setDraft] = useState<ClubDraft | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const reload = useCallback(async (): Promise<void> => {
    if (clubId === null) return;
    setLoading(true);
    setLoadError(null);
    try {
      const club = await getClub(api, clubId);
      setView({
        name: club.name,
        address: club.address,
        phone: club.phone ?? '',
        about: club.about,
        opens: hm(club.opensAtMin),
        closes: hm(club.closesAtMin),
        minHours: String(club.minBookingHours),
        maxHours: String(club.maxBookingHours),
        advanceDays: String(club.maxAdvanceDays),
        extendMax: String(club.extendMaxHours),
        slotStep: String(club.slotStepMin),
        googleMapsUrl: club.googleMapsUrl ?? '',
        yandexMapsUrl: club.yandexMapsUrl ?? '',
      });
      setStatus(club.status);
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

  const publish = async (): Promise<void> => {
    if (clubId === null) return;
    setPublishing(true);
    try {
      await publishClub(api, clubId);
      toast.success('Klub faollashtirildi — endi mijozlarga ko‘rinadi');
      await reload();
    } catch (cause) {
      toast.error(errorText(cause));
    } finally {
      setPublishing(false);
    }
  };

  const submit = async (): Promise<void> => {
    if (!draft || clubId === null) return;
    const opensMin = parseHm(draft.opens);
    const closesMin = parseHm(draft.closes);
    if (opensMin === null || closesMin === null) {
      setError('Vaqt HH:MM shaklida bo‘lishi kerak');
      return;
    }
    if (closesMin <= opensMin) {
      setError('Yopilish vaqti ochilishdan keyin bo‘lsin (tunda 26:00 gacha yoziladi)');
      return;
    }
    if (draft.name.trim().length === 0) {
      setError('Klub nomini kiriting');
      return;
    }

    // `0033` bu chegaralarni klub ustuniga ko'chirdi, lekin ularni
    // YOZADIGAN yo'l yo'q edi — har bir klub 1/6/14/3/30 ga mixlangan
    // qolgan edi. Oraliqlar migratsiyadagi CHECK'lar bilan bir xil.
    const limits = {
      minBookingHours: num(draft.minHours, 1, 12),
      maxBookingHours: num(draft.maxHours, 1, 12),
      maxAdvanceDays: num(draft.advanceDays, 1, 365),
      extendMaxHours: num(draft.extendMax, 1, 12),
      slotStepMin: num(draft.slotStep, 15, 60),
    };
    if (Object.values(limits).some((value) => value === null)) {
      setError('Bron chegaralari butun son bo‘lsin (soat 1–12, kun 1–365, qadam 15–60)');
      return;
    }
    if ((limits.minBookingHours as number) > (limits.maxBookingHours as number)) {
      setError('Eng kam davomiylik eng ko‘pdan oshmasin');
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await updateClub(api, clubId, {
        name: draft.name.trim(),
        address: draft.address,
        phone: draft.phone.trim() || null,
        about: draft.about,
        opensAtMin: opensMin,
        closesAtMin: closesMin,
        minBookingHours: limits.minBookingHours as number,
        maxBookingHours: limits.maxBookingHours as number,
        maxAdvanceDays: limits.maxAdvanceDays as number,
        extendMaxHours: limits.extendMaxHours as number,
        slotStepMin: limits.slotStepMin as number,
        googleMapsUrl: draft.googleMapsUrl.trim() || null,
        yandexMapsUrl: draft.yandexMapsUrl.trim() || null,
      });
      setDraft(null);
      toast.success('Klub ma’lumoti saqlandi');
      await reload();
    } catch (cause) {
      const message = errorText(cause);
      setError(message);
      toast.error(message);
    } finally {
      setSaving(false);
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
        title="Klub ma’lumotini tahrirlash"
        variant="drawer"
      >
        {draft ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
            <FormGrid>
              <TextField
                label="Klub nomi"
                value={draft.name}
                onChange={(value) => setDraft({ ...draft, name: value })}
                icon="storefront"
                placeholder="Neon Arena"
              />
              <TextField
                label="Telefon"
                value={draft.phone}
                onChange={(value) => setDraft({ ...draft, phone: value })}
                icon="call"
                inputMode="tel"
                placeholder="+998901234567"
              />
            </FormGrid>

            <TextField
              label="Manzil"
              value={draft.address}
              onChange={(value) => setDraft({ ...draft, address: value })}
              icon="location_on"
              placeholder="Toshkent, Chilonzor tumani"
            />
            <TextField
              label="Tavsif"
              value={draft.about}
              onChange={(value) => setDraft({ ...draft, about: value })}
              icon="notes"
              placeholder="Klub haqida qisqacha"
            />

            <FormGrid>
              <TextField
                label="Google Maps havolasi"
                value={draft.googleMapsUrl}
                onChange={(value) => setDraft({ ...draft, googleMapsUrl: value })}
                icon="map"
                placeholder="https://maps.google.com/?q=..."
              />
              <TextField
                label="Yandex Maps havolasi"
                value={draft.yandexMapsUrl}
                onChange={(value) => setDraft({ ...draft, yandexMapsUrl: value })}
                icon="map"
                placeholder="https://yandex.uz/maps/?ll=..."
              />
            </FormGrid>
            {/* Mijoz ilovasidagi "Manzil" tugmasi shu havolani ochadi — klub
                haritada joylashuvni Google/Yandex'dan ulashib, shu yerga
                qo'yish yetarli, koordinata qo'lda kiritilmaydi. */}

            <FormGrid>
              <TextField
                label="Ochilish"
                value={draft.opens}
                onChange={(value) => setDraft({ ...draft, opens: value })}
                icon="schedule"
                placeholder="10:00"
              />
              <TextField
                label="Yopilish"
                value={draft.closes}
                onChange={(value) => setDraft({ ...draft, closes: value })}
                icon="bedtime"
                placeholder="26:00"
              />
            </FormGrid>

            <FormGrid>
              <TextField
                label="Eng kam davomiylik (soat)"
                value={draft.minHours}
                onChange={(value) => setDraft({ ...draft, minHours: value })}
                icon="hourglass_bottom"
                inputMode="numeric"
                placeholder="1"
              />
              <TextField
                label="Eng ko‘p davomiylik (soat)"
                value={draft.maxHours}
                onChange={(value) => setDraft({ ...draft, maxHours: value })}
                icon="hourglass_top"
                inputMode="numeric"
                placeholder="6"
              />
            </FormGrid>
            <FormGrid>
              <TextField
                label="Oldindan bron (kun)"
                value={draft.advanceDays}
                onChange={(value) => setDraft({ ...draft, advanceDays: value })}
                icon="event"
                inputMode="numeric"
                placeholder="14"
              />
              <TextField
                label="Bir marta uzaytirish (soat)"
                value={draft.extendMax}
                onChange={(value) => setDraft({ ...draft, extendMax: value })}
                icon="more_time"
                inputMode="numeric"
                placeholder="3"
              />
            </FormGrid>
            <TextField
              label="Slot qadami (daqiqa)"
              value={draft.slotStep}
              onChange={(value) => setDraft({ ...draft, slotStep: value })}
              icon="grid_view"
              inputMode="numeric"
              placeholder="30"
            />
            {/* Mijoz ilovasi davomiylik tugmalari, kun tasmasi va slot
                to'rini SHU sozlamalardan quradi. */}

            {error ? <StatusLine tone="danger" icon="error" parts={error} /> : null}

            <div style={{ display: 'flex', gap: 'var(--gap-tight)', flexWrap: 'wrap' }}>
              <Button
                variant="primary"
                notch
                icon="check"
                disabled={saving}
                onClick={() => void submit()}
              >
                {saving ? 'Saqlanmoqda…' : 'Saqlash'}
              </Button>
              <Button
                variant="ghost"
                disabled={saving}
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
        title="Asosiy ma’lumot"
        notch
        brackets
        action={
          <Button
            variant="secondary"
            size="sm"
            icon="edit"
            disabled={!view}
            onClick={() => {
              if (view) setDraft(view);
              setError(null);
            }}
          >
            Tahrirlash
          </Button>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-block)' }}>
          {status === 'draft' ? (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
                padding: 'var(--card-pad)',
                background: 'var(--surface-inset)',
                border: '1px solid var(--yellow-100)',
                clipPath: 'var(--clip-tr)',
              }}
            >
              <StatusLine
                tone="warn"
                icon="visibility_off"
                parts={['Klub hali mijozlarga ko‘rinmaydi', 'Kamida bitta faol xona kerak']}
              />
              <Button
                variant="primary"
                size="sm"
                icon="rocket_launch"
                disabled={publishing}
                onClick={() => void publish()}
                style={{ alignSelf: 'flex-start' }}
              >
                {publishing ? 'Faollashtirilmoqda…' : 'Klubni faollashtirish'}
              </Button>
            </div>
          ) : null}

          {loadError ? <StatusLine tone="danger" icon="error" parts={[loadError]} /> : null}

          {view ? (
            <FieldLadder>
              <FieldRow label="Klub nomi" value={view.name} />
              <FieldRow label="Telefon" value={view.phone || '—'} />
              <FieldRow label="Manzil" value={view.address || '—'} />
              <FieldRow label="Tavsif" value={view.about || '—'} />
              <FieldRow label="Google Maps" value={view.googleMapsUrl || '—'} />
              <FieldRow label="Yandex Maps" value={view.yandexMapsUrl || '—'} />
              <FieldRow label="Ish vaqti" value={`${view.opens} – ${view.closes}`} />
            </FieldLadder>
          ) : (
            <StatusLine
              tone="neutral"
              icon="hourglass_empty"
              parts={[loading ? 'Yuklanmoqda…' : 'Ma’lumot topilmadi']}
            />
          )}
        </div>
      </Panel>
    </>
  );
}

// ─────────────────────────── xonalar ───────────────────────────

// Eski (0023'dan oldingi) xonalarda hali `console_type` bor — jadvalda
// ko'rsatiladi, lekin FORMADA endi tanlanmaydi (reja #38, loyiha egasi,
// 2026-08-16): "xona qo'shganda konsolni tanlash kerak emas — mijoz/xodim
// bron/hisob ochishda tanlaydi".
const CONSOLE_LABEL: Record<string, string> = {
  ps3: 'PS3',
  ps4: 'PS4',
  ps4pro: 'PS4 Pro',
  ps5: 'PS5',
  ps5pro: 'PS5 Pro',
};

interface StationDraft {
  id: number | null;
  code: string;
  roomLabel: string;
  rate: string;
  status: 'active' | 'maintenance';
}

const EMPTY_STATION_DRAFT: StationDraft = {
  id: null,
  code: '',
  roomLabel: 'Standart',
  rate: '40000',
  status: 'active',
};

function StationsTab(): ReactNode {
  const session = useSession((state) => state.session);
  // Faol klub — header'dagi almashtirgichdan (`store/board.ts::activeClubId`);
  // hali sinxronlanmagan bo'lsa (App() darhol sozlaydi) birinchi a'zolikka tushadi.
  const activeClubId = useBoard((state) => state.activeClubId);
  const clubId = activeClubId ?? session?.clubs[0]?.id ?? null;

  const [stations, setStations] = useState<StationDto[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [draft, setDraft] = useState<StationDraft | null>(null);
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
          rate,
        });
        toast.success(`Xona qo‘shildi — ${draft.code.trim()}`);
      } else {
        await updateStation(api, clubId, draft.id, {
          roomLabel: draft.roomLabel.trim() || 'Standart',
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
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-panel)' }}>
            <FormGrid gap="var(--gap-panel)">
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
              <TextField
                label="Soatlik summa"
                value={draft.rate}
                onChange={(value) => setDraft({ ...draft, rate: value })}
                icon="payments"
                inputMode="numeric"
                placeholder="40000"
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
              setDraft(EMPTY_STATION_DRAFT);
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
              // Eski (0023'dan oldingi) xonalarda ko'rinadi — yangi xonada
              // konsol endi bron/hisob ochilganda tanlanadi (reja #38).
              key: 'console',
              header: 'Konsol',
              render: (row) =>
                row.consoleType ? (CONSOLE_LABEL[row.consoleType] ?? row.consoleType) : '—',
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

// ─────────────────────────── jurnal ───────────────────────────

const LOG_LABEL: Record<string, string> = {
  staff_created: 'Xodim qo‘shildi',
  staff_updated: 'Xodim ma’lumoti o‘zgartirildi',
  staff_deactivated: 'Xodim chiqarildi',
  product_created: 'Mahsulot qo‘shildi',
  product_updated: 'Mahsulot o‘zgartirildi',
  station_created: 'Xona qo‘shildi',
  station_updated: 'Xona o‘zgartirildi',
  club_updated: 'Klub ma’lumoti o‘zgartirildi',
  expense_created: 'Xarajat qo‘shildi',
  expense_updated: 'Xarajat o‘zgartirildi',
  expense_archived: 'Xarajat arxivlandi',
  shift_opened: 'Smena ochildi',
  shift_cash_in: 'Kassaga kirim',
  shift_cash_out: 'Kassadan chiqim',
  shift_closed: 'Smena yopildi',
  staff_login: 'Kirdi',
  logout: 'Chiqdi',
};

function logLabel(event: string): string {
  return LOG_LABEL[event] ?? event;
}

function formatLogAt(iso: string): string {
  return new Date(iso).toLocaleString('uz-UZ', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function logDetailSummary(row: ActivityLogDto): string {
  if (!row.detail) return '—';
  const parts = Object.entries(row.detail)
    .filter(([, value]) => value !== null && value !== undefined && value !== '')
    .map(([key, value]) => `${key}: ${String(value)}`);
  return parts.length > 0 ? parts.join(' · ') : '—';
}

/**
 * Klub faoliyat jurnali — xodim/mahsulot/xona/klub o'zgarishlari
 * (`audit_log`) + kirish/chiqish (`auth_events`) bitta ro'yxatda,
 * so'nggidan boshlab. RLS o'zi shu klubga cheklaydi.
 */
function LogTab(): ReactNode {
  const session = useSession((state) => state.session);
  // Faol klub — header'dagi almashtirgichdan (`store/board.ts::activeClubId`);
  // hali sinxronlanmagan bo'lsa (App() darhol sozlaydi) birinchi a'zolikka tushadi.
  const activeClubId = useBoard((state) => state.activeClubId);
  const clubId = activeClubId ?? session?.clubs[0]?.id ?? null;

  const [rows, setRows] = useState<ActivityLogDto[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const reload = useCallback(async (): Promise<void> => {
    if (clubId === null) return;
    setLoading(true);
    setLoadError(null);
    try {
      setRows(await listClubLogs(api, clubId));
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

  return (
    <Panel title={`Jurnal (${rows.length})`} notch brackets>
      {loadError ? <StatusLine tone="danger" icon="error" parts={[loadError]} /> : null}

      <EntityTable
        rows={rows}
        rowKey={(row) => row.id}
        empty={loading ? 'Yuklanmoqda…' : 'Hozircha yozuv yo‘q'}
        columns={[
          {
            key: 'at',
            header: 'Vaqt',
            render: (row) => (
              <span style={{ font: 'var(--type-data)', color: 'var(--text-title)', whiteSpace: 'nowrap' }}>
                {formatLogAt(row.at)}
              </span>
            ),
          },
          {
            key: 'event',
            header: 'Amal',
            render: (row) => (
              <Tag tone={row.source === 'auth' ? 'neutral' : 'violet'}>{logLabel(row.event)}</Tag>
            ),
          },
          {
            key: 'actor',
            header: 'Kim',
            render: (row) => (
              <span style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
                <span style={{ color: 'var(--text-title)' }}>{row.actorName ?? '—'}</span>
                <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                  {row.actorLogin ?? '—'}
                </span>
              </span>
            ),
          },
          {
            key: 'target',
            header: 'Nishon',
            render: (row) => row.target ?? '—',
          },
          {
            key: 'detail',
            header: 'Tafsilot',
            render: (row) => (
              <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                {logDetailSummary(row)}
              </span>
            ),
          },
        ]}
      />
    </Panel>
  );
}
