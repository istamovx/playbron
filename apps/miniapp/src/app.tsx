import { CyberLoaderOverlay, Icon, Wordmark } from '@playbron/ui';
import { type ReactNode } from 'react';

import { useT, type Translate } from './i18n';
import { clock, hhmm } from './lib/format';
import { consoleForRequest, freeStations, isoDateOf, startInstantIso } from './lib/slots';
import { useTelegramAuth } from './lib/auth';
import { TABS, TAB_ROOT, TITLE_KEY } from './nav';
import { BookingsScreen } from './screens/bookings';
import { BootScreen } from './screens/boot';
import { ClubScreen } from './screens/club';
import { ClubsScreen } from './screens/clubs';
import { ConfirmScreen } from './screens/confirm';
import { ProfileScreen } from './screens/profile';
import { SentScreen } from './screens/sent';
import { SessionScreen } from './screens/session';
import { SlotsScreen } from './screens/slots';
import { useApp, useClock, useNow, useProfile } from './store/app';
import { useBooking } from './store/booking';

/** Mijoz Mini App — `docs/designs/PlayBron Mijoz.dc.html` shelli. */
export function App(): ReactNode {
  useClock();
  const t = useT();
  const state = useApp();
  const profile = useProfile((current) => current.profile);
  const signedIn = useProfile((current) => current.signedIn);
  // Telegram ichida sessiya jimgina ochiladi — qo'lda forma yo'q (§lib/auth.ts)
  const boot = useTelegramAuth();
  const authenticated = boot.state === 'authenticated' && profile && signedIn;
  const bookingSubmitting = useBooking((s) => s.submitting);
  const clubTimezone = useBooking(
    (s) => s.clubs.find((club) => club.id === state.clubId)?.timezone,
  );
  const now = useNow(clubTimezone);

  const main = mainButton(state, bookingSubmitting, t);
  const canBack = state.stack.length > 0;
  const activeTab = TAB_ROOT[state.screen] ?? state.screen;
  const title = t(TITLE_KEY[state.screen]);

  // Telegram'ning MainButton va BackButton'i ATAYLAB ishlatilmaydi: ekranda
  // o'z tugmamiz va o'z header'imiz bor, ikkalasi birga chiqsa foydalanuvchi
  // pastda bir xil yozuvli ikkita tugma ko'radi. Ular `initTelegram()` da
  // bir marta yashiriladi.

  return (
    <div className="pb-stage">
      <div
        className="pb-phone"
        style={{
          background: 'var(--bg-frame)',
          display: 'flex',
          flexDirection: 'column',
          font: 'var(--type-body)',
          color: 'var(--text-body)',
          position: 'relative',
        }}
      >
        {boot.state === 'checking' ? (
          // Konsoldagi yuklanish holatining o'zi — mijoz yuzasida ham
          // bir xil (loyiha egasi, 2026-08-17: "yuklanishda loader yo'q").
          <CyberLoaderOverlay label={t('loading')} />
        ) : authenticated ? (
          <>
            <header
              style={{
                flex: 'none',
                minHeight: 52,
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '0 var(--gutter)',
                background: 'var(--void-2)',
                borderBottom: '1px solid var(--line-1)',
              }}
            >
              {canBack ? (
                <button
                  type="button"
                  onClick={state.back}
                  aria-label={t('back')}
                  style={{
                    cursor: 'pointer',
                    width: 30,
                    height: 30,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    border: 'none',
                    background: 'transparent',
                    color: 'var(--text-muted)',
                  }}
                >
                  <Icon name="arrow_back" size={20} />
                </button>
              ) : (
                // Belgi — konsoldagi bilan bitta komponent (`@playbron/ui`).
                // Ichki ekranda «orqaga» tugmasiga joy beradi.
                <Wordmark width={120} />
              )}

              {/* Bir qatorli mobil header: faqat sarlavha — subtitr olib tashlandi */}
              <span
                style={{
                  flex: 1,
                  minWidth: 0,
                  font: 'var(--fw-medium) var(--fs-lg)/1.2 var(--font-display)',
                  color: 'var(--text-title)',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  textAlign: canBack ? 'left' : 'right',
                }}
              >
                {title}
              </span>

              <span style={{ font: 'var(--type-data-xs)', color: 'var(--text-dim)' }}>
                {clock(now)}
              </span>
            </header>

            <main
              style={{
                flex: 1,
                minHeight: 0,
                minWidth: 0,
                overflowY: 'auto',
                overflowX: 'hidden',
                display: 'flex',
                flexDirection: 'column',
                padding: 'var(--gutter)',
              }}
            >
              {state.screen === 'clubs' ? <ClubsScreen /> : null}
              {state.screen === 'club' ? <ClubScreen /> : null}
              {state.screen === 'slots' ? <SlotsScreen /> : null}
              {state.screen === 'confirm' ? <ConfirmScreen /> : null}
              {state.screen === 'sent' ? <SentScreen /> : null}
              {state.screen === 'session' ? <SessionScreen /> : null}
              {state.screen === 'bookings' ? <BookingsScreen /> : null}
              {state.screen === 'profile' ? <ProfileScreen /> : null}
            </main>

            {main ? (
              <button
                type="button"
                onClick={main.act}
                disabled={main.enabled === false}
                style={{
                  flex: 'none',
                  cursor: main.enabled === false ? 'not-allowed' : 'pointer',
                  minHeight: 50,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                  border: 'none',
                  background: main.enabled === false ? 'var(--surface-inset)' : 'var(--primary-100)',
                  color: main.enabled === false ? 'var(--text-dim)' : 'var(--text-on-accent)',
                  font: 'var(--fw-medium) var(--fs-base)/1 var(--font-display)',
                  letterSpacing: '.02em',
                  transition: 'background 140ms cubic-bezier(.22,.61,.36,1)',
                }}
              >
                {main.label}
              </button>
            ) : null}

            <nav
              style={{
                flex: 'none',
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                background: 'var(--void-2)',
                borderTop: '1px solid var(--line-1)',
              }}
            >
              {TABS.map((tab) => {
                const on = activeTab === tab.id;
                const label = t(tab.label);
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => state.tab(tab.id)}
                    aria-label={label}
                    title={label}
                    aria-current={on ? 'page' : undefined}
                    style={{
                      cursor: 'pointer',
                      minHeight: 54,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      border: 'none',
                      borderTop: `2px solid ${on ? 'var(--primary-100)' : 'transparent'}`,
                      background: on ? 'var(--surface-selected)' : 'transparent',
                      color: on ? 'var(--text-title)' : 'var(--text-dim)',
                      transition: 'var(--t-control)',
                    }}
                  >
                    <Icon name={tab.icon} size={22} />
                  </button>
                );
              })}
            </nav>
          </>
        ) : (
          <main style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: 'var(--gutter)' }}>
            <BootScreen state={boot.state} error={boot.error} onRetry={boot.retry} />
          </main>
        )}
      </div>
    </div>
  );
}

interface MainAction {
  label: string;
  act: () => void;
  enabled?: boolean;
}

/**
 * Ekranga qarab pastdagi asosiy amal.
 *
 * Faqat REAL bron oqimi qoldi (`store/booking.ts`). Avvalgi "savatni
 * yuborish" va "chekni yuklash" amallari mock bar/hisob ekranlariga
 * tegishli edi — backendda ularning ekvivalenti yo'q, shuning uchun
 * ekranlar bilan birga olib tashlandi.
 */
function mainButton(
  state: ReturnType<typeof useApp.getState>,
  bookingSubmitting: boolean,
  t: Translate,
): MainAction | null {
  const booking = useBooking.getState();
  const clubId = state.clubId;
  const stationScope = { room: state.room, console: state.console };
  const club = clubId === null ? null : (booking.clubs.find((c) => c.id === clubId) ?? null);
  const timezone = club?.timezone ?? 'Asia/Tashkent';
  const dayBookings =
    clubId === null ? [] : (booking.dayBookings[isoDateOf(state.day, timezone)] ?? []);
  const closeMin = club?.closesAtMin ?? 0;

  const free = freeStations(
    booking.stations,
    dayBookings,
    state.start,
    state.hours,
    closeMin,
    stationScope,
    timezone,
  );
  const station = free.find((item) => item.id === state.station) ?? null;

  switch (state.screen) {
    case 'club':
      return { label: t('bookAction'), act: () => state.go('slots') };
    case 'slots': {
      if (!station) {
        return { label: t('pickFreeTime'), act: () => undefined, enabled: false };
      }
      // Konsolsiz xonada konsol tanlanmaguncha oldinga o'tkazmaymiz —
      // aks holda server 400 `CONSOLE_TYPE_REQUIRED` qaytarardi va mijoz
      // sababini bilmasdi (audit topilmasi, 2026-08-16).
      if (station.consoleType === null && !state.bookingConsole) {
        return { label: t('pickConsole'), act: () => undefined, enabled: false };
      }
      // Summa YOZILMAYDI: oynaning haqiqiy narxini server tarif jadvali
      // bo'yicha hisoblaydi (`bookings/pricing.py`), `rate × soat` esa
      // tarif kun ichida o'zgarsa unga teng bo'lmaydi.
      return {
        label: `${hhmm(state.start)} → ${hhmm(state.start + state.hours * 60)}`,
        act: () => state.go('confirm'),
      };
    }
    case 'confirm':
      if (!station || clubId === null) {
        return { label: t('roomNotSelected'), act: () => undefined, enabled: false };
      }
      return {
        label: bookingSubmitting ? t('submitting') : t('submitBooking'),
        enabled: !bookingSubmitting,
        act: () => {
          if (useBooking.getState().submitting) return;
          const iso = startInstantIso(state.day, state.start, timezone);
          void useBooking
            .getState()
            .submitBooking(
              clubId,
              station.id,
              iso,
              state.hours,
              consoleForRequest(station, state.bookingConsole),
            )
            .then((ok) => {
              if (ok) {
                // Yangi bron darhol «Bronlarim» va «Seans» ekranlarida
                // ko'rinishi uchun ro'yxat qayta o'qiladi.
                void useBooking.getState().loadMyBookings();
                state.go('sent');
              }
            });
        },
      };
    case 'sent':
      return { label: t('goBookings'), act: () => state.tab('bookings') };
    case 'bookings':
      return { label: t('newBooking'), act: () => state.tab('clubs') };
    default:
      return null;
  }
}

export type { ScreenId } from './nav';
